"""
Meal Analysis Service
Accepts raw image bytes, normalises them to JPEG using Pillow,
then sends them to OpenAI vision and returns a meal-only nutritional breakdown.
"""
import base64
import io
import json
from copy import deepcopy
from openai import AsyncOpenAI
from PIL import Image
from models import LLMMealResponse
from prompts import MEAL_IMAGE_SYSTEM_PROMPT, MEAL_TEXT_SYSTEM_PROMPT
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIC not supported – Android side should always re-encode to JPEG anyway


WEB_SEARCH_TOOLS = [{"type": "web_search"}]


def _strictify_json_schema(node):
    """Recursively enforce OpenAI Structured Outputs object constraints."""
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "object":
            properties = node.get("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(properties.keys())

        for value in node.values():
            _strictify_json_schema(value)
    elif isinstance(node, list):
        for item in node:
            _strictify_json_schema(item)


def _meal_json_schema() -> dict:
    """Build a strict JSON schema for response.text.format."""
    schema = deepcopy(LLMMealResponse.model_json_schema())
    _strictify_json_schema(schema)

    return {
        "type": "json_schema",
        "name": "meal_analysis",
        "strict": True,
        "schema": schema,
    }


def _parse_meal_response_output(output_text: str) -> LLMMealResponse:
    """Validate model JSON against the Pydantic schema."""
    if not output_text or not output_text.strip():
        raise ValueError("Model returned an empty response")

    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc

    return LLMMealResponse.model_validate(payload)

# ── Image normalisation ────────────────────────────────────────────────────────


def _to_jpeg_bytes(image_bytes: bytes) -> bytes:
    """
    Convert any image format (JPEG, PNG, WEBP, HEIC, raw camera buffers, etc.)
    to a clean JPEG using Pillow so OpenAI always receives a supported format.

    Returns JPEG bytes ready for base64 encoding.
    """
    if not image_bytes:
        raise ValueError("Received empty image bytes (0 bytes)")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Convert RGBA / P mode to RGB so JPEG encoder doesn't complain
        if img.mode in ("RGBA", "P", "LA", "CMYK"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception as exc:
        # Include magic bytes to help diagnose format issues
        magic = image_bytes[:16].hex() if len(
            image_bytes) >= 2 else "(too short)"
        raise ValueError(
            f"Could not decode image ({len(image_bytes)} bytes, magic={magic}): {exc}"
        ) from exc


# ── Main function ──────────────────────────────────────────────────────────────

async def analyze_meal_image(
    image_bytes: bytes,
    content_type: str,
    openai_client: AsyncOpenAI,
    model: str = "gpt-5.4-2026-03-05",
    user_note: str | None = None,
) -> dict:
    """
    Analyse a meal photograph using GPT-5.4-2026-03-05 vision.

    Args:
        image_bytes:   Raw bytes of the uploaded image (any format Pillow can read).
        content_type:  Original MIME type (informational; we always send JPEG).
        openai_client: Shared AsyncOpenAI client.
        model:         OpenAI model to use (must support vision).
        user_note:     Optional text note from the user (e.g. "I only ate half").
                       Factored into serving-size / _pkg nutriment estimates.

    Returns:
        A dict compatible with the meal response models.
    """
    # Normalise to clean JPEG regardless of what Android sent
    jpeg_bytes = _to_jpeg_bytes(image_bytes)
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"

    response = await openai_client.responses.create(
        model=model,
        max_output_tokens=2000,
        text={"format": _meal_json_schema()},
        tools=WEB_SEARCH_TOOLS,
        tool_choice="required",
        input=[
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": MEAL_IMAGE_SYSTEM_PROMPT}
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": data_uri,
                        "detail": "auto",
                    },
                    {
                        "type": "input_text",
                        "text": (
                            "Analyse this meal photo and return the JSON nutritional estimate. "
                            "for each meal use the web search tool and find the average serving size and the nutrient content of the meal."
                            + (
                                f" The user added this note: '{user_note}'."
                                if user_note and user_note.strip()
                                else ""
                            )
                        ),
                    },
                ],
            },
        ],
    )

    data = _parse_meal_response_output(response.output_text)

    return {
        "reasoning": data.reasoning,
        "web_source_links": data.web_source_links,
        "name_of_meal": data.name_of_meal,
        "serving_size": data.serving_size,
        "nutritional_value": data.nutritional_value.model_dump(),
    }


# ── Text-only analysis ────────────────────────────────────────────────────────

async def analyze_meal_text(
    description: str,
    openai_client: AsyncOpenAI,
    model: str = "gpt-5.4-2026-03-05",
) -> dict:
    """
    Estimate nutritional info from a plain-text description of a meal (no image).

    Args:
        description:   User's text description, e.g. "2 chapatis with dal and a glass of milk".
        openai_client: Shared AsyncOpenAI client.
        model:         OpenAI model to use.

    Returns:
        A dict compatible with the meal response models.
    """
    if not description or not description.strip():
        raise ValueError("Meal description must not be empty")

    response = await openai_client.responses.create(
        model=model,
        max_output_tokens=2000,
        text={"format": _meal_json_schema()},
        tools=WEB_SEARCH_TOOLS,
        tool_choice="required",
        input=[
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": MEAL_TEXT_SYSTEM_PROMPT}
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Estimate the nutritional breakdown for: {description.strip()}. "
                            "for each meal use the web search tool and find the average serving size and the nutrient content of the meal"
                        ),
                    }
                ],
            },
        ],
    )

    data = _parse_meal_response_output(response.output_text)

    return {
        "reasoning": data.reasoning,
        "web_source_links": data.web_source_links,
        "name_of_meal": data.name_of_meal,
        "serving_size": data.serving_size,
        "nutritional_value": data.nutritional_value.model_dump(),
    }


async def answer_meal_question(
    question: str,
    meal_data: dict,
    openai_client: AsyncOpenAI,
    model: str = "gpt-5.4-2026-03-05",
) -> str:
    """
    Answer a user follow-up question about an already analysed meal.

    Args:
        question: User question such as "Is this healthy?"
        meal_data: Structured meal analysis output produced by analyze_meal_image.
        openai_client: Shared AsyncOpenAI client.
        model: OpenAI model to use.

    Returns:
        A short, practical answer grounded in the analysed meal data.
    """
    clean_question = (question or "").strip()
    if not clean_question:
        return ""

    meal_context = {
        "name_of_meal": meal_data.get("name_of_meal"),
        "serving_size": meal_data.get("serving_size"),
        "nutritional_value": meal_data.get("nutritional_value"),
        "web_source_links": meal_data.get("web_source_links"),
    }

    response = await openai_client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=250,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a nutrition coach. Answer the user's question using only the provided meal "
                    "analysis context. Be concise, practical, and transparent about uncertainty. "
                    "Keep the answer to 2-4 short sentences."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Meal analysis context (JSON): {json.dumps(meal_context, ensure_ascii=True)}\n\n"
                    f"User question: {clean_question}"
                ),
            },
        ],
    )

    answer = response.choices[0].message.content if response.choices else None
    return (answer or "").strip()
