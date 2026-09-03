from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from .config import get_settings
from .security.request_guard import request_guard
from .routers import access, ai, audit, auth, blockchain, cases, documents, evidence, health, integrations, reports, search, verification

settings = get_settings()
app = FastAPI(title="NyayaGraph API", version="0.1.0", openapi_url="/openapi.json", docs_url="/docs")
allowed_origins = [settings.frontend_url]
if settings.dev_mode:
    allowed_origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
app.add_middleware(CORSMiddleware, allow_origins=list(dict.fromkeys(allowed_origins)), allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
app.middleware("http")(request_guard.middleware)


@app.get("/health", tags=["operations"], include_in_schema=False)
def root_health():
    """Container/orchestrator health alias; the versioned endpoint remains public API."""
    return health.health()


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path == "/docs":
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src https://cdn.jsdelivr.net 'unsafe-inline'; style-src https://cdn.jsdelivr.net 'unsafe-inline'; img-src data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
    elif request.url.path.endswith("/verification-report"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'"
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(access.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(blockchain.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
