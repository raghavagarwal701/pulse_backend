"""
Feature Engineering module for the Health Copilot Chat Pipeline.
Computes 5 core signals from raw chat context.
"""
from typing import Any, Optional
from schemas.chat import ChatContext, HealthSignals

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _get_nested(data: Any, *keys) -> Any:
    current = data
    for k in keys:
        if not isinstance(current, dict) and hasattr(current, "model_dump"):
            current = current.model_dump()
        
        if isinstance(current, dict):
            current = current.get(k)
        else:
            try:
                current = getattr(current, k, None)
            except Exception:
                return None
        if current is None:
            return None
    return current

def _map_goal(raw_goal: Optional[str]) -> str:
    if not raw_goal:
        return "maintenance"
    raw = str(raw_goal).lower()
    if any(k in raw for k in ["lose", "cut", "fat", "lean", "weight loss"]):
        return "fat_loss"
    if any(k in raw for k in ["gain", "bulk", "muscle", "mass", "strength"]):
        return "muscle_gain"
    return "maintenance"

def compute_signals(context: Optional[ChatContext]) -> HealthSignals:
    if not context:
        return HealthSignals(missing_fields=["context"])

    missing = []
    
    # 1. Extract raw data safely
    profile = context.user_profile
    weight = _safe_float(_get_nested(profile, "weight_kg"))
    height = _safe_float(_get_nested(profile, "height_cm"))
    age = _safe_int(_get_nested(profile, "age"))
    gender = str(_get_nested(profile, "gender") or "").lower()
    raw_goal = _get_nested(profile, "goal")

    today_history = context.history_today
    today_activity = _get_nested(today_history, "activity")
    today_steps = _safe_int(_get_nested(today_activity, "steps"), 0)
    
    today_meals = _get_nested(today_history, "meals")
    if isinstance(today_meals, str):  # "no logs present"
        today_meals = []
    
    today_sleep = _get_nested(today_history, "sleep_session")
    today_sleep_hours = _safe_float(_get_nested(today_sleep, "total_sleep_hours"))
    
    yesterday_history = context.yesterday_history
    yesterday_sleep = _get_nested(yesterday_history, "sleep_session")
    yesterday_sleep_hours = _safe_float(_get_nested(yesterday_sleep, "total_sleep_hours"))

    past_7d = context.past_7_day_average
    avg_steps = _safe_float(_get_nested(past_7d, "average_activity", "avg_steps"))

    # 2. Supporting Computations
    bmr = None
    if weight and height:
        a = age or 25
        if gender == "female":
            bmr = (10 * weight) + (6.25 * height) - (5 * a) - 161
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * a) + 5
    else:
        missing.append("weight/height for BMR")

    tdee = None
    if bmr:
        steps = today_steps or 0
        if steps < 5000:
            mult = 1.2
        elif steps < 8000:
            mult = 1.375
        elif steps < 12000:
            mult = 1.55
        else:
            mult = 1.725
        tdee = bmr * mult

    mapped_goal = _map_goal(raw_goal)
    
    req_protein = None
    if weight:
        if mapped_goal == "fat_loss":
            req_protein = weight * 1.6
        elif mapped_goal == "muscle_gain":
            req_protein = weight * 1.8
        else:
            req_protein = weight * 1.2

    consumed_cals = 0.0
    consumed_protein = 0.0
    meal_count = 0
    if isinstance(today_meals, list):
        for m in today_meals:
            if isinstance(m, dict):
                consumed_cals += _safe_float(m.get("calories"), 0.0)
                mac = m.get("macros", {})
                consumed_protein += _safe_float(mac.get("protein_g"), 0.0)
                meal_count += 1
            else:
                consumed_cals += _safe_float(getattr(m, "calories", 0.0), 0.0)
                mac = getattr(m, "macros", None)
                consumed_protein += _safe_float(getattr(mac, "protein_g", 0.0) if mac else 0.0, 0.0)
                meal_count += 1

    meal_conf = "low"
    if meal_count >= 3:
        meal_conf = "high"
    elif meal_count > 0:
        meal_conf = "medium"

    # 3. Core Signals
    calorie_balance = None
    if tdee and meal_conf != "low":
        calorie_balance = consumed_cals - tdee
    if meal_conf == "low":
        missing.append("meal data (confidence low)")

    protein_gap = None
    if req_protein is not None and meal_conf != "low":
        protein_gap = req_protein - consumed_protein

    activity_ratio = None
    if today_steps is not None and avg_steps and avg_steps > 0:
        activity_ratio = today_steps / avg_steps
    elif avg_steps == 0:
        activity_ratio = 1.0

    recovery = "unknown"
    if today_sleep_hours is not None:
        if today_sleep_hours < 6:
            recovery = "low"
        elif today_sleep_hours <= 7:
            recovery = "moderate"
        else:
            recovery = "high"
    else:
        missing.append("sleep hours")
        
    recent_workout = None
    exercises = _get_nested(today_history, "exercise_session")
    if isinstance(exercises, list) and len(exercises) > 0:
        ex = exercises[-1]
        recent_workout = _get_nested(ex, "exercise_name")
        if not recent_workout and hasattr(ex, "exercise_name"):
             recent_workout = ex.exercise_name

    return HealthSignals(
        calorie_balance=calorie_balance,
        protein_gap_g=protein_gap,
        sleep_hours=today_sleep_hours,
        activity_ratio=activity_ratio,
        recovery_level=recovery,
        
        bmr=bmr,
        tdee=tdee,
        meal_confidence=meal_conf,
        mapped_goal=mapped_goal,
        today_steps=today_steps,
        today_calories_consumed=consumed_cals if meal_count > 0 else None,
        today_protein_consumed=consumed_protein if meal_count > 0 else None,
        yesterday_sleep_hours=yesterday_sleep_hours,
        recent_workout_type=recent_workout,
        missing_fields=missing
    )
