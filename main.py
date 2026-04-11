"""
Pulse Backend - FastAPI server for Health Copilot
Provides /api/chat endpoint that accepts health data and returns LLM responses.
"""
from starlette.concurrency import iterate_in_threadpool
from fastapi import Request
import logging
import json
import time
import os
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from typing import Optional
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import (
    ChatRequest, ChatResponse, ToolCall, ProductResponse, ProductInfo, ProductNutriments,
    MealAnalysisResponse, MealAnalysis,
    FatSecretAutocompleteResponse, FatSecretSearchResponse, FatSecretFoodResponse,
    FatSecretMealAddPreviewResponse
)
from product_service import lookup_product, ProductNotFoundError
import meal_analysis_service
from openai import AsyncOpenAI
from fatsecret_service import FatSecretClient

# Pipeline modules
import feature_engineering
import rule_engine
import query_classifier
import context_builder
import llm_service

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Pulse Backend",
    description="Health Copilot API for mobile app",
    version="1.0.0"
)

# Logging Middleware


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Skip logging for health check endpoint
    if request.url.path == "/api/health":
        return await call_next(request)

    # Read request body
    request_body_bytes = await request.body()

    # Determine content type to skip binary/multipart bodies
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
        # Binary body — don't attempt JSON/text decode, just log a placeholder
        request_body = f"<binary upload: {len(request_body_bytes)} bytes>"
    else:
        try:
            request_body = json.loads(request_body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            try:
                request_body = request_body_bytes.decode(
                    "utf-8", errors="replace")
            except Exception:
                request_body = f"<unreadable body: {len(request_body_bytes)} bytes>"

    # Create a new request with the body so it can be read again
    async def receive():
        return {"type": "http.request", "body": request_body_bytes}
    request._receive = receive

    response = await call_next(request)

    # Read response body
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    try:
        response_json = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        try:
            response_json = response_body.decode("utf-8", errors="replace")
        except Exception:
            response_json = f"<unreadable response: {len(response_body)} bytes>"

    # Re-create the response iterator
    async def new_response_iterator():
        yield response_body

    response.body_iterator = new_response_iterator()

    # Log to file
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    request_for_log = request_body

    log_entry = {
        "timestamp": timestamp,
        "method": request.method,
        "url": str(request.url),
        "request": request_for_log,
        "response": response_json,
        "status_code": response.status_code
    }

    # Attach image path if the handler saved one (e.g. /api/meal/analyze)
    image_log_path = getattr(request.state, "image_log_path", None)
    if image_log_path:
        log_entry["image_path"] = image_log_path

    # Attach LLM reasoning if the handler stored one (meal analysis endpoints)
    meal_reasoning = getattr(request.state, "meal_reasoning", None)
    if meal_reasoning:
        log_entry["llm_reasoning"] = meal_reasoning

    meal_question = getattr(request.state, "meal_question", None)
    if meal_question:
        log_entry["meal_question"] = meal_question

    meal_question_answer = getattr(request.state, "meal_question_answer", None)
    if meal_question_answer:
        log_entry["meal_question_answer"] = meal_question_answer

    # Attach LLM context from chat endpoint
    llm_context = getattr(request.state, "llm_context", None)
    if llm_context:
        log_entry["llm_context"] = llm_context

    llm_query_type = getattr(request.state, "llm_query_type", None)
    if llm_query_type:
        log_entry["llm_query_type"] = llm_query_type

    llm_messages = getattr(request.state, "llm_messages", None)
    if llm_messages:
        log_entry["llm_messages"] = llm_messages

    llm_structured_output = getattr(request.state, "llm_structured_output", None)
    if llm_structured_output:
        log_entry["llm_structured_output"] = llm_structured_output

    try:
        os.makedirs("logs", exist_ok=True)
        filename = f"logs/{timestamp}_{int(time.time() * 1000)}.json"
        with open(filename, "w") as f:
            json.dump(log_entry, f, indent=2)
    except Exception:
        # Request logging should never fail the actual API request.
        logging.exception("Failed to write request log")

    return response

# Add CORS middleware to allow mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your mobile app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client for meal analysis endpoints
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
text_model_name = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")

if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

openai_client = AsyncOpenAI(api_key=api_key)
chat_model_name = os.getenv("OPENAI_CHAT_MODEL", text_model_name)


# Initialize FatSecret client for meal search endpoints
fatsecret_client_id = os.getenv("FATSECRET_CLIENT_ID")
fatsecret_client_secret = os.getenv("FATSECRET_CLIENT_SECRET")

if fatsecret_client_id and fatsecret_client_secret:
    fatsecret_client = FatSecretClient(
        client_id=fatsecret_client_id,
        client_secret=fatsecret_client_secret,
        scope=os.getenv("FATSECRET_SCOPE", "premier"),
        region=os.getenv("FATSECRET_REGION", "IN"),
        language=os.getenv("FATSECRET_LANGUAGE", "en")
    )
else:
    # Allow app to start even if FatSecret creds are missing (graceful degradation)
    fatsecret_client = None
    logging.warning("FatSecret credentials not found; meal search endpoints will be unavailable")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pulse_backend",
        "version": "1.0.0"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, fastapi_request: Request):
    """
    Chat endpoint for the mobile app.
    """
    try:
        # 1. Compute 5 signals (pure math, <1ms)
        signals = feature_engineering.compute_signals(request.chat_context)
        
        # 2. Produce structured constraints + decision hints
        constraints, hints = rule_engine.evaluate(signals)
        
        # 3. Classify query deterministically
        query_type = query_classifier.classify(request.query)
        
        # 4. Build <=5 field context + constraints + hints
        context = context_builder.build(signals, query_type, constraints, hints)
        
        fastapi_request.state.llm_context = context
        fastapi_request.state.llm_query_type = query_type
        
        # 5. LLM explains the backend's decisions
        answer, messages, structured_output = await llm_service.generate_response(
            query=request.query,
            query_type=query_type,
            context=context,
            conversation_history=request.conversation_history,
            openai_client=openai_client,
            model_name=chat_model_name
        )
        
        fastapi_request.state.llm_messages = messages
        fastapi_request.state.llm_structured_output = structured_output
        
        return ChatResponse(response=answer, tool_calls=[])

    except HTTPException:
        raise
    except Exception as exc:
        error_msg = str(exc) if str(exc) else type(exc).__name__
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating chat response: {error_msg}")


