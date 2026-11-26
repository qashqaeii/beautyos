# Fast-forward main from GitHub (Windows). Resolves common untracked-file pull blockers.
# Usage from repo root: .\scripts\sync-from-github.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path (Join-Path $Root ".git"))) {
    Write-Error "Not a git repository: $Root"
}

# Files that exist on origin but are often copied locally without `git add` — `git pull` then fails.
$untrackedPullBlockers = @(
    "static/images/photos/luna-salon-hero.webp"
)

foreach ($rel in $untrackedPullBlockers) {
    $full = Join-Path $Root $rel
    if (-not (Test-Path -LiteralPath $full)) {
        continue
    }
    git ls-files --error-unmatch -- $rel 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $stamp = Get-Date -Format "yyyyMMddHHmmss"
        $backup = "$full.untracked-backup-$stamp"
        Write-Host "Untracked file blocks pull; moving to: $backup"
        Move-Item -LiteralPath $full -Destination $backup -Force
    }
}

# Git writes progress to stderr; PowerShell may show it as an error even on success.
$prevRedirect = $env:GIT_REDIRECT_STDERR
$env:GIT_REDIRECT_STDERR = "2>&1"
try {
    git fetch origin
    if ($LASTEXITCODE -ne 0) {
        throw "git fetch failed (exit $LASTEXITCODE)"
    }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) {
        throw "git pull failed (exit $LASTEXITCODE)"
    }
}
finally {
    if ($null -eq $prevRedirect) {
        Remove-Item Env:\GIT_REDIRECT_STDERR -ErrorAction SilentlyContinue
    } else {
        $env:GIT_REDIRECT_STDERR = $prevRedirect
    }
}

Write-Host "main is up to date with origin/main."