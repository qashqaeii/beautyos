param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $DatabaseUrl) {
    Write-Error "DATABASE_URL is not set."
}

$env:DATABASE_URL = $DatabaseUrl
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"

.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe -m pytest tests/test_appointment_lifecycle_commission.py -v -o addopts= --create-db