from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["Health"])

@router.get("")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pulse_backend",
        "version": "1.0.0"
    }
