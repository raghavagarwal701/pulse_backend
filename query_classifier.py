"""
Query classifier. Deterministically maps user questions to categories.
"""
import re

KEYWORD_GROUPS = {
    "nutrition": {
        "eat", "food", "meal", "snack", "breakfast", "lunch", "dinner",
        "calories", "calorie", "protein", "carb", "fat", "diet", "nutrition",
        "hungry", "appetite", "cook", "recipe", "drink", "water", "hydration",
        "macro", "fiber", "sugar", "sodium", "vitamin"
    },
    "fitness": {
        "workout", "exercise", "run", "gym", "train", "lift", "yoga",
        "cardio", "walk", "jog", "cycle", "swim", "stretch", "push-up",
        "squat", "plank", "hiit", "strength", "active", "sport"
    },
    "recovery": {
        "tired", "fatigue", "sleep", "rest", "energy", "exhausted",
        "sore", "recovery", "recover", "burnout", "stress", "relax",
        "nap", "drowsy", "insomnia", "overtraining"
    }
}

PRIORITY = ["recovery", "nutrition", "fitness"]

def classify(query: str) -> str:
    if not query:
        return "general"
        
    query = query.lower()
    # Simple tokenization
    # Simple tokenization by regex is unused in basic logic, mapping string below natively
    
    hits = {category: 0 for category in KEYWORD_GROUPS}
    
    for category, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:
            if kw in query:
                hits[category] += 1

        
    max_hits = max(hits.values())
    
    if max_hits == 0:
        return "general"
        
    # Find tags with max hits
    top_categories = [k for k, v in hits.items() if v == max_hits]
    
    # Tie-breaker using priority array
    if len(top_categories) > 1:
        for p in PRIORITY:
            if p in top_categories:
                return p
                
    return top_categories[0]
