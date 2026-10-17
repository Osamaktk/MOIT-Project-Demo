$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
& .\.venv\Scripts\python.exe -m app.db.seed
