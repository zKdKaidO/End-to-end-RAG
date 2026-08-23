param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Redis", "Postgres", "MinIO", "BusinessStores", "AllDrillData")]
    [string]$Target,
    [Parameter(Mandatory=$true)]
    [string]$ConfirmToken
)

$expected = "DESTROY:rag_recovery_v1:$Target"
if ($ConfirmToken -cne $expected) {
    throw "Confirmation mismatch. Required token: $expected"
}

$compose = Join-Path $PSScriptRoot "docker-compose.recovery-test.yml"
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
docker compose --env-file $envFile -f $compose down --remove-orphans
if ($LASTEXITCODE -ne 0) { throw "Failed to stop recovery-test project" }

$targets = switch ($Target) {
    "Redis" { @("rag_recovery_v1_redis") }
    "Postgres" { @("rag_recovery_v1_postgres") }
    "MinIO" { @("rag_recovery_v1_minio") }
    "BusinessStores" { @("rag_recovery_v1_postgres", "rag_recovery_v1_minio") }
    "AllDrillData" {
        @(
            "rag_recovery_v1_postgres",
            "rag_recovery_v1_redis",
            "rag_recovery_v1_minio",
            "rag_recovery_v1_control",
            "rag_recovery_v1_backups",
            "rag_recovery_v1_model_cache"
        )
    }
}

foreach ($volume in $targets) {
    if ($volume -notmatch '^rag_recovery_v1_[a-z_]+$') {
        throw "Volume guard rejected $volume"
    }
    docker volume rm $volume 2>$null
}

Write-Output "Removed only explicit recovery-test volumes: $($targets -join ', ')"
