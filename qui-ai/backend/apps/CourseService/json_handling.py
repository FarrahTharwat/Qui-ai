from fastapi import Request, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
import json
import logging
import re
import asyncio

logger = logging.getLogger(__name__)


def clean_json_string(json_str):
    """Clean JSON string by handling control characters"""
    if not isinstance(json_str, str):
        return json_str

    # Remove control characters except for common whitespace (\t, \n, \r)
    cleaned = ''.join(char for char in json_str if ord(char) >= 32 or char in '\t\n\r')

    try:
        # Handle unescaped newlines within string values
        if cleaned.strip().startswith('{') or cleaned.strip().startswith('['):
            cleaned = re.sub(r'(?<!\\)\n', '\\n', cleaned)
            cleaned = re.sub(r'(?<!\\)\t', '\\t', cleaned)
            cleaned = re.sub(r'(?<!\\)\r', '\\r', cleaned)
    except Exception as e:
        logger.warning(f"Error in additional JSON cleaning: {str(e)}")

    return cleaned


class JSONValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate and clean JSON payloads"""

    async def dispatch(self, request: Request, call_next):
        # Only process POST/PUT requests with JSON content
        if request.method in ["POST", "PUT"] and request.headers.get("content-type", "").startswith("application/json"):
            try:
                # Read the request body
                body = await request.body()

                if body:
                    body_str = body.decode('utf-8')

                    # Try to parse the JSON
                    try:
                        json.loads(body_str)
                        # If parsing succeeds, continue normally
                    except json.JSONDecodeError:
                        # If parsing fails, try to clean and fix the JSON
                        logger.info("JSON parsing failed, attempting to clean...")
                        cleaned_body = clean_json_string(body_str)

                        try:
                            # Validate the cleaned JSON
                            json.loads(cleaned_body)

                            # Replace the request body with cleaned version
                            async def receive():
                                return {
                                    "type": "http.request",
                                    "body": cleaned_body.encode('utf-8'),
                                    "more_body": False
                                }

                            request._receive = receive

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON validation failed even after cleaning: {str(e)}")
                            raise HTTPException(
                                status_code=400,
                                detail=f"Invalid JSON payload: {str(e)}"
                            )

            except Exception as e:
                logger.error(f"Error in JSON validation middleware: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid request payload")

        response = await call_next(request)
        return response