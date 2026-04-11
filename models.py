"""
Pydantic models for API request/response validation.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ===== Health Data Models =====

class ActivitySummary(BaseModel):
    """Activity and step count summary"""
    daily_averages: Optional[Dict[str, Any]] = None
    daily_ranges: Optional[Dict[str, Any]] = None
    weekly_averages: Optional[Dict[str, Any]] = None
    activity_patterns: Optional[Dict[str, Any]] = None


class SleepSummary(BaseModel):
    """Sleep data summary"""
    sleep_sessions: Optional[List[Dict[str, Any]]] = None
    sleep_quality: Optional[Dict[str, Any]] = None
    sleep_patterns: Optional[Dict[str, Any]] = None


class HeartRateSummary(BaseModel):
    """Heart rate data summary"""
    resting_hr: Optional[float] = None
    average_hr: Optional[float] = None
    hr_ranges: Optional[Dict[str, Any]] = None
    measurements: Optional[List[Dict[str, Any]]] = None


class HRVSummary(BaseModel):
    """HRV (Heart Rate Variability) summary"""
    average_hrv: Optional[float] = None
    hrv_trend: Optional[str] = None
    measurements: Optional[List[Dict[str, Any]]] = None


class ExerciseSummary(BaseModel):
    """Exercise and workout data summary"""
    sessions: Optional[List[Dict[str, Any]]] = None
    total_sessions: Optional[int] = None
    exercise_types: Optional[List[str]] = None
    performance_metrics: Optional[Dict[str, Any]] = None


class UserProfile(BaseModel):
    """User profile and demographic data"""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    location: Optional[Dict[str, Any]] = None
    medical_history: Optional[Dict[str, Any]] = None
    lifestyle_preferences: Optional[Dict[str, Any]] = None
    goals: Optional[Dict[str, Any]] = None


class HealthData(BaseModel):
    """Complete health data payload from mobile app"""
    activity_summary_for_llm: Optional[ActivitySummary] = None
    sleep_summary_for_llm: Optional[SleepSummary] = None
    heart_rate_summary_for_llm: Optional[HeartRateSummary] = None
    hrv_summary_for_llm: Optional[HRVSummary] = None
    exercise_summary_for_llm: Optional[ExerciseSummary] = None
    user_data: Optional[UserProfile] = None


# ===== Conversation Models =====

class ConversationMessage(BaseModel):
    """Single message in conversation history"""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatMealEntry(BaseModel):
    """One meal entry sent from the app chat context."""
    name: str
    calories: Optional[float] = None
    macros: Optional[Dict[str, Any]] = None
    micronutrients: Optional[Dict[str, Any]] = None


class ChatExerciseSession(BaseModel):
    """Exercise session included in chat context."""
    title: Optional[str] = None
    exercise_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None


class ChatActivityDetail(BaseModel):
    """Detailed activity summary for a single day."""
    steps: Optional[int] = None
    distance_km: Optional[float] = None
    calories_burned: Optional[float] = None
    workout_minutes: Optional[float] = None


class ChatSleepSummary(BaseModel):
    """Compact daily sleep summary."""
    total_sleep_hours: Optional[float] = None
    deep_sleep_hours: Optional[float] = None
    light_sleep_hours: Optional[float] = None
    rem_sleep_hours: Optional[float] = None
    awake_hours: Optional[float] = None


class ChatDailyHistory(BaseModel):
    """Today/yesterday grouped context."""
    activity: Optional[Any] = None
    exercise_session: Optional[Any] = None
    sleep_session: Optional[Any] = None
    meals: Optional[Any] = None


class ChatAverageActivity(BaseModel):
    """Past 7 day average activity stats."""
    avg_steps: Optional[float] = None
    avg_distance_km: Optional[float] = None
    avg_calories_burned: Optional[float] = None
    avg_workout_minutes: Optional[float] = None


class ChatAverageMeals(BaseModel):
    """Past 7 day meal averages."""
    avg_meals_logged_per_day: Optional[float] = None
    avg_calories_consumed_kcal: Optional[float] = None
    avg_macros: Optional[Dict[str, Any]] = None
    avg_micronutrients: Optional[Dict[str, Any]] = None


class ChatPastSevenDayAverage(BaseModel):
    """Aggregated averages for the past seven days."""
    average_activity: Optional[Any] = None
    sleep_detail: Optional[Any] = None
    meals: Optional[Any] = None
    heart_rate_summary: Optional[Any] = None
    sleep_summary: Optional[Any] = None
    hrv_summary: Optional[Any] = None
    exercise_summary: Optional[Any] = None


class ChatUserProfileContext(BaseModel):
    """User profile context sent with chat requests."""
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    goal: Optional[str] = None
    activity_level: Optional[str] = None


class ChatContext(BaseModel):
    """Structured context used by the chat endpoint."""
    history_today: Optional[ChatDailyHistory] = None
    yesterday_history: Optional[ChatDailyHistory] = None
    past_7_day_average: Optional[ChatPastSevenDayAverage] = None
    # Backward compatibility with previous payload shape while app rollout happens.
    last_two_days_meal_activity: Optional[List[Dict[str, Any]]] = None
    seven_day_nutrition_summary: Optional[Dict[str, Any]] = None
    seven_day_activity_history: Optional[List[Dict[str, Any]]] = None
    seven_day_sleep_history: Optional[List[Dict[str, Any]]] = None
    user_profile: Optional[ChatUserProfileContext] = None


# ===== Health Copilot Pipeline Models =====

class HealthSignals(BaseModel):
    """Computed health signals from raw data. Only 5 core signals."""
    # Core signals
    calorie_balance: Optional[float] = None      # intake - TDEE (None if meal data unreliable)
    protein_gap_g: Optional[float] = None        # required - consumed (None if no meal data)
    sleep_hours: Optional[float] = None          # total sleep today
    activity_ratio: Optional[float] = None       # today_steps / 7d_avg_steps
    recovery_level: str = "unknown"              # "low" | "moderate" | "high" | "unknown"

    # Supporting (used by rule engine, not sent to LLM directly)
    bmr: Optional[float] = None
    tdee: Optional[float] = None
    meal_confidence: str = "low"                 # "high" | "medium" | "low"
    mapped_goal: str = "maintenance"             # "fat_loss" | "muscle_gain" | "maintenance"
    today_steps: Optional[int] = None
    today_calories_consumed: Optional[float] = None
    today_protein_consumed: Optional[float] = None
    yesterday_sleep_hours: Optional[float] = None
    recent_workout_type: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)


class Constraints(BaseModel):
    """Structured constraints from rule engine. LLM must follow these."""
    max_workout_intensity: str = "moderate"  # "none" | "light" | "moderate" | "intense"
    protein_priority: bool = False
    avoid_heavy_meals: bool = False
    suggest_more_movement: bool = False
    avoid_extra_strain: bool = False
    allow_higher_calories: bool = False
    suggest_lighter_meals: bool = False
    use_flexible_nutrition: bool = False


class DecisionHints(BaseModel):
    """Explicit boolean conclusions. LLM reads these, not infers."""
    low_protein: bool = False
    poor_sleep: bool = False
    low_activity: bool = False
    high_activity: bool = False
    calorie_surplus: bool = False
    calorie_deficit: bool = False
    data_is_unreliable: bool = False


# ===== API Request/Response Models =====

class ChatRequest(BaseModel):
    """Request body for /api/chat endpoint"""
    query: str = Field(..., description="User's question or message")
    chat_context: Optional[ChatContext] = Field(
        default=None,
        description="Structured activity, diet, sleep, and profile context from the app"
    )
    health_data: Optional[HealthData] = Field(
        default=None,
        description="Legacy health data from Health Connect"
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=[],
        description="Previous conversation messages for context"
    )


class ToolCall(BaseModel):
    """Information about a tool that was called"""
    name: str
    timestamp: str


class ChatResponse(BaseModel):
    """Response body for /api/chat endpoint"""
    response: str = Field(..., description="Assistant's response")
    tool_calls: List[ToolCall] = Field(
        default=[],
        description="List of tools that were called during processing"
    )

class StructuredLLMResponse(BaseModel):
    """Structured response used to improve CoT in the LLM internally."""
    reasoning: str = Field(
        description="Your step-by-step reasoning for deciding the final response. Use this space to think."
    )
    data_used: str = Field(
        description="A list of nutrition, recovery, or fitness data you considered before responding."
    )
    response: str = Field(
        description="The final personalized response to show to the user. This must be concise, practical, and conversational."
    )


# ===== Product Scanner Models =====

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


class MealAnalysisResponse(BaseModel):
    """Response for POST /api/meal/analyze and /api/meal/analyze-text."""
    status: str = Field(..., description="'analyzed' or 'error'")
    meal: Optional[MealAnalysis] = None
    asked_question: Optional[str] = None
    question_answer: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# FatSecret Integration Models
# =============================================================================

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
