from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services import records_search


def test_local_embedding_model_normalizes_vectors(monkeypatch: Any) -> None:
    class FakeModel:
        def encode(self, texts: list[str], **kwargs: Any) -> Any:
            assert texts == ["Urdu and English"]
            assert kwargs["normalize_embeddings"] is True

            class Encoded:
                def tolist(self) -> list[list[float]]:
                    return [[0.6, 0.8]]

            return Encoded()

    monkeypatch.setattr(settings, "embedding_model", "fake/multilingual")
    monkeypatch.setattr(records_search, "_sentence_transformer", lambda _: FakeModel())

    assert records_search.embed_local("Urdu and English") == [0.6, 0.8]


def test_offline_embedding_is_deterministic(monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "embedding_model", "")

    first = records_search.embed_local("Meeting notes for Urdu and English")
    second = records_search.embed_local("Meeting notes for Urdu and English")

    assert len(first) == records_search.DIMENSIONS
    assert first == second
