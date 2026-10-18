$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\backend')
$python = if ($env:MOITT_PYTHON) { $env:MOITT_PYTHON } else { 'python' }
& $python -m app.db.seed
