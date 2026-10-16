[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [string]$Account = "meteofriul@gmail.com",
    [string]$ProjectId = "meteo-friul",
    [string]$DatabaseId = "(default)",
    [string]$GcloudPath = "",
    [string]$SnapshotFixturePath = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "firestore-community-ttl-audit.psm1") -Force

function Get-CommunityAuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Resolve-CommunityAuditGcloudExecutable {
    if ($GcloudPath) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) {
            throw "community_ttl_gcloud_not_found"
        }
        return (Resolve-Path -LiteralPath $GcloudPath).Path
    }
    foreach ($commandName in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    $fallback = Join-Path $env:LOCALAPPDATA (
        "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    )
    if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) {
        throw "community_ttl_gcloud_not_found"
    }
    return $fallback
}

function Assert-CommunityAuditPowerShellCapabilities {
    if ($PSVersionTable.PSVersion.Major -lt 7) {
        throw "community_ttl_powershell_7_required"
    }
    $convertFromJson = Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($null -eq $convertFromJson -or
        -not $convertFromJson.Parameters.ContainsKey("DateKind")) {
        throw "community_ttl_convertfromjson_datekind_required"
    }
}

function Invoke-CommunityAuditGcloudJson {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$FailureCode
    )
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw $FailureCode }
    $text = [string]($output -join [Environment]::NewLine)
    try { return ($text | ConvertFrom-Json) }
    catch { throw "${FailureCode}_invalid_json" }
}

function Get-CommunityAuditTypedField {
    param([object]$Fields, [string]$FieldPath)
    if ($null -eq $Fields) {
        return [PSCustomObject]@{ type = "missing"; value = $null }
    }
    $fieldProperty = $Fields.PSObject.Properties[$FieldPath]
    if ($null -eq $fieldProperty -or $null -eq $fieldProperty.Value) {
        return [PSCustomObject]@{ type = "missing"; value = $null }
    }
    $field = $fieldProperty.Value
    $knownTypes = @(
        "timestampValue", "stringValue", "integerValue", "doubleValue",
        "booleanValue", "nullValue", "arrayValue", "mapValue",
        "referenceValue", "geoPointValue", "bytesValue"
    )
    foreach ($type in $knownTypes) {
        $typedProperty = $field.PSObject.Properties[$type]
        if ($null -ne $typedProperty) {
            return [PSCustomObject]@{
                type = $type
                value = if ($type -ceq "timestampValue") {
                    $typedProperty.Value
                } else {
                    $null
                }
            }
        }
    }
    return [PSCustomObject]@{ type = "unknown"; value = $null }
}

function Invoke-CommunityAuditProjection {
    param(
        [string]$CollectionGroup,
        [string]$ExpiryField,
        [string]$BaselineField,
        [hashtable]$Headers
    )
    $uri = (
        "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/" +
        "$DatabaseId/documents:runQuery"
    )
    $request = [ordered]@{
        structuredQuery = [ordered]@{
            select = [ordered]@{
                fields = @(
                    [ordered]@{ fieldPath = $ExpiryField },
                    [ordered]@{ fieldPath = $BaselineField }
                )
            }
            from = @([ordered]@{
                collectionId = $CollectionGroup
                allDescendants = $true
            })
        }
    }
    try {
        $response = Invoke-WebRequest -Method Post -Uri $uri -Headers $Headers `
            -ContentType "application/json" `
            -Body ($request | ConvertTo-Json -Depth 10)
        $raw = $response.Content | ConvertFrom-Json -DateKind String
    } catch {
        throw "community_ttl_firestore_readback_failed:$CollectionGroup"
    }
    $records = New-Object System.Collections.Generic.List[object]
    foreach ($item in @($raw)) {
        $document = Get-CommunityAuditProperty $item "document"
        if ($null -eq $document) { continue }
        $fields = Get-CommunityAuditProperty $document "fields"
        $expiry = Get-CommunityAuditTypedField $fields $ExpiryField
        $baseline = Get-CommunityAuditTypedField $fields $BaselineField
        # Deliberately discard document.name and every non-projected field.
        $records.Add([PSCustomObject]@{
            collectionGroup = $CollectionGroup
            expiryType = [string]$expiry.type
            expiresAt = $expiry.value
            baselineType = [string]$baseline.type
            baselineAt = $baseline.value
        })
    }
    return $records.ToArray()
}

