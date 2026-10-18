"""Check configured OpenRouter model identifiers against its live catalogue."""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


async def main() -> int:
    configured = {
        key: value
        for key, value in {
            "chat": settings.model_chat,
            "reasoning": settings.model_reasoning,
            "extraction": settings.model_extraction,
            "fast": settings.model_fast,
            "embedding": settings.model_embedding,
            "fallback": settings.model_fallback,
            "chat_fallback": settings.model_chat_fallback,
            "reasoning_fallback": settings.model_reasoning_fallback,
            "extraction_fallback": settings.model_extraction_fallback,
            "fast_fallback": settings.model_fast_fallback,
        }.items()
        if value
    }
    if not configured:
        print("No model identifiers are configured; model catalogue check skipped.")
        return 0
    # The public catalogue endpoint does not need credentials. Keep this check
    # independent of user secrets; it only verifies model identifiers.
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{settings.openrouter_base_url.rstrip('/')}/models")
        response.raise_for_status()
        payload = response.json()
    available = {row["id"] for row in payload.get("data", []) if isinstance(row, dict) and row.get("id")}
    missing = {role: model for role, model in configured.items() if model not in available}
    if missing:
        for role, model in missing.items():
            print(f"Missing catalogue model for {role}: {model}")
        return 1
    print(f"Verified {len(configured)} configured identifiers against the current OpenRouter catalogue.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
