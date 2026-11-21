# Local BeautyOS dev server (Windows). Run from repo root: .\scripts\run-dev.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvActivate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Error @"
Virtual environment not found at .venv
Setup:
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements/dev.txt
  copy .env.example .env
  npm install
  npm run build:css
"@
}

. $venvActivate
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

if (-not (Test-Path (Join-Path $Root ".env"))) {
    $example = Join-Path $Root ".env.example"
    if (Test-Path $example) {
        Copy-Item $example (Join-Path $Root ".env")
        Write-Host "Created .env from .env.example (SQLite default when DATABASE_URL is unset)."
    }
}

python manage.py migrate --noinput
Write-Host "Starting http://127.0.0.1:8000/"
python manage.py runserver 127.0.0.1:8000