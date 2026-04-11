from typing import Tuple, Dict, Any, List
import feature_engineering
import rule_engine
import query_classifier
import context_builder
import llm_service
from services.spell_checker_service import pulse_spell_checker
from schemas.chat import ChatRequest
from openai import AsyncOpenAI

async def process_chat_request(
    request: ChatRequest,
    openai_client: AsyncOpenAI,
    chat_model_name: str
) -> Tuple[str, List[Dict[str, str]], Dict[str, Any], Dict[str, Any], str]:
    """
    Process the chat request through the pipeline:
    1. Feature engineering
    2. Rule engine
    3. Query classifier
    4. Context builder
    5. LLM generation
    
    Returns:
    (answer, messages, structured_output, context, query_type)
    """
    # 0. Check and correct spelling in the user query
    corrected_query = pulse_spell_checker.correct_query(request.query)

    # 1. Compute 5 signals (pure math, <1ms)
    signals = feature_engineering.compute_signals(request.chat_context)
    
    # 2. Produce structured constraints + decision hints
    constraints, hints = rule_engine.evaluate(signals)
    
    # 3. Classify query deterministically
    query_type = query_classifier.classify(corrected_query)
    
    # 4. Build <=5 field context + constraints + hints
    context = context_builder.build(signals, query_type, constraints, hints)
    
    # 5. LLM explains the backend's decisions
    answer, messages, structured_output = await llm_service.generate_response(
        query=corrected_query,
        query_type=query_type,
        context=context,
        conversation_history=request.conversation_history,
        openai_client=openai_client,
        model_name=chat_model_name
    )
    
    return answer, messages, structured_output, context, query_type