function Assert-CommunityAuditLiveIdentity {
    param([object]$Identity)
    $activeAccounts = @(Get-CommunityAuditProperty $Identity "activeAccounts")
    if ($activeAccounts.Count -ne 1 -or [string]$activeAccounts[0] -cne $Account) {
        throw "community_ttl_active_account_mismatch"
    }
    if ([string](Get-CommunityAuditProperty $Identity "configuredAccount") -cne $Account) {
        throw "community_ttl_configured_account_mismatch"
    }
    if ([string](Get-CommunityAuditProperty $Identity "configuredProject") -cne $ProjectId) {
        throw "community_ttl_configured_project_mismatch"
    }
    if ([string](Get-CommunityAuditProperty $Identity "projectId") -cne $ProjectId -or
        [string](Get-CommunityAuditProperty $Identity "projectNumber") -cne "49007668366" -or
        [string](Get-CommunityAuditProperty $Identity "projectState") -cne "ACTIVE") {
        throw "community_ttl_project_identity_mismatch"
    }
    if ([string](Get-CommunityAuditProperty $Identity "databaseName") -cne
            "projects/meteo-friul/databases/(default)" -or
        [string](Get-CommunityAuditProperty $Identity "databaseType") -cne
            "FIRESTORE_NATIVE") {
        throw "community_ttl_database_identity_mismatch"
    }
}

