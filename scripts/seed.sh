#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../backend"
PYTHON=${MOITT_PYTHON:-python3}
"$PYTHON" -m app.db.seed
