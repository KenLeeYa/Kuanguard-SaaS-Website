[CmdletBinding()]
param([switch]$SkipMigrations)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    & uv sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
& $pythonExecutable scripts/setup_local.py
$env:PORTAL_PROXY_SECRET = & $pythonExecutable -c 'from dotenv import dotenv_values; print(dotenv_values(".env").get("PORTAL_PROXY_SECRET", ""))'
& docker compose up -d --no-recreate db queue
if ($LASTEXITCODE -ne 0) { throw 'Local database/queue start failed' }
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    & docker compose exec -T db pg_isready -U kuanguard_owner -d kuanguard *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'Database is not ready; existing data was preserved' }
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$env:PYTHONUNBUFFERED = '1'
if (-not $SkipMigrations) {
    & $pythonExecutable scripts/migrate.py
    if ($LASTEXITCODE -ne 0) { throw 'Additive migration failed; no services started' }
    & $pythonExecutable scripts/seed_local.py
    if ($LASTEXITCODE -ne 0) { throw 'Development fixture initialization failed' }
}
$runtimeDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
function Start-KuanGuardProcess {
    param([string]$Name, [string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory, [int]$Port = 0)
    $pidFile = Join-Path $runtimeDirectory ($Name + '.managed.json')
    if (Test-Path -LiteralPath $pidFile) {
        $receipt = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
        $existing = Get-Process -Id $receipt.id -ErrorAction SilentlyContinue
        if ($existing -and $existing.StartTime.ToUniversalTime().Ticks -eq ([datetime]$receipt.startedAt).ToUniversalTime().Ticks) {
            Write-Output "$Name already running; preserved"
            return
        }
    }
    if ($Port -and (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
        Write-Output "$Name port $Port is occupied; existing process preserved"
        return
    }
    $started = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeDirectory ($Name + '.managed.stdout.log')) `
        -RedirectStandardError (Join-Path $runtimeDirectory ($Name + '.managed.stderr.log'))
    @{ id = $started.Id; startedAt = $started.StartTime.ToUniversalTime().ToString('o'); executable = $Executable } |
        ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding utf8
    Write-Output "$Name started (PID $($started.Id))"
}
Start-KuanGuardProcess -Name 'api' -Executable $pythonExecutable -Arguments @('-m','uvicorn','kuanguard.api:app','--host','127.0.0.1','--port','8180','--no-access-log','--no-proxy-headers') -WorkingDirectory $projectRoot -Port 8180
Start-KuanGuardProcess -Name 'worker' -Executable $pythonExecutable -Arguments @('-m','kuanguard.worker') -WorkingDirectory $projectRoot
$webDirectory = Join-Path $projectRoot 'apps\web'
if (-not (Test-Path -LiteralPath (Join-Path $webDirectory 'node_modules\next'))) {
    Push-Location -LiteralPath $webDirectory
    try { & npm ci; if ($LASTEXITCODE -ne 0) { throw 'Web dependency installation failed' } }
    finally { Pop-Location }
}
$nodeExecutable = (Get-Command node).Source
Start-KuanGuardProcess -Name 'web' -Executable $nodeExecutable -Arguments @('node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','3180') -WorkingDirectory $webDirectory -Port 3180
Write-Output 'KUANGUARD local URL: http://127.0.0.1:3180 ; formal providers remain gated'