function Invoke-CommunityAuditLiveSnapshot {
    $gcloud = Resolve-CommunityAuditGcloudExecutable
    $activeAccountsRaw = @(
        Invoke-CommunityAuditGcloudJson -Executable $gcloud -Arguments @(
            "auth", "list", "--filter=status:ACTIVE",
            "--format=json(account,status)", "--quiet", "--verbosity=error"
        ) -FailureCode "community_ttl_gcloud_active_account_failed"
    )
    $activeAccounts = @($activeAccountsRaw | ForEach-Object {
        [string](Get-CommunityAuditProperty $_ "account")
    } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

    $configurationRows = @(
        Invoke-CommunityAuditGcloudJson -Executable $gcloud -Arguments @(
            "config", "configurations", "list", "--filter=is_active:true",
            "--format=json(name,is_active,properties.core.account,properties.core.project)",
            "--quiet", "--verbosity=error"
        ) -FailureCode "community_ttl_gcloud_configuration_failed"
    )
    if ($configurationRows.Count -ne 1) {
        throw "community_ttl_active_configuration_ambiguous"
    }
    $properties = Get-CommunityAuditProperty $configurationRows[0] "properties"
    $core = Get-CommunityAuditProperty $properties "core"
    $configuredAccount = [string](Get-CommunityAuditProperty $core "account")
    $configuredProject = [string](Get-CommunityAuditProperty $core "project")
    if ($activeAccounts.Count -ne 1 -or [string]$activeAccounts[0] -cne $Account) {
        throw "community_ttl_active_account_mismatch"
    }
    if ($configuredAccount -cne $Account) {
        throw "community_ttl_configured_account_mismatch"
    }
    if ($configuredProject -cne $ProjectId) {
        throw "community_ttl_configured_project_mismatch"
    }

    $project = Invoke-CommunityAuditGcloudJson -Executable $gcloud -Arguments @(
        "projects", "describe", $ProjectId, "--account=$Account",
        "--format=json(projectId,projectNumber,lifecycleState)",
        "--quiet", "--verbosity=error"
    ) -FailureCode "community_ttl_gcloud_project_failed"
    $database = Invoke-CommunityAuditGcloudJson -Executable $gcloud -Arguments @(
        "firestore", "databases", "describe", "--database=$DatabaseId",
        "--project=$ProjectId", "--account=$Account",
        "--format=json(name,type,locationId)", "--quiet", "--verbosity=error"
    ) -FailureCode "community_ttl_gcloud_database_failed"
    $identity = [PSCustomObject]@{
        activeAccounts = $activeAccounts
        configuredAccount = $configuredAccount
        configuredProject = $configuredProject
        projectId = [string](Get-CommunityAuditProperty $project "projectId")
        projectNumber = [string](Get-CommunityAuditProperty $project "projectNumber")
        projectState = [string](Get-CommunityAuditProperty $project "lifecycleState")
        databaseName = [string](Get-CommunityAuditProperty $database "name")
        databaseType = [string](Get-CommunityAuditProperty $database "type")
    }
    Assert-CommunityAuditLiveIdentity $identity

    $policies = @(
        Invoke-CommunityAuditGcloudJson -Executable $gcloud -Arguments @(
            "firestore", "fields", "ttls", "list",
            "--database=$DatabaseId", "--project=$ProjectId", "--account=$Account",
            "--format=json", "--quiet", "--verbosity=error"
        ) -FailureCode "community_ttl_gcloud_policy_readback_failed"
    )

    $tokenOutput = & $gcloud auth print-access-token "--account=$Account" `
        "--project=$ProjectId" --quiet --verbosity=error 2>&1
    if ($LASTEXITCODE -ne 0) { throw "community_ttl_gcloud_access_token_failed" }
    $accessToken = [string]($tokenOutput -join "").Trim()
    if ([string]::IsNullOrWhiteSpace($accessToken)) {
        throw "community_ttl_gcloud_access_token_empty"
    }
    $headers = @{ Authorization = "Bearer $accessToken" }
    $documents = New-Object System.Collections.Generic.List[object]
    foreach ($contract in @(Get-CommunityTtlAuditContract)) {
        foreach ($record in @(Invoke-CommunityAuditProjection `
            -CollectionGroup ([string]$contract.collectionGroup) `
            -ExpiryField ([string]$contract.field) `
            -BaselineField ([string]$contract.baselineField) `
            -Headers $headers)) {
            $documents.Add($record)
        }
    }
    return [PSCustomObject]@{
        capturedAtUtc = [DateTimeOffset]::UtcNow.ToString("o")
        identity = $identity
        policies = $policies
        documents = $documents.ToArray()
    }
}

function Read-CommunityAuditFixtureSnapshot {
    if (-not (Test-Path -LiteralPath $SnapshotFixturePath -PathType Leaf)) {
        throw "community_ttl_snapshot_fixture_not_found"
    }
    try {
        return Get-Content -LiteralPath $SnapshotFixturePath -Raw |
            ConvertFrom-Json -DateKind String
    } catch {
        throw "community_ttl_snapshot_fixture_invalid"
    }
}

function Write-CommunityAuditEvidence {
    param([object]$Evidence)
    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        throw "community_ttl_output_path_required"
    }
    $resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
    if (Test-Path -LiteralPath $resolvedOutput -PathType Container) {
        throw "community_ttl_output_path_is_directory"
    }
    $parent = Split-Path -Parent $resolvedOutput
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "community_ttl_output_parent_missing"
    }
    if ((Test-Path -LiteralPath $resolvedOutput) -and -not $Force) {
        throw "community_ttl_output_exists"
    }
    $temporaryOutput = Join-Path $parent (
        ".$([IO.Path]::GetFileName($resolvedOutput)).$PID.tmp"
    )
    if (Test-Path -LiteralPath $temporaryOutput) {
        throw "community_ttl_output_temporary_exists"
    }
    $json = $Evidence | ConvertTo-Json -Depth 10
    try {
        [IO.File]::WriteAllText(
            $temporaryOutput,
            "$json$([Environment]::NewLine)",
            [Text.UTF8Encoding]::new($false)
        )
        Move-Item -LiteralPath $temporaryOutput -Destination $resolvedOutput -Force:$Force
    } finally {
        if (Test-Path -LiteralPath $temporaryOutput) {
            Remove-Item -LiteralPath $temporaryOutput -Force
        }
    }
    return [PSCustomObject]@{ path = $resolvedOutput; json = $json }
}

if ($Account -cne "meteofriul@gmail.com" -or
    $ProjectId -cne "meteo-friul" -or
    $DatabaseId -cne "(default)") {
    throw "community_ttl_target_mismatch"
}
Assert-CommunityAuditPowerShellCapabilities

$sourceMode = if ($SnapshotFixturePath) { "fixture-read-only" } else { "live-read-only" }
$snapshot = if ($SnapshotFixturePath) {
    Read-CommunityAuditFixtureSnapshot
} else {
    Invoke-CommunityAuditLiveSnapshot
}
$capturedAt = Get-CommunityAuditProperty $snapshot "capturedAtUtc"
if ($null -eq $capturedAt) { $capturedAt = [DateTimeOffset]::UtcNow }
$audit = Test-FirestoreCommunityTtlSnapshot `
    -Identity (Get-CommunityAuditProperty $snapshot "identity") `
    -Policies @(Get-CommunityAuditProperty $snapshot "policies") `
    -Documents @(Get-CommunityAuditProperty $snapshot "documents") `
    -CapturedAtUtc $capturedAt `
    -SourceMode $sourceMode
$written = Write-CommunityAuditEvidence $audit
Write-Output $written.json
if (-not $audit.ready) {
    throw "firestore_community_ttl_audit_failed: blocking_count=$($audit.blockingCount)"
}
