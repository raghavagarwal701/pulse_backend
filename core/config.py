import os
import logging
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fatsecret_service import FatSecretClient

# Load environment variables
load_dotenv()

# OpenAI Configuration
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
text_model_name = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
chat_model_name = os.getenv("OPENAI_CHAT_MODEL", text_model_name)

if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is required")

openai_client = AsyncOpenAI(api_key=api_key)

# FatSecret Configuration
fatsecret_client_id = os.getenv("FATSECRET_CLIENT_ID")
fatsecret_client_secret = os.getenv("FATSECRET_CLIENT_SECRET")

if fatsecret_client_id and fatsecret_client_secret:
    fatsecret_client = FatSecretClient(
        client_id=fatsecret_client_id,
        client_secret=fatsecret_client_secret,
        scope=os.getenv("FATSECRET_SCOPE", "premier"),
        region=os.getenv("FATSECRET_REGION", "IN"),
        language=os.getenv("FATSECRET_LANGUAGE", "en")
    )
else:
    # Allow app to start even if FatSecret creds are missing (graceful degradation)
    fatsecret_client = None
    logging.warning("FatSecret credentials not found; meal search endpoints will be unavailable")
