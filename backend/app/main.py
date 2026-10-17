from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.assurance import router as assurance_router
from app.api.v1.admin import router as admin_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.engagements import router as engagements_router
from app.api.v1.health import router as health_router
from app.api.v1.jarvis import router as jarvis_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.register import router as register_router
from app.api.v1.records import router as records_router
from app.api.v1.transactions import router as transactions_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.middleware import RequestSecurityMiddleware

app = FastAPI(title="PC Command Center API", version="0.1.0", description="Synthetic-data office command center demo")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Request-ID"])
app.add_middleware(RequestSecurityMiddleware)
app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(register_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(decisions_router, prefix="/api/v1")
app.include_router(engagements_router, prefix="/api/v1")
app.include_router(assurance_router, prefix="/api/v1")
app.include_router(meetings_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(records_router)
app.include_router(jarvis_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
register_error_handlers(app)
