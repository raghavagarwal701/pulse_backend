"""
FatSecret Integration Models.
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class FatSecretServing(BaseModel):
    """Serving size option from FatSecret food"""
    serving_description: str = Field(..., description="e.g., '1 cup', '100g', '1 medium'")

    class Config:
        extra = "allow"

class FatSecretFood(BaseModel):
    """Food item from FatSecret search or detail query"""
    food_id: int = Field(..., description="FatSecret food ID")
    food_name: str = Field(..., description="Common food name")
    brand_name: Optional[str] = None
    servings: List[FatSecretServing] = Field(default_factory=list, description="Available serving sizes")

    class Config:
        extra = "allow"

class FatSecretAutocompleteResponse(BaseModel):
    """Response for GET /api/fatsecret/autocomplete"""
    status: str = Field(..., description="'success' or 'error'")
    suggestions: List[str] = Field(default_factory=list, description="Food name suggestions")
    error: Optional[str] = None

class FatSecretSearchResponse(BaseModel):
    """Response for GET /api/fatsecret/search"""
    status: str = Field(..., description="'success' or 'error'")
    query: Optional[str] = None
    page_number: Optional[int] = None
    max_results: Optional[int] = None
    total_results: Optional[int] = None
    results: List[FatSecretFood] = Field(default_factory=list, description="List of matching foods")
    error: Optional[str] = None

class FatSecretFoodResponse(BaseModel):
    """Response for GET /api/fatsecret/food/{food_id}"""
    status: str = Field(..., description="'success' or 'error'")
    food: Optional[FatSecretFood] = None
    error: Optional[str] = None

class FatSecretMealAddRequest(BaseModel):
    """Request body for POST /api/fatsecret/add-preview"""
    food_id: int
    serving_description: str
    quantity: float = 1.0  # Number of servings to consume

class FatSecretMealAddPreviewResponse(BaseModel):
    """Response for POST /api/fatsecret/add-preview — calculates totals for a meal item"""
    status: str = Field(..., description="'success' or 'error'")
    food_id: Optional[int] = None
    food_name: Optional[str] = None
    serving_description: Optional[str] = None
    quantity: Optional[float] = None
    
    # Calculated totals for this meal (serving * quantity)
    totals: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Calculated nutrient totals (calories, carbs, protein, fat, etc.)"
    )
    error: Optional[str] = None
