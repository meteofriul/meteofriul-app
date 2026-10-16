$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$fixturePath = Join-Path $scriptRoot "fixtures\official-alert-monitoring\pass.json"
$auditScript = Join-Path $scriptRoot "audit-official-alert-monitoring.ps1"
Import-Module (
    Join-Path $scriptRoot "official-alert-monitoring-audit.psm1"
) -Force

function Get-TestSnapshot {
    Get-Content -LiteralPath $fixturePath -Raw | ConvertFrom-Json
}

function Assert-Test {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw "contract_assertion_failed: $Message"
    }
}

function Assert-ThrowsLike {
    param([scriptblock]$Action, [string]$Pattern, [string]$Message)
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -like "*$Pattern*") {
            return
        }
        throw "contract_wrong_failure: $Message actual=$($_.Exception.Message)"
    }
    throw "contract_missing_failure: $Message"
}

$pass = Assert-OfficialAlertMonitoringSnapshot -Snapshot (Get-TestSnapshot)
Assert-Test ($pass.Status -ceq "PASS") "la configurazione valida deve passare"
Assert-Test ($pass.FailureThreshold -eq 2) "la soglia deve restare due fallimenti"
Assert-Test ($pass.WindowSeconds -eq 18000) "la finestra deve restare cinque ore"

$legacyJob = Get-TestSnapshot
$legacyJob.alertPolicies[0].conditions[0].conditionThreshold.filter =
    $legacyJob.alertPolicies[0].conditions[0].conditionThreshold.filter.Replace(
        "meteofriul-official-alert-sync",
        "meteofriul-alert-sync-pilot"
    )
Assert-ThrowsLike {
    Assert-OfficialAlertMonitoringSnapshot -Snapshot $legacyJob
} "official_alert_monitoring_job_filter_invalid" (
    "il vecchio nome pilot non deve superare l'audit"
)

$legacyDocumentation = Get-TestSnapshot
$legacyDocumentation.alertPolicies[0].documentation.content =
    "Controllare meteofriul-alert-sync-pilot."
Assert-ThrowsLike {
    Assert-OfficialAlertMonitoringSnapshot -Snapshot $legacyDocumentation
} "official_alert_monitoring_documentation_invalid" (
    "la documentazione non deve rinviare al job eliminato"
)

$wrongWindow = Get-TestSnapshot
$wrongWindow.alertPolicies[0].conditions[0].conditionThreshold.aggregations[0].alignmentPeriod =
    "3600s"
Assert-ThrowsLike {
    Assert-OfficialAlertMonitoringSnapshot -Snapshot $wrongWindow
} "official_alert_monitoring_window_invalid" (
    "la finestra Monitoring non deve restringersi silenziosamente"
)

$misleadingChannel = Get-TestSnapshot
$misleadingChannel.notificationChannels[0].displayName =
    "Meteo Friul - controllo fonti Eventi"
Assert-ThrowsLike {
    Assert-OfficialAlertMonitoringSnapshot -Snapshot $misleadingChannel
} "official_alert_monitoring_channel_invalid" (
    "il canale condiviso deve avere un nome operativo generico"
)

$auditSource = Get-Content -LiteralPath $auditScript -Raw
Assert-Test ($auditSource -match 'x-goog-user-project') (
    "le letture live devono attribuire la quota al progetto verificato"
)
Assert-Test ($auditSource -match 'nextPageToken') (
    "il collector deve gestire la paginazione Monitoring"
)

$fixtureOutput = & $auditScript -SnapshotPath $fixturePath -FixtureMode
$fixtureResult = ($fixtureOutput -join "`n") | ConvertFrom-Json
Assert-Test ($fixtureResult.Status -ceq "PASS") (
    "lo script deve supportare una verifica fixture senza credenziali cloud"
)

Write-Host "Official alert Monitoring audit contract tests: OK"
