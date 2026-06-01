# Local setup + one ingestion run (Windows PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
}

Write-Host "Installing dependencies..."
& $Python -m pip install -q -r requirements.txt

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Created .env from .env.example — set OPENAI_API_KEY and DATABASE_URL, then run again."
    exit 1
}

Write-Host "Checking database connection (5s timeout)..."
$checkDb = @"
import sys
from app.config.settings import get_settings
url = get_settings().database_url.replace('+asyncpg', '').replace('+psycopg', '')
try:
    import psycopg
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute('SELECT 1')
    print('DB_OK')
except Exception as e:
    print(f'DB_FAIL:{e}')
    sys.exit(1)
"@
$dbResult = & $Python -c $checkDb 2>&1 | Out-String
if ($dbResult -notmatch "DB_OK") {
    Write-Host ""
    $dbHint = (& $Python -c "from app.config.settings import get_settings; print(get_settings().database_url)" 2>$null)
    Write-Host "Database is not reachable. DATABASE_URL in .env:"
    Write-Host "  $dbHint"
    Write-Host ""
    Write-Host "Pick ONE option:"
    Write-Host "  A) Install Docker Desktop, then:  docker compose up db -d"
    Write-Host "  B) Free cloud DB (recommended for local + GitHub cron):"
    Write-Host "     1. https://neon.tech -> create project -> copy connection string"
    Write-Host "     2. Set DATABASE_URL and SYNC_DATABASE_URL in .env (must include ?ssl=require)"
    Write-Host "     3. Re-run:  .\scripts\run_local.ps1"
    Write-Host ""
    if ($dbResult -match "DB_FAIL:(.+)") { Write-Host "Error: $($Matches[1])" }
    exit 1
}

Write-Host "Running migrations..."
$env:SYNC_DATABASE_URL = & $Python scripts/alembic_database_url.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed. Fix DATABASE_URL / SYNC_DATABASE_URL in .env and retry."
    exit $LASTEXITCODE
}

Write-Host "Running daily ingestion (OpenAI calls — may take several minutes)..."
& $Python -m app.scheduler.runner

$reports = Join-Path $Root "reports"
if (Test-Path $reports) {
    Write-Host ""
    Write-Host "Excel reports:"
    Get-ChildItem $reports -Filter "*.xlsx" | ForEach-Object { Write-Host "  $($_.FullName)" }
}
Write-Host ""
Write-Host "API (optional):  .\.venv\Scripts\uvicorn app.main:app --reload --port 8000"
Write-Host "  Browse leads: http://localhost:8000/docs"
