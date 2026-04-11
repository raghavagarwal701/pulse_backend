"""
Product lookup service using the OpenFoodFacts API.
Fetches product details by barcode and returns parsed nutritional info.
"""
import httpx



class ProductNotFoundError(Exception):
    """Raised when a product is not found in OpenFoodFacts."""
    pass


OPENFOODFACTS_BASE = "https://world.openfoodfacts.net/api/v2/product"


async def lookup_product(barcode: str) -> dict:
    """
    Look up a product by barcode from OpenFoodFacts.

    Args:
        barcode: The product barcode string (e.g. EAN-13).

    Returns:
        A dict with parsed product information.

    Raises:
        ProductNotFoundError: If the product is not found.
    """
    url = f"{OPENFOODFACTS_BASE}/{barcode}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                url,
                headers={"User-Agent": "PulseBackend/1.0 (health-copilot)"}
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise Exception("OpenFoodFacts API request timed out after 15 seconds")
        except httpx.RequestError as e:
            raise Exception(f"Network error connecting to OpenFoodFacts: {type(e).__name__}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ProductNotFoundError(f"Product with barcode {barcode} not found")
            raise Exception(f"OpenFoodFacts API returned HTTP error {e.response.status_code}")

    if data.get("status") != 1:
        raise ProductNotFoundError(f"Product with barcode {barcode} not found")

    product = data.get("product", {})
    nutriments = product.get("nutriments", {})

    # Package quantity info
    product_quantity = product.get("product_quantity")       # e.g. 21.8 (numeric)
    product_quantity_unit = product.get("product_quantity_unit", "g")  # e.g. "g"
    serving_size = product.get("serving_size")               # e.g. "21.6 g"
    serving_quantity = product.get("serving_quantity")       # e.g. 21.6 (numeric grams)

    def scale(val_100g, qty):
        """Scale a per-100g value to the given quantity (in grams)."""
        if val_100g is None or qty is None:
            return None
        try:
            return round(float(val_100g) * float(qty) / 100, 2)
        except (TypeError, ValueError):
            return None

    # Per-100g values
    energy_100g = nutriments.get("energy-kcal_100g")
    fat_100g = nutriments.get("fat_100g")
    carbs_100g = nutriments.get("carbohydrates_100g")
    sugars_100g = nutriments.get("sugars_100g")
    proteins_100g = nutriments.get("proteins_100g")
    fiber_100g = nutriments.get("fiber_100g")
    salt_100g = nutriments.get("salt_100g")

    return {
        "barcode": barcode,
        "product_name": product.get("product_name"),
        "brands": product.get("brands"),
        "categories": product.get("categories"),
        "nutriscore_grade": product.get("nutriscore_grade"),
        "image_url": product.get("image_url"),
        "ingredients_text": product.get("ingredients_text"),
        "product_quantity": product_quantity,
        "product_quantity_unit": product_quantity_unit,
        "serving_size": serving_size,
        "serving_quantity": serving_quantity,
        "nutriments": {
            "energy_kcal_100g": energy_100g,
            "fat_100g": fat_100g,
            "carbohydrates_100g": carbs_100g,
            "sugars_100g": sugars_100g,
            "proteins_100g": proteins_100g,
            "fiber_100g": fiber_100g,
            "salt_100g": salt_100g,
            # Per-package values
            "energy_kcal_pkg": scale(energy_100g, product_quantity),
            "fat_pkg": scale(fat_100g, product_quantity),
            "carbohydrates_pkg": scale(carbs_100g, product_quantity),
            "sugars_pkg": scale(sugars_100g, product_quantity),
            "proteins_pkg": scale(proteins_100g, product_quantity),
            "fiber_pkg": scale(fiber_100g, product_quantity),
            "salt_pkg": scale(salt_100g, product_quantity),
        },
    }
