$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$runtimeDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$pythonExecutable = Join-Path $backendRoot '.venv\Scripts\python.exe'
$nextExecutable = Join-Path $frontendRoot 'node_modules\next\dist\bin\next'
if (!(Test-Path -LiteralPath $pythonExecutable) -or !(Test-Path -LiteralPath $nextExecutable)) {
    throw 'Install backend/frontend dependencies first; see README.md.'
}
if (!(Test-Path -LiteralPath (Join-Path $frontendRoot '.next\BUILD_ID'))) {
    throw 'Run npm run build in frontend first.'
}
$listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue
foreach ($port in @(8000, 3000)) {
    if ($listeners | Where-Object LocalPort -eq $port) {
        throw "Port $port is already in use. No process was stopped."
    }
}
$backendProcess = Start-Process -FilePath $pythonExecutable -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory 'backend.log') -RedirectStandardError (Join-Path $runtimeDirectory 'backend-error.log')
$nodeExecutable = (Get-Command node).Source
$frontendProcess = Start-Process -FilePath $nodeExecutable -ArgumentList @($nextExecutable,'start','--hostname','127.0.0.1','--port','3000') -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory 'frontend.log') -RedirectStandardError (Join-Path $runtimeDirectory 'frontend-error.log')
@{ backend = $backendProcess.Id; frontend = $frontendProcess.Id } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDirectory 'processes.json')
Write-Output 'Started local backend and frontend. Dashboard: http://127.0.0.1:3000'
Write-Output 'Process IDs and logs are in .local/. Both servers listen only on loopback.'
