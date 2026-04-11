"""
LLM Service handles building messages and calling OpenAI.
Backend decisions and constraints act as hard guidelines.
"""
import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
import logging

from prompts import (
    CHAT_SYSTEM_PROMPT_V2,
    NUTRITION_INSTRUCTIONS,
    FITNESS_INSTRUCTIONS,
    RECOVERY_INSTRUCTIONS,
    GENERAL_INSTRUCTIONS
)
from models import ConversationMessage, StructuredLLMResponse

async def generate_response(
    query: str,
    query_type: str,
    context: Dict[str, Any],
    conversation_history: Optional[List[ConversationMessage]],
    openai_client: AsyncOpenAI,
    model_name: str
) -> tuple[str, List[Dict[str, str]], Dict[str, Any]]:
    # Build System Prompt
    system_content = CHAT_SYSTEM_PROMPT_V2
    
    if query_type == "nutrition":
        system_content += f"\n\n{NUTRITION_INSTRUCTIONS}"
    elif query_type == "fitness":
        system_content += f"\n\n{FITNESS_INSTRUCTIONS}"
    elif query_type == "recovery":
        system_content += f"\n\n{RECOVERY_INSTRUCTIONS}"
    else:
        system_content += f"\n\n{GENERAL_INSTRUCTIONS}"
        
    messages = [
        {"role": "system", "content": system_content}
    ]
    
    # Add history
    if conversation_history:
        for msg in conversation_history:
            messages.append({"role": msg.role, "content": msg.content})
            
    # Add Current query
    user_content = (
        f"Context (JSON - ONLY USE THIS):\n{json.dumps(context, indent=2)}\n\n"
        f"User question: {query}"
    )
    
    messages.append({"role": "user", "content": user_content})
    
    response = await openai_client.beta.chat.completions.parse(
        model=model_name,
        temperature=0.2, # Strict compliance with constraints
        # max_tokens=300,  # Structured responses don't always need max_tokens to be strictly restricted at 300 since it includes reasoning, but we can safely omit it or increase it. Let's omit to give room for reasoning.
        messages=messages,
        response_format=StructuredLLMResponse,
    )
    
    parsed = response.choices[0].message.parsed
    if not parsed or not parsed.response.strip():
        raise ValueError("OpenAI returned an empty response")
        
    return parsed.response.strip(), messages, parsed.model_dump()
