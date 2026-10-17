from importlib.util import find_spec

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok", "environment": settings.app_env, "ai_zone": settings.ai_zone_mode}


@router.get("/health/ai")
def ai_health() -> dict[str, object]:
    extraction_zone = (settings.ai_provider_extraction or settings.ai_zone_mode).strip().lower()
    extraction_model = settings.model_extraction or settings.model_extraction_fallback or settings.model_fallback
    provider_ready = bool(extraction_model) and (
        bool(settings.openrouter_api_key.get_secret_value()) if extraction_zone == "cloud" else bool(settings.local_llm_base_url)
    )
    stt_installed = find_spec("faster_whisper") is not None
    chroma_installed = find_spec("chromadb") is not None
    chroma_ready = chroma_installed and (settings.resolved_data_dir / "chroma").exists()
    embedding_model = settings.embedding_model.strip()
    embedding_provider_ready = (
        bool(settings.model_embedding.strip())
        if settings.embedding_provider == "openrouter"
        else not embedding_model or find_spec("sentence_transformers") is not None
    )
    return {
        "status": "ready" if provider_ready else "not_configured",
        "zone": extraction_zone,
        "provider_configured": provider_ready,
        "extraction_model_configured": bool(extraction_model),
        "stt_ready": stt_installed,
        "stt_model": settings.stt_model_size,
        "vector_store_ready": chroma_ready,
        "vector_store_installed": chroma_installed,
        "embedding_provider": settings.embedding_provider,
        "embedding_model_configured": bool(settings.model_embedding.strip() or embedding_model),
        "embedding_provider_ready": embedding_provider_ready,
        "demo_mode_cache_enabled": settings.demo_mode_cache,
    }
