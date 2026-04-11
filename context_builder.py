"""
Builds minimal JSON context for LLM based on query type. strict limit of <= 5 fields.
"""
from typing import Dict, Any
from schemas.chat import HealthSignals, Constraints, DecisionHints

def build(signals: HealthSignals, query_type: str, constraints: Constraints, hints: DecisionHints) -> Dict[str, Any]:
    context = {}
    
    # Missing data array
    missing = []
    if getattr(signals, 'missing_fields', None):
        missing = signals.missing_fields.copy()
        
    if hints.data_is_unreliable:
        missing.append("calorie_balance unreliable (low meal confidence)")

    if query_type == "nutrition":
        if hints.data_is_unreliable:
            context["calorie_balance"] = None
        else:
            context["calorie_balance"] = signals.calorie_balance
            
        context["protein_gap_g"] = signals.protein_gap_g
        context["meal_confidence"] = signals.meal_confidence
        context["goal"] = signals.mapped_goal
        context["sleep_quality"] = signals.recovery_level  # Use recovery string
        
    elif query_type == "fitness":
        context["recovery_level"] = signals.recovery_level
        context["sleep_hours"] = signals.sleep_hours
        context["activity_ratio"] = signals.activity_ratio
        context["goal"] = signals.mapped_goal
        context["recent_workout_type"] = signals.recent_workout_type
        
    elif query_type == "recovery":
        context["sleep_hours"] = signals.sleep_hours
        context["recovery_level"] = signals.recovery_level
        context["activity_ratio"] = signals.activity_ratio
        context["goal"] = signals.mapped_goal
        context["yesterday_sleep_hours"] = signals.yesterday_sleep_hours
        
    else: # general
        context["recovery_level"] = signals.recovery_level
        
        if hints.data_is_unreliable:
            context["calorie_balance"] = None
        else:
            context["calorie_balance"] = signals.calorie_balance
            
        context["protein_gap_g"] = signals.protein_gap_g
        context["activity_ratio"] = signals.activity_ratio
        context["goal"] = signals.mapped_goal

    # Add constraints & hints as separate top-level blocks
    full_context = context.copy()
    full_context["constraints"] = constraints.model_dump()
    full_context["decision_hints"] = hints.model_dump()
    
    if missing:
        full_context["missing_data"] = missing
        
    return full_context
