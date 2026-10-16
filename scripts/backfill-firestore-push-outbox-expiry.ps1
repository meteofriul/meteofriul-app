[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$ProjectId = "meteo-friul",
    [string]$DatabaseId = "(default)",
    [string]$GcloudPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expected = [ordered]@{
    push_official_alert_outbox = [PSCustomObject]@{
        missingCount = 1
        retentionDays = 30
        terminalStates = @("sent", "failed_invalid_token")
    }
    push_local_notice_outbox = [PSCustomObject]@{
        missingCount = 3
        retentionDays = 14
        terminalStates = @("sent", "failed_invalid_token")
    }
}

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

function ConvertTo-UtcTimestamp {
    param([object]$Value, [string]$FailureCode)
    $parsed = [DateTimeOffset]::MinValue
    $ok = $false
    if ($Value -is [DateTimeOffset]) {
        $parsed = [DateTimeOffset]$Value
        $ok = $true
    } elseif ($Value -is [DateTime]) {
        $parsed = [DateTimeOffset]([DateTime]$Value)
        $ok = $true
    } else {
        $ok = [DateTimeOffset]::TryParse([string]$Value, [ref]$parsed)
    }
    if (-not $ok) { throw $FailureCode }
    return $parsed.ToUniversalTime()
}

function Get-FieldScalar {
    param([object]$Fields, [string]$Name)
    if ($null -eq $Fields -or -not ($Fields.PSObject.Properties.Name -ccontains $Name)) {
        return $null
    }
    $value = $Fields.$Name
    foreach ($property in @("timestampValue", "stringValue", "integerValue")) {
        if ($null -ne $value -and $value.PSObject.Properties.Name -ccontains $property) {
            return $value.$property
        }
    }
    return $null
}

function Invoke-OutboxProjection {
    param([string]$CollectionGroup, [hashtable]$Headers)
    $uri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:runQuery"
    $fieldPaths = @(
        "schema_version", "kind", "state", "claimed_at", "updated_at",
        "finished_at", "attempt_count", "expires_at"
    )
    $request = [ordered]@{
        structuredQuery = [ordered]@{
            select = [ordered]@{
                fields = @($fieldPaths | ForEach-Object { [ordered]@{ fieldPath = $_ } })
            }
            from = @([ordered]@{ collectionId = $CollectionGroup; allDescendants = $true })
        }
    }
    try {
        $raw = Invoke-RestMethod -Method Post -Uri $uri -Headers $Headers `
            -ContentType "application/json" -Body ($request | ConvertTo-Json -Depth 10)
    } catch {
        throw "firestore_readback_failed:$CollectionGroup"
    }
    $items = @()
    foreach ($item in $raw) { $items += $item }
    return @($items | Where-Object {
        $null -ne $_ -and $_.PSObject.Properties.Name -ccontains "document"
    } | ForEach-Object { $_.document })
}

if ($ProjectId -cne "meteo-friul" -or $DatabaseId -cne "(default)") {
    throw "firestore_target_mismatch"
}

$accessToken = Get-AccessToken
$headers = @{ Authorization = "Bearer $accessToken" }
$writes = New-Object System.Collections.Generic.List[object]
$targetProof = New-Object System.Collections.Generic.List[string]
$preflight = New-Object System.Collections.Generic.List[object]

foreach ($entry in $expected.GetEnumerator()) {
    $collection = [string]$entry.Key
    $contract = $entry.Value
    $documents = @(Invoke-OutboxProjection -CollectionGroup $collection -Headers $headers)
    $missing = @($documents | Where-Object {
        $null -eq (Get-FieldScalar -Fields $_.fields -Name "expires_at")
    })
    if ($missing.Count -ne [int]$contract.missingCount) {
        throw "historical_missing_count_changed:$collection expected=$($contract.missingCount) actual=$($missing.Count)"
    }
    foreach ($document in $missing) {
        $name = [string]$document.name
        $namePattern = "^projects/meteo-friul/databases/\(default\)/documents/$([regex]::Escape($collection))/[^/]+$"
        if ($name -cnotmatch $namePattern) { throw "historical_document_path_invalid:$collection" }
        $state = [string](Get-FieldScalar -Fields $document.fields -Name "state")
        if ($state -notin @($contract.terminalStates)) {
            throw "historical_document_not_terminal:$collection state=$state"
        }
        $finishedAtValue = Get-FieldScalar -Fields $document.fields -Name "finished_at"
        $finishedAt = ConvertTo-UtcTimestamp -Value $finishedAtValue `
            -FailureCode "historical_finished_at_invalid:$collection"
        $updateTime = ConvertTo-UtcTimestamp -Value $document.updateTime `
            -FailureCode "historical_update_time_invalid:$collection"
        $expiresAt = $finishedAt.AddDays([int]$contract.retentionDays)
        if ($expiresAt -le $finishedAt) { throw "historical_expiry_invalid:$collection" }
        $expiresAtText = $expiresAt.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ")
        $updateTimeText = $updateTime.ToString("yyyy-MM-ddTHH:mm:ss.fffffffZ")
        $writes.Add([ordered]@{
            update = [ordered]@{
                name = $name
                fields = [ordered]@{
                    expires_at = [ordered]@{ timestampValue = $expiresAtText }
                }
            }
            updateMask = [ordered]@{ fieldPaths = @("expires_at") }
            currentDocument = [ordered]@{ updateTime = $updateTimeText }
        })
        $targetProof.Add("$name|$state|$expiresAtText|$updateTimeText")
    }
    $preflight.Add([PSCustomObject]@{
        collectionGroup = $collection
        documentCount = $documents.Count
        missingExpiresAt = $missing.Count
        retentionDays = [int]$contract.retentionDays
        terminalOnly = $true
    })
}

if ($writes.Count -ne 4) { throw "historical_write_count_invalid" }
$targetDigest = Get-Sha256Text -Value ((@($targetProof) | Sort-Object) -join "`n")

if (-not $Apply) {
    [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-backfill-v1"
        mode = "dry-run"
        readyToApply = $true
        writeCount = $writes.Count
        targetSetSha256 = $targetDigest
        preflight = $preflight.ToArray()
    } | ConvertTo-Json -Depth 8
    exit 0
}

$commitUri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:commit"
$commitRequest = [ordered]@{ writes = $writes.ToArray() }
try {
    $commitResult = Invoke-RestMethod -Method Post -Uri $commitUri -Headers $headers `
        -ContentType "application/json" -Body ($commitRequest | ConvertTo-Json -Depth 12)
} catch {
    throw "firestore_atomic_backfill_failed"
}
$writeResults = @($commitResult.writeResults)
if ($writeResults.Count -ne 4) { throw "firestore_atomic_backfill_result_invalid" }

$postflight = New-Object System.Collections.Generic.List[object]
foreach ($entry in $expected.GetEnumerator()) {
    $collection = [string]$entry.Key
    $documents = @(Invoke-OutboxProjection -CollectionGroup $collection -Headers $headers)
    $missing = @($documents | Where-Object {
        $null -eq (Get-FieldScalar -Fields $_.fields -Name "expires_at")
    })
    if ($missing.Count -ne 0) { throw "firestore_backfill_readback_failed:$collection" }
    $postflight.Add([PSCustomObject]@{
        collectionGroup = $collection
        documentCount = $documents.Count
        missingOrInvalidExpiresAt = 0
    })
}

[PSCustomObject]@{
    schemaVersion = "firestore-push-ttl-backfill-v1"
    mode = "applied"
    ready = $true
    writeCount = 4
    targetSetSha256 = $targetDigest
    commitTimeUtc = (ConvertTo-UtcTimestamp -Value $commitResult.commitTime -FailureCode "commit_time_invalid").ToString("o")
    postflight = $postflight.ToArray()
} | ConvertTo-Json -Depth 8
