import os
from fastapi import Request, HTTPException, Header
from hmac import compare_digest

# Shared internal API key for service-to-service authentication
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-this-in-production")

async def require_internal_auth(x_internal_key: str = Header(..., alias="X-Internal-Key")):
    """
    Middleware dependency to protect internal service endpoints.
    """
    if not compare_digest(x_internal_key, INTERNAL_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing internal service authentication key"
        )
    return True
