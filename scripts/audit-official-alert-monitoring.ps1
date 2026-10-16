[CmdletBinding()]
param(
    [string]$SnapshotPath,

    [switch]$FixtureMode,

    [string]$ExpectedAccount = "meteofriul@gmail.com",

    [string]$ProjectId = "meteo-friul",

    [string]$ExpectedJobName = "meteofriul-official-alert-sync",

    [string]$ExpectedPolicyDisplayName = "Meteo Friul - job allerte ufficiali",

    [string]$ExpectedChannelName =
        "projects/meteo-friul/notificationChannels/11334808831344967323",

    [string]$ExpectedChannelDisplayName = "Meteo Friul - notifiche operative",

    [string]$GcloudPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Import-Module (
    Join-Path $PSScriptRoot "official-alert-monitoring-audit.psm1"
) -Force

function Resolve-OfficialAlertAuditGcloud {
    param([string]$Candidate)
    if ($Candidate) {
        $resolved = [IO.Path]::GetFullPath($Candidate)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "official_alert_monitoring_gcloud_not_found"
        }
        return $resolved
    }
    foreach ($commandName in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    $fallback = Join-Path $env:LOCALAPPDATA (
        "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    )
    if (Test-Path -LiteralPath $fallback -PathType Leaf) {
        return $fallback
    }
    throw "official_alert_monitoring_gcloud_not_found"
}

function Invoke-OfficialAlertAuditGcloudText {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureCode`: $($output -join ' ')"
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Invoke-OfficialAlertAuditGet {
    param([string]$Uri, [string]$AccessToken, [string]$FailureCode)
    try {
        return Invoke-RestMethod -Method Get -Uri $Uri -Headers @{
            Authorization = "Bearer $AccessToken"
            "x-goog-user-project" = $ProjectId
        }
    } catch {
        throw "$FailureCode`: $($_.Exception.Message)"
    }
}

function Get-OfficialAlertAuditPages {
    param([string]$Collection, [string]$AccessToken, [string]$PropertyName)
    $rows = [Collections.Generic.List[object]]::new()
    $pageToken = ""
    $seenTokens = [Collections.Generic.HashSet[string]]::new(
        [StringComparer]::Ordinal
    )
    do {
        if (-not $seenTokens.Add($pageToken)) {
            throw "official_alert_monitoring_pagination_cycle"
        }
        $uri = "https://monitoring.googleapis.com/v3/projects/$ProjectId/" +
            "${Collection}?pageSize=1000"
        if ($pageToken) {
            $uri += "&pageToken=$([Uri]::EscapeDataString($pageToken))"
        }
        $page = Invoke-OfficialAlertAuditGet `
            -Uri $uri `
            -AccessToken $AccessToken `
            -FailureCode "official_alert_monitoring_${Collection}_read_failed"
        $property = $page.PSObject.Properties[$PropertyName]
        if ($null -ne $property) {
            foreach ($row in @($property.Value)) {
                $rows.Add($row)
            }
        }
        $nextProperty = $page.PSObject.Properties["nextPageToken"]
        $pageToken = if ($null -ne $nextProperty) {
            [string]$nextProperty.Value
        } else {
            ""
        }
    } while ($pageToken)
    return $rows.ToArray()
}

function Get-LiveOfficialAlertMonitoringSnapshot {
    $gcloud = Resolve-OfficialAlertAuditGcloud -Candidate $GcloudPath
    $account = Invoke-OfficialAlertAuditGcloudText `
        -Executable $gcloud `
        -Arguments @(
            "auth", "list", "--filter=status:ACTIVE", "--format=value(account)",
            "--quiet"
        ) `
        -FailureCode "official_alert_monitoring_account_read_failed"
    if (($account -split "`r?`n").Count -ne 1) {
        throw "official_alert_monitoring_active_account_ambiguous"
    }
    $configuredProject = Invoke-OfficialAlertAuditGcloudText `
        -Executable $gcloud `
        -Arguments @("config", "get-value", "project", "--quiet") `
        -FailureCode "official_alert_monitoring_project_read_failed"
    $accessToken = Invoke-OfficialAlertAuditGcloudText `
        -Executable $gcloud `
        -Arguments @(
            "auth", "print-access-token", "--account=$ExpectedAccount",
            "--project=$ProjectId", "--quiet"
        ) `
        -FailureCode "official_alert_monitoring_token_failed"

    return [PSCustomObject]@{
        schemaVersion = 1
        identity = [PSCustomObject]@{
            activeAccount = $account
            projectId = $configuredProject
        }
        alertPolicies = @(Get-OfficialAlertAuditPages `
            -Collection "alertPolicies" `
            -AccessToken $accessToken `
            -PropertyName "alertPolicies")
        notificationChannels = @(Get-OfficialAlertAuditPages `
            -Collection "notificationChannels" `
            -AccessToken $accessToken `
            -PropertyName "notificationChannels")
    }
}

$hasSnapshot = [bool]$SnapshotPath
if ($hasSnapshot -ne [bool]$FixtureMode) {
    throw "official_alert_monitoring_fixture_mode_invalid"
}

$snapshot = if ($hasSnapshot) {
    $resolved = [IO.Path]::GetFullPath($SnapshotPath)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "official_alert_monitoring_snapshot_not_found"
    }
    Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
} else {
    Get-LiveOfficialAlertMonitoringSnapshot
}

$result = Assert-OfficialAlertMonitoringSnapshot `
    -Snapshot $snapshot `
    -ExpectedAccount $ExpectedAccount `
    -ExpectedProjectId $ProjectId `
    -ExpectedJobName $ExpectedJobName `
    -ExpectedPolicyDisplayName $ExpectedPolicyDisplayName `
    -ExpectedChannelName $ExpectedChannelName `
    -ExpectedChannelDisplayName $ExpectedChannelDisplayName

$result | ConvertTo-Json -Depth 5
