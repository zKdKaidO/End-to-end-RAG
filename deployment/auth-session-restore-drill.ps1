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

$origin = @{Origin="http://localhost:15173"}
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18001/api/v1/auth/login" `
    -Headers $origin -WebSession $session -ContentType "application/json" `
    -Body (@{email="recovery-admin@example.invalid";password=$Password} | ConvertTo-Json) | Out-Null
$cookies = @($session.Cookies.GetCookies("http://127.0.0.1:18001"))
if ($cookies.Count -ne 1) { throw "Expected exactly one authentication cookie" }
$cookieName = $cookies[0].Name
$rawCookie = $cookies[0].Value

$backupId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-" + [Guid]::NewGuid().ToString("N").Substring(0,8)
docker @composeArgs --profile operations run --rm deployment-tool python -m app.deployment.cli `
    backup-create --root /backups --backup-id $backupId | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Session drill backup failed" }

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18001/api/v1/auth/logout" `
    -Headers $origin -WebSession $session | Out-Null

& "$PSScriptRoot/recovery-drill.ps1" -Target Postgres -ConfirmToken "DESTROY:rag_recovery_v1:Postgres"
docker @composeArgs up -d postgres redis minio minio-init | Out-Null
docker @composeArgs --profile operations run --rm deployment-tool python -m app.deployment.cli `
    restore --root /backups --backup-id $backupId --environment recovery-test `
    --confirm "RESTORE:$backupId" --ollama-stopped `
    --output "/recovery-control/evidence/test-k-session-resurrection.json" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Session drill restore failed" }

docker @composeArgs up -d api worker processing-worker indexing-worker | Out-Null
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $health = docker inspect --format "{{.State.Health.Status}}" rag_recovery_v1-api-1 2>$null
} while ($health -ne "healthy" -and (Get-Date) -lt $deadline)
if ($health -ne "healthy") { throw "Restored API did not become healthy" }

$oldSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$oldSession.Cookies.Add((New-Object System.Net.Cookie($cookieName, $rawCookie, "/", "127.0.0.1")))
$status = 0
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:18001/api/v1/auth/me" -Headers $origin -WebSession $oldSession | Out-Null
    $status = 200
} catch {
    $status = [int]$_.Exception.Response.StatusCode
}
if ($status -ne 401) { throw "Restored session was not revoked: HTTP $status" }
Write-Output "SESSION_RESURRECTION_BLOCKED backup_id=$backupId http_status=$status"