@app.get("/api/product/{barcode}", response_model=ProductResponse)
async def get_product(barcode: str):
    """
    Look up product info by barcode via OpenFoodFacts API.
    """
    try:
        product_data = await lookup_product(barcode)

        nutriments = ProductNutriments(**product_data.get("nutriments", {}))
        product_info = ProductInfo(
            barcode=product_data["barcode"],
            product_name=product_data.get("product_name"),
            brands=product_data.get("brands"),
            categories=product_data.get("categories"),
            nutriscore_grade=product_data.get("nutriscore_grade"),
            nutriments=nutriments,
            image_url=product_data.get("image_url"),
            ingredients_text=product_data.get("ingredients_text"),
        )

        return ProductResponse(status="found", product=product_info)

    except ProductNotFoundError:
        return ProductResponse(
            status="not_found",
            error=f"Product with barcode {barcode} not found in OpenFoodFacts"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error looking up product: {error_msg}"
        )


@app.post("/api/meal/analyze", response_model=MealAnalysisResponse)
async def analyze_meal(
    request: Request,
    image: UploadFile = File(...),
    note: Optional[str] = Form(None),
    question: Optional[str] = Form(None),
):
    """
    Analyse a meal photo using GPT-4o vision.
    Returns estimated nutritional info in the same shape as /api/product/{barcode}
    so the frontend can reuse the same result card UI.
    Accepts an optional 'note' form field (e.g. 'I only ate half of it') which
    is forwarded to the LLM to factor into its portion/nutriment estimates.
    Accepts an optional 'question' form field (e.g. 'Is this healthy?') and
    returns a short answer alongside the nutrition payload.
    """
    try:
        image_bytes = await image.read()
        content_type = image.content_type or "image/jpeg"
        clean_question = question.strip() if question and question.strip() else None

        # Persist the image so it can be referenced from the request log
        os.makedirs("logs/images", exist_ok=True)
        img_timestamp = time.strftime("%Y%m%d_%H%M%S")
        img_filename = f"logs/images/{img_timestamp}_{int(time.time() * 1000)}.jpg"
        with open(img_filename, "wb") as img_file:
            img_file.write(image_bytes)
        request.state.image_log_path = img_filename

        meal_data = await meal_analysis_service.analyze_meal_image(
            image_bytes=image_bytes,
            content_type=content_type,
            openai_client=openai_client,
            model=model_name,
            user_note=note,
        )

        question_answer = None
        if clean_question:
            question_answer = await meal_analysis_service.answer_meal_question(
                question=clean_question,
                meal_data=meal_data,
                openai_client=openai_client,
                model=model_name,
            )

        # Store reasoning in request.state so the logging middleware can persist it
        request.state.meal_reasoning = meal_data.get("reasoning")
        request.state.meal_question = clean_question
        request.state.meal_question_answer = question_answer

        meal = MealAnalysis(**meal_data)

        return MealAnalysisResponse(
            status="analyzed",
            meal=meal,
            asked_question=clean_question,
            question_answer=question_answer,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=422, detail=f"Meal analysis parse error: {str(e)}")
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error analysing meal image: {error_msg}"
        )


class MealTextRequest(BaseModel):
    description: str  # e.g. "2 chapatis with dal and a glass of milk"


