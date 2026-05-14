# local_ai/run_eval.ps1
# Run C exam offline evaluation pack (Windows PowerShell launcher)

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

function Write-Fail($message) {
    Write-Host "  xx $message" -ForegroundColor Red
    exit 1
}

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
    $bundledPythonCandidates = @(
        (Join-Path $runtimeDir "python\python.exe"),
        (Join-Path $runtimeDir "python\python3.exe"),
        (Join-Path $runtimeDir "python\bin\python.exe"),
        (Join-Path $runtimeDir "bin\python.exe")
    )
    foreach ($candidate in $bundledPythonCandidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    if ($strictOffline) { return $null }

    $pythonPath = Resolve-CommandPath "python"
    if (-not $pythonPath) { $pythonPath = Resolve-CommandPath "python3" }
    if (-not $pythonPath) { $pythonPath = Resolve-CommandPath "py" }
    return $pythonPath
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$evalDir = Join-Path $scriptDir "eval_cases\c_exam"
$runtimeDir = Join-Path $scriptDir "runtime"
$strictOffline = Test-Truthy $env:CLAW_STRICT_OFFLINE

# Check if eval cases exist
if (-not (Test-Path $evalDir)) {
    Write-Fail "Eval cases not found at $evalDir"
}

# Find Python
$pythonPath = Resolve-PythonPath $runtimeDir $strictOffline
if (-not $pythonPath) {
    if ($strictOffline) {
        Write-Fail "bundled Python not found (strict offline mode requires local_ai\runtime\python\python.exe)"
    }
    Write-Fail "python not found; install Python or add it to PATH"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:POWERSHELL_TELEMETRY_OPTOUT = "1"

Write-Header "C Exam Offline Evaluation Pack"

# Parse arguments
$useAi = $false
$useProxyAi = $false
$filter = ""
$output = ""
$answersDir = ""
$timeoutSeconds = ""

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--use-ai" {
            $useAi = $true
            Write-Info "Will generate code using local AI (claw-based)"
        }
        "--use-proxy-ai" {
            $useProxyAi = $true
            Write-Info "Will generate code via proxy sync API (Windows recommended)"
        }
        "--filter" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--filter requires a TEXT" }
            $filter = $args[$i + 1]
            Write-Info "Filtering cases: $filter"
            $i++
        }
        "--output" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--output requires a FILE" }
            $output = $args[$i + 1]
            Write-Info "Output file: $output"
            $i++
        }
        "--answers-dir" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--answers-dir requires a DIR" }
            $answersDir = $args[$i + 1]
            Write-Info "Using answer files from: $answersDir"
            $i++
        }
        "--timeout-seconds" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--timeout-seconds requires a number" }
            $timeoutSeconds = $args[$i + 1]
            Write-Info "Per-case timeout: ${timeoutSeconds}s"
            $i++
        }
        { $_ -in "--help", "-h" } {
            Write-Host "Usage: powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 [options]"
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  --use-proxy-ai        Generate code via proxy sync API. Starts Ollama + proxy"
            Write-Host "                        automatically. Recommended on Windows. (default model: qwen2.5-coder:1.5b)"
            Write-Host "  --use-ai              Generate code via claw/run.sh (may be unstable on Windows)."
            Write-Host "  --answers-dir DIR     Use DIR/<case_id>.c answers instead of the model."
            Write-Host "  --filter TEXT         Run cases whose id, filename, year, or topic matches TEXT."
            Write-Host "  --output FILE         Write eval_report.json to FILE."
            Write-Host "  --timeout-seconds N   Hard per-case wall-clock timeout (default: adaptive by model size)."
            Write-Host ""
            Write-Host "Windows recommended:"
            Write-Host "  powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-proxy-ai --filter 2025"
            Write-Host "  powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 --use-ai --filter 2025 --timeout-seconds 180"
            exit 0
        }
        default {
            Write-Warn "Unknown argument: $($args[$i])"
        }
    }
}

if ($timeoutSeconds) {
    $env:CLAW_EVAL_CASE_TIMEOUT_SECONDS = $timeoutSeconds
}

# Build eval runner command
$evalArgs = @((Join-Path $scriptDir "eval_runner.py"), "--eval-dir", $evalDir)

if ($useAi) {
    $evalArgs += "--use-ai"
}

if ($filter) {
    $evalArgs += "--filter"
    $evalArgs += $filter
}

