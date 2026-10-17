"""Benchmark Register filtering, ORM loading, and response serialization.

This measures the API handler with an isolated in-memory SQLite database. It
does not include HTTP transport or browser rendering.
Run from ``backend`` with ``python scripts/benchmark_register_1000.py``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.register import list_register
from app.db import models as _models  # noqa: F401 - registers all ORM tables
from app.db.base import Base
from app.db.models import RegisterEntry, User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=9)
    args = parser.parse_args()
    if not 1 <= args.rows <= 1000:
        parser.error("--rows must be between 1 and the API limit of 1000")
    if args.repetitions < 3:
        parser.error("--repetitions must be at least 3")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        officer = User(
            id=str(uuid4()),
            name="Synthetic benchmark officer",
            email="benchmark@example.invalid",
            password_hash="not-used",
            role="minister",
            designation="Benchmark",
            active=True,
        )
        db.add(officer)
        db.flush()
        now = datetime.now(timezone.utc)
        db.add_all(
            RegisterEntry(
                id=str(uuid4()),
                serial_no=index + 1,
                fy="2026-27",
                occurred_at=now - timedelta(minutes=index),
                occasion_type="meeting",
                description=f"Synthetic benchmark Register entry {index + 1:04}",
                officer_id=officer.id,
                deadline=date.today() + timedelta(days=3),
                priority="B",
                source_record=f"BENCH-{index + 1:04}",
                status="open",
                origin="manual",
                review_state="approved",
                created_at=now,
                updated_at=now,
            )
            for index in range(args.rows)
        )
        db.commit()

        samples_ms: list[float] = []
        response_bytes = 0
        result = None
        for _ in range(args.repetitions):
            started = perf_counter()
            result = list_register(
                q=None,
                status=None,
                priority=None,
                officer_id=None,
                transaction_id=None,
                origin=None,
                overdue=None,
                review_state="approved",
                occurred_from=None,
                occurred_to=None,
                limit=args.rows,
                offset=0,
                db=db,
                user=officer,
            )
            response_bytes = len(result.model_dump_json().encode("utf-8"))
            samples_ms.append((perf_counter() - started) * 1000)

    samples_ms.sort()
    p95_index = min(len(samples_ms) - 1, int(len(samples_ms) * 0.95))
    assert result is not None
    print(
        f"rows={len(result.items)} total={result.total} "
        f"p50_ms={median(samples_ms):.2f} p95_ms={samples_ms[p95_index]:.2f} "
        f"max_ms={samples_ms[-1]:.2f} json_kb={response_bytes / 1024:.1f}"
    )


if __name__ == "__main__":
    main()
