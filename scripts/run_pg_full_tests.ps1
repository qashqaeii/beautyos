# Full BeautyOS pytest suite on isolated PostgreSQL (port 5433).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = (& "$PSScriptRoot\start_pg_test.ps1" | Select-Object -Last 1).Trim()
}
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

Write-Host "DATABASE_URL: $($env:DATABASE_URL)"
.\.venv\Scripts\python.exe -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.local'); django.setup(); from django.conf import settings; e=settings.DATABASES['default']['ENGINE']; assert 'postgresql' in e; print('Backend:', e)"
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest tests -v -o addopts= --reuse-db --tb=line