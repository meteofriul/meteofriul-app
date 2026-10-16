[CmdletBinding()]
param(
    [ValidateSet("Live", "Fixture")]
    [string]$Mode = "Live",
    [ValidateSet("PreActivation", "Final")]
    [string]$Stage = "PreActivation",
    [string]$SnapshotFixturePath = "",
    [string]$GcloudPath = "",
    [switch]$PassThru
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Mode = if ($Mode -ieq "Fixture") { "Fixture" } else { "Live" }
$Stage = if ($Stage -ieq "PreActivation") {
    "PreActivation"
} else {
    "Final"
}

Import-Module (
    Join-Path $PSScriptRoot "community-moderation-runtime-audit.psm1"
) -Force

$ExpectedAccount = "meteofriul@gmail.com"
$ExpectedProjectId = "meteo-friul"
$ExpectedProjectNumber = "49007668366"
$ExpectedRegion = "europe-west1"
$ExpectedJobName = "meteofriul-community-moderation-digest"
$ExpectedSchedulerName = "community-moderation-digest"
$ExpectedRuntimeServiceAccount = (
    "community-moderation-digest@meteo-friul.iam.gserviceaccount.com"
)
$ExpectedSchedulerServiceAccount = (
    "community-moderation-scheduler@meteo-friul.iam.gserviceaccount.com"
)
$ExpectedNotificationChannel = (
    "projects/meteo-friul/notificationChannels/11334808831344967323"
)
$ExpectedImage = (
    "europe-west1-docker.pkg.dev/meteo-friul/" +
    "cloud-run-source-deploy/meteofriul-api@sha256:" +
    "07c50b39437ecb07e9fd707fd8cd60e706d9f5822637652f30bfb5d6063ce0f5"
)

function Get-AuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Resolve-AuditGcloud {
    if ($GcloudPath) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) {
            throw "community_moderation_runtime_gcloud_not_found"
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
        throw "community_moderation_runtime_gcloud_not_found"
    }
    return $fallback
}

function Invoke-AuditGcloudText {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$FailureCode
    )
    $output = @(& $Executable @Arguments)
    if ($LASTEXITCODE -ne 0) { throw $FailureCode }
    return ([string]($output -join [Environment]::NewLine)).Trim()
}

