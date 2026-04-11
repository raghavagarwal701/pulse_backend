"""
Chat and conversation models.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from schemas.health import HealthData

# ===== Conversation Models =====

class ConversationMessage(BaseModel):
    """Single message in conversation history"""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")

class ChatDailyHistory(BaseModel):
    """Today/yesterday grouped context."""
    activity: Optional[Any] = None
    exercise_session: Optional[Any] = None
    sleep_session: Optional[Any] = None
    meals: Optional[Any] = None

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
        default_factory=list,
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
        default_factory=list,
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
