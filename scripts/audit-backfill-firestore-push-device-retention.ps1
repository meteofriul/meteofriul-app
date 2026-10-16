[CmdletBinding()]
param(
    [switch]$ApplyBackfill,
    [string]$ExpectedTargetSetSha256 = "",
    [switch]$ApplyLegacyCleanup,
    [string]$ExpectedLegacyTargetSetSha256 = "",
    [string]$ProjectId = "meteo-friul",
    [string]$DatabaseId = "(default)",
    [string]$GcloudPath = "",
    [string]$PolicyFixturePath = "",
    [string]$DeviceFixturePath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "push-device-retention-audit.psm1") -Force

function Resolve-GcloudExecutable {
    if ($GcloudPath) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) { throw "gcloud_not_found" }
        return (Resolve-Path -LiteralPath $GcloudPath).Path
    }
    $command = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    $fallback = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) { throw "gcloud_not_found" }
    return $fallback
}

function Get-AccessToken {
    $gcloud = Resolve-GcloudExecutable
    $output = & $gcloud auth print-access-token "--project=$ProjectId" --quiet --verbosity=error 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gcloud_access_token_failed" }
    $token = [string]($output -join "").Trim()
    if ([string]::IsNullOrWhiteSpace($token)) { throw "gcloud_access_token_empty" }
    return $token
}

