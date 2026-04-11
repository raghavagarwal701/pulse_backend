import os
import time
from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile, Request, HTTPException, BackgroundTasks
from schemas.meal import MealAnalysisResponse, MealAnalysis, MealTextRequest
from core.config import openai_client, model_name, text_model_name
import meal_analysis_service

router = APIRouter(prefix="/api/meal", tags=["Meal"])

def save_image_to_disk(image_bytes: bytes, log_dir: str, filename: str):
    """Synchronous function to perform disk IO in the background"""
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(filename, "wb") as img_file:
            img_file.write(image_bytes)
    except Exception as e:
        import logging
        logging.exception(f"Failed to save meal image to disk: {e}")

@router.post("/analyze", response_model=MealAnalysisResponse)
async def analyze_meal(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    note: Optional[str] = Form(None),
    question: Optional[str] = Form(None),
):
    try:
        image_bytes = await image.read()
        content_type = image.content_type or "image/jpeg"
        clean_question = question.strip() if question and question.strip() else None

        # Schedule the image to be logged to disk in the background seamlessly
        img_timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_dir = "logs/images"
        img_filename = f"{log_dir}/{img_timestamp}_{int(time.time() * 1000)}.jpg"
        
        background_tasks.add_task(save_image_to_disk, image_bytes, log_dir, img_filename)
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
        raise HTTPException(status_code=422, detail=f"Meal analysis parse error: {str(e)}")
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error analysing meal image: {error_msg}"
        )

@router.post("/analyze-text", response_model=MealAnalysisResponse)
async def analyze_meal_text(body: MealTextRequest, request: Request):
    """
    Analyse a meal described in plain text using GPT-4o.
    No image required — the user simply describes what they ate.
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
        raise HTTPException(status_code=422, detail=f"Meal text analysis parse error: {str(e)}")
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error analysing meal description: {error_msg}"
        )
