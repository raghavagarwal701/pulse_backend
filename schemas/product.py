"""
Product scanner models.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from schemas.meal import MealItem

class ProductNutriments(BaseModel):
    """Nutritional values per 100g and per full package"""
    energy_kcal_100g: Optional[float] = None
    fat_100g: Optional[float] = None
    carbohydrates_100g: Optional[float] = None
    sugars_100g: Optional[float] = None
    proteins_100g: Optional[float] = None
    fiber_100g: Optional[float] = None
    salt_100g: Optional[float] = None
    # Per-package values (scaled by product_quantity)
    energy_kcal_pkg: Optional[float] = None
    fat_pkg: Optional[float] = None
    carbohydrates_pkg: Optional[float] = None
    sugars_pkg: Optional[float] = None
    proteins_pkg: Optional[float] = None
    fiber_pkg: Optional[float] = None
    salt_pkg: Optional[float] = None

class ProductInfo(BaseModel):
    """Product information from OpenFoodFacts"""
    barcode: str
    product_name: Optional[str] = None
    brands: Optional[str] = None
    categories: Optional[str] = None
    nutriscore_grade: Optional[str] = None
    nutriments: Optional[ProductNutriments] = None
    image_url: Optional[str] = None
    ingredients_text: Optional[str] = None
    product_quantity: Optional[float] = None
    product_quantity_unit: Optional[str] = None
    serving_size: Optional[str] = None
    serving_quantity: Optional[float] = None
    # Meal-analysis-specific fields (null for barcode scans)
    description: Optional[str] = None
    ingredients: Optional[List[str]] = None
    insights: Optional[str] = None
    pros: Optional[List[str]] = None
    cons: Optional[List[str]] = None
    items: Optional[List[MealItem]] = None
    calorie_approximations: Optional[str] = None

class ProductResponse(BaseModel):
    """Response for /api/product/{barcode} endpoint"""
    status: str = Field(..., description="'found' or 'not_found'")
    product: Optional[ProductInfo] = None
    error: Optional[str] = None
