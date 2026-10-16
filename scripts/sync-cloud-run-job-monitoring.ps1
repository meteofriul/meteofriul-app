[CmdletBinding()]
param(
    [ValidateSet("Audit", "Apply")]
    [string]$Mode = "Audit",

    [string]$ConfigPath,

    [string]$PolicyKey,

    [string]$ExpectedAccount = "meteofriul@gmail.com",

    [string]$GcloudPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $PSScriptRoot "cloud-run-job-monitoring-policies.json"
}

function Resolve-MonitoringGcloud {
    if ($GcloudPath) {
        $resolved = [IO.Path]::GetFullPath($GcloudPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "monitoring_gcloud_not_found"
        }
        return $resolved
    }
    foreach ($name in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    $fallback = Join-Path $env:LOCALAPPDATA (
        "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    )
    if (Test-Path -LiteralPath $fallback -PathType Leaf) { return $fallback }
    throw "monitoring_gcloud_not_found"
}

function Invoke-MonitoringGcloudText {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$FailureCode`: $output" }
    return (($output | Out-String).Trim())
}

function Get-MonitoringPolicies {
    param([string]$ProjectId, [hashtable]$Headers)
    $policies = [Collections.Generic.List[object]]::new()
    $pageToken = ""
    do {
        $uri = "https://monitoring.googleapis.com/v3/projects/$ProjectId/" +
            "alertPolicies?pageSize=1000"
        if ($pageToken) {
            $uri += "&pageToken=$([Uri]::EscapeDataString($pageToken))"
        }
        $page = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers
        foreach ($policy in @($page.alertPolicies)) { $policies.Add($policy) }
        $tokenProperty = $page.PSObject.Properties["nextPageToken"]
        $pageToken = if ($null -ne $tokenProperty) {
            [string]$tokenProperty.Value
        } else { "" }
    } while ($pageToken)
    return $policies.ToArray()
}

function New-DesiredMonitoringPolicy {
    param([object]$Definition, [string]$Channel)
    $conditionType = [string](Get-MonitoringPropertyValue `
        $Definition "conditionType" "failed_execution_count")
    $metricResult = if ($conditionType -in @(
        "successful_execution_absent",
        "successful_execution_window"
    )) {
        "succeeded"
    } else { "failed" }
    $metricFilter = (
        'resource.type="cloud_run_job" AND ' +
        'resource.labels.job_name="' +
        [string]$Definition.jobName + '" AND ' +
        'metric.type="run.googleapis.com/job/completed_execution_count" AND ' +
        'metric.labels.result="' + $metricResult + '"'
    )
    $condition = [ordered]@{
        displayName = [string]$Definition.conditionDisplayName
    }
    if ($conditionType -ceq "failed_execution_count") {
        $condition.conditionThreshold = [ordered]@{
            filter = $metricFilter
            comparison = "COMPARISON_GT"
            thresholdValue = [int]$Definition.failedExecutionThreshold - 1
            duration = "0s"
            trigger = [ordered]@{ count = 1 }
            aggregations = @(
                [ordered]@{
                    alignmentPeriod = (
                        [string]$Definition.alignmentPeriodSeconds + "s"
                    )
                    perSeriesAligner = "ALIGN_SUM"
                }
            )
        }
    } elseif ($conditionType -ceq "successful_execution_absent") {
        $condition.conditionAbsent = [ordered]@{
            filter = $metricFilter
            duration = [string]$Definition.absenceDurationSeconds + "s"
            trigger = [ordered]@{ count = 1 }
            aggregations = @(
                [ordered]@{
                    alignmentPeriod = (
                        [string]$Definition.alignmentPeriodSeconds + "s"
                    )
                    perSeriesAligner = "ALIGN_SUM"
                }
            )
        }
    } elseif ($conditionType -ceq "successful_execution_window") {
        $condition.conditionThreshold = [ordered]@{
            filter = $metricFilter
            comparison = "COMPARISON_LT"
            thresholdValue = 1
            duration = [string]$Definition.durationSeconds + "s"
            evaluationMissingData = "EVALUATION_MISSING_DATA_ACTIVE"
            trigger = [ordered]@{ count = 1 }
            aggregations = @(
                [ordered]@{
                    alignmentPeriod = (
                        [string]$Definition.alignmentPeriodSeconds + "s"
                    )
                    perSeriesAligner = "ALIGN_SUM"
                }
            )
        }
    } elseif ($conditionType -ceq "scheduler_log_failure") {
        $condition.conditionMatchedLog = [ordered]@{
            filter = (
                'resource.type="cloud_scheduler_job" AND ' +
                'resource.labels.job_id="' +
                [string]$Definition.jobName + '" AND severity>=ERROR'
            )
        }
    } elseif ($conditionType -ceq "job_log_match") {
        $condition.conditionMatchedLog = [ordered]@{
            filter = (
                'resource.type="cloud_run_job" AND ' +
                'resource.labels.job_name="' +
                [string]$Definition.jobName + '" AND ' +
                'jsonPayload.event="' +
                [string]$Definition.logEvent + '"'
            )
        }
    } else {
        throw "monitoring_condition_type_invalid: $conditionType"
    }

    $labels = [ordered]@{}
    foreach ($property in @($Definition.labels.PSObject.Properties)) {
        $labels[$property.Name] = [string]$property.Value
    }
    if ($conditionType -ne "failed_execution_count") {
        $labels["managed_key"] = [string]$Definition.policyKey
    }

    $autoCloseSeconds = [int](Get-MonitoringPropertyValue `
        $Definition "autoCloseSeconds" 86400)
    $alertStrategy = [ordered]@{
        autoClose = [string]$autoCloseSeconds + "s"
    }
    $notifyOnRecovery = Get-MonitoringPropertyValue `
        $Definition "notifyOnRecovery" $null
    if ($null -ne $notifyOnRecovery) {
        $alertStrategy.notificationPrompts = if ([bool]$notifyOnRecovery) {
            @("OPENED", "CLOSED")
        } else { @("OPENED") }
    }
    if ($conditionType -in @("scheduler_log_failure", "job_log_match")) {
        $rateLimitSeconds = [int](Get-MonitoringPropertyValue `
            $Definition "notificationRateLimitSeconds" 3600)
        $alertStrategy.notificationRateLimit = [ordered]@{
            period = [string]$rateLimitSeconds + "s"
        }
        $alertStrategy.notificationPrompts = @("OPENED")
    }

    return [ordered]@{
        displayName = [string]$Definition.displayName
        combiner = "OR"
        conditions = @($condition)
        documentation = [ordered]@{
            content = [string]$Definition.documentation
            mimeType = "text/markdown"
        }
        notificationChannels = @($Channel)
        userLabels = [PSCustomObject]$labels
        enabled = $true
        alertStrategy = $alertStrategy
    }
}

function Get-PolicyJobNames {
    param([object]$Policy)
    $serialized = $Policy | ConvertTo-Json -Depth 20 -Compress
    return @(
        [regex]::Matches($serialized, 'meteofriul-[a-z0-9-]+') |
            ForEach-Object Value |
            Sort-Object -Unique
    )
}

function Get-MonitoringPropertyValue {
    param([object]$Object, [string]$Name, [object]$Default)
    if ($null -eq $Object) { return $Default }
    if (
        $Object -is [Collections.IDictionary] -and
        $Object.Contains($Name)
    ) {
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

function Test-PolicyMatches {
    param([object]$Actual, [hashtable]$Desired)
    $actualCondition = @($Actual.conditions)[0]
    $desiredCondition = @($Desired.conditions)[0]
    $conditionMatches = $false
    if ($desiredCondition.Contains("conditionThreshold")) {
        $actualThreshold = Get-MonitoringPropertyValue `
            $actualCondition "conditionThreshold" $null
        $desiredThreshold = $desiredCondition.conditionThreshold
        $desiredEvaluationMissingData = [string](Get-MonitoringPropertyValue `
            $desiredThreshold "evaluationMissingData" "")
        $actualEvaluationMissingData = [string](Get-MonitoringPropertyValue `
            $actualThreshold "evaluationMissingData" "")
        $conditionMatches = (
            $null -ne $actualThreshold -and
            [string]$actualThreshold.filter -ceq [string]$desiredThreshold.filter -and
            [string]$actualThreshold.comparison -ceq
                [string]$desiredThreshold.comparison -and
            [double](Get-MonitoringPropertyValue `
                $actualThreshold "thresholdValue" 0) -eq
                [double]$desiredThreshold.thresholdValue -and
            [string]$actualThreshold.duration -ceq
                [string]$desiredThreshold.duration -and
            $actualEvaluationMissingData -ceq $desiredEvaluationMissingData -and
            [int]$actualThreshold.trigger.count -eq 1 -and
            [string]@($actualThreshold.aggregations)[0].alignmentPeriod -ceq
                [string]@($desiredThreshold.aggregations)[0].alignmentPeriod -and
            [string]@($actualThreshold.aggregations)[0].perSeriesAligner -ceq
                "ALIGN_SUM"
        )
    } elseif ($desiredCondition.Contains("conditionAbsent")) {
        $actualAbsent = Get-MonitoringPropertyValue `
            $actualCondition "conditionAbsent" $null
        $desiredAbsent = $desiredCondition.conditionAbsent
        $conditionMatches = (
            $null -ne $actualAbsent -and
            [string]$actualAbsent.filter -ceq [string]$desiredAbsent.filter -and
            [string]$actualAbsent.duration -ceq [string]$desiredAbsent.duration -and
            [int]$actualAbsent.trigger.count -eq 1 -and
            [string]@($actualAbsent.aggregations)[0].alignmentPeriod -ceq
                [string]@($desiredAbsent.aggregations)[0].alignmentPeriod -and
            [string]@($actualAbsent.aggregations)[0].perSeriesAligner -ceq
                "ALIGN_SUM"
        )
    } elseif ($desiredCondition.Contains("conditionMatchedLog")) {
        $actualMatchedLog = Get-MonitoringPropertyValue `
            $actualCondition "conditionMatchedLog" $null
        $desiredMatchedLog = $desiredCondition.conditionMatchedLog
        $conditionMatches = (
            $null -ne $actualMatchedLog -and
            [string]$actualMatchedLog.filter -ceq
                [string]$desiredMatchedLog.filter
        )
    }
    $actualLabelProperties = @($Actual.userLabels.PSObject.Properties)
    $desiredLabelProperties = @($Desired.userLabels.PSObject.Properties)
    $labelsMatch = $actualLabelProperties.Count -eq $desiredLabelProperties.Count
    foreach ($property in $desiredLabelProperties) {
        $actualProperty = $Actual.userLabels.PSObject.Properties[$property.Name]
        if (
            $null -eq $actualProperty -or
            [string]$actualProperty.Value -cne [string]$property.Value
        ) {
            $labelsMatch = $false
        }
    }
    $promptsMatch = $true
    if ($Desired.alertStrategy.Contains("notificationPrompts")) {
        $actualPrompts = @(
            Get-MonitoringPropertyValue `
                $Actual.alertStrategy "notificationPrompts" @()
        )
        $desiredPrompts = @($Desired.alertStrategy.notificationPrompts)
        $promptsMatch = (
            $actualPrompts.Count -eq $desiredPrompts.Count -and
            [string]::Join("|", $actualPrompts) -ceq
                [string]::Join("|", $desiredPrompts)
        )
    }
    $rateLimitMatches = $true
    if ($Desired.alertStrategy.Contains("notificationRateLimit")) {
        $actualRateLimit = Get-MonitoringPropertyValue `
            $Actual.alertStrategy "notificationRateLimit" $null
        $rateLimitMatches = (
            $null -ne $actualRateLimit -and
            [string]$actualRateLimit.period -ceq
                [string]$Desired.alertStrategy.notificationRateLimit.period
        )
    }
    return (
        [string]$Actual.displayName -ceq [string]$Desired.displayName -and
        [string]$Actual.combiner -ceq "OR" -and
        [bool]$Actual.enabled -and
        [string]$actualCondition.displayName -ceq
            [string]$desiredCondition.displayName -and
        $conditionMatches -and
        @($Actual.notificationChannels).Count -eq 1 -and
        [string]@($Actual.notificationChannels)[0] -ceq
            [string]@($Desired.notificationChannels)[0] -and
        [string]$Actual.documentation.content -ceq
            [string]$Desired.documentation.content -and
        [string]$Actual.documentation.mimeType -ceq "text/markdown" -and
        $labelsMatch -and
        $promptsMatch -and
        $rateLimitMatches -and
        [string]$Actual.alertStrategy.autoClose -ceq
            [string]$Desired.alertStrategy.autoClose
    )
}

$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
if ([int]$config.schemaVersion -ne 2) { throw "monitoring_config_version_invalid" }
$definitions = @($config.policies)
if ($definitions.Count -eq 0) { throw "monitoring_config_empty" }
$duplicates = @(
    $definitions | Group-Object policyKey | Where-Object Count -ne 1
)
if ($duplicates.Count -gt 0) { throw "monitoring_config_duplicate_key" }
$duplicateNames = @(
    $definitions | Group-Object displayName | Where-Object Count -ne 1
)
if ($duplicateNames.Count -gt 0) { throw "monitoring_config_duplicate_name" }
if ($PolicyKey) {
    $definitions = @($definitions | Where-Object {
        [string]$_.policyKey -ceq $PolicyKey
    })
    if ($definitions.Count -ne 1) {
        throw "monitoring_policy_key_not_found: $PolicyKey"
    }
}
foreach ($definition in $definitions) {
    if ([string]$definition.policyKey -cnotmatch '^[a-z][a-z0-9-]{0,62}$') {
        throw "monitoring_policy_key_invalid"
    }
    if ([string]$definition.jobName -cnotmatch '^meteofriul-[a-z0-9-]+$') {
        throw "monitoring_job_name_invalid"
    }
    if (-not [string]$definition.displayName) {
        throw "monitoring_display_name_invalid"
    }
    $conditionType = [string](Get-MonitoringPropertyValue `
        $definition "conditionType" "failed_execution_count")
    if ($conditionType -ceq "failed_execution_count") {
        if ([int]$definition.failedExecutionThreshold -lt 1) {
            throw "monitoring_failure_threshold_invalid"
        }
    } elseif ($conditionType -ceq "successful_execution_absent") {
        $duration = [int]$definition.absenceDurationSeconds
        if ($duration -lt 120 -or $duration % 60 -ne 0) {
            throw "monitoring_absence_duration_invalid"
        }
    } elseif ($conditionType -ceq "successful_execution_window") {
        $duration = [int]$definition.durationSeconds
        if ($duration -lt 60 -or $duration % 60 -ne 0) {
            throw "monitoring_success_window_duration_invalid"
        }
    } elseif ($conditionType -in @("scheduler_log_failure", "job_log_match")) {
        $rateLimit = [int](Get-MonitoringPropertyValue `
            $definition "notificationRateLimitSeconds" 3600)
        if ($rateLimit -lt 300 -or $rateLimit % 60 -ne 0) {
            throw "monitoring_notification_rate_limit_invalid"
        }
        if ($conditionType -ceq "job_log_match" -and
            [string]$definition.logEvent -cnotmatch '^[a-z][a-z0-9_]{0,62}$') {
            throw "monitoring_log_event_invalid"
        }
    } else {
        throw "monitoring_condition_type_invalid: $conditionType"
    }
    if ($conditionType -notin @("scheduler_log_failure", "job_log_match")) {
        $alignment = [int]$definition.alignmentPeriodSeconds
        if (
            $alignment -lt 60 -or $alignment -gt 90000 -or
            $alignment % 60 -ne 0
        ) {
            throw "monitoring_alignment_invalid"
        }
    }
}

$gcloud = Resolve-MonitoringGcloud
$account = Invoke-MonitoringGcloudText -Executable $gcloud -Arguments @(
    "auth", "list", "--filter=status:ACTIVE", "--format=value(account)", "--quiet"
) -FailureCode "monitoring_account_read_failed"
if ($account -cne $ExpectedAccount) { throw "monitoring_account_mismatch: $account" }
$project = Invoke-MonitoringGcloudText -Executable $gcloud -Arguments @(
    "config", "get-value", "project", "--quiet"
) -FailureCode "monitoring_project_read_failed"
if ($project -cne [string]$config.projectId) {
    throw "monitoring_project_mismatch: $project"
}
$token = Invoke-MonitoringGcloudText -Executable $gcloud -Arguments @(
    "auth", "print-access-token", "--account=$ExpectedAccount",
    "--project=$project", "--quiet"
) -FailureCode "monitoring_token_failed"
$headers = @{ Authorization = "Bearer $token" }
$policies = @(Get-MonitoringPolicies -ProjectId $project -Headers $headers)
$results = [Collections.Generic.List[object]]::new()

foreach ($definition in $definitions) {
    $jobName = [string]$definition.jobName
    $policyKey = [string]$definition.policyKey
    $conditionType = [string](Get-MonitoringPropertyValue `
        $definition "conditionType" "failed_execution_count")
    $matches = @(
        $policies | Where-Object {
            [string](Get-MonitoringPropertyValue `
                $_.userLabels "managed_key" "") -ceq $policyKey
        }
    )
    if ($matches.Count -eq 0) {
        $matches = @(
            $policies | Where-Object {
                [string]$_.displayName -ceq [string]$definition.displayName
            }
        )
    }
    if ($matches.Count -eq 0 -and $conditionType -ceq "failed_execution_count") {
        $matches = @(
            $policies | Where-Object {
                -not [string](Get-MonitoringPropertyValue `
                    $_.userLabels "managed_key" "") -and
                (Get-PolicyJobNames $_) -ccontains $jobName
            }
        )
    }
    if ($matches.Count -gt 1) { throw "monitoring_policy_duplicate: $policyKey" }
    $desired = New-DesiredMonitoringPolicy `
        -Definition $definition `
        -Channel ([string]$config.notificationChannel)
    if ($matches.Count -eq 1 -and (Test-PolicyMatches $matches[0] $desired)) {
        $results.Add([PSCustomObject]@{
            key = $policyKey; job = $jobName; status = "unchanged"
        })
        continue
    }
    if ($Mode -ceq "Audit") {
        $status = if ($matches.Count -eq 0) { "missing" } else { "drifted" }
        $results.Add([PSCustomObject]@{
            key = $policyKey; job = $jobName; status = $status
        })
        continue
    }
    $body = $desired | ConvertTo-Json -Depth 20
    if ($matches.Count -eq 0) {
        $uri = "https://monitoring.googleapis.com/v3/projects/$project/alertPolicies"
        $created = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers `
            -ContentType "application/json; charset=utf-8" -Body $body
        $policies += $created
        $results.Add([PSCustomObject]@{
            key = $policyKey; job = $jobName; status = "created"
        })
    } else {
        $actualCondition = @($matches[0].conditions)[0]
        $actualConditionName = [string](Get-MonitoringPropertyValue `
            $actualCondition "name" "")
        $sameConditionKind = (
            ($desired.conditions[0].Contains("conditionThreshold") -and
                $null -ne (Get-MonitoringPropertyValue `
                    $actualCondition "conditionThreshold" $null)) -or
            ($desired.conditions[0].Contains("conditionAbsent") -and
                $null -ne (Get-MonitoringPropertyValue `
                    $actualCondition "conditionAbsent" $null)) -or
            ($desired.conditions[0].Contains("conditionMatchedLog") -and
                $null -ne (Get-MonitoringPropertyValue `
                    $actualCondition "conditionMatchedLog" $null))
        )
        if ($actualConditionName -and $sameConditionKind) {
            $desired.conditions[0]["name"] = $actualConditionName
        }
        $desired.name = [string]$matches[0].name
        $body = $desired | ConvertTo-Json -Depth 20
        $uri = "https://monitoring.googleapis.com/v3/$($matches[0].name)"
        $updated = Invoke-RestMethod -Method Patch -Uri $uri -Headers $headers `
            -ContentType "application/json; charset=utf-8" -Body $body
        $policies = @($policies | Where-Object name -cne $updated.name) + @($updated)
        $results.Add([PSCustomObject]@{
            key = $policyKey; job = $jobName; status = "updated"
        })
    }
}

$failed = @($results | Where-Object status -in @("missing", "drifted"))
[PSCustomObject]@{
    mode = $Mode
    projectId = $project
    notificationChannel = [string]$config.notificationChannel
    policies = $results.ToArray()
    ready = $failed.Count -eq 0
} | ConvertTo-Json -Depth 8
if ($failed.Count -gt 0) { exit 2 }
