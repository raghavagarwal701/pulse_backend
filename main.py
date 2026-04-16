"""
Pulse Backend - FastAPI server for Health Copilot
Provides API endpoints via modular routers.
"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from core.middleware import log_requests
from routers import health, chat, product, meal, fatsecret

# Initialize FastAPI app
app = FastAPI(
    title="Pulse Backend",
    description="Health Copilot API for mobile app",
    version="1.0.0"
)

# Add Middleware
app.middleware("http")(log_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your mobile app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(product.router)
app.include_router(meal.router)
app.include_router(fatsecret.router)

@app.get("/api/docs", include_in_schema=False)
async def docs_redirect():
    """Redirect to the API documentation."""
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
