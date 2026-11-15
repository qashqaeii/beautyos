# Isolated local PostgreSQL for pytest (port 5433). Not for production data.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$PgBin = "C:\Program Files\PostgreSQL\16\bin"
if (-not (Test-Path $PgBin)) {
    Write-Error "PostgreSQL 16 binaries not found at $PgBin"
}

$DataDir = Join-Path (Get-Location) ".pg_test_data"
$Port = 5433
$DbName = "beautyos_test"
$DbUser = "beautyos_test"
$LogFile = Join-Path $DataDir "server.log"
$PidFile = Join-Path $DataDir "postmaster.pid"

$Env:PGTEST_URL = "postgres://${DbUser}@127.0.0.1:${Port}/${DbName}"

function Test-PgListening {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $Port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Path $DataDir)) {
    Write-Host "Initializing isolated PostgreSQL data directory..."
    & "$PgBin\initdb.exe" -D $DataDir -U $DbUser -E UTF8 --locale=C -A trust | Out-Null
    $hba = Join-Path $DataDir "pg_hba.conf"
    @"
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
"@ | Set-Content -Path $hba -Encoding ASCII
}

if (-not (Test-PgListening)) {
    Write-Host "Starting PostgreSQL test instance on port $Port..."
    & "$PgBin\pg_ctl.exe" -D $DataDir -l $LogFile -o "-p $Port -h 127.0.0.1" start | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-PgListening) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        Write-Error "PostgreSQL test server did not start on port $Port. See $LogFile"
    }
}

$env:PGHOST = "127.0.0.1"
$env:PGPORT = "$Port"
$env:PGUSER = $DbUser

& "$PgBin\psql.exe" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DbName'" | Out-Null
$exists = (& "$PgBin\psql.exe" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'").Trim()
if ($exists -ne "1") {
    & "$PgBin\createdb.exe" $DbName | Out-Null
}

Write-Host "Test PostgreSQL ready: $Env:PGTEST_URL"
Write-Output $Env:PGTEST_URL