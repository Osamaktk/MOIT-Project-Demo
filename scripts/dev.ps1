$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $PSScriptRoot 'run_backend.ps1'
$frontend = Join-Path $PSScriptRoot 'run_frontend.ps1'
$powershell = (Get-Process -Id $PID).Path
$backendArg = '"' + $backend + '"'
$frontendArg = '"' + $frontend + '"'
Start-Process -FilePath $powershell -WorkingDirectory $repo -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $backendArg)
Start-Process -FilePath $powershell -WorkingDirectory $repo -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $frontendArg)
Write-Output 'Backend logs are in the new backend window; frontend logs are in the new frontend window.'
Write-Output 'Open http://127.0.0.1:5173 after both windows report ready.'
