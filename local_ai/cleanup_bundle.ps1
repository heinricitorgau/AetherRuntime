$ErrorActionPreference = "Stop"

function Write-Info($message) {
    Write-Host "  -> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "  ok $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "  !! $message" -ForegroundColor Yellow
}

function Write-Header($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor White
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $scriptDir "runtime"

Write-Header "cleanup target"
Write-Info "repo bundle dir: $runtimeDir"

if (-not (Test-Path $runtimeDir)) {
    Write-Warn "nothing to clean; $runtimeDir does not exist"
    exit 0
}

$bundleSize = "unknown"
try {
    $sizeBytes = (Get-ChildItem -Path $runtimeDir -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    if ($null -ne $sizeBytes) {
        $bundleSize = "{0:N2} MB" -f ($sizeBytes / 1MB)
    }
} catch {
}

Remove-Item -Path $runtimeDir -Recurse -Force
Write-Ok "removed repo bundle: $runtimeDir"

Write-Host ""
Write-Host "Removed offline bundle created by deploy_local.ps1 / prepare_bundle.ps1."
Write-Host "Freed space: approx $bundleSize"
Write-Host ""
Write-Host "Note:"
Write-Host "- This only removes local_ai/runtime/"
Write-Host "- It does NOT remove the system-wide model cache in `$env:USERPROFILE\.ollama"