function Invoke-AuditGcloudJson {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$FailureCode
    )
    $text = Invoke-AuditGcloudText -Executable $Executable `
        -Arguments $Arguments -FailureCode $FailureCode
    if ([string]::IsNullOrWhiteSpace($text)) { return @() }
    try { return ($text | ConvertFrom-Json) }
    catch { throw "${FailureCode}_invalid_json" }
}

function ConvertTo-AuditSeconds {
    param([object]$Value)
    if ($null -eq $Value) { return $null }
    $text = [string]$Value
    if ($text -cmatch '^(?<seconds>[0-9]+)(?:\.0+)?s$') {
        return [int]$Matches.seconds
    }
    $number = 0
    if ([int]::TryParse($text, [ref]$number)) { return $number }
    return $null
}

function ConvertTo-AuditIamBindings {
    param([object]$Bindings)
    return @(@($Bindings) | ForEach-Object {
        $condition = Get-AuditProperty $_ "condition"
        [PSCustomObject]@{
            role = [string](Get-AuditProperty $_ "role")
            members = @(
                @(Get-AuditProperty $_ "members") |
                    ForEach-Object { [string]$_ } |
                    Sort-Object -Unique
            )
            condition = if ($null -eq $condition) { $null } else {
                [PSCustomObject]@{
                    expression = [string](
                        Get-AuditProperty $condition "expression"
                    )
                }
            }
        }
    })
}

function Get-MonitoringAlertPolicies {
    param([hashtable]$Headers)
    $rows = @()
    $uri = (
        "https://monitoring.googleapis.com/v3/projects/$ExpectedProjectId/" +
        "alertPolicies?pageSize=1000"
    )
    do {
        $page = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers
        $pageRows = Get-AuditProperty $page "alertPolicies"
        if ($null -ne $pageRows) { $rows += @($pageRows) }
        $next = [string](Get-AuditProperty $page "nextPageToken")
        $uri = if ($next) {
            (
                "https://monitoring.googleapis.com/v3/projects/" +
                "$ExpectedProjectId/alertPolicies?pageSize=1000&pageToken=" +
                [uri]::EscapeDataString($next)
            )
        } else { $null }
    } while ($null -ne $uri)
    return @($rows)
}

function Get-AllCloudSchedulerJobs {
    param([hashtable]$Headers, [object[]]$Locations)
    $rows = @()
    foreach ($location in $Locations) {
        $locationId = [string](Get-AuditProperty $location "locationId")
        if ([string]::IsNullOrWhiteSpace($locationId)) {
            $locationId = (
                [string](Get-AuditProperty $location "name") -split '/'
            )[-1]
        }
        if ([string]::IsNullOrWhiteSpace($locationId)) {
            throw "community_moderation_runtime_scheduler_location_invalid"
        }
        $uri = (
            "https://cloudscheduler.googleapis.com/v1/projects/" +
            "$ExpectedProjectId/locations/$locationId/jobs?pageSize=500"
        )
        do {
            try {
                $page = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers
            } catch {
                throw (
                    "community_moderation_runtime_scheduler_list_failed:" +
                    $locationId
                )
            }
            $pageRows = Get-AuditProperty $page "jobs"
            if ($null -ne $pageRows) { $rows += @($pageRows) }
            $next = [string](Get-AuditProperty $page "nextPageToken")
            $uri = if ($next) {
                (
                    "https://cloudscheduler.googleapis.com/v1/projects/" +
                    "$ExpectedProjectId/locations/$locationId/jobs?" +
                    "pageSize=500&pageToken=" + [uri]::EscapeDataString($next)
                )
            } else { $null }
        } while ($null -ne $uri)
    }
    return @($rows)
}

function ConvertTo-AuditAlertPolicy {
    param([object]$Policy)
    $strategy = Get-AuditProperty $Policy "alertStrategy"
    $rateLimit = Get-AuditProperty $strategy "notificationRateLimit"
    $documentation = Get-AuditProperty $Policy "documentation"
    $conditions = @(
        @(Get-AuditProperty $Policy "conditions") | ForEach-Object {
            $matchedLog = Get-AuditProperty $_ "conditionMatchedLog"
            [PSCustomObject]@{
                displayName = [string](
                    Get-AuditProperty $_ "displayName"
                )
                type = if ($null -ne $matchedLog) {
                    "conditionMatchedLog"
                } else { "unsupported" }
                filter = if ($null -ne $matchedLog) {
                    [string](Get-AuditProperty $matchedLog "filter")
                } else { "" }
                labelExtractors = if ($null -ne $matchedLog -and
                    $null -ne (
                        Get-AuditProperty $matchedLog "labelExtractors"
                    )) {
                    @((Get-AuditProperty (
                        $matchedLog
                    ) "labelExtractors").PSObject.Properties |
                        ForEach-Object {
                            "$($_.Name)=$([string]$_.Value)"
                        } | Sort-Object)
                } else { @() }
            }
        }
    )
    return [PSCustomObject]@{
        name = [string](Get-AuditProperty $Policy "name")
        displayName = [string](Get-AuditProperty $Policy "displayName")
        enabled = (Get-AuditProperty $Policy "enabled") -eq $true
        severity = [string](Get-AuditProperty $Policy "severity")
        combiner = [string](Get-AuditProperty $Policy "combiner")
        documentation = [PSCustomObject]@{
            mimeType = [string](Get-AuditProperty $documentation "mimeType")
            content = [string](Get-AuditProperty $documentation "content")
        }
        userLabels = Get-AuditProperty $Policy "userLabels"
        conditions = @($conditions)
        notificationChannels = @(
            @(Get-AuditProperty $Policy "notificationChannels") |
                ForEach-Object { [string]$_ }
        )
        notificationRateLimitPeriod = [string](
            Get-AuditProperty $rateLimit "period"
        )
        autoClose = [string](Get-AuditProperty $strategy "autoClose")
        notificationPrompts = @(
            @(Get-AuditProperty $strategy "notificationPrompts") |
                ForEach-Object { [string]$_ }
        )
    }
}

function Get-LiveCommunityModerationSnapshot {
    $gcloud = Resolve-AuditGcloud
    $activeAccounts = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "auth", "list", "--filter=status:ACTIVE", "--format=json"
        ) -FailureCode "community_moderation_runtime_auth_failed"
    )
    if ($activeAccounts.Count -ne 1) {
        throw "community_moderation_runtime_active_account_invalid"
    }
    $configuredProject = Invoke-AuditGcloudText -Executable $gcloud `
        -Arguments @("config", "get-value", "project") `
        -FailureCode "community_moderation_runtime_config_failed"
    $project = Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
        "projects", "describe", $ExpectedProjectId, "--format=json"
    ) -FailureCode "community_moderation_runtime_project_failed"
    $enabledServices = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "services", "list", "--enabled", "--project=$ExpectedProjectId",
            "--format=json"
        ) -FailureCode "community_moderation_runtime_services_failed"
    )

    $allServiceAccounts = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "iam", "service-accounts", "list",
            "--project=$ExpectedProjectId", "--format=json"
        ) -FailureCode "community_moderation_runtime_sa_list_failed"
    )
    $serviceAccounts = @()
    foreach ($email in @(
        $ExpectedRuntimeServiceAccount,
        $ExpectedSchedulerServiceAccount
    )) {
        foreach ($account in @($allServiceAccounts | Where-Object {
            [string](Get-AuditProperty $_ "email") -ceq $email
        })) {
            $keys = @(
                Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
                    "iam", "service-accounts", "keys", "list",
                    "--iam-account=$email", "--managed-by=user",
                    "--project=$ExpectedProjectId", "--format=json"
                ) -FailureCode "community_moderation_runtime_sa_keys_failed"
            )
            $serviceAccounts += [PSCustomObject]@{
                email = $email
                disabled = if (
                    $account.PSObject.Properties.Name -contains "disabled"
                ) { [bool](Get-AuditProperty $account "disabled") } else {
                    $null
                }
                userManagedKeyCount = $keys.Count
            }
        }
    }

    $rawJobs = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "run", "jobs", "list", "--project=$ExpectedProjectId",
            "--format=json"
        ) -FailureCode "community_moderation_runtime_job_list_failed"
    )
    $jobs = @()
    foreach ($listedJob in $rawJobs) {
        $listedJobName = [string](Get-AuditProperty (
            Get-AuditProperty $listedJob "metadata"
        ) "name")
        if ([string]::IsNullOrWhiteSpace($listedJobName)) { continue }
        $rawJob = $listedJob
        $jobLabels = Get-AuditProperty (
            Get-AuditProperty $rawJob "metadata"
        ) "labels"
        $listedJobRegion = [string](Get-AuditProperty (
            $jobLabels
        ) "cloud.googleapis.com/location")
        $executionSpec = $rawJob.spec.template.spec
        $taskSpec = $executionSpec.template.spec
        $containers = @($taskSpec.containers)
        $container = if ($containers.Count -gt 0) {
            $containers[0]
        } else {
            $null
        }
        $candidateTokens = @(
            $containers | ForEach-Object {
                @(Get-AuditProperty $_ "command") +
                    @(Get-AuditProperty $_ "args")
            } | ForEach-Object { [string]$_ }
        )
        $candidateArgs = @(@(Get-AuditProperty $container "args") |
            ForEach-Object { [string]$_ })
        $candidateServiceAccount = [string](
            Get-AuditProperty $taskSpec "serviceAccountName"
        )
        $isModerationCandidate = (
            $listedJobName -ceq $ExpectedJobName -or
            $listedJobName -match '(?i)community.*moderation|moderation.*community' -or
            $candidateServiceAccount -ceq $ExpectedRuntimeServiceAccount -or
            $candidateTokens -ccontains 'app.jobs.emit_community_moderation_digest'
        )
        if (-not $isModerationCandidate) { continue }
        $rawJobIam = Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "run", "jobs", "get-iam-policy", $listedJobName,
            "--project=$ExpectedProjectId", "--region=$listedJobRegion",
            "--format=json"
        ) -FailureCode "community_moderation_runtime_job_iam_failed"
        $volumes = if ($taskSpec.PSObject.Properties.Name -contains "volumes") {
            @($taskSpec.volumes)
        } else { @() }
        $volumeMounts = if (
            $container.PSObject.Properties.Name -contains "volumeMounts"
        ) { @($container.volumeMounts) } else { @() }
        $limits = Get-AuditProperty (
            Get-AuditProperty $container "resources"
        ) "limits"
        $readyCondition = @(
            @($rawJob.status.conditions) | Where-Object {
                [string](Get-AuditProperty $_ "type") -ceq "Ready"
            }
        )
        $jobs += [PSCustomObject]@{
            name = $listedJobName
            region = $listedJobRegion
            ready = ($readyCondition.Count -eq 1 -and
                [string](Get-AuditProperty (
                    $readyCondition[0]
                ) "status") -ceq "True")
            image = [string](Get-AuditProperty $container "image")
            serviceAccount = $candidateServiceAccount
            command = @(
                @(Get-AuditProperty $container "command") |
                    ForEach-Object { [string]$_ }
            )
            args = @($candidateArgs)
            env = @(
                @(Get-AuditProperty $container "env") | ForEach-Object {
                    [PSCustomObject]@{
                        name = [string](Get-AuditProperty $_ "name")
                        value = if ($null -ne (
                            Get-AuditProperty $_ "valueFrom"
                        )) { "__VALUE_FROM__" } else {
                            [string](Get-AuditProperty $_ "value")
                        }
                    }
                }
            )
            containerCount = $containers.Count
            volumeCount = $volumes.Count
            volumeMountCount = $volumeMounts.Count
            taskCount = [int](Get-AuditProperty $executionSpec "taskCount")
            parallelism = [int](
                Get-AuditProperty $executionSpec "parallelism"
            )
            maxRetries = if ($null -ne (
                Get-AuditProperty $taskSpec "maxRetries"
            )) { [int](Get-AuditProperty $taskSpec "maxRetries") } else {
                $null
            }
            timeoutSeconds = ConvertTo-AuditSeconds (
                Get-AuditProperty $taskSpec "timeoutSeconds"
            )
            cpu = [string](Get-AuditProperty $limits "cpu")
            memory = [string](Get-AuditProperty $limits "memory")
            iamBindings = @(
                ConvertTo-AuditIamBindings (
                    Get-AuditProperty $rawJobIam "bindings"
                )
            )
        }
    }

    $schedulerLocations = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "scheduler", "locations", "list", "--project=$ExpectedProjectId",
            "--format=json"
        ) -FailureCode "community_moderation_runtime_scheduler_locations_failed"
    )
    $accessToken = Invoke-AuditGcloudText -Executable $gcloud -Arguments @(
        "auth", "print-access-token"
    ) -FailureCode "community_moderation_runtime_token_failed"
    $headers = @{ Authorization = "Bearer $accessToken" }
    $rawSchedulers = @(
        Get-AllCloudSchedulerJobs -Headers $headers `
            -Locations $schedulerLocations
    )
    $schedulers = @()
    $candidateJobNames = @($jobs | ForEach-Object { [string]$_.name })
    foreach ($rawScheduler in $rawSchedulers) {
        $schedulerResourceName = [string](
            Get-AuditProperty $rawScheduler "name"
        )
        $schedulerNameParts = @($schedulerResourceName -split '/')
        $schedulerName = $schedulerNameParts[-1]
        $schedulerRegion = if ($schedulerNameParts.Count -ge 4) {
            $schedulerNameParts[3]
        } else { "" }
        $target = Get-AuditProperty $rawScheduler "httpTarget"
        $oauth = Get-AuditProperty $target "oauthToken"
        $oidc = Get-AuditProperty $target "oidcToken"
        $retry = Get-AuditProperty $rawScheduler "retryConfig"
        $targetUri = [string](Get-AuditProperty $target "uri")
        $targetServiceAccount = if ($null -ne $oauth) {
            [string](Get-AuditProperty $oauth "serviceAccountEmail")
        } elseif ($null -ne $oidc) {
            [string](Get-AuditProperty $oidc "serviceAccountEmail")
        } else { "" }
        $isModerationCandidate = (
            $schedulerName -ceq $ExpectedSchedulerName -or
            $schedulerName -match '(?i)community.*moderation|moderation.*community' -or
            $targetUri -match [regex]::Escape($ExpectedJobName) -or
            @($candidateJobNames | Where-Object {
                $targetUri -match [regex]::Escape($_)
            }).Count -gt 0 -or
            $targetServiceAccount -ceq $ExpectedSchedulerServiceAccount
        )
        if (-not $isModerationCandidate) { continue }
        $schedulers += [PSCustomObject]@{
            name = $schedulerName
            region = $schedulerRegion
            state = [string](Get-AuditProperty $rawScheduler "state")
            schedule = [string](Get-AuditProperty $rawScheduler "schedule")
            timeZone = [string](Get-AuditProperty $rawScheduler "timeZone")
            uri = $targetUri
            httpMethod = [string](Get-AuditProperty $target "httpMethod")
            authType = if ($null -ne $oauth) {
                "oauth"
            } elseif ($null -ne $oidc) { "oidc" } else { "none" }
            serviceAccount = $targetServiceAccount
            scope = if ($null -ne $oauth) {
                [string](Get-AuditProperty $oauth "scope")
            } else { "" }
            attemptDeadlineSeconds = ConvertTo-AuditSeconds (
                Get-AuditProperty $rawScheduler "attemptDeadline"
            )
            maxRetryAttempts = if ($null -ne (
                Get-AuditProperty $retry "maxRetryAttempts"
            )) { [int](Get-AuditProperty $retry "maxRetryAttempts") } else {
                $null
            }
            body = [string](Get-AuditProperty $target "body")
            headers = @(
                $rawHeaders = Get-AuditProperty $target "headers"
                if ($null -ne $rawHeaders) {
                    $rawHeaders.PSObject.Properties | ForEach-Object {
                        "$($_.Name)=$([string]$_.Value)"
                    } | Sort-Object
                }
            )
        }
    }

    $projectIam = Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
        "projects", "get-iam-policy", $ExpectedProjectId, "--format=json"
    ) -FailureCode "community_moderation_runtime_project_iam_failed"

    $rawChannel = Invoke-RestMethod -Method Get -Headers $headers -Uri (
        "https://monitoring.googleapis.com/v3/$ExpectedNotificationChannel"
    )
    $rawPolicies = @(Get-MonitoringAlertPolicies -Headers $headers)
    $rawMetrics = @(
        Invoke-AuditGcloudJson -Executable $gcloud -Arguments @(
            "logging", "metrics", "list", "--project=$ExpectedProjectId",
            "--format=json"
        ) -FailureCode "community_moderation_runtime_metrics_failed"
    )

    return [PSCustomObject]@{
        account = [string](Get-AuditProperty $activeAccounts[0] "account")
        configuredProject = $configuredProject
        project = [PSCustomObject]@{
            projectId = [string](Get-AuditProperty $project "projectId")
            projectNumber = [string](
                Get-AuditProperty $project "projectNumber"
            )
            state = [string](Get-AuditProperty $project "lifecycleState")
        }
        enabledApis = @($enabledServices | ForEach-Object {
            [string](Get-AuditProperty (
                Get-AuditProperty $_ "config"
            ) "name")
        } | Where-Object { $_ } | Sort-Object -Unique)
        serviceAccounts = @($serviceAccounts)
        jobs = @($jobs)
        schedulers = @($schedulers)
        projectIamBindings = @(
            ConvertTo-AuditIamBindings (
                Get-AuditProperty $projectIam "bindings"
            )
        )
        notificationChannel = [PSCustomObject]@{
            name = [string](Get-AuditProperty $rawChannel "name")
            type = [string](Get-AuditProperty $rawChannel "type")
            enabled = (Get-AuditProperty $rawChannel "enabled") -eq $true
            verificationStatus = [string](
                Get-AuditProperty $rawChannel "verificationStatus"
            )
            emailAddress = [string](Get-AuditProperty (
                Get-AuditProperty $rawChannel "labels"
            ) "email_address")
        }
        alertPolicies = @($rawPolicies | ForEach-Object {
            ConvertTo-AuditAlertPolicy $_
        })
        logMetrics = @($rawMetrics | ForEach-Object {
            [PSCustomObject]@{
                name = [string](Get-AuditProperty $_ "name")
                description = [string](
                    Get-AuditProperty $_ "description"
                )
                filter = [string](Get-AuditProperty $_ "filter")
            }
        })
    }
}

