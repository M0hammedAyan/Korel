from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import uuid

_SKIP_AUDIT_PATHS = {"/health", "/health/live", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next: Callable):
        req_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if req_id:
            req_id = req_id.split(",")[0].strip()
        else:
            req_id = uuid.uuid4().hex
        request.state.request_id = req_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class AuditAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next: Callable):
        response: Response = await call_next(request)
        path = request.url.path
        if path in _SKIP_AUDIT_PATHS or request.method == "OPTIONS":
            return response
        if response.status_code >= 400:
            try:
                from backend.audit import write_audit
                import hashlib
                raw_key = request.headers.get("X-API-Key", "")
                actor = ("anon" if not raw_key
                         else hashlib.sha256(raw_key.encode()).hexdigest()[:12])
                write_audit(
                    "api.access_denied" if response.status_code in (401, 403) else "api.error",
                    actor,
                    path,
                    {"method": request.method, "status": response.status_code,
                     "request_id": getattr(request.state, "request_id", "")},
                )
            except Exception:
                pass
        return response


class ErrorResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next: Callable):
        try:
            return await call_next(request)
        except Exception as exc:
            req_id = getattr(request.state, "request_id", None) or ""
            body = {
                "status": "error",
                "code": 500,
                "request_id": req_id,
                "message": "internal_server_error",
                "details": str(exc),
            }
            return Response(content=__import__("json").dumps(body), media_type="application/json", status_code=500)
