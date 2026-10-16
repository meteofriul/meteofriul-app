$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "push-device-retention-audit.psm1") -Force

function Assert-Test {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "assertion_failed:$Message" }
}

function Assert-ThrowsCode {
    param([scriptblock]$Operation, [string]$Code)
    try {
        & $Operation
    } catch {
        if ($_.Exception.Message -ceq $Code) { return }
        throw "assertion_failed:expected=$Code actual=$($_.Exception.Message)"
    }
    throw "assertion_failed:missing_exception:$Code"
}

function New-Policy {
    param([string]$State = "ACTIVE")
    return [PSCustomObject]@{
        name = "projects/meteo-friul/databases/(default)/collectionGroups/push_devices/fields/expires_at"
        ttlConfig = [PSCustomObject]@{ state = $State }
    }
}

function New-Device {
    param(
        [AllowNull()][object]$Active = $true,
        [string]$Reason = "",
        [string]$UpdatedAt = "2026-08-17T10:01:55Z",
        [AllowNull()][object]$ExpiresAt = $null,
        [string]$SchemaVersion = "2.1",
        [bool]$HasTargetValue = $false,
        [bool]$HasLegacyToken = $false,
        [bool]$ReferencedByOwner = $false,
        [bool]$ReferencedByCapacity = $false
    )
    return [PSCustomObject]@{
        documentName = "projects/meteo-friul/databases/(default)/documents/push_devices/redacted"
        documentKeyHash = "1" * 64
        updateTime = "2026-08-17T10:01:56Z"
        schemaVersion = $SchemaVersion
        active = $Active
        disabledReason = $Reason
        hasTargetValue = $HasTargetValue
        hasLegacyToken = $HasLegacyToken
        referencedByOwner = $ReferencedByOwner
        referencedByCapacity = $ReferencedByCapacity
        updatedAt = $UpdatedAt
        expiresAt = $ExpiresAt
    }
}

$validExpiry = "2026-09-16T10:01:55Z"
$clean = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $true -ExpiresAt $null),
    (New-Device -Active $false -Reason "fcm_token_invalid" -ExpiresAt $validExpiry)
)
Assert-Test $clean.ready "snapshot conforme"
Assert-Test ($clean.backfillCount -eq 0) "nessun backfill su snapshot conforme"

$missing = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $false -Reason "fcm_token_invalid")
)
Assert-Test (-not $missing.ready) "scadenza mancante non pronta"
Assert-Test $missing.readyForBackfill "scadenza mancante correggibile"
Assert-Test ($missing.backfillCount -eq 1) "un target di backfill"
Assert-Test (
    $missing.backfill[0].expectedExpiry.ToString("o") -ceq "2026-09-16T10:01:55.0000000+00:00"
) "orizzonte esatto di 30 giorni"

$activeExpiry = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $true -ExpiresAt $validExpiry)
)
Assert-Test (-not $activeExpiry.readyForBackfill) "TTL su attivo deve bloccare"
Assert-Test (@($activeExpiry.findings | Where-Object code -ceq "active_device_has_expiry").Count -eq 1) "finding TTL attivo"

$legacy = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $null -SchemaVersion "")
)
Assert-Test (-not $legacy.ready) "legacy richiede decisione"
Assert-Test ($legacy.legacyUnclassifiedCount -eq 1) "conteggio legacy"
Assert-Test $legacy.readyForLegacyCleanup "legacy non referenziato eliminabile separatamente"
Assert-Test ($legacy.legacyCleanupCount -eq 1) "un target legacy"
Assert-Test ($legacy.legacyCleanup[0].updateTime -ceq "2026-08-17T10:01:56Z") "updateTime conservato senza normalizzazione"
$legacyDigest = "a" * 64
$legacyPlan = New-PushDeviceLegacyCleanupPlan `
    -Audit $legacy `
    -ExpectedTargetSetSha256 $legacyDigest `
    -ActualTargetSetSha256 $legacyDigest
Assert-Test ($legacyPlan.deleteCount -eq 1) "un solo hard-delete"
Assert-Test ($legacyPlan.writes[0].currentDocument.updateTime -ceq "2026-08-17T10:01:56Z") "delete condizionato all'updateTime esatto"
Assert-ThrowsCode {
    New-PushDeviceLegacyCleanupPlan `
        -Audit $legacy `
        -ExpectedTargetSetSha256 ("a" * 64) `
        -ActualTargetSetSha256 ("b" * 64)
} "push_device_legacy_cleanup_target_digest_mismatch"

$legacyReferenced = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $null -SchemaVersion "" -ReferencedByOwner $true)
)
Assert-Test (-not $legacyReferenced.readyForLegacyCleanup) "legacy referenziato fail-closed"
Assert-Test ($legacyReferenced.legacyCleanupCount -eq 0) "legacy referenziato escluso dal delete"
Assert-ThrowsCode {
    New-PushDeviceLegacyCleanupPlan `
        -Audit $legacyReferenced `
        -ExpectedTargetSetSha256 ("a" * 64) `
        -ActualTargetSetSha256 ("a" * 64)
} "push_device_legacy_cleanup_preflight_failed"

$legacyAmbiguous = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $null -SchemaVersion "2.0")
)
Assert-Test (-not $legacyAmbiguous.readyForLegacyCleanup) "schema presente impedisce hard-delete legacy"

foreach ($field in @("HasTargetValue", "HasLegacyToken", "ReferencedByOwner", "ReferencedByCapacity")) {
    $arguments = @{ Active = $false; Reason = "fcm_token_invalid" }
    $arguments[$field] = $true
    $unsafe = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
        (New-Device @arguments)
    )
    Assert-Test (-not $unsafe.readyForBackfill) "invariante $field"
}

$wrongReason = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $false -Reason "manual_disable")
)
Assert-Test (-not $wrongReason.readyForBackfill) "motivo non previsto"

$missingPolicy = Test-PushDeviceRetentionSnapshot -Policies @() -Devices @(
    (New-Device -Active $false -Reason "fcm_token_invalid")
)
Assert-Test (-not $missingPolicy.ready) "policy assente non pronta"
Assert-Test $missingPolicy.readyForBackfill "policy assente non rende insicuro il backfill del timestamp"

$wrongHorizon = Test-PushDeviceRetentionSnapshot -Policies @(New-Policy) -Devices @(
    (New-Device -Active $false -Reason "fcm_token_invalid" -ExpiresAt "2026-09-15T10:01:55Z")
)
Assert-Test (-not $wrongHorizon.readyForBackfill) "orizzonte discordante"

$operationSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "audit-backfill-firestore-push-device-retention.ps1") -Raw
$moduleSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "push-device-retention-audit.psm1") -Raw
Assert-Test ($operationSource.Contains('if (-not $ApplyBackfill -and -not $ApplyLegacyCleanup)')) "dry-run predefinito"
Assert-Test ($operationSource.Contains("push_device_backfill_target_digest_mismatch")) "digest di conferma obbligatorio"
Assert-Test ($operationSource.Contains("ApplyLegacyCleanup")) "switch hard-delete legacy esplicito"
Assert-Test ($moduleSource.Contains("push_device_legacy_cleanup_target_digest_mismatch")) "digest legacy obbligatorio"
Assert-Test ($operationSource.Contains('currentDocument = [ordered]@{')) "precondizione updateTime"
Assert-Test (-not $operationSource.Contains("--enable-ttl")) "lo script non attiva la policy"
Assert-Test (-not $operationSource.Contains("--disable-ttl")) "lo script non disattiva la policy"

Write-Host "Push device retention audit contract tests: OK"
