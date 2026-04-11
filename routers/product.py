from fastapi import APIRouter, HTTPException
from schemas.product import ProductResponse, ProductInfo, ProductNutriments
from product_service import lookup_product, ProductNotFoundError

router = APIRouter(prefix="/api/product", tags=["Product"])

@router.get("/{barcode}", response_model=ProductResponse)
async def get_product(barcode: str):
    """
    Look up product info by barcode via OpenFoodFacts API.
    """
    try:
        product_data = await lookup_product(barcode)

        nutriments = ProductNutriments(**product_data.get("nutriments", {}))
        product_info = ProductInfo(
            barcode=product_data["barcode"],
            product_name=product_data.get("product_name"),
            brands=product_data.get("brands"),
            categories=product_data.get("categories"),
            nutriscore_grade=product_data.get("nutriscore_grade"),
            nutriments=nutriments,
            image_url=product_data.get("image_url"),
            ingredients_text=product_data.get("ingredients_text"),
        )

        return ProductResponse(status="found", product=product_info)

    except ProductNotFoundError:
        return ProductResponse(
            status="not_found",
            error=f"Product with barcode {barcode} not found in OpenFoodFacts"
        )
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Error looking up product: {error_msg}"
        )