function Get-Sha256Text {
    param([string]$Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-FieldValue {
    param([object]$Fields, [string]$Name)
    if ($null -eq $Fields -or -not ($Fields.PSObject.Properties.Name -ccontains $Name)) {
        return $null
    }
    $value = $Fields.$Name
    foreach ($property in @("timestampValue", "stringValue", "booleanValue", "integerValue", "doubleValue")) {
        if ($null -ne $value -and $value.PSObject.Properties.Name -ccontains $property) {
            return $value.$property
        }
    }
    return $null
}

function Get-StringArrayField {
    param([object]$Fields, [string]$Name)
    if ($null -eq $Fields -or -not ($Fields.PSObject.Properties.Name -ccontains $Name)) {
        return @()
    }
    $array = $Fields.$Name.arrayValue
    if ($null -eq $array -or -not ($array.PSObject.Properties.Name -ccontains "values")) {
        return @()
    }
    return @($array.values | ForEach-Object { [string]$_.stringValue } | Where-Object { $_ })
}

function Invoke-Projection {
    param([string]$CollectionGroup, [string[]]$FieldPaths, [hashtable]$Headers)
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "powershell_7_required_for_live_firestore_precision"
    }
    $uri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:runQuery"
    $request = [ordered]@{
        structuredQuery = [ordered]@{
            select = [ordered]@{
                fields = @($FieldPaths | ForEach-Object { [ordered]@{ fieldPath = $_ } })
            }
            from = @([ordered]@{ collectionId = $CollectionGroup; allDescendants = $true })
        }
    }
    try {
        $response = Invoke-WebRequest -Method Post -Uri $uri -Headers $Headers `
            -ContentType "application/json" -Body ($request | ConvertTo-Json -Depth 10)
        # PowerShell 7 converte per impostazione predefinita i timestamp JSON in
        # DateTime, perdendo l'eventuale precisione nanosecondo di updateTime.
        # Le precondizioni Firestore richiedono invece il valore ISO originale.
        $raw = $response.Content | ConvertFrom-Json -DateKind String
    } catch {
        throw "firestore_readback_failed:$CollectionGroup"
    }
    $items = @()
    foreach ($item in $raw) { $items += $item }
    return @($items | Where-Object {
        $null -ne $_ -and $_.PSObject.Properties.Name -ccontains "document"
    } | ForEach-Object { $_.document })
}

function Invoke-LiveSnapshot {
    $gcloud = Resolve-GcloudExecutable
    $policyOutput = & $gcloud firestore fields ttls list `
        "--project=$ProjectId" "--database=$DatabaseId" --format=json --quiet --verbosity=error 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gcloud_ttl_list_failed" }
    try { $policies = @(([string]($policyOutput -join [Environment]::NewLine)) | ConvertFrom-Json) }
    catch { throw "gcloud_ttl_list_invalid_json" }

    $accessToken = Get-AccessToken
    $headers = @{ Authorization = "Bearer $accessToken" }
    $deviceDocuments = @(Invoke-Projection -CollectionGroup "push_devices" -Headers $headers -FieldPaths @(
        "schema_version", "active", "disabled_reason", "target_value", "token",
        "target_hash", "token_hash", "updated_at", "expires_at"
    ))
    $ownerDocuments = @(Invoke-Projection -CollectionGroup "push_target_owners" -Headers $headers -FieldPaths @("device_id"))
    $capacityDocuments = @(Invoke-Projection -CollectionGroup "push_pilot_state" -Headers $headers -FieldPaths @("active_device_ids"))

    $ownerIds = @{}
    foreach ($document in $ownerDocuments) {
        $ownerId = [string](Get-FieldValue $document.fields "device_id")
        if ($ownerId) { $ownerIds[$ownerId] = $true }
    }
    $capacityIds = @{}
    foreach ($document in $capacityDocuments) {
        foreach ($deviceId in @(Get-StringArrayField $document.fields "active_device_ids")) {
            $capacityIds[$deviceId] = $true
        }
    }

    $devices = foreach ($document in $deviceDocuments) {
        $name = [string]$document.name
        if ($name -cnotmatch '^projects/meteo-friul/databases/\(default\)/documents/push_devices/([^/]+)$') {
            throw "push_device_document_path_invalid"
        }
        $deviceId = [string]$Matches[1]
        $fields = $document.fields
        [PSCustomObject]@{
            documentName = $name
            documentKeyHash = Get-Sha256Text $deviceId
            updateTime = [string]$document.updateTime
            schemaVersion = [string](Get-FieldValue $fields "schema_version")
            active = Get-FieldValue $fields "active"
            disabledReason = [string](Get-FieldValue $fields "disabled_reason")
            hasTargetValue = -not [string]::IsNullOrEmpty([string](Get-FieldValue $fields "target_value"))
            hasLegacyToken = -not [string]::IsNullOrEmpty([string](Get-FieldValue $fields "token"))
            referencedByOwner = $ownerIds.ContainsKey($deviceId)
            referencedByCapacity = $capacityIds.ContainsKey($deviceId)
            updatedAt = Get-FieldValue $fields "updated_at"
            expiresAt = Get-FieldValue $fields "expires_at"
        }
    }
    return [PSCustomObject]@{ policies = @($policies); devices = @($devices); headers = $headers }
}

function Read-FixtureSnapshot {
    if (-not $PolicyFixturePath -or -not $DeviceFixturePath) {
        throw "both_policy_and_device_fixtures_are_required"
    }
    $policies = @(Get-Content -LiteralPath $PolicyFixturePath -Raw | ConvertFrom-Json)
    $devices = @(Get-Content -LiteralPath $DeviceFixturePath -Raw | ConvertFrom-Json)
    return [PSCustomObject]@{ policies = $policies; devices = $devices; headers = $null }
}

if ($ProjectId -cne "meteo-friul" -or $DatabaseId -cne "(default)") {
    throw "firestore_target_mismatch"
}
if (($PolicyFixturePath -and -not $DeviceFixturePath) -or ($DeviceFixturePath -and -not $PolicyFixturePath)) {
    throw "both_policy_and_device_fixtures_are_required"
}
if ($ApplyBackfill -and ($PolicyFixturePath -or $DeviceFixturePath)) {
    throw "fixture_backfill_forbidden"
}
if ($ApplyLegacyCleanup -and ($PolicyFixturePath -or $DeviceFixturePath)) {
    throw "fixture_legacy_cleanup_forbidden"
}
if ($ApplyBackfill -and $ApplyLegacyCleanup) {
    throw "push_device_mutation_modes_are_mutually_exclusive"
}

$snapshot = if ($PolicyFixturePath) { Read-FixtureSnapshot } else { Invoke-LiveSnapshot }
$audit = Test-PushDeviceRetentionSnapshot -Policies $snapshot.policies -Devices $snapshot.devices -RetentionDays 30
$targets = @($audit.backfill)
$targetDigest = Get-Sha256Text ((@($targets | ForEach-Object {
    "$($_.documentKeyHash)|$($_.expectedExpiry.ToString('o'))|$($_.updateTime)"
}) | Sort-Object) -join "`n")
$legacyTargets = @($audit.legacyCleanup)
$legacyTargetDigest = Get-Sha256Text ((@($legacyTargets | ForEach-Object {
    "$($_.documentKeyHash)|$($_.updateTime)"
}) | Sort-Object) -join "`n")
$legacyUpdateTimeDigest = Get-Sha256Text ((@($legacyTargets | ForEach-Object {
    [string]$_.updateTime
}) | Sort-Object) -join "`n")

if (-not $ApplyBackfill -and -not $ApplyLegacyCleanup) {
    [PSCustomObject]@{
        schemaVersion = "push-device-retention-operation-v1"
        mode = "audit-dry-run"
        ready = $audit.ready
        readyForBackfill = $audit.readyForBackfill
        retentionDays = 30
        activeDeviceCount = $audit.activeDeviceCount
        inactiveInvalidTokenCount = $audit.inactiveInvalidTokenCount
        legacyUnclassifiedCount = $audit.legacyUnclassifiedCount
        legacyCleanupCount = $audit.legacyCleanupCount
        legacyTargetSetSha256 = $legacyTargetDigest
        legacyUpdateTimeSetSha256 = $legacyUpdateTimeDigest
        backfillCount = $audit.backfillCount
        targetSetSha256 = $targetDigest
        blockingCount = $audit.blockingCount
        findings = $audit.findings
    } | ConvertTo-Json -Depth 8
    exit $(if ($audit.ready) { 0 } else { 2 })
}

if ($ApplyLegacyCleanup) {
    $legacyPlan = New-PushDeviceLegacyCleanupPlan `
        -Audit $audit `
        -ExpectedTargetSetSha256 $ExpectedLegacyTargetSetSha256 `
        -ActualTargetSetSha256 $legacyTargetDigest
    $legacyCommitUri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:commit"
    $legacyCommitRequest = [ordered]@{ writes = @($legacyPlan.writes) }
    try {
        $legacyCommitResult = Invoke-RestMethod -Method Post -Uri $legacyCommitUri -Headers $snapshot.headers `
            -ContentType "application/json" -Body ($legacyCommitRequest | ConvertTo-Json -Depth 10)
    } catch {
        throw "firestore_push_device_legacy_atomic_delete_failed"
    }
    if (@($legacyCommitResult.writeResults).Count -ne 1) {
        throw "firestore_push_device_legacy_delete_result_invalid"
    }
    $legacyPostSnapshot = Invoke-LiveSnapshot
    $legacyPostAudit = Test-PushDeviceRetentionSnapshot `
        -Policies $legacyPostSnapshot.policies `
        -Devices $legacyPostSnapshot.devices `
        -RetentionDays 30
    if ($legacyPostAudit.legacyCleanupCount -ne 0 -or
        $legacyPostAudit.legacyUnclassifiedCount -ne 0) {
        throw "firestore_push_device_legacy_delete_readback_failed"
    }
    [PSCustomObject]@{
        schemaVersion = "push-device-retention-operation-v1"
        mode = "legacy-hard-delete-applied"
        ready = $legacyPostAudit.ready
        deleteCount = 1
        legacyTargetSetSha256 = $legacyTargetDigest
        legacyUpdateTimeSetSha256 = $legacyUpdateTimeDigest
        commitTimeUtc = [string]$legacyCommitResult.commitTime
        remainingBlockingCount = $legacyPostAudit.blockingCount
        findings = $legacyPostAudit.findings
    } | ConvertTo-Json -Depth 8
    exit 0
}

if (-not $audit.readyForBackfill) { throw "push_device_backfill_preflight_failed" }
if ($targets.Count -eq 0) {
    [PSCustomObject]@{
        schemaVersion = "push-device-retention-operation-v1"
        mode = "already-backfilled"
        ready = $audit.ready
        writeCount = 0
        targetSetSha256 = $targetDigest
    } | ConvertTo-Json -Depth 5
    exit 0
}
if ($ExpectedTargetSetSha256 -cnotmatch '^[0-9a-f]{64}$' -or
    $ExpectedTargetSetSha256 -cne $targetDigest) {
    throw "push_device_backfill_target_digest_mismatch"
}

$writes = foreach ($target in $targets) {
    [void][DateTimeOffset]::Parse([string]$target.updateTime)
    [ordered]@{
        update = [ordered]@{
            name = [string]$target.documentName
            fields = [ordered]@{
                expires_at = [ordered]@{
                    timestampValue = $target.expectedExpiry.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ")
                }
            }
        }
        updateMask = [ordered]@{ fieldPaths = @("expires_at") }
        currentDocument = [ordered]@{
            updateTime = [string]$target.updateTime
        }
    }
}
$commitUri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:commit"
$commitRequest = [ordered]@{ writes = @($writes) }
try {
    $commitResult = Invoke-RestMethod -Method Post -Uri $commitUri -Headers $snapshot.headers `
        -ContentType "application/json" -Body ($commitRequest | ConvertTo-Json -Depth 12)
} catch {
    throw "firestore_push_device_atomic_backfill_failed"
}
if (@($commitResult.writeResults).Count -ne $targets.Count) {
    throw "firestore_push_device_backfill_result_invalid"
}

$postSnapshot = Invoke-LiveSnapshot
$postAudit = Test-PushDeviceRetentionSnapshot -Policies $postSnapshot.policies -Devices $postSnapshot.devices -RetentionDays 30
if ($postAudit.backfillCount -ne 0) { throw "firestore_push_device_backfill_readback_failed" }

[PSCustomObject]@{
    schemaVersion = "push-device-retention-operation-v1"
    mode = "backfill-applied"
    ready = $postAudit.ready
    writeCount = $targets.Count
    targetSetSha256 = $targetDigest
    commitTimeUtc = [string]$commitResult.commitTime
    remainingBlockingCount = $postAudit.blockingCount
    findings = $postAudit.findings
} | ConvertTo-Json -Depth 8
