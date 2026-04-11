from fastapi import APIRouter, Request, HTTPException
from schemas.chat import ChatResponse, ChatRequest
from services.chat_service import process_chat_request
from core.config import openai_client, chat_model_name

router = APIRouter(prefix="/api/chat", tags=["Chat"])

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, fastapi_request: Request):
    """
    Chat endpoint for the mobile app.
    """
    try:
        # Process chat via the pipeline defined in the service
        answer, messages, structured_output, context, query_type = await process_chat_request(
            request, openai_client, chat_model_name
        )
        
        # Store in state for logging middleware
        fastapi_request.state.llm_context = context
        fastapi_request.state.llm_query_type = query_type
        fastapi_request.state.llm_messages = messages
        fastapi_request.state.llm_structured_output = structured_output
        
        return ChatResponse(response=answer, tool_calls=[])

    except HTTPException:
        raise
    except Exception as exc:
        error_msg = str(exc) if str(exc) else type(exc).__name__
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating chat response: {error_msg}")
