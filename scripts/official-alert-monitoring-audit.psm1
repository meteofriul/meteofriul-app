Set-StrictMode -Version Latest

function Get-OfficialAlertMonitoringProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) {
        return $null
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Assert-OfficialAlertMonitoringSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Snapshot,

        [string]$ExpectedAccount = "meteofriul@gmail.com",

        [string]$ExpectedProjectId = "meteo-friul",

        [string]$ExpectedJobName = "meteofriul-official-alert-sync",

        [string]$ExpectedPolicyDisplayName = "Meteo Friul - job allerte ufficiali",

        [string]$ExpectedChannelName =
            "projects/meteo-friul/notificationChannels/11334808831344967323",

        [string]$ExpectedChannelDisplayName = "Meteo Friul - notifiche operative"
    )

    if ([int](Get-OfficialAlertMonitoringProperty $Snapshot "schemaVersion") -ne 1) {
        throw "official_alert_monitoring_schema_unsupported"
    }

    $identity = Get-OfficialAlertMonitoringProperty $Snapshot "identity"
    $account = [string](Get-OfficialAlertMonitoringProperty $identity "activeAccount")
    $projectId = [string](Get-OfficialAlertMonitoringProperty $identity "projectId")
    if ($account -cne $ExpectedAccount) {
        throw "official_alert_monitoring_account_mismatch"
    }
    if ($projectId -cne $ExpectedProjectId) {
        throw "official_alert_monitoring_project_mismatch"
    }

    $matchingPolicies = @(
        @(Get-OfficialAlertMonitoringProperty $Snapshot "alertPolicies") |
            Where-Object {
                [string](Get-OfficialAlertMonitoringProperty $_ "displayName") -ceq
                    $ExpectedPolicyDisplayName
            }
    )
    if ($matchingPolicies.Count -ne 1) {
        throw "official_alert_monitoring_policy_count_invalid"
    }
    $policy = $matchingPolicies[0]
    if ((Get-OfficialAlertMonitoringProperty $policy "enabled") -ne $true) {
        throw "official_alert_monitoring_policy_disabled"
    }
    if ([string](Get-OfficialAlertMonitoringProperty $policy "combiner") -cne "OR") {
        throw "official_alert_monitoring_combiner_invalid"
    }

    $conditions = @(Get-OfficialAlertMonitoringProperty $policy "conditions")
    if ($conditions.Count -ne 1) {
        throw "official_alert_monitoring_condition_count_invalid"
    }
    $condition = $conditions[0]
    $threshold = Get-OfficialAlertMonitoringProperty $condition "conditionThreshold"
    $expectedFilter =
        "resource.type=`"cloud_run_job`" AND " +
        "resource.labels.job_name=`"$ExpectedJobName`" AND " +
        "metric.type=`"run.googleapis.com/job/completed_execution_count`" AND " +
        "metric.labels.result=`"failed`""
    if ([string](Get-OfficialAlertMonitoringProperty $threshold "filter") -cne $expectedFilter) {
        throw "official_alert_monitoring_job_filter_invalid"
    }
    if ([string](Get-OfficialAlertMonitoringProperty $threshold "comparison") -cne
        "COMPARISON_GT" -or
        [double](Get-OfficialAlertMonitoringProperty $threshold "thresholdValue") -ne 1 -or
        [string](Get-OfficialAlertMonitoringProperty $threshold "duration") -cne "0s") {
        throw "official_alert_monitoring_threshold_invalid"
    }
    $trigger = Get-OfficialAlertMonitoringProperty $threshold "trigger"
    if ([int](Get-OfficialAlertMonitoringProperty $trigger "count") -ne 1) {
        throw "official_alert_monitoring_trigger_invalid"
    }
    $aggregations = @(Get-OfficialAlertMonitoringProperty $threshold "aggregations")
    if ($aggregations.Count -ne 1 -or
        [string](Get-OfficialAlertMonitoringProperty $aggregations[0] "alignmentPeriod") -cne
            "18000s" -or
        [string](Get-OfficialAlertMonitoringProperty $aggregations[0] "perSeriesAligner") -cne
            "ALIGN_SUM") {
        throw "official_alert_monitoring_window_invalid"
    }

    $documentation = Get-OfficialAlertMonitoringProperty $policy "documentation"
    $documentationText = [string](
        Get-OfficialAlertMonitoringProperty $documentation "content"
    )
    if (-not $documentationText.Contains($ExpectedJobName) -or
        $documentationText.Contains("meteofriul-alert-sync-pilot")) {
        throw "official_alert_monitoring_documentation_invalid"
    }

    $notificationChannels = @(
        Get-OfficialAlertMonitoringProperty $policy "notificationChannels"
    )
    if ($notificationChannels.Count -ne 1 -or
        [string]$notificationChannels[0] -cne $ExpectedChannelName) {
        throw "official_alert_monitoring_policy_channel_invalid"
    }

    $matchingChannels = @(
        @(Get-OfficialAlertMonitoringProperty $Snapshot "notificationChannels") |
            Where-Object {
                [string](Get-OfficialAlertMonitoringProperty $_ "name") -ceq
                    $ExpectedChannelName
            }
    )
    if ($matchingChannels.Count -ne 1) {
        throw "official_alert_monitoring_channel_count_invalid"
    }
    $channel = $matchingChannels[0]
    if ((Get-OfficialAlertMonitoringProperty $channel "enabled") -ne $true -or
        [string](Get-OfficialAlertMonitoringProperty $channel "type") -cne "email" -or
        [string](Get-OfficialAlertMonitoringProperty $channel "displayName") -cne
            $ExpectedChannelDisplayName) {
        throw "official_alert_monitoring_channel_invalid"
    }

    return [PSCustomObject]@{
        Status = "PASS"
        JobName = $ExpectedJobName
        PolicyName = [string](Get-OfficialAlertMonitoringProperty $policy "name")
        ChannelName = [string](Get-OfficialAlertMonitoringProperty $channel "name")
        WindowSeconds = 18000
        FailureThreshold = 2
    }
}

Export-ModuleMember -Function Assert-OfficialAlertMonitoringSnapshot
