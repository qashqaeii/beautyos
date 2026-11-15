# Requires PostgreSQL DATABASE_URL (uncomment in .env or set here).
# Example: $env:DATABASE_URL = "postgres://beautyos:beautyos@localhost:5432/beautyos"
param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $DatabaseUrl) {
    Write-Error "DATABASE_URL is not set. Uncomment DATABASE_URL in .env or pass -DatabaseUrl."
}

$env:DATABASE_URL = $DatabaseUrl
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

Write-Host "Running internal booking concurrency tests on PostgreSQL..."
.\.venv\Scripts\python.exe -m pytest tests/test_appointment_booking_concurrency.py -v -o addopts= --create-db