$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
& .\.venv\Scripts\alembic.exe upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
