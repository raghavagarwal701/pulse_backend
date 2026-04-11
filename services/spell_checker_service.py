import logging
import os
import re
import pandas as pd
from spellchecker import SpellChecker
from typing import Set

logger = logging.getLogger(__name__)

class PulseSpellChecker:
    def __init__(self, dataset_path: str = None):
        """
        Initializes the spell checker and loads food-specific terms
        from the nutrition dataset.
        """
        self.spell = SpellChecker()
        if dataset_path is None:
            self.dataset_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "final_dataset.csv")
            )
        else:
            self.dataset_path = os.path.abspath(dataset_path)
        self._load_custom_words()

    def _load_custom_words(self):
        try:
            if not os.path.exists(self.dataset_path):
                raise FileNotFoundError(f"Dataset file does not exist: {self.dataset_path}")
            df = pd.read_csv(self.dataset_path, usecols=["dish_name"])
            dish_names = df["dish_name"].dropna()
            custom_words: Set[str] = set()
            
            # Extract all words from dish names in dataset
            for name in dish_names:
                words = re.findall(r'\b[a-zA-Z]+\b', name.lower())
                custom_words.update(words)
            
            # Add extra health and fitness specific words to avoid false corrections
            custom_words.update([
                "protein", "calorie", "calories", "carbs", "fats", "workout", 
                "cardio", "bmi", "bmr", "keto", "vegan", "macros", "creatine",
                "whey", "hypertrophy"
            ])
            
            self.spell.word_frequency.load_words(list(custom_words))
        except Exception as e:
            logger.warning("Could not load dataset for spell checker from %s: %s", self.dataset_path, e)

    def correct_query(self, query: str) -> str:
        """
        Corrects the spelling of words in a query while preserving case and non-alphabetical characters.
        """
        def replace_word(match):
            word = match.group(0)
            
            # 1. Ignore if word is already correct according to custom + standard dictionary
            if word.lower() in self.spell:
                return word
                
            # 2. Get correction
            corrected = self.spell.correction(word)
            
            if not corrected: # If no correction found, return original
                return word
                
            # 3. Preserve original case
            if word.istitle():
                return corrected.title()
            elif word.isupper():
                return corrected.upper()
            return corrected

        # Find all words (alphabetical only) and apply replacement
        return re.sub(r'\b[a-zA-Z]+\b', replace_word, query)

# Singleton instance to be imported by other modules
pulse_spell_checker = PulseSpellChecker()
