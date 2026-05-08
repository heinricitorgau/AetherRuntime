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
    Write-Fail "Eval cases not found at $evalDir (找不到評估案例目錄)"
}

# Find Python
$pythonPath = Resolve-PythonPath $runtimeDir $strictOffline
if (-not $pythonPath) {
    if ($strictOffline) {
        Write-Fail "bundled Python not found (strict offline 模式需要 local_ai\runtime\python\python.exe)"
    }
    Write-Fail "python not found; install Python or add it to PATH (找不到 Python，請確認已安裝或加入 PATH)"
}

Write-Header "C Exam Offline Evaluation Pack (C 語言離線評估包)"

# Parse arguments
$useAi = $false
$filter = ""
$output = ""
$answersDir = ""

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--use-ai" {
            $useAi = $true
            Write-Info "Will generate code using local AI (將使用本地 AI 產生程式碼)"
        }
        "--filter" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--filter requires a TEXT" }
            $filter = $args[$i + 1]
            Write-Info "Filtering cases (過濾條件): $filter"
            $i++
        }
        "--output" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--output requires a FILE" }
            $output = $args[$i + 1]
            Write-Info "Output file (輸出檔案): $output"
            $i++
        }
        "--answers-dir" {
            if ($i + 1 -ge $args.Count) { Write-Fail "--answers-dir requires a DIR" }
            $answersDir = $args[$i + 1]
            Write-Info "Using answer files from (使用答案目錄): $answersDir"
            $i++
        }
        { $_ -in "--help", "-h" } {
            Write-Host "Usage: powershell -ExecutionPolicy Bypass -File .\local_ai\run_eval.ps1 [options]"
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  --use-ai              Ask the bundled/local model to answer each case."
            Write-Host "  --answers-dir DIR     Use DIR/<case_id>.c answers instead of the model."
            Write-Host "  --filter TEXT         Run cases whose id, filename, year, or topic matches TEXT."
            Write-Host "  --output FILE         Write eval_report.json to FILE."
            exit 0
        }
        default {
            Write-Warn "Unknown argument (未知參數): $($args[$i])"
        }
    }
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
Write-Header "Running Evaluation (開始評估)"
& $pythonPath @evalArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Ok "Evaluation complete (評估完成)"
} else {
    Write-Fail "Evaluation failed with exit code $exitCode (評估失敗)"
}
exit $exitCode
