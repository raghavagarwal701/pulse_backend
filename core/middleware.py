import json
import logging
import os
import time
from fastapi import Request

async def log_requests(request: Request, call_next):
    # Skip logging for health check endpoint
    if request.url.path == "/api/health":
        return await call_next(request)

    # Read request body
    request_body_bytes = await request.body()

    # Determine content type to skip binary/multipart bodies
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
        # Binary body — don't attempt JSON/text decode, just log a placeholder
        request_body = f"<binary upload: {len(request_body_bytes)} bytes>"
    else:
        try:
            request_body = json.loads(request_body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            try:
                request_body = request_body_bytes.decode(
                    "utf-8", errors="replace")
            except Exception:
                request_body = f"<unreadable body: {len(request_body_bytes)} bytes>"

    # Create a new request with the body so it can be read again
    async def receive():
        return {"type": "http.request", "body": request_body_bytes}
    request._receive = receive

    response = await call_next(request)

    # Read response body
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    try:
        response_json = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        try:
            response_json = response_body.decode("utf-8", errors="replace")
        except Exception:
            response_json = f"<unreadable response: {len(response_body)} bytes>"

    # Re-create the response iterator
    async def new_response_iterator():
        yield response_body

    response.body_iterator = new_response_iterator()

    # Log to file
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    log_entry = {
        "timestamp": timestamp,
        "method": request.method,
        "url": str(request.url),
        "request": request_body,
        "response": response_json,
        "status_code": response.status_code
    }

    # Attach image path if the handler saved one (e.g. /api/meal/analyze)
    image_log_path = getattr(request.state, "image_log_path", None)
    if image_log_path:
        log_entry["image_path"] = image_log_path

    # Attach LLM reasoning if the handler stored one (meal analysis endpoints)
    meal_reasoning = getattr(request.state, "meal_reasoning", None)
    if meal_reasoning:
        log_entry["llm_reasoning"] = meal_reasoning

    meal_question = getattr(request.state, "meal_question", None)
    if meal_question:
        log_entry["meal_question"] = meal_question

    meal_question_answer = getattr(request.state, "meal_question_answer", None)
    if meal_question_answer:
        log_entry["meal_question_answer"] = meal_question_answer

    # Attach LLM context from chat endpoint
    llm_context = getattr(request.state, "llm_context", None)
    if llm_context:
        log_entry["llm_context"] = llm_context

    llm_query_type = getattr(request.state, "llm_query_type", None)
    if llm_query_type:
        log_entry["llm_query_type"] = llm_query_type

    llm_messages = getattr(request.state, "llm_messages", None)
    if llm_messages:
        log_entry["llm_messages"] = llm_messages

    llm_structured_output = getattr(request.state, "llm_structured_output", None)
    if llm_structured_output:
        log_entry["llm_structured_output"] = llm_structured_output

    try:
        os.makedirs("logs", exist_ok=True)
        filename = f"logs/{timestamp}_{int(time.time() * 1000)}.json"
        with open(filename, "w") as f:
            json.dump(log_entry, f, indent=2)
    except Exception:
        # Request logging should never fail the actual API request.
        logging.exception("Failed to write request log")

    return response
