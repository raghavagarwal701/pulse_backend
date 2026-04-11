# Pulse Backend

FastAPI backend for the Health Copilot mobile app. Accepts health data from Android app and returns AI-powered health insights using OpenAI.

## Setup

1. **Install dependencies:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Run the server:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### `GET /api/health`

Health check endpoint.

**Response:**

```json
{
  "status": "healthy",
  "service": "pulse_backend",
  "version": "1.0.0"
}
```

### `POST /api/chat`

Main chat endpoint - accepts the structured chat context from the mobile app and returns an LLM response.

**Request:**

```json
{
  "query": "How am I doing this week?",
  "chat_context": {
    "last_two_days_meal_activity": [
      {
        "date": "2026-04-09",
        "meals": [
          {
            "name": "Oatmeal",
            "calories": 240,
            "macros": { "protein_g": 8, "carbs_g": 42, "fat_g": 5 },
            "micronutrients": { "fiber_g": 6, "sugar_g": 8 }
          }
        ],
        "activity": {
          "steps": 9200,
          "distance_km": 6.4,
          "calories_burned": 480,
          "workout_minutes": 35,
          "exercise_sessions": []
        }
      }
    ],
    "seven_day_nutrition_summary": {
      "avg_energy_consumed_kcal": 2140,
      "avg_energy_expended_kcal": 2280,
      "avg_macros": { "protein_g": 92, "carbs_g": 240, "fat_g": 72 },
      "avg_micronutrients": { "fiber_g": 24, "sugar_g": 38, "sodium_mg": 2100 }
    },
    "seven_day_activity_history": [
      {
        "date": "2026-04-09",
        "steps": 9200,
        "distance_km": 6.4,
        "calories_burned": 480,
        "workout_minutes": 35,
        "exercise_sessions": []
      }
    ],
    "seven_day_sleep_history": [
      {
        "date": "2026-04-09",
        "sleep_sessions": [
          {
            "uid": "sleep-1",
            "start_time": "2026-04-08T22:40:00Z",
            "end_time": "2026-04-09T06:15:00Z",
            "duration_minutes": 455,
            "stages": []
          }
        ]
      }
    ],
    "user_profile": {
      "weight_kg": 72,
      "height_cm": 172,
      "goal": "lose_weight",
      "activity_level": "moderately_active"
    }
  },
  "health_data": { ... optional legacy summary ... },
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:**

```json
{
  "response": "Based on your activity data, you've taken 10,000 steps today...",
  "tool_calls": [
    { "name": "get_activity_summary", "timestamp": "2024-02-16T13:40:00" }
  ]
}
```

## Testing

Test with curl:

```bash
# Health check
curl http://localhost:8000/api/health

# Chat endpoint with sample data
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How are my steps?",
    "health_data": {
      "activity_summary_for_llm": {
        "daily_averages": {"steps": 10000}
      },
      "user_data": {
        "name": "Test User",
        "age": 22
      }
    }
  }'
