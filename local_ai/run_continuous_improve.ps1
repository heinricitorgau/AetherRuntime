# local_ai/run_continuous_improve.ps1
# Start the local proxy if needed, then run the continuous improvement loop.

$ErrorActionPreference = "Stop"

function Write-Info($message) { Write-Host "  -> $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "  ok $message" -ForegroundColor Green }
function Write-Fail($message) { Write-Host "  xx $message" -ForegroundColor Red; exit 1 }
function Write-Header($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor White
}

function Resolve-CommandPath($name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -eq $command) { return $null }
    return $command.Source
}

function Find-BinaryPath($primary, $fallbacks) {
    if (Test-Path $primary) { return $primary }
    foreach ($candidate in $fallbacks) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

function Test-PortListening($port) {
    try {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return $listener.Count -gt 0
    } catch {
        return $false
    }
}

function Wait-HttpOk($url, $seconds) {
    for ($i = 1; $i -le $seconds; $i++) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
            return $i
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $null
}

function Test-Truthy($value) {
    if (-not $value) { return $false }
    return @("1", "true", "yes", "on") -contains $value.ToString().Trim().ToLowerInvariant()
}

function Resolve-PythonPath($runtimeDir, $strictOffline) {
    $candidates = @(
        (Join-Path $runtimeDir "python\python.exe"),
        (Join-Path $runtimeDir "python\python3.exe"),
        (Join-Path $runtimeDir "python\bin\python.exe"),
        (Join-Path $runtimeDir "bin\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    if ($strictOffline) { return $null }

    $pythonPath = Resolve-CommandPath "python"
    if (-not $pythonPath) { $pythonPath = Resolve-CommandPath "python3" }
    if (-not $pythonPath) { $pythonPath = Resolve-CommandPath "py" }
    return $pythonPath
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $scriptDir "runtime"
$binDir = Join-Path $runtimeDir "bin"
$strictOffline = Test-Truthy $env:CLAW_STRICT_OFFLINE

$pythonPath = Resolve-PythonPath $runtimeDir $strictOffline
if (-not $pythonPath) {
    if ($strictOffline) { Write-Fail "bundled Python not found in local_ai\runtime" }
    Write-Fail "python not found; install Python or add it to PATH"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:POWERSHELL_TELEMETRY_OPTOUT = "1"

$proxyPort = if ($env:CLAW_PROXY_PORT) { [int]$env:CLAW_PROXY_PORT } else { 8082 }
$ollamaPort = if ($env:CLAW_OLLAMA_PORT) { [int]$env:CLAW_OLLAMA_PORT } else { 11435 }
$ollamaUrl = if ($env:OLLAMA_URL) { $env:OLLAMA_URL } else { "http://127.0.0.1:$ollamaPort" }
$proxyUrl = "http://127.0.0.1:$proxyPort"
$model = if ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { "qwen2.5-coder:3b" }
$promptProfile = if ($env:CLAW_PROMPT_PROFILE) { $env:CLAW_PROMPT_PROFILE } else { "c_programming" }
$promptDir = if ($env:CLAW_PROMPT_DIR) { $env:CLAW_PROMPT_DIR } else { Join-Path $scriptDir "prompts" }
$bundledOllamaHome = Join-Path $runtimeDir "ollama-home"

Write-Header "Continuous Improvement Loop"
Write-Info "model: $model"
Write-Info "proxy: $proxyUrl"

$ollamaPath = Find-BinaryPath (Join-Path $binDir "ollama.exe") @(Resolve-CommandPath "ollama")
if (-not $ollamaPath) { Write-Fail "cannot find ollama binary" }

if (Test-Path $bundledOllamaHome) {
    $env:OLLAMA_MODELS = Join-Path $bundledOllamaHome "models"
    Write-Ok "using bundled models: $env:OLLAMA_MODELS"
}
$env:OLLAMA_HOST = "127.0.0.1:$ollamaPort"

$ollamaProcess = $null
if (Test-PortListening $ollamaPort) {
    Write-Ok "ollama already running on port $ollamaPort"
} else {
    Write-Info "starting ollama on port $ollamaPort"
    $ollamaProcess = Start-Process -FilePath $ollamaPath -ArgumentList "serve" -PassThru -WindowStyle Hidden
    $ready = Wait-HttpOk "$ollamaUrl/api/tags" 30
    if ($null -eq $ready) { Write-Fail "ollama failed to start within 30s" }
    Write-Ok "ollama ready in ${ready}s"
}

$proxyProcess = $null
if (Test-PortListening $proxyPort) {
    Write-Ok "proxy already running on port $proxyPort"
} else {
    Write-Info "starting proxy on port $proxyPort"
    $logsDir = Join-Path $runtimeDir "logs"
    if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
    $proxyScript = Join-Path $scriptDir "proxy.py"
    $proxyArgStr = "`"$proxyScript`" --model `"$model`" --ollama-model `"$model`" --port $proxyPort --ollama-url `"$ollamaUrl`" --prompt-profile `"$promptProfile`" --prompt-dir `"$promptDir`""
    $proxyProcess = Start-Process -FilePath $pythonPath -ArgumentList $proxyArgStr `
        -RedirectStandardOutput (Join-Path $logsDir "proxy-continuous.out.log") `
        -RedirectStandardError (Join-Path $logsDir "proxy-continuous.err.log") `
        -PassThru -WindowStyle Hidden
    $ready = Wait-HttpOk "$proxyUrl/health" 15
    if ($null -eq $ready) { Write-Fail "proxy failed to start within 15s; check $logsDir\proxy-continuous.err.log" }
    Write-Ok "proxy ready in ${ready}s"
}

$env:CLAW_MODEL = $model
$env:CLAW_PROXY_URL = $proxyUrl

$runner = Join-Path $scriptDir "benchmark\continuous_improve.py"
$runnerArgs = @($runner, "--proxy-url", $proxyUrl, "--model", $model) + $args

Write-Header "Running"
Write-Host "  Press Ctrl+C to stop. Partial results are saved after every attempt." -ForegroundColor Green
Write-Host ""

try {
    & $pythonPath @runnerArgs
    $exitCode = $LASTEXITCODE
} finally {
    if ($proxyProcess -and -not $proxyProcess.HasExited) {
        Stop-Process -Id $proxyProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "proxy stopped"
    }
    if ($ollamaProcess -and -not $ollamaProcess.HasExited) {
        Stop-Process -Id $ollamaProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Info "ollama stopped"
    }
}

exit $exitCode