@app.post("/api/meal/analyze-text", response_model=MealAnalysisResponse)
async def analyze_meal_text(body: MealTextRequest, request: Request):
    """
    Analyse a meal described in plain text using GPT-4o.
    No image required — the user simply describes what they ate.
    Returns the same shape as /api/meal/analyze so the frontend reuses the same result card.
    """
    try:
        meal_data = await meal_analysis_service.analyze_meal_text(
            description=body.description,
            openai_client=openai_client,
            model=text_model_name,
        )

        # Store reasoning in request.state so the logging middleware can persist it
        request.state.meal_reasoning = meal_data.get("reasoning")

        meal = MealAnalysis(**meal_data)

        return MealAnalysisResponse(status="analyzed", meal=meal)

    except ValueError as e:
        raise HTTPException(
            status_code=422, detail=f"Meal text analysis parse error: {str(e)}")
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error analysing meal description: {error_msg}"
        )


# =============================================================================
# FatSecret Integration Endpoints
# =============================================================================

@app.get("/api/fatsecret/autocomplete", response_model=FatSecretAutocompleteResponse)
async def fatsecret_autocomplete(expression: str, max_results: int = 10):
    """
    Get autocomplete suggestions for food search.
    
    Args:
        expression: Partial food name (e.g., "chic" for chicken suggestions)
        max_results: Maximum number of suggestions (default: 10, max: 10)
    
    Returns:
        List of food name suggestions
    """
    if not fatsecret_client:
        raise HTTPException(
            status_code=501,
            detail="FatSecret integration is not configured"
        )
    
    try:
        suggestions = await fatsecret_client.autocomplete(
            expression=expression,
            max_results=max_results
        )
        return FatSecretAutocompleteResponse(
            status="success",
            suggestions=suggestions
        )
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error getting autocomplete suggestions: {error_msg}"
        )


@app.get("/api/fatsecret/search", response_model=FatSecretSearchResponse)
async def fatsecret_search(query: str, page_number: int = 0, max_results: int = 20):
    """
    Search for foods by name with pagination.
    
    Args:
        query: Food search query (e.g., "chicken breast")
        page_number: Zero-based page number (default: 0)
        max_results: Results per page (default: 20, max: 50)
    
    Returns:
        Paginated list of matching foods with serving options
    """
    if not fatsecret_client:
        raise HTTPException(
            status_code=501,
            detail="FatSecret integration is not configured"
        )
    
    try:
        search_result = await fatsecret_client.search(
            query=query,
            page_number=page_number,
            max_results=max_results
        )
        return FatSecretSearchResponse(
            status="success",
            query=query,
            page_number=page_number,
            max_results=search_result.get("max_results"),
            total_results=search_result.get("total_results"),
            results=search_result.get("results", [])
        )
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error searching foods: {error_msg}"
        )


@app.get("/api/fatsecret/food/{food_id}", response_model=FatSecretFoodResponse)
async def fatsecret_get_food(food_id: int):
    """
    Get detailed food information including all serving sizes and nutrition data.
    
    Args:
        food_id: FatSecret food ID (integer)
    
    Returns:
        Food object with name, brand, all available servings, and per-serving nutrients
    """
    if not fatsecret_client:
        raise HTTPException(
            status_code=501,
            detail="FatSecret integration is not configured"
        )
    
    try:
        food = await fatsecret_client.get_food(food_id=food_id)
        
        if not food:
            raise HTTPException(
                status_code=404,
                detail=f"Food with ID {food_id} not found"
            )
        
        return FatSecretFoodResponse(
            status="success",
            food=food
        )
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving food details: {error_msg}"
        )


class FatSecretMealAddRequest(BaseModel):
    """Request body for POST /api/fatsecret/add-preview"""
    food_id: int
    serving_description: str
    quantity: float = 1.0  # Number of servings to consume


@app.post("/api/fatsecret/add-preview", response_model=FatSecretMealAddPreviewResponse)
async def fatsecret_add_preview(body: FatSecretMealAddRequest):
    """
    Preview meal nutrients before adding (calculates totals based on serving * quantity).
    
    Request body:
        food_id: FatSecret food ID
        serving_description: Serving size description from the food's servings list
        quantity: Multiplier (e.g., 1.5 servings)
    
    Returns:
        Calculated nutrient totals for this meal (as if user consumed quantity servings)
    """
    if not fatsecret_client:
        raise HTTPException(
            status_code=501,
            detail="FatSecret integration is not configured"
        )
    
    try:
        # Get food details
        food = await fatsecret_client.get_food(food_id=body.food_id)
        
        if not food:
            raise HTTPException(
                status_code=404,
                detail=f"Food with ID {body.food_id} not found"
            )
        
        # Calculate totals for the specified serving * quantity
        totals = await fatsecret_client.calculate_meal_totals(
            food=food,
            serving_description=body.serving_description,
            quantity=body.quantity
        )
        
        # Find the serving to confirm the description
        servings = food.get("servings", [])
        serving_list = servings if isinstance(servings, list) else []
        
        serving_description = None
        for s in serving_list:
            if s.get("serving_description") == body.serving_description:
                serving_description = s.get("serving_description")
                break
        
        return FatSecretMealAddPreviewResponse(
            status="success",
            food_id=body.food_id,
            food_name=food.get("food_name"),
            serving_description=serving_description,
            quantity=body.quantity,
            totals=totals
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Meal calculation error: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating meal preview: {error_msg}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
