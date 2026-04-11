"""
Rule engine for the Health Copilot Chat Pipeline.
Converts signals into structured constraints and explicit decision hints.
"""
from typing import Tuple
from models import HealthSignals, Constraints, DecisionHints

def evaluate(signals: HealthSignals) -> Tuple[Constraints, DecisionHints]:
    # Base states
    max_intensity = "moderate"
    protein_priority = False
    avoid_heavy = False
    more_movement = False
    avoid_strain = False
    allow_higher_cal = False
    suggest_lighter = False
    use_flexible = False
    
    # Sleep Rules -> Intensity & Heavy Meals
    sleep = signals.sleep_hours
    if sleep is not None:
        if sleep < 5:
            max_intensity = "none"
            avoid_heavy = True
        elif sleep < 6:
            max_intensity = "light"
        elif sleep <= 7:
            max_intensity = "moderate"
        else:
            max_intensity = "intense"
            
    # Protein Priority
    p_gap = signals.protein_gap_g
    if p_gap is not None and p_gap > 25:
        protein_priority = True

    # Calorie Rules (Goal modified)
    c_bal = signals.calorie_balance
    if c_bal is not None:
        deficit_threshold = -300
        surplus_threshold = 300
        
        if signals.mapped_goal == "fat_loss":
            surplus_threshold = 150 # tighter
        elif signals.mapped_goal == "muscle_gain":
            allow_higher_cal = True # bias
            
        if c_bal < deficit_threshold:
            allow_higher_cal = True
        elif c_bal > surplus_threshold:
            suggest_lighter = True
            avoid_heavy = True

    # Goal Rules
    if signals.mapped_goal == "muscle_gain":
        protein_priority = True
        
    # Activity Rules
    a_ratio = signals.activity_ratio
    if a_ratio is not None:
        if a_ratio < 0.7:
            more_movement = True
        elif a_ratio > 1.2:
            avoid_strain = True

    # Unreliable data
    if signals.meal_confidence == "low":
        use_flexible = True
        allow_higher_cal = False
        suggest_lighter = False
        
    constraints = Constraints(
        max_workout_intensity=max_intensity,
        protein_priority=protein_priority,
        avoid_heavy_meals=avoid_heavy,
        suggest_more_movement=more_movement,
        avoid_extra_strain=avoid_strain,
        allow_higher_calories=allow_higher_cal,
        suggest_lighter_meals=suggest_lighter,
        use_flexible_nutrition=use_flexible
    )
    
    hints = DecisionHints(
        low_protein=(p_gap > 25) if p_gap else False,
        poor_sleep=(sleep < 6) if sleep else False,
        low_activity=(a_ratio < 0.7) if a_ratio else False,
        high_activity=(a_ratio > 1.2) if a_ratio else False,
        calorie_surplus=(c_bal > 300) if c_bal else False,
        calorie_deficit=(c_bal < -300) if c_bal else False,
        data_is_unreliable=use_flexible
    )
    
    return constraints, hints
