# Requires PostgreSQL DATABASE_URL (uncomment in .env or set here).
# Example: $env:DATABASE_URL = "postgres://beautyos:beautyos@localhost:5432/beautyos"
param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $DatabaseUrl) {
    $DatabaseUrl = (& "$PSScriptRoot\start_pg_test.ps1" | Select-Object -Last 1).Trim()
}

$env:DATABASE_URL = $DatabaseUrl
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

Write-Host "DATABASE_URL set (isolated test instance when using start_pg_test.ps1)."
.\.venv\Scripts\python.exe -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.local'); import django; django.setup(); from django.conf import settings; e=settings.DATABASES['default']['ENGINE']; n=settings.DATABASES['default'].get('NAME',''); print('Django DB engine:', e); print('Django DB name:', n); assert 'postgresql' in e, 'not postgresql'"

Write-Host "Running internal booking concurrency tests on PostgreSQL..."
# --reuse-db: isolated instance on 5433; avoids DROP/CREATE races between back-to-back runs.
.\.venv\Scripts\python.exe -m pytest tests/test_appointment_booking_concurrency.py tests/test_appointment_deposit.py -v -o addopts= --reuse-db