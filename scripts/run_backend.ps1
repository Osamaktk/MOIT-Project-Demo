$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
$python = if ($env:MOITT_PYTHON) { $env:MOITT_PYTHON } else { 'python' }
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Alembic migration failed.' }
& $python -m app.db.seed
if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed.' }
& $python -m uvicorn app.main:app --reload --host 127.0.0.1