if ($output) {
    $evalArgs += "--output"
    $evalArgs += $output
}

if ($answersDir) {
    $evalArgs += "--answers-dir"
    $evalArgs += $answersDir
}

# Run evaluation
if ($useProxyAi) {
    $binDir = Join-Path $runtimeDir "bin"
    $bundledOllamaHome = Join-Path $runtimeDir "ollama-home"
    $proxyPort = if ($env:CLAW_PROXY_PORT) { [int]$env:CLAW_PROXY_PORT } else { 8082 }
    $ollamaPort = if ($env:CLAW_OLLAMA_PORT) { [int]$env:CLAW_OLLAMA_PORT } else { 11435 }
    $ollamaUrl = if ($env:OLLAMA_URL) { $env:OLLAMA_URL } else { "http://127.0.0.1:$ollamaPort" }
    $proxyUrl = "http://127.0.0.1:$proxyPort"
    $proxyModel = if ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { "qwen2.5-coder:1.5b" }
    $promptProfile = if ($env:CLAW_PROMPT_PROFILE) { $env:CLAW_PROMPT_PROFILE } else { "c_programming" }
    $promptDir = if ($env:CLAW_PROMPT_DIR) { $env:CLAW_PROMPT_DIR } else { Join-Path $scriptDir "prompts" }

    $ollamaPath = Find-BinaryPath (Join-Path $binDir "ollama.exe") @(Resolve-CommandPath "ollama")
    if (-not $ollamaPath) { Write-Fail "cannot find ollama binary (looked in $binDir and PATH)" }

    if (Test-Path $bundledOllamaHome) {
        $env:OLLAMA_MODELS = Join-Path $bundledOllamaHome "models"
        Write-Ok "using bundled models: $env:OLLAMA_MODELS"
    } else {
        Write-Warn "bundled model cache not found; using system ollama cache"
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
        $proxyArgStr = "`"$proxyScript`" --model `"$proxyModel`" --ollama-model `"$proxyModel`" --port $proxyPort --ollama-url `"$ollamaUrl`" --prompt-profile `"$promptProfile`" --prompt-dir `"$promptDir`""
        $proxyProcess = Start-Process -FilePath $pythonPath -ArgumentList $proxyArgStr `
            -RedirectStandardOutput (Join-Path $logsDir "proxy-eval.out.log") `
            -RedirectStandardError (Join-Path $logsDir "proxy-eval.err.log") `
            -PassThru -WindowStyle Hidden
        $ready = Wait-HttpOk "http://127.0.0.1:$proxyPort/health" 15
        if ($null -eq $ready) { Write-Fail "proxy failed to start within 15s; check $logsDir\proxy-eval.err.log" }
        Write-Ok "proxy ready in ${ready}s"
    }

    Write-Info "Using proxy sync AI mode"
    Write-Info "Proxy URL: $proxyUrl"
    Write-Info "Model: $proxyModel"

    $env:CLAW_MODEL = $proxyModel
    $env:CLAW_EVAL_USE_PROXY_AI = "1"
    $env:CLAW_PROXY_URL = $proxyUrl
    $evalArgs += "--use-proxy-ai"
    $evalArgs += "--proxy-url"
    $evalArgs += $proxyUrl
    $evalArgs += "--proxy-model"
    $evalArgs += $proxyModel

    Write-Header "Running Evaluation"
    Write-Host "  If one case appears stuck for too long, press Ctrl+C." -ForegroundColor DarkGray
    Write-Host "  Partial report may not be complete." -ForegroundColor DarkGray
    Write-Host ""
    try {
        & $pythonPath @evalArgs
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
        Write-Host ""
        Write-Host "  Log hints (run after stopping):" -ForegroundColor DarkGray
        Write-Host "    Get-Content .\local_ai\runtime\logs\proxy.err.log -Tail 120" -ForegroundColor DarkGray
    }
} else {
    Write-Header "Running Evaluation"
    Write-Host "  If one case appears stuck for too long, press Ctrl+C." -ForegroundColor DarkGray
    Write-Host "  Partial report may not be complete." -ForegroundColor DarkGray
    Write-Host ""
    & $pythonPath @evalArgs
    $exitCode = $LASTEXITCODE
}

if ($exitCode -eq 0) {
    Write-Ok "Evaluation complete"
} else {
    Write-Fail "Evaluation failed with exit code $exitCode"
}
exit $exitCode
