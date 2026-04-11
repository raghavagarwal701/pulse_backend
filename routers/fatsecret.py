from fastapi import APIRouter, HTTPException
from schemas.fatsecret import (
    FatSecretAutocompleteResponse, FatSecretSearchResponse,
    FatSecretFoodResponse, FatSecretMealAddPreviewResponse,
    FatSecretMealAddRequest
)
from core.config import fatsecret_client

router = APIRouter(prefix="/api/fatsecret", tags=["FatSecret"])

@router.get("/autocomplete", response_model=FatSecretAutocompleteResponse)
async def fatsecret_autocomplete(expression: str, max_results: int = 10):
    if not fatsecret_client:
        raise HTTPException(status_code=501, detail="FatSecret integration is not configured")
    try:
        suggestions = await fatsecret_client.autocomplete(
            expression=expression,
            max_results=max_results
        )
        return FatSecretAutocompleteResponse(status="success", suggestions=suggestions)
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(status_code=500, detail=f"Error getting autocomplete suggestions: {error_msg}")

@router.get("/search", response_model=FatSecretSearchResponse)
async def fatsecret_search(query: str, page_number: int = 0, max_results: int = 20):
    if not fatsecret_client:
        raise HTTPException(status_code=501, detail="FatSecret integration is not configured")
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
        raise HTTPException(status_code=500, detail=f"Error searching foods: {error_msg}")

@router.get("/food/{food_id}", response_model=FatSecretFoodResponse)
async def fatsecret_get_food(food_id: int):
    if not fatsecret_client:
        raise HTTPException(status_code=501, detail="FatSecret integration is not configured")
    try:
        food = await fatsecret_client.get_food(food_id=food_id)
        if not food:
            raise HTTPException(status_code=404, detail=f"Food with ID {food_id} not found")
        return FatSecretFoodResponse(status="success", food=food)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(status_code=500, detail=f"Error retrieving food details: {error_msg}")

@router.post("/add-preview", response_model=FatSecretMealAddPreviewResponse)
async def fatsecret_add_preview(body: FatSecretMealAddRequest):
    if not fatsecret_client:
        raise HTTPException(status_code=501, detail="FatSecret integration is not configured")
    try:
        food = await fatsecret_client.get_food(food_id=body.food_id)
        if not food:
            raise HTTPException(status_code=404, detail=f"Food with ID {body.food_id} not found")
        
        totals = await fatsecret_client.calculate_meal_totals(
            food=food,
            serving_description=body.serving_description,
            quantity=body.quantity
        )
        
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
        raise HTTPException(status_code=422, detail=f"Meal calculation error: {str(e)}")
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(status_code=500, detail=f"Error calculating meal preview: {error_msg}")
