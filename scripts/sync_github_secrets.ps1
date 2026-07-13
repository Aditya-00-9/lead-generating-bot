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

# Prefer Python sync to avoid PowerShell pipe/CRLF corrupting connection strings.
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

& $Python -c @"
import subprocess
from pathlib import Path

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#') or '=' not in raw:
            continue
        k, v = raw.split('=', 1)
        out[k.strip()] = v.strip().strip('\"').strip(\"'\")
    return out

env = load_env('.env')
keys = [
    'DATABASE_URL', 'SYNC_DATABASE_URL', 'OPENAI_API_KEY', 'KEYWORDS',
    'OPENAI_MODEL', 'OPENAI_TRIAGE_MODEL', 'SLACK_WEBHOOK_URL',
    'SLACK_BOT_TOKEN', 'SLACK_CHANNEL_ID', 'GOOGLE_ALERT_RSS_URLS',
    'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET',
]
for key in keys:
    value = env.get(key, '').strip()
    if not value or value.startswith('your_') or 'xxx' in value.lower() or 'zzz' in value.lower():
        print(f'skip {key}')
        continue
    r = subprocess.run(['gh', 'secret', 'set', key, '--body', value], capture_output=True, text=True)
    if r.returncode != 0:
        print(f'FAIL {key}: {r.stderr.strip()}')
        raise SystemExit(1)
    print(f'Setting secret {key} ...')
print('Done. Trigger a run: gh workflow run \"Daily lead ingestion\"')
"@

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
