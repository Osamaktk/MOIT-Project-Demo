#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../backend"
.venv/bin/alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