```

## FatSecret Integration (Meal Search & Nutrition)

Pulse Backend includes optional FatSecret API integration for meal searching and nutrition data. Users can search for foods by name, browse serving options, and preview nutritional values.

### Setup

1. Add FatSecret OAuth2 credentials to `.env`:

   ```
   FATSECRET_CLIENT_ID=your_client_id
   FATSECRET_CLIENT_SECRET=your_client_secret
   FATSECRET_SCOPE=premier
   FATSECRET_REGION=IN
   FATSECRET_LANGUAGE=en
   ```

2. Credentials are optional — the app works without them. If missing, FatSecret endpoints return HTTP 501.

### FatSecret API Endpoints

**Note:** All FatSecret endpoints return JSON responses. Token management and format conversion are handled automatically by `fatsecret_service.py`.

**CSV augmentation:** On server startup, `final_dataset.csv` is loaded into memory and merged with FatSecret search results.

- Search results include `source_type` as either `csv` or `fatsecret`.
- CSV results are returned first on `page_number=0`, then FatSecret results.
- CSV items use synthetic `food_id` values (`1000000 + dish_id`) so they can be used with `GET /api/fatsecret/food/{food_id}` and `POST /api/fatsecret/add-preview`.
- `page_number > 0` returns FatSecret results only (no repeated CSV rows).

#### `GET /api/fatsecret/autocomplete`

Get autocomplete suggestions for food search (prefix-based suggestions).

**Query Parameters:**

- `expression` (required): Partial food name (e.g., "chic" for chicken suggestions)
- `max_results` (optional, default: 4): Maximum suggestions to return (1-10)

**Example Request:**

```bash
curl "http://localhost:8000/api/fatsecret/autocomplete?expression=chic&max_results=4"
```

**Response:**

```json
{
  "status": "success",
  "suggestions": [
    "Chicken Breast",
    "Chicken Thighs",
    "Chicken Wings",
    "Chicken Drumsticks"
  ],
  "error": null
}
```

---

#### `GET /api/fatsecret/search`

Search for foods by name with pagination.

**Query Parameters:**

- `query` (required): Food search query (e.g., "chicken breast")
- `page_number` (optional, default: 0): Zero-based page number for pagination
- `max_results` (optional, default: 20): Results per page (1-50)

**Example Request:**

```bash
curl "http://localhost:8000/api/fatsecret/search?query=chicken&page_number=0&max_results=10"
```

**Response:**

```json
{
  "status": "success",
  "query": "chicken",
  "page_number": 0,
  "max_results": 10,
  "total_results": 542,
  "results": [
    {
      "food_id": 1234,
      "food_name": "Chicken Breast",
      "food_type": "Generic",
      "brand_name": null,
      "servings": [
        {
          "serving_id": 5001,
          "serving_description": "1 cup (155g) boneless, skinless",
          "metric_serving_amount": 155,
          "metric_serving_unit": "g",
          "number_of_units": 1,
          "calories": 220,
          "carbohydrate": 0,
          "protein": 38,
          "fat": 5,
          "saturated_fat": 1.5,
          "fiber": 0,
          "sugar": 0,
          "sodium": 75,
          "potassium": 360,
          "cholesterol": 85,
          "vitamin_a": null,
          "vitamin_c": null,
          "calcium": 15,
          "iron": 1.5,
          "trans_fat": 0,
          "added_sugars": null,
          "vitamin_d": null,
          "is_default": true
        },
        {
          "serving_id": 5002,
          "serving_description": "100g",
          "metric_serving_amount": 100,
          "metric_serving_unit": "g",
          "calories": 142,
          "protein": 24.5,
          "fat": 3.2,
          "is_default": false
        }
      ]
    }
  ],
  "error": null
}
```

---

#### `GET /api/fatsecret/food/{food_id}`

Get detailed food information with all serving options.

**Path Parameters:**

- `food_id` (required): Food ID (integer). Can be a FatSecret ID or a synthetic CSV ID (`1000000 + dish_id`).

**Example Request:**

```bash
curl "http://localhost:8000/api/fatsecret/food/1234"
```

**Response:**

```json
{
  "status": "success",
  "food": {
    "food_id": 1234,
    "food_name": "Chicken Breast",
    "food_type": "Generic",
    "brand_name": null,
    "servings": [
      {
        "serving_id": 5001,
        "serving_description": "1 cup (155g) boneless, skinless",
        "metric_serving_amount": 155,
        "metric_serving_unit": "g",
        "number_of_units": 1,
        "calories": 220,
        "carbohydrate": 0,
        "protein": 38,
        "fat": 5,
        "saturated_fat": 1.5,
        "fiber": 0,
        "sugar": 0,
        "sodium": 75,
        "potassium": 360,
        "cholesterol": 85,
        "vitamin_a": null,
        "vitamin_c": null,
        "calcium": 15,
        "iron": 1.5,
        "trans_fat": 0,
        "added_sugars": null,
        "vitamin_d": null,
        "is_default": true
      }
    ]
  },
  "error": null
}
```

---

#### `POST /api/fatsecret/add-preview`

Calculate nutritional totals for a meal (serving × quantity).

**Request Body:**

```json
{
  "food_id": 1234,
  "serving_id": 5001,
  "quantity": 1.5
}
```

**Example Request:**

```bash
curl -X POST "http://localhost:8000/api/fatsecret/add-preview" \
  -H "Content-Type: application/json" \
  -d '{
    "food_id": 1234,
    "serving_id": 5001,
    "quantity": 1.5
  }'
