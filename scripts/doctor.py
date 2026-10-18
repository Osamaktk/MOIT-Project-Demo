"""Read-only first-run checks for the MoITT Command Center repository."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
sys.path.insert(0, str(BACKEND))


def report(label: str, passed: bool, detail: str) -> bool:
    state = "PASS" if passed else "FAIL"
    print(f"[{state}] {label}: {detail}")
    return passed


def command_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0]


def npm_command() -> list[str] | None:
    if os.name == "nt":
        candidate = shutil.which("npm.cmd") or shutil.which("npm")
        return ["cmd.exe", "/c", candidate] if candidate else None
    candidate = shutil.which("npm")
    return [candidate] if candidate else None


def main() -> int:
    results: list[bool] = []
    tts = "browser"
    python_ok = sys.version_info >= (3, 11)
    results.append(report("Python", python_ok, f"{sys.version.split()[0]} (requires 3.11+)"))

    node_version = command_version(["node", "--version"])
    npm = npm_command()
    npm_version = command_version([*npm, "--version"]) if npm else None
    node_match = re.search(r"(\d+)\.(\d+)\.(\d+)", node_version or "")
    node_tuple = tuple(map(int, node_match.groups())) if node_match else (0, 0, 0)
    node_ok = (node_tuple[0] == 20 and node_tuple >= (20, 19, 0)) or (node_tuple[0] >= 22 and node_tuple >= (22, 12, 0))
    results.append(report("Node.js", node_ok, f"{node_version or 'not found'} (requires 20.19+ or 22.12+)"))
    npm_ok = npm_version is not None
    results.append(report("npm", npm_ok, npm_version or "not found"))

    env_path = BACKEND / ".env"
    env_exists = env_path.is_file()
    results.append(report("Backend configuration", env_exists, "backend/.env found" if env_exists else "backend/.env is missing; copy .env.example and configure it"))

    try:
        from app.core.config import Settings

        settings = Settings()
        key_configured = bool(settings.openrouter_api_key.get_secret_value().strip())
        results.append(report("OpenRouter key", key_configured, "configured" if key_configured else "not configured (key value is never displayed)"))
        models = [model for model in (settings.model_chat, settings.model_extraction) if model]
        model_ok = bool(models)
        if model_ok:
            verifier = BACKEND / "scripts" / "verify_openrouter_models.py"
            try:
                checked = subprocess.run([sys.executable, str(verifier)], cwd=BACKEND, capture_output=True, text=True, timeout=60)
                model_ok = checked.returncode == 0
            except (OSError, subprocess.SubprocessError):
                model_ok = False
        results.append(report("Model chain", model_ok, "configured identifiers verified against provider catalogue" if model_ok else "not configured or could not be verified; see backend/scripts/verify_openrouter_models.py"))
        stt_provider = settings.stt_provider
    except Exception:
        settings = None
        stt_provider = ""
        results.append(report("OpenRouter key", False, "configuration could not be loaded; key value is never displayed"))
        results.append(report("Model chain", False, "configuration could not be loaded"))
        results.append(report("Database migration", False, "configuration could not be loaded"))
        results.append(report("Demo seed", False, "configuration could not be loaded"))

    if settings is not None:
        from sqlalchemy import create_engine, inspect, text

        try:
            from sqlalchemy.engine import make_url

            database_url = settings.database_url
            parsed_url = make_url(database_url)
            sqlite_path = Path(parsed_url.database) if parsed_url.get_backend_name() == "sqlite" and parsed_url.database != ":memory:" else None
            if sqlite_path is not None and not sqlite_path.is_absolute():
                sqlite_path = ROOT / sqlite_path
            if sqlite_path is not None and not sqlite_path.is_file():
                raise FileNotFoundError
            engine = create_engine(database_url)
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            migration_ok = "alembic_version" in tables
            if migration_ok:
                with engine.connect() as connection:
                    migration_ok = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first() is not None
            results.append(report("Database migration", migration_ok, "migration version found" if migration_ok else "run the Alembic upgrade command"))

            entity_table = "projects" if "projects" in tables else "transactions" if "transactions" in tables else None
            seed_ok = False
            if "users" in tables and entity_table:
                with engine.connect() as connection:
                    users = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
                    entities = connection.execute(text(f"SELECT COUNT(*) FROM {entity_table}")).scalar_one()
                seed_ok = users > 0 and entities > 0
            results.append(report("Demo seed", seed_ok, "users and project records found" if seed_ok else "seed users and project data with `python -m app.db.seed`"))
            engine.dispose()
        except Exception:
            results.append(report("Database migration", False, "database is unavailable or not migrated"))
            results.append(report("Demo seed", False, "database is unavailable or seed records are missing"))

    stt_available = stt_provider == "browser" or (stt_provider == "faster_whisper" and importlib.util.find_spec("faster_whisper") is not None)
    results.append(report("Speech input", stt_available, f"{stt_provider or 'unknown'} {'available' if stt_available else 'not installed/configured'}"))
    results.append(report("Speech output", tts == "browser", "browser speech synthesis selected"))

    lock_file = FRONTEND / "package-lock.json"
    lock_ok = lock_file.is_file() and npm is not None
    if lock_ok:
        try:
            result = subprocess.run([*npm, "install", "--package-lock-only", "--dry-run", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=FRONTEND, capture_output=True, text=True, timeout=90)
            lock_ok = result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            lock_ok = False
    results.append(report("npm lockfile", lock_ok, "package.json and package-lock.json are consistent" if lock_ok else "run `npm install` in frontend/ and commit the regenerated lockfile"))

    passed = sum(results)
    print(f"\nDoctor: {passed}/{len(results)} checks passed.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