try {
    if ($Mode -ceq "Fixture") {
        if ([string]::IsNullOrWhiteSpace($SnapshotFixturePath)) {
            throw "community_moderation_runtime_fixture_required"
        }
        $fixture = (Resolve-Path -LiteralPath $SnapshotFixturePath `
            -ErrorAction Stop).Path
        $snapshot = Get-Content -LiteralPath $fixture -Raw |
            ConvertFrom-Json
    } else {
        if (-not [string]::IsNullOrWhiteSpace($SnapshotFixturePath)) {
            throw "community_moderation_runtime_fixture_forbidden_live"
        }
        $snapshot = Get-LiveCommunityModerationSnapshot
    }

    $result = Test-CommunityModerationRuntimeSnapshot -Snapshot $snapshot `
        -Stage $Stage -ExpectedImage $ExpectedImage
    $result | Add-Member -NotePropertyName mode -NotePropertyValue $Mode
    $result | Add-Member -NotePropertyName expectedImage `
        -NotePropertyValue $ExpectedImage
    if ($PassThru) { return $result }
    $result | ConvertTo-Json -Depth 16
    if (-not $result.ready) { exit 2 }
    exit 0
} catch {
    $failure = [PSCustomObject]@{
        schemaVersion = "community-moderation-runtime-audit-v1"
        event = "community_moderation_runtime_audit"
        mode = $Mode
        stage = $Stage
        expectedImage = $ExpectedImage
        ready = $false
        blockingCount = 1
        warningCount = 0
        findings = @([PSCustomObject]@{
            code = "audit_failed"
            message = $_.Exception.Message
            blocking = $true
        })
    }
    if ($PassThru) { return $failure }
    $failure | ConvertTo-Json -Depth 8
    exit 1
}
