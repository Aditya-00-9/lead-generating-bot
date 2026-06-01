# Push .env values to GitHub Actions secrets (requires: gh auth login)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "Install GitHub CLI: https://cli.github.com/ then run: gh auth login"
    exit 1
}

gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: gh auth login"
    exit 1
}

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Missing .env"
    exit 1
}

$keys = @(
    "DATABASE_URL",
    "SYNC_DATABASE_URL",
    "OPENAI_API_KEY",
    "KEYWORDS",
    "OPENAI_MODEL",
    "OPENAI_TRIAGE_MODEL",
    "SLACK_WEBHOOK_URL",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "GOOGLE_ALERT_RSS_URLS",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET"
)

foreach ($key in $keys) {
    $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) { continue }
    $value = ($line -split "=", 2)[1].Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($value)) { continue }
    Write-Host "Setting secret $key ..."
    $value | gh secret set $key
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Done. Trigger a run: gh workflow run daily-ingestion.yml"
