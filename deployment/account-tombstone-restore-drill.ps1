param([Parameter(Mandatory=$true)][string]$Password)
$ErrorActionPreference = "Stop"
$compose = "deployment/docker-compose.recovery-test.yml"
$composeArgs = @("compose", "--env-file", ".env", "-f", $compose)

docker @composeArgs up -d api worker processing-worker indexing-worker | Out-Null
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $health = docker inspect --format "{{.State.Health.Status}}" rag_recovery_v1-api-1 2>$null
} while ($health -ne "healthy" -and (Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Recovery API did not become healthy" }

$backupId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
docker @composeArgs --profile operations run --rm deployment-tool python -m app.deployment.cli `
    backup-create --root /backups --backup-id $backupId | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Tombstone drill backup failed" }

$origin = @{Origin="http://localhost:15173"}
$alice = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18001/api/v1/auth/login" `
    -Headers $origin -WebSession $alice -ContentType "application/json" `
    -Body (@{email="recovery-alice@example.invalid";password=$Password} | ConvertTo-Json) | Out-Null
$deletion = Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:18001/api/v1/auth/account" `
    -Headers $origin -WebSession $alice -ContentType "application/json" `
    -Body (@{password=$Password} | ConvertTo-Json)
if (-not $deletion.job_id) { throw "Deletion intent was not created" }
Start-Sleep -Seconds 3

& "$PSScriptRoot/recovery-drill.ps1" -Target BusinessStores -ConfirmToken "DESTROY:rag_recovery_v1:BusinessStores"
docker @composeArgs up -d postgres redis minio minio-init | Out-Null
docker @composeArgs --profile operations run --rm deployment-tool python -m app.deployment.cli `
    restore --root /backups --backup-id $backupId --environment recovery-test `
    --confirm "RESTORE:$backupId" --ollama-stopped `
    --output "/recovery-control/evidence/test-l-account-resurrection.json" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Tombstone drill restore failed" }

$remaining = docker @composeArgs exec -T postgres psql -U postgres -d rag_db -Atc `
    "select count(*) from users where normalized_email='recovery-alice@example.invalid'"
if ($remaining.Trim() -ne "0") { throw "Deleted account was resurrected" }

docker @composeArgs up -d api worker processing-worker indexing-worker | Out-Null
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $health = docker inspect --format "{{.State.Health.Status}}" rag_recovery_v1-api-1 2>$null
} while ($health -ne "healthy" -and (Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Restored API did not become healthy" }

$status = 0
try {
    Invoke-WebRequest -Method Post -Uri "http://127.0.0.1:18001/api/v1/auth/login" `
        -Headers $origin -ContentType "application/json" `
        -Body (@{email="recovery-alice@example.invalid";password=$Password} | ConvertTo-Json) | Out-Null
    $status = 200
} catch {
    $status = [int]$_.Exception.Response.StatusCode
}
if ($status -ne 401) { throw "Deleted account login was not rejected: HTTP $status" }
Write-Output "ACCOUNT_RESURRECTION_BLOCKED backup_id=$backupId job_id=$($deletion.job_id) http_status=$status"
