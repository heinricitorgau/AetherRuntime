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

function Find-BinaryPath($primary, $fallbacks) {
    if (Test-Path $primary) {
        return $primary
    }
    foreach ($candidate in $fallbacks) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Test-Truthy($value) {
    if (-not $value) {
        return $false
    }
    return @("1", "true", "yes", "on") -contains $value.ToString().Trim().ToLowerInvariant()
}

function Resolve-CommandPath($name) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

function Test-PortListening($port) {
    try {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return $listener.Count -gt 0
    } catch {
        return $false
    }
}

function Stop-ListenerOnPort($port, $label) {
    try {
        $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
    } catch {
        return
    }
    if (-not $listeners) {
        return
    }
    Write-Warn "port $port already in use; restarting $label"
    $listeners | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        try {
            Stop-Process -Id $_ -Force -ErrorAction Stop
        } catch {
        }
    }
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 1
        try {
            $remaining = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        } catch {
            $remaining = $null
        }
        if (-not $remaining) {
            Write-Ok "$label port $port cleared"
            return
        }
    }
    Write-Fail "could not free port $port for $label"
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

function Resolve-PythonPath($runtimeDir, $strictOffline) {
    $bundledPythonCandidates = @(
        (Join-Path $runtimeDir "python/python.exe"),
        (Join-Path $runtimeDir "python/python3.exe"),
        (Join-Path $runtimeDir "python/bin/python.exe"),
        (Join-Path $runtimeDir "bin/python.exe")
    )
    foreach ($candidate in $bundledPythonCandidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    if ($strictOffline) {
        return $null
    }

    $pythonPath = Resolve-CommandPath "python"
    if (-not $pythonPath) {
        $pythonPath = Resolve-CommandPath "python3"
    }
    if (-not $pythonPath) {
        $pythonPath = Resolve-CommandPath "py"
    }
    return $pythonPath
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$runtimeDir = Join-Path $scriptDir "runtime"
$binDir = Join-Path $runtimeDir "bin"
$bundledOllamaHome = Join-Path $runtimeDir "ollama-home"
$manifestPath = Join-Path $runtimeDir "bundle-manifest.txt"

function Get-ModelSizeClass($modelName) {
    if ($modelName -match ':(0\.5|1|1\.5|3)b') { return "small" }
    if ($modelName -match ':(7|8)b')            { return "medium" }
    return "large"
}

function Get-AdaptiveTimeouts($sizeClass) {
    switch ($sizeClass) {
        "small"  { return @{ Full = 60;  FirstToken = 15 } }
        "medium" { return @{ Full = 180; FirstToken = 30 } }
        default  { return @{ Full = 300; FirstToken = 60 } }
    }
}

function Get-BundledModelManifestPath($bundledOllamaHome, $model) {
    $modelName = $model.Split(":", 2)[0]
    $baseDir = Join-Path $bundledOllamaHome ("models/manifests/registry.ollama.ai/library/" + $modelName)
    if ($model.Contains(":")) {
        $modelTag = $model.Split(":", 2)[1]
        $exactPath = Join-Path $baseDir $modelTag
        if (Test-Path $exactPath) {
            return $exactPath
        }
    }
    $latestPath = Join-Path $baseDir "latest"
    if (Test-Path $latestPath) {
        return $latestPath
    }
    if ($model.Contains(":")) {
        return (Join-Path $baseDir $model.Split(":", 2)[1])
    }
    return $latestPath
}

function Get-BundledModelRequestName($bundledOllamaHome, $model) {
    $modelName = $model.Split(":", 2)[0]
    $baseDir = Join-Path $bundledOllamaHome ("models/manifests/registry.ollama.ai/library/" + $modelName)
    if ($model.Contains(":")) {
        $modelTag = $model.Split(":", 2)[1]
        $exactPath = Join-Path $baseDir $modelTag
        if (Test-Path $exactPath) {
            return $model
        }
    }
    $latestPath = Join-Path $baseDir "latest"
    if (Test-Path $latestPath) {
        return $modelName
    }
    return $model
}

$defaultModel = "qwen2.5-coder:1.5b"
if (Test-Path $manifestPath) {
    $manifestModelLine = Select-String -Path $manifestPath -Pattern '^model=' -ErrorAction SilentlyContinue
    if ($manifestModelLine) {
        $defaultModel = $manifestModelLine.Line.Substring(6)
    }
}
$isDefaultModel = (-not $env:CLAW_MODEL)
$model = if ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { $defaultModel }
$proxyPort = if ($env:CLAW_PROXY_PORT) { [int]$env:CLAW_PROXY_PORT } else { 8082 }
$ollamaPort = if ($env:CLAW_OLLAMA_PORT) { [int]$env:CLAW_OLLAMA_PORT } else { 11435 }
$ollamaUrl = if ($env:OLLAMA_URL) { $env:OLLAMA_URL } else { "http://127.0.0.1:$ollamaPort" }
$permissionMode = if ($env:CLAW_PERMISSION_MODE) { $env:CLAW_PERMISSION_MODE } else { "read-only" }
$systemPrompt = if ($env:CLAW_SYSTEM_PROMPT) { $env:CLAW_SYSTEM_PROMPT } else { "" }
$promptProfile = if ($env:CLAW_PROMPT_PROFILE) { $env:CLAW_PROMPT_PROFILE } else { "default_zh_tw" }
$promptDir = if ($env:CLAW_PROMPT_DIR) { $env:CLAW_PROMPT_DIR } else { Join-Path $scriptDir "prompts" }
$strictOffline = Test-Truthy $env:CLAW_STRICT_OFFLINE
$ragQuery = ""

$smokeTest = $args -contains "--smoke-test"
if ($smokeTest) {
    $model = "qwen2.5-coder:1.5b"
    $env:CLAW_MODEL = $model
    $env:CLAW_OLLAMA_TIMEOUT_SECONDS = "60"
    $env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS = "15"
    $env:CLAW_MAX_REPAIR_RETRIES = "0"
    $env:CLAW_FORCE_NON_STREAM = "1"
    $env:CLAW_SMOKE_TEST = "1"
    $env:CLAW_SYSTEM_PROMPT = "Reply with exactly OK."
    $promptProfile = "smoke_test"
}

$clawStreamTest = $args -contains "--claw-stream-test"
if ($clawStreamTest) {
    $model = "qwen2.5-coder:1.5b"
    $env:CLAW_MODEL = $model
    $env:CLAW_DEBUG = "1"
    $env:CLAW_DISABLE_TOOLS = "1"
    $env:CLAW_MAX_REPAIR_RETRIES = "0"
    $env:CLAW_OLLAMA_TIMEOUT_SECONDS = "60"
    $env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS = "15"
    $env:CLAW_FORCE_NON_STREAM = "1"
    $env:CLAW_SMOKE_TEST = "1"
    $env:CLAW_SYSTEM_PROMPT = "Reply with exactly OK."
    $promptProfile = "smoke_test"
}

$sizeClass = Get-ModelSizeClass $model
$timeouts = Get-AdaptiveTimeouts $sizeClass
if (-not $env:CLAW_OLLAMA_TIMEOUT_SECONDS) {
    $env:CLAW_OLLAMA_TIMEOUT_SECONDS = $timeouts.Full.ToString()
}
if (-not $env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS) {
    $env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS = $timeouts.FirstToken.ToString()
}

$proxyProcess = $null
$ollamaProcess = $null

try {
    Write-Host @"
   _____ _                    _       ___  ___
  / ____| |                  | |     / _ \|_ _|
 | |    | | __ ___      __   | |    | | | || |
 | |    | |/ _` \ \ /\ / /   | |    | |_| || |
 | |____| | (_| |\ V  V /    | |___ \___/|___|
  \_____|_|\__,_| \_/\_/     |_____| offline
"@
    Write-Host ""
    if ($smokeTest) {
        Write-Host "  running lightweight offline smoke test" -ForegroundColor Green
        Write-Host "  force non-stream: enabled" -ForegroundColor Green
    }
    elseif ($clawStreamTest) {
        Write-Host "  running claw stream compatibility test (non-stream mode)" -ForegroundColor Green
        Write-Host "  force non-stream: enabled for claw stream compatibility test" -ForegroundColor Green
    }
    elseif ($isDefaultModel) { Write-Host "  default smoke-test model selected ($model)" -ForegroundColor DarkGray }
    Write-Host "  model: $model ($sizeClass)" -ForegroundColor Cyan
    Write-Host "  timeout: $($env:CLAW_OLLAMA_TIMEOUT_SECONDS)s (first-token: $($env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS)s)" -ForegroundColor Cyan
    Write-Host "  perms: $permissionMode" -ForegroundColor Cyan
    Write-Host "  proxy: http://127.0.0.1:$proxyPort" -ForegroundColor Cyan
    Write-Host "  ollama: $ollamaUrl" -ForegroundColor Cyan
    Write-Host "  prompt: $promptProfile" -ForegroundColor Cyan
    if ($strictOffline) {
        Write-Host "  strict: on" -ForegroundColor Cyan
    }
    Write-Host ""

    Write-Header "preflight"
    $pythonPath = Resolve-PythonPath $runtimeDir $strictOffline
    if (-not $pythonPath) {
        if ($strictOffline) {
            Write-Fail "bundled Python not found; strict offline mode expects local_ai/runtime/python/python.exe"
        }
        Write-Fail "python not found; install Python or add it to PATH"
    }
    Write-Ok "python: $pythonPath"

    $passthroughArgs = @()
    for ($i = 0; $i -lt $args.Count; $i++) {
        switch ($args[$i]) {
            "--smoke-test" {
                # Handled globally
            }
            "--claw-stream-test" {
                # Handled globally
            }
            "--import-docs" {
                if ($i + 1 -ge $args.Count) { Write-Fail "--import-docs requires a source path" }
                & $pythonPath (Join-Path $scriptDir "rag/import_usb_docs.py") $args[$i + 1]
                exit $LASTEXITCODE
            }
            "--reindex-rag" {
                & $pythonPath (Join-Path $scriptDir "rag/build_index.py")
                exit $LASTEXITCODE
            }
            "--rag" {
                if ($i + 1 -ge $args.Count) { Write-Fail "--rag requires a question" }
                $env:CLAW_RAG_ENABLED = "1"
                $ragQuery = $args[$i + 1]
                $i++
            }
            default {
                $passthroughArgs += $args[$i]
            }
        }
    }
    if ($smokeTest) {
        $args = @("--output-format", "text", "prompt", "hello")
    } else {
        $args = $passthroughArgs
    }

    $clawFallbacks = @()
    if (-not $strictOffline) {
        $clawFallbacks = @(
            (Join-Path $projectDir "rust/target/release/claw.exe"),
            (Join-Path $projectDir "rust/target/debug/claw.exe"),
            (Resolve-CommandPath "claw")
        )
    }
    $clawPath = Find-BinaryPath (Join-Path $binDir "claw.exe") $clawFallbacks
    if (-not $clawPath) {
        if ($strictOffline) {
            Write-Fail "bundled claw.exe not found; strict offline mode expects local_ai/runtime/bin/claw.exe"
        }
        Write-Fail "cannot find claw binary"
    }
    Write-Ok "claw: $clawPath"

    $ollamaFallbacks = @()
    if (-not $strictOffline) {
        $ollamaFallbacks = @(
            (Resolve-CommandPath "ollama")
        )
    }
    $ollamaPath = Find-BinaryPath (Join-Path $binDir "ollama.exe") $ollamaFallbacks
    if (-not $ollamaPath) {
        if ($strictOffline) {
            Write-Fail "bundled ollama.exe not found; strict offline mode expects local_ai/runtime/bin/ollama.exe"
        }
        Write-Fail "cannot find ollama binary"
    }
    Write-Ok "ollama: $ollamaPath"

    if (Test-Path $bundledOllamaHome) {
        $env:OLLAMA_MODELS = Join-Path $bundledOllamaHome "models"
        Write-Ok "using bundled models: $env:OLLAMA_MODELS"
    } else {
        if ($strictOffline) {
            Write-Fail "bundled model cache not found; strict offline mode expects local_ai/runtime/ollama-home"
        }
        Write-Warn "bundled model cache not found; falling back to system ollama cache"
    }

    if (Test-Path $manifestPath) {
        $manifest = @{}
        Get-Content $manifestPath | ForEach-Object {
            if ($_ -match '^(.*?)=(.*)$') {
                $manifest[$matches[1]] = $matches[2]
            }
        }
        if ($manifest.ContainsKey("bundle_os") -and $manifest["bundle_os"] -ne "Windows") {
            Write-Fail "bundle targets $($manifest['bundle_os']), but this machine is Windows"
        }
        Write-Ok "bundle target matches this machine: Windows/$env:PROCESSOR_ARCHITECTURE"
    } elseif ($strictOffline) {
        Write-Fail "bundle manifest not found; strict offline mode expects local_ai/runtime/bundle-manifest.txt"
    }

    $env:OLLAMA_HOST = "127.0.0.1:$ollamaPort"
    $ollamaRequestModel = if (Test-Path $bundledOllamaHome) { Get-BundledModelRequestName $bundledOllamaHome $model } else { $model }

    Write-Header "ollama"
    if (Test-PortListening $ollamaPort) {
        Write-Ok "bundled service already running at $ollamaUrl"
    } else {
        Write-Info "starting bundled ollama service on $ollamaUrl"
        $ollamaProcess = Start-Process -FilePath $ollamaPath -ArgumentList "serve" -PassThru -WindowStyle Hidden
        $readyIn = Wait-HttpOk "$ollamaUrl/api/tags" 30
        if ($null -eq $readyIn) {
            Write-Fail "bundled ollama failed to start"
        }
        Write-Ok "bundled service ready in ${readyIn}s"
    }
    $bundledModelManifest = Get-BundledModelManifestPath $bundledOllamaHome $model
    if ((Test-Path $bundledOllamaHome) -and (-not (Test-Path $bundledModelManifest))) {
        Write-Fail "model '$model' is not available in the bundled runtime"
    }
    Write-Ok "model cached locally: $model"

    Write-Header "proxy"
    Stop-ListenerOnPort $proxyPort "proxy"
    $logsDir = Join-Path $runtimeDir "logs"
    if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
    $proxyOutLog = Join-Path $logsDir "proxy.out.log"
    $proxyErrLog = Join-Path $logsDir "proxy.err.log"
    Write-Info "proxy target ollama: $ollamaUrl"
    $env:CLAW_MODEL = $model
    $env:OLLAMA_MODEL = $model
    $env:CLAW_OLLAMA_URL = $ollamaUrl
    $proxyScript = Join-Path $scriptDir "proxy.py"
    $proxyArgString = "`"$proxyScript`" --model `"$model`" --ollama-model `"$ollamaRequestModel`" --port $proxyPort --ollama-url `"$ollamaUrl`" --prompt-profile `"$promptProfile`" --prompt-dir `"$promptDir`" --first-token-timeout $($env:CLAW_FIRST_TOKEN_TIMEOUT_SECONDS)"
    if ($systemPrompt) {
        $proxyArgString += " --system-prompt `"$systemPrompt`""
    }
    if ($smokeTest) {
        $proxyArgString += " --smoke-test"
    }
    $proxyProcess = Start-Process -FilePath $pythonPath -ArgumentList $proxyArgString -RedirectStandardOutput $proxyOutLog -RedirectStandardError $proxyErrLog -PassThru -WindowStyle Hidden
    $proxyReadyIn = Wait-HttpOk "http://127.0.0.1:$proxyPort/health" 10
    if ($null -eq $proxyReadyIn) {
        Write-Fail "proxy failed to start; check $proxyOutLog and $proxyErrLog"
    }
    Write-Ok "proxy ready in ${proxyReadyIn}s"

    Write-Header "launch"
    Write-Host "ready local AI is up. Press Ctrl+C to exit." -ForegroundColor Green
    Write-Host "  If no new output appears for 60 seconds, press Ctrl+C to stop." -ForegroundColor DarkGray
    Write-Host "  Cleanup will stop proxy and bundled Ollama automatically." -ForegroundColor DarkGray
    Write-Host ""

    $env:ANTHROPIC_BASE_URL = "http://127.0.0.1:$proxyPort"
    $env:ANTHROPIC_API_KEY = "local-ollama"

    if ($smokeTest -and ($env:CLAW_SMOKE_USE_CLAW -ne "1")) {
        Write-Info "running proxy-level smoke test..."
        $body = @{
            model = $model
            messages = @(
                @{ role = "user"; content = "hello" }
            )
            stream = $false
        } | ConvertTo-Json -Depth 3 -Compress

        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$proxyPort/v1/messages" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 60
            $text = $response.content[0].text
            if ($text) {
                Write-Host ""
                Write-Host "Assistant: $text" -ForegroundColor Green
                Write-Host ""
                Write-Ok "smoke-test passed: proxy sync API returned text"
                exit 0
            } else {
                Write-Fail "smoke-test failed: empty text returned from proxy. Raw response: $($response | ConvertTo-Json -Compress)"
            }
        } catch {
            Write-Fail "smoke-test failed: $_"
        }
    }

    if ($clawStreamTest) {
        Write-Info "running claw stream test with prompt 'hello'..."
        Write-Info "inspect SSE log: $(Join-Path $runtimeDir 'logs\proxy.sse.log')"
        Write-Info "inspect proxy stderr: $proxyErrLog"
        $streamTestArgs = "--model $model --permission-mode $permissionMode prompt hello"
        $streamProc = Start-Process -FilePath $clawPath -ArgumentList $streamTestArgs -NoNewWindow -PassThru
        $streamProc.WaitForExit()
        exit $streamProc.ExitCode
    }

    if ($ragQuery -and $args.Count -eq 0) {
        $args = @("--output-format", "text", "prompt", $ragQuery)
    }

    $finalArgs = @()
    if ($args -notcontains "--model") {
        $finalArgs += @("--model", $model)
    }
    if (($args -notcontains "--permission-mode") -and (-not ($args | Where-Object { $_ -like "--permission-mode=*" }))) {
        $finalArgs += @("--permission-mode", $permissionMode)
    }
    $finalArgs += $args

    # Start-Process -NoNewWindow passes the parent's console handle directly so
    # claw sees a real TTY.  '& $clawPath' creates an internal pipe; crossterm
    # ANSI sequences are buffered with response text and the spinner finish()
    # clears the response line before it reaches the screen.
    $clawArgStr = ($finalArgs | ForEach-Object {
        if ($_ -match '[ \t"]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ }
    }) -join ' '
    $clawProcParams = @{ FilePath = $clawPath; NoNewWindow = $true; PassThru = $true }
    if ($clawArgStr) { $clawProcParams['ArgumentList'] = $clawArgStr }
    $clawProc = Start-Process @clawProcParams
    $clawProc.WaitForExit()
    $exitCode = $clawProc.ExitCode
    exit $exitCode
} finally {
    Write-Host ""
    Write-Host "[claw-local] shutting down..."
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
    Write-Host "    Get-Content .\local_ai\runtime\logs\proxy.out.log -Tail 40" -ForegroundColor DarkGray
}
