"""
FatSecret API integration service for meal search and nutrition data.
Handles OAuth2 authentication, token caching, and API interactions.
"""

import httpx
import json
import os
import time
import csv
from typing import Optional, Dict, Any, List

import logging

logger = logging.getLogger(__name__)


class FatSecretToken:
    """Token holder with caching and expiry management."""
    
    def __init__(self, access_token: str, expires_in: int):
        self.access_token = access_token
        self.token_type = "Bearer"
        self.issued_at = time.time()
        self.expires_in = expires_in
        # Refresh at 80% of TTL to be safe
        self.refresh_threshold = expires_in * 0.8
    
    def is_expired(self) -> bool:
        """Check if token is expired or close to expiry."""
        elapsed = time.time() - self.issued_at
        return elapsed > self.refresh_threshold
    
    def get_auth_header(self) -> Dict[str, str]:
        """Return Authorization header for API requests."""
        return {
            "Authorization": f"{self.token_type} {self.access_token}"
        }


class FatSecretClient:
    """
    Async HTTP client for FatSecret API interactions.
    Handles OAuth2 token management and autocomplete/search/food-detail queries.
    """
    
    TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
    API_BASE = "https://platform.fatsecret.com/rest/"
    API_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs", "fatsecreate_api_logs")
    CSV_DATASET_PATH = os.path.join(os.path.dirname(__file__), "final_dataset.csv")
    CSV_ID_OFFSET = 1_000_000
    
    def __init__(self, client_id: str, client_secret: str, scope: str = "premier", 
                 region: str = "IN", language: str = "en"):
        """
        Initialize FatSecret client.
        
        Args:
            client_id: FatSecret OAuth2 client ID
            client_secret: FatSecret OAuth2 client secret
            scope: OAuth2 scope (default: "premier")
            region: Region code (default: "IN" for India)
            language: Language code (default: "en" for English)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.region = region
        self.language = language
        self.token: Optional[FatSecretToken] = None
        self.csv_foods: List[Dict[str, Any]] = []
        self.csv_foods_by_id: Dict[int, Dict[str, Any]] = {}
        self._load_csv_foods()

    def _to_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _strip_per_100g_fields(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Remove per-100g nutrition keys so clients consume serving-based values only."""
        cleaned: Dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key).lower()
            if "per_100" in key_text or "100g" in key_text:
                continue
            cleaned[key] = value
        return cleaned

    def _build_csv_food(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        dish_id_raw = row.get("dish_id")
        dish_name = str(row.get("dish_name") or "").strip()

        if not dish_id_raw or not dish_name:
            return None

        dish_id = int(self._to_float(dish_id_raw, 0.0))
        if dish_id <= 0:
            return None

        synthetic_food_id = self.CSV_ID_OFFSET + dish_id

        calories_100g = self._to_float(row.get("calories_per_100g"))
        protein_100g = self._to_float(row.get("protein_per_100g"))
        fat_100g = self._to_float(row.get("fat_per_100g"))
        carbs_100g = self._to_float(row.get("carbs_per_100g"))
        avg_serving_size = self._to_float(row.get("average_serving_size"), 100.0)
        if avg_serving_size <= 0:
            avg_serving_size = 100.0

        serving_factor = avg_serving_size / 100.0

        servings = [
            {
                "serving_description": f"{avg_serving_size:g} g",
                "metric_serving_amount": avg_serving_size,
                "metric_serving_unit": "g",
                "number_of_units": 1.0,
                "measurement_description": "serving",
                "calories": round(calories_100g * serving_factor, 2),
                "protein": round(protein_100g * serving_factor, 2),
                "fat": round(fat_100g * serving_factor, 2),
                "carbohydrate": round(carbs_100g * serving_factor, 2),
            },
        ]

        return {
            "food_id": synthetic_food_id,
            "food_name": dish_name,
            "food_type": "Generic",
            "brand_name": row.get("source") or "final_dataset",
            "servings": servings,
            "source_type": "csv",
            "source_db": row.get("source"),
            "confidence_score": self._to_float(row.get("confidence_score"), 0.0),
            "normalized_name": row.get("normalized_name") or dish_name.lower(),
            "average_serving_size": avg_serving_size,
            "dish_id": dish_id,
        }

    def _load_csv_foods(self) -> None:
        if not os.path.exists(self.CSV_DATASET_PATH):
            logger.warning("CSV dataset not found at %s", self.CSV_DATASET_PATH)
            return

        try:
            with open(self.CSV_DATASET_PATH, "r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    csv_food = self._build_csv_food(row)
                    if not csv_food:
                        continue
                    food_id = int(csv_food["food_id"])
                    self.csv_foods.append(csv_food)
                    self.csv_foods_by_id[food_id] = csv_food

            logger.info("Loaded %d foods from CSV dataset", len(self.csv_foods))
        except Exception:
            logger.exception("Failed loading CSV dataset from %s", self.CSV_DATASET_PATH)

    def _search_csv_foods(self, normalized_query: str) -> List[Dict[str, Any]]:
        if not normalized_query:
            return []

        matches: List[Dict[str, Any]] = []
        for food in self.csv_foods:
            name = str(food.get("food_name", "")).lower()
            normalized_name = str(food.get("normalized_name", "")).lower()
            if normalized_query in name or normalized_query in normalized_name:
                matches.append(dict(food))
        return matches

    def _autocomplete_csv_foods(self, expression: str, max_results: int) -> List[str]:
        normalized_expression = expression.strip().lower()
        if not normalized_expression:
            return []

        suggestions: List[str] = []
        seen = set()
        for food in self.csv_foods:
            food_name = str(food.get("food_name", "")).strip()
            normalized_name = str(food.get("normalized_name", "")).strip().lower()
            if not food_name:
                continue
            if normalized_expression in food_name.lower() or normalized_expression in normalized_name:
                if food_name not in seen:
                    seen.add(food_name)
                    suggestions.append(food_name)
            if 0 < max_results <= len(suggestions):
                break

        return suggestions

    def _sanitize_log_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: ("[redacted]" if key in {"access_token", "client_secret", "refresh_token"} else self._sanitize_log_value(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._sanitize_log_value(item) for item in value]
        return value

    def _write_api_log(
        self,
        api_name: str,
        request_data: Dict[str, Any],
        response_data: Optional[Any] = None,
        status_code: Optional[int] = None,
        error: Optional[Exception] = None,
    ) -> None:
        try:
            os.makedirs(self.API_LOG_DIR, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{int(time.time() * 1000)}.json"
            log_entry: Dict[str, Any] = {
                "timestamp": timestamp,
                "api": api_name,
                "request": self._sanitize_log_value(request_data),
            }

            if response_data is not None:
                log_entry["response"] = self._sanitize_log_value(response_data)

            if status_code is not None:
                log_entry["status_code"] = status_code

            if error is not None:
                log_entry["error"] = str(error)

            file_path = os.path.join(self.API_LOG_DIR, file_name)
            with open(file_path, "w") as log_file:
                json.dump(log_entry, log_file, indent=2, ensure_ascii=False)
        except Exception:
            logger.exception("Failed to write FatSecret API log")

    def _normalize_food(self, food: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize FatSecret food payload so `servings` is always a list."""
        servings_obj = food.get("servings") or {}
        serving_items = []

        if isinstance(servings_obj, list):
            serving_items = servings_obj
        elif isinstance(servings_obj, dict):
            raw = servings_obj.get("serving", [])
            if isinstance(raw, list):
                serving_items = raw
            elif isinstance(raw, dict):
                serving_items = [raw]

        normalized = self._strip_per_100g_fields(dict(food))
        normalized["servings"] = serving_items
        normalized.setdefault("source_type", "fatsecret")
        return normalized
    
    async def _get_token(self, client: httpx.AsyncClient) -> str:
        """
        Obtain OAuth2 access token from FatSecret.
        Uses client_credentials grant type.
        
        Returns:
            Access token string
            
        Raises:
            Exception: If token request fails
        """
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope
        }

        response = None
        try:
            response = await client.post(self.TOKEN_URL, data=payload)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            self._write_api_log(
                api_name="connect.token",
                request_data={
                    "method": "POST",
                    "url": self.TOKEN_URL,
                    "data": payload,
                },
                response_data=data,
                status_code=response.status_code,
            )
            response.raise_for_status()
        except Exception as exc:
            if response is not None:
                try:
                    error_body = response.json()
                except Exception:
                    error_body = {"raw_response": response.text}
                self._write_api_log(
                    api_name="connect.token",
                    request_data={
                        "method": "POST",
                        "url": self.TOKEN_URL,
                        "data": payload,
                    },
                    response_data=error_body,
                    status_code=response.status_code,
                    error=exc,
                )
            else:
                self._write_api_log(
                    api_name="connect.token",
                    request_data={
                        "method": "POST",
                        "url": self.TOKEN_URL,
                        "data": payload,
                    },
                    error=exc,
                )
            raise
        
        # Cache token with expiry management
        self.token = FatSecretToken(
            access_token=data["access_token"],
            expires_in=data.get("expires_in", 86400)
        )
        
        logger.info("FatSecret token obtained, expires in %d seconds", self.token.expires_in)
        return data["access_token"]
    
    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        """
        Ensure valid access token, refreshing if necessary.
        
        Returns:
            Valid access token string
        """
        if self.token is None or self.token.is_expired():
            logger.info("Token expired or missing, refreshing...")
            await self._get_token(client)
        
        return self.token.access_token
    
    async def autocomplete(self, expression: str, max_results: int = 10) -> List[str]:
        """
        Get autocomplete suggestions for a food search expression.
        
        Args:
            expression: Partial food name (e.g., "chic")
            max_results: Maximum number of suggestions (default: 10, max: 10)
            
        Returns:
            List of suggestion strings
        """
        csv_suggestions = self._autocomplete_csv_foods(expression, max_results)

        async with httpx.AsyncClient() as client:
            await self._ensure_token(client)
            
            params = {
                "method": "foods.autocomplete.v2",
                "expression": expression,
                "max_results": min(max_results, 10),
                "region": self.region,
                "format": "json"
            }
            
            headers = self.token.get_auth_header()

            response = await client.get(self.API_BASE, params=params, headers=headers)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            self._write_api_log(
                api_name="foods.autocomplete.v2",
                request_data={
                    "method": "GET",
                    "url": self.API_BASE,
                    "params": params,
                },
                response_data=data,
                status_code=response.status_code,
            )
            response.raise_for_status()

            suggestions = data.get("suggestions", {})
            
            # Extract suggestion list (FatSecret returns array within suggestions object)
            api_suggestions = []
            if isinstance(suggestions, dict):
                # FatSecret format: {"suggestions": [{"value": "Chicken Breast"},  ...]}
                if "suggestion" in suggestions:
                    items = suggestions["suggestion"]
                    if isinstance(items, list):
                        api_suggestions = [item.get("value", item) if isinstance(item, dict) else item for item in items]
                    elif isinstance(items, dict):
                        api_suggestions = [items.get("value", items)]

            merged_suggestions: List[str] = []
            seen = set()
            for suggestion in csv_suggestions + api_suggestions:
                suggestion_text = str(suggestion).strip()
                if not suggestion_text or suggestion_text in seen:
                    continue
                seen.add(suggestion_text)
                merged_suggestions.append(suggestion_text)
                if 0 < max_results <= len(merged_suggestions):
                    break

            return merged_suggestions
            
    
    async def search(
        self,
        query: str,
        page_number: int = 0,
        max_results: int = 20,
        include_food_images: bool = True,
    ) -> Dict[str, Any]:
        """
        Search for foods by name, with pagination, region filtering, and optional images.
        
        Args:
            query: Food search query (e.g., "chicken breast")
            page_number: Zero-based page number (default: 0)
            max_results: Results per page (default: 20, max: 50)
            
        Returns:
            Dict with keys: max_results, total_results, page_number, results (list of food objects)
        """
        normalized_query = query.strip().lower()
        csv_results: List[Dict[str, Any]] = []
        if page_number == 0:
            csv_results = self._search_csv_foods(normalized_query)

        async with httpx.AsyncClient() as client:
            await self._ensure_token(client)
            
            params = {
                "method": "foods.search.v5",
                "search_expression": query,
                "page_number": page_number,
                "max_results": 50,
                "region": self.region,
                "include_sub_categories": "true",
                "include_food_images": str(include_food_images).lower(),
                "include_food_attributes": "true",
                "flag_default_serving": "true",
                "format": "json"
            }
            
            headers = self.token.get_auth_header()

            response = await client.get(self.API_BASE, params=params, headers=headers)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            self._write_api_log(
                api_name="foods.search.v5",
                request_data={
                    "method": "GET",
                    "url": self.API_BASE,
                    "params": params,
                },
                response_data=data,
                status_code=response.status_code,
            )
            response.raise_for_status()

            foods_search = data.get("foods_search", {})
            
            # Extract results list
            fatsecret_results = []
            if "results" in foods_search:
                food_results = foods_search["results"]
                if isinstance(food_results, dict) and "food" in food_results:
                    foods = food_results["food"]
                    raw_foods = foods if isinstance(foods, list) else [foods]
                    fatsecret_results = [
                        self._normalize_food(food)
                        for food in raw_foods
                        if isinstance(food, dict)
                        and normalized_query in str(food.get("food_name", "")).lower()
                    ]

            merged_results = csv_results + fatsecret_results
            total_results = len(merged_results)

            if max_results > 0:
                merged_results = merged_results[: min(max_results, 50)]
            
            return {
                "max_results": len(merged_results),
                "total_results": total_results,
                "page_number": foods_search.get("page_number", page_number),
                "results": merged_results
            }
    
    async def get_food(self, food_id: int) -> Dict[str, Any]:
        """
        Get detailed food information including all serving sizes and nutrition data.
        
        Args:
            food_id: FatSecret food ID (integer)
            
        Returns:
            Dict with food object containing food_id, food_name, servings list, etc.
        """
        csv_food = self.csv_foods_by_id.get(food_id)
        if csv_food is not None:
            return dict(csv_food)

        async with httpx.AsyncClient() as client:
            await self._ensure_token(client)
            
            params = {
                "method": "food.get.v5",
                "food_id": food_id,
                "include_sub_categories": "true",
                "include_food_images": "true",
                "include_food_attributes": "true",
                "flag_default_serving": "true",
                "region": self.region,
                "language": self.language,
                "format": "json"
            }
            
            headers = self.token.get_auth_header()

            response = await client.get(self.API_BASE, params=params, headers=headers)
            try:
                data = response.json()
            except Exception:
                data = {"raw_response": response.text}

            self._write_api_log(
                api_name="food.get.v5",
                request_data={
                    "method": "GET",
                    "url": self.API_BASE,
                    "params": params,
                },
                response_data=data,
                status_code=response.status_code,
            )
            response.raise_for_status()

            food = data.get("food", {})
            if isinstance(food, dict):
                return self._normalize_food(food)
            return {}
    
    async def calculate_meal_totals(self, food: Dict[str, Any], serving_description: str, 
                                   quantity: float) -> Dict[str, float]:
        """
        Calculate total nutrition for a meal item (food + serving + quantity).
        
        Args:
            food: Food object from get_food() response
            serving_description: Serving description from the food's servings list
            quantity: Number of servings to consume (e.g., 1.5)
            
        Returns:
            Dict with calculated nutrient totals (calories, carbs, protein, fat, etc.)
        """
        servings = food.get("servings", [])
        if isinstance(servings, list):
            serving_list = servings
        elif isinstance(servings, dict):
            maybe_serving = servings.get("serving", [])
            serving_list = maybe_serving if isinstance(maybe_serving, list) else [maybe_serving]
        else:
            serving_list = []
        
        # Find matching serving
        selected_serving = None
        for s in serving_list:
            if s.get("serving_description") == serving_description:
                selected_serving = s
                break
        
        if not selected_serving:
            raise ValueError(f"Serving '{serving_description}' not found")
        
        # Calculate totals by multiplying serving nutrients by quantity
        totals = {}
        nutrient_fields = [
            "calories", "carbohydrate", "protein", "fat", "saturated_fat",
            "fiber", "sugar", "sodium", "potassium", "cholesterol",
            "vitamin_a", "vitamin_c", "calcium", "iron", "trans_fat",
            "added_sugars", "vitamin_d"
        ]
        
        for field in nutrient_fields:
            value = selected_serving.get(field)
            if value is not None:
                try:
                    totals[field] = float(value) * quantity
                except (ValueError, TypeError):
                    totals[field] = 0.0
        
        return totals