```

**Response:**

```json
{
  "status": "success",
  "food_id": 1234,
  "food_name": "Chicken Breast",
  "serving_description": "1 cup (155g) boneless, skinless",
  "quantity": 1.5,
  "totals": {
    "calories": 330,
    "carbohydrate": 0,
    "protein": 57,
    "fat": 7.5,
    "saturated_fat": 2.25,
    "fiber": 0,
    "sugar": 0,
    "sodium": 112.5,
    "potassium": 540,
    "cholesterol": 127.5,
    "calcium": 22.5,
    "iron": 2.25,
    "trans_fat": 0,
    "vitamin_a": 0,
    "vitamin_c": 0,
    "added_sugars": 0,
    "vitamin_d": 0
  },
  "error": null
}
```

```
pulse_backend/
├── main.py                        # FastAPI app and all endpoints
├── models.py                      # Pydantic models for request/response
├── meal_analysis_service.py       # GPT-4o vision + text meal analysis
├── product_service.py             # OpenFoodFacts barcode lookup
├── fatsecret_service.py           # FatSecret API integration (OAuth2, search, food detail)
├── copilot_tools/                 # Health, nutrition, and workout tools
│   ├── health_data_tools.py
│   ├── nutrition_tools.py
│   └── workout_tools.py
├── ifct2017/                      # IFCT2017 nutrition database (cloned from GitHub)
├── logs/                          # Request/response logs (JSON files)
├── requirements.txt
├── .env.example                   # Environment variables template
├── .env                           # Local environment variables (not committed)
└── .gitignore
```

## Project Files

- **main.py**: FastAPI application with all endpoints
  - `/api/health` – Health check
  - `/api/chat` – Chat endpoint (deprecated)
  - `/api/product/{barcode}` – OpenFoodFacts barcode lookup
  - `/api/meal/analyze` – GPT-4o photo analysis
  - `/api/meal/analyze-text` – GPT-4o text analysis
  - `/api/fatsecret/autocomplete` – Food name suggestions
  - `/api/fatsecret/search` – Food search with pagination
  - `/api/fatsecret/food/{food_id}` – Food details
  - `/api/fatsecret/add-preview` – Calculate meal totals
- **models.py**: Pydantic models for all requests/responses (includes ProductInfo, MealAnalysisResponse, FatSecretFood, etc.)
- **meal_analysis_service.py**: Async meal analysis using OpenAI GPT-4o vision and text models
- **product_service.py**: OpenFoodFacts barcode lookup service
- **fatsecret_service.py**: FatSecret API integration with OAuth2 token management and async HTTP helpers

## Features

- **Health Data Analysis**: Steps, sleep, heart rate, HRV, exercise (from Android app)
- **Meal Analysis**: Photo-based via GPT-4o vision, or text description via GPT-4o
- **Product Lookup**: Barcode scanning via OpenFoodFacts API
- **Meal Search**: FatSecret API integration for food database search and nutrition lookup
  - Autocomplete suggestions
  - Paginated food search
  - Detailed serving options
  - Nutritional calculations
- **Nutrition Database**: IFCT2017 Indian foods database (542 foods)
  - Automatically loaded from `ifct2017/` directory
  - Provides detailed nutritional information for Indian foods
- **Workout Catalog**: 800+ exercises via wger API (no setup needed)
- **Conversation Context**: Maintains chat history across requests
- **Tool Tracking**: Shows which data sources were used
- **Request Logging**: All API requests and responses logged to `logs/` directory (JSON format)
