$ErrorActionPreference = "Stop"

function Write-Info($message) {
    Write-Host "  -> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "  ok $message" -ForegroundColor Green
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
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

function Ensure-Directory($path) {
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

function Bundle-SingleModel($model, $manifestRoot, $blobRoot, $runtimeDir) {
    $sourceManifest = Join-Path $manifestRoot "$model/latest"
    if (-not (Test-Path $sourceManifest)) {
        Write-Fail "cannot find manifest for model ${model}: $sourceManifest"
    }

    $targetRoot = Join-Path $runtimeDir "ollama-home/models"
    $targetManifestDir = Join-Path $targetRoot "manifests/registry.ollama.ai/library/$model"
    $targetBlobDir = Join-Path $targetRoot "blobs"

    $ollamaHomeDir = Join-Path $runtimeDir "ollama-home"
    if (Test-Path $ollamaHomeDir) {
        Remove-Item -Path $ollamaHomeDir -Recurse -Force
    }

    Ensure-Directory $targetManifestDir
    Ensure-Directory $targetBlobDir
    Copy-Item -Path $sourceManifest -Destination (Join-Path $targetManifestDir "latest") -Force

    $manifestContent = Get-Content -Path $sourceManifest -Raw
    $matches = [regex]::Matches($manifestContent, 'sha256:[0-9a-f]{64}')
    foreach ($match in $matches) {
        $digest = $match.Value
        $blobName = $digest.Replace(":", "-")
        $blobPath = Join-Path $blobRoot $blobName
        if (-not (Test-Path $blobPath)) {
            Write-Fail "missing blob for digest $digest"
        }
        Copy-Item -Path $blobPath -Destination (Join-Path $targetBlobDir $blobName) -Force
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$rustDir = Join-Path $projectDir "rust"
$runtimeDir = Join-Path $scriptDir "runtime"
$binDir = Join-Path $runtimeDir "bin"
$model = if ($args.Count -gt 0) { $args[0] } elseif ($env:CLAW_MODEL) { $env:CLAW_MODEL } else { "llama3.2" }
$sourceOllamaHome = if ($env:OLLAMA_HOME_OVERRIDE) { $env:OLLAMA_HOME_OVERRIDE } else { Join-Path $HOME ".ollama" }
$manifestRoot = Join-Path $sourceOllamaHome "models/manifests/registry.ollama.ai/library"
$blobRoot = Join-Path $sourceOllamaHome "models/blobs"

Write-Header "bundle target"
Ensure-Directory $binDir
Write-Ok "runtime dir: $runtimeDir"

Write-Header "tooling"
$cargoPath = Resolve-CommandPath "cargo"
if (-not $cargoPath) {
    Write-Fail "cargo not found; install Rust first"
}
$ollamaPath = Resolve-CommandPath "ollama"
if (-not $ollamaPath) {
    Write-Fail "ollama not found; install Ollama first"
}
Write-Ok "cargo: $(& $cargoPath --version)"
try {
    Write-Ok "ollama: $(& $ollamaPath --version)"
} catch {
    Write-Ok "ollama: installed"
}

Write-Header "build claw"
Push-Location $rustDir
try {
    & $cargoPath build --workspace --release
} finally {
    Pop-Location
}
$clawSource = Join-Path $rustDir "target/release/claw.exe"
if (-not (Test-Path $clawSource)) {
    Write-Fail "cannot find built claw binary at $clawSource"
}
Copy-Item -Path $clawSource -Destination (Join-Path $binDir "claw.exe") -Force
Write-Ok "bundled claw binary"

Write-Header "prepare model"
$modelAvailable = & $ollamaPath list 2>$null | Select-String -SimpleMatch $model
if (-not $modelAvailable) {
    Write-Info "model not cached yet, pulling $model"
    & $ollamaPath pull $model
}
Write-Ok "model available locally: $model"

Write-Header "bundle ollama"
Copy-Item -Path $ollamaPath -Destination (Join-Path $binDir "ollama.exe") -Force
Write-Ok "bundled ollama executable"

if (-not (Test-Path $sourceOllamaHome)) {
    Write-Fail "cannot find Ollama home at $sourceOllamaHome"
}

Bundle-SingleModel $model $manifestRoot $blobRoot $runtimeDir
Write-Ok "bundled only the selected model: $model"

Write-Header "write manifest"
$manifestLines = @(
    "prepared_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
    "bundle_os=Windows"
    "bundle_arch=$($env:PROCESSOR_ARCHITECTURE)"
    "model=$model"
    "claw_binary=$(Join-Path $binDir 'claw.exe')"
    "ollama_binary=$(Join-Path $binDir 'ollama.exe')"
    "ollama_home=$(Join-Path $runtimeDir 'ollama-home')"
    "launch_command=powershell -ExecutionPolicy Bypass -File local_ai/run.ps1"
)
$manifestLines | Set-Content -Path (Join-Path $runtimeDir "bundle-manifest.txt") -Encoding UTF8
Write-Ok "bundle manifest written"

Write-Header "summary"
try {
    $sizeBytes = (Get-ChildItem -Path $runtimeDir -Recurse -Force | Measure-Object -Property Length -Sum).Sum
    if ($null -ne $sizeBytes) {
        Write-Info ("bundle size: {0:N2} MB" -f ($sizeBytes / 1MB))
    }
} catch {
}

Write-Host ""
Write-Host "離線 bundle 已完成。"
Write-Host ""
Write-Host "之後只要把整個 repo 複製到目標機器，就可以直接執行："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/run.ps1"
Write-Host ""
Write-Host "若想改模型："
Write-Host "  powershell -ExecutionPolicy Bypass -File local_ai/prepare_bundle.ps1 codellama"
