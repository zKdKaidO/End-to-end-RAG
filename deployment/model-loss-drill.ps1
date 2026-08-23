$ErrorActionPreference = "Stop"
$modelLossPath = [System.IO.Path]::GetFullPath("A:\RAG\.recovery-model-loss-test")
if ($modelLossPath -ne "A:\RAG\.recovery-model-loss-test") {
    throw "Model-loss path guard failed"
}

New-Item -ItemType Directory -Force -Path $modelLossPath | Out-Null
$oldModels = $env:OLLAMA_MODELS
$oldHost = $env:OLLAMA_HOST
$env:OLLAMA_MODELS = $modelLossPath
$env:OLLAMA_HOST = "127.0.0.1:11435"
$process = $null
try {
    $process = Start-Process -FilePath (Get-Command ollama).Source -ArgumentList "serve" -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 500
        try { $tags = Invoke-RestMethod http://127.0.0.1:11435/api/tags -TimeoutSec 2 } catch { $tags = $null }
    } while ($null -eq $tags -and (Get-Date) -lt $deadline)
    if ($null -eq $tags) { throw "Empty Ollama instance did not start" }

    docker compose --env-file .env -f deployment/docker-compose.recovery-test.yml --profile operations run --rm `
        -e OLLAMA_BASE_URL=http://host.docker.internal:11435 `
        deployment-tool python -m app.deployment.cli model-check
    if ($LASTEXITCODE -eq 0) { throw "Empty model store was incorrectly accepted" }
    Write-Output "MODEL_LOSS_FAIL_CLOSED_EXIT=$LASTEXITCODE"
}
finally {
    if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id }
    $env:OLLAMA_MODELS = $oldModels
    $env:OLLAMA_HOST = $oldHost
}
