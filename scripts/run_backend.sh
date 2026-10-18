#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../backend"
PYTHON=${MOITT_PYTHON:-python3}
"$PYTHON" -m alembic upgrade head
"$PYTHON" -m app.db.seed
"$PYTHON" -m uvicorn app.main:app --reload --host 127.0.0.1
