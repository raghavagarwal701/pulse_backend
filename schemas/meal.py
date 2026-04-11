"""
Meal analysis models.
"""
from typing import Optional, List
from pydantic import BaseModel, Field

class MealItemNutrients(BaseModel):
    """Per-item nutrient breakdown returned by the meal analysis LLM."""
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbohydrates: Optional[float] = None
    fat: Optional[float] = None
    sugar: Optional[float] = None
    fiber: Optional[float] = None
    sodium: Optional[float] = None

class MealItem(BaseModel):
    """One food component of an analysed meal."""
    name: str
    estimated_quantity: str
    nutrients: MealItemNutrients

class MealNutritionalValue(BaseModel):
    """Meal nutrient totals aligned with FatSecret-style nutrient keys."""
    calories: Optional[float] = None
    carbohydrate: Optional[float] = None
    protein: Optional[float] = None
    fat: Optional[float] = None
    saturated_fat: Optional[float] = None
    fiber: Optional[float] = None
    sugar: Optional[float] = None
    sodium: Optional[float] = None
    potassium: Optional[float] = None
    cholesterol: Optional[float] = None
    vitamin_a: Optional[float] = None
    vitamin_c: Optional[float] = None
    calcium: Optional[float] = None
    iron: Optional[float] = None
    trans_fat: Optional[float] = None
    added_sugars: Optional[float] = None
    vitamin_d: Optional[float] = None

class LLMMealResponse(BaseModel):
    """Structured output schema used as response_format for meal analysis LLM calls."""
    reasoning: str = Field(
        description=(
            "Step-by-step chain-of-thought: what the LLM sees in the image/description, "
            "why each food item is identified as it is, and how web-backed serving/nutrient "
            "estimates were derived. Stored in server logs only."
        ),
    )
    web_source_links: List[str] = Field(default_factory=list)
    name_of_meal: str
    serving_size: Optional[str] = None
    nutritional_value: MealNutritionalValue = Field(default_factory=MealNutritionalValue)

class MealAnalysis(BaseModel):
    """Meal-only analysis payload returned by the meal endpoints."""
    reasoning: str
    web_source_links: List[str] = Field(default_factory=list)
    name_of_meal: str
    serving_size: Optional[str] = None
    nutritional_value: MealNutritionalValue = Field(default_factory=MealNutritionalValue)

class MealAnalysisResponse(BaseModel):
    """Response for POST /api/meal/analyze and /api/meal/analyze-text."""
    status: str = Field(..., description="'analyzed' or 'error'")
    meal: Optional[MealAnalysis] = None
    asked_question: Optional[str] = None
    question_answer: Optional[str] = None
    error: Optional[str] = None

class MealTextRequest(BaseModel):
    description: str  # e.g. "2 chapatis with dal and a glass of milk"
