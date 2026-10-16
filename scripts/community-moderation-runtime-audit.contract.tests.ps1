$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Import-Module (
    Join-Path $PSScriptRoot "community-moderation-runtime-audit.psm1"
) -Force

$ExpectedImage = (
    "europe-west1-docker.pkg.dev/meteo-friul/" +
    "cloud-run-source-deploy/meteofriul-api@sha256:" +
    "07c50b39437ecb07e9fd707fd8cd60e706d9f5822637652f30bfb5d6063ce0f5"
)

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw "Community moderation runtime contract fallito: $Message"
    }
}

function Read-Fixture {
    param([string]$Name)
    $path = Join-Path $PSScriptRoot "fixtures\$Name"
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Copy-Snapshot {
    param([object]$Snapshot)
    return ($Snapshot | ConvertTo-Json -Depth 30 | ConvertFrom-Json)
}

function Test-HasFinding {
    param([object]$Result, [string]$Code)
    return @($Result.findings | Where-Object {
        [string]$_.code -ceq $Code
    }).Count -gt 0
}

function Test-Snapshot {
    param(
        [object]$Snapshot,
        [ValidateSet("PreActivation", "Final")]
        [string]$Stage = "PreActivation",
        [string]$Image = $ExpectedImage
    )
    return Test-CommunityModerationRuntimeSnapshot -Snapshot $Snapshot `
        -Stage $Stage -ExpectedImage $Image
}

$pre = Read-Fixture "community-moderation-runtime-preactivation.json"
$preResult = Test-Snapshot $pre -Stage PreActivation
Assert-Contract $preResult.ready "la fixture PreActivation deve passare"
Assert-Contract ($preResult.blockingCount -eq 0) (
    "la fixture PreActivation non deve avere blocker"
)
Assert-Contract ($preResult.observed.schedulerState -ceq "PAUSED") (
    "PreActivation deve esporre scheduler PAUSED"
)

$final = Read-Fixture "community-moderation-runtime-final.json"
$finalResult = Test-Snapshot $final -Stage Final
Assert-Contract $finalResult.ready "la fixture Final deve passare"
Assert-Contract ($finalResult.observed.schedulerState -ceq "ENABLED") (
    "Final deve esporre scheduler ENABLED"
)

$lowerCaseStageResult = Test-Snapshot $pre -Stage preactivation
Assert-Contract $lowerCaseStageResult.ready (
    "lo stage deve essere normalizzato senza dipendere dalle maiuscole"
)

$wrongStage = Test-Snapshot $pre -Stage Final
Assert-Contract (-not $wrongStage.ready) (
    "Final non deve accettare scheduler PAUSED"
)
Assert-Contract (Test-HasFinding $wrongStage "scheduler_state_mismatch") (
    "manca il blocker stato scheduler"
)

$wrongAccount = Copy-Snapshot $pre
$wrongAccount.account = "altro@example.invalid"
$wrongAccountResult = Test-Snapshot $wrongAccount
Assert-Contract (-not $wrongAccountResult.ready) (
    "account inatteso non deve passare"
)
Assert-Contract (Test-HasFinding $wrongAccountResult "account_mismatch") (
    "manca il blocker account"
)

$wrongConfiguredProject = Copy-Snapshot $pre
$wrongConfiguredProject.configuredProject = "altro-progetto"
$wrongConfiguredProjectResult = Test-Snapshot $wrongConfiguredProject
Assert-Contract (-not $wrongConfiguredProjectResult.ready) (
    "config gcloud su altro progetto non deve passare"
)
Assert-Contract (Test-HasFinding (
    $wrongConfiguredProjectResult
) "configured_project_mismatch") "manca il blocker config project"

$missingApi = Copy-Snapshot $pre
$missingApi.enabledApis = @($missingApi.enabledApis | Where-Object {
    $_ -cne "monitoring.googleapis.com"
})
$missingApiResult = Test-Snapshot $missingApi
Assert-Contract (-not $missingApiResult.ready) (
    "API Monitoring assente non deve passare"
)
Assert-Contract (Test-HasFinding $missingApiResult "required_api_missing") (
    "manca il blocker API"
)

$disabledRuntime = Copy-Snapshot $pre
$disabledRuntime.serviceAccounts[0].disabled = $true
$disabledRuntimeResult = Test-Snapshot $disabledRuntime
Assert-Contract (-not $disabledRuntimeResult.ready) (
    "runtime SA disabilitato non deve passare"
)
Assert-Contract (Test-HasFinding (
    $disabledRuntimeResult
) "service_account_disabled") "manca il blocker SA disabilitato"

$unknownRuntimeState = Copy-Snapshot $pre
$unknownRuntimeState.serviceAccounts[0].PSObject.Properties.Remove("disabled")
$unknownRuntimeStateResult = Test-Snapshot $unknownRuntimeState
Assert-Contract (-not $unknownRuntimeStateResult.ready) (
    "runtime SA senza stato esplicito non deve passare"
)
Assert-Contract (Test-HasFinding (
    $unknownRuntimeStateResult
) "service_account_disabled") "manca il blocker stato SA ignoto"

$userKey = Copy-Snapshot $pre
$userKey.serviceAccounts[1].userManagedKeyCount = 1
$userKeyResult = Test-Snapshot $userKey
Assert-Contract (-not $userKeyResult.ready) (
    "chiave user-managed non deve passare"
)
Assert-Contract (Test-HasFinding (
    $userKeyResult
) "service_account_user_key_present") "manca il blocker chiave SA"

$wrongImage = Copy-Snapshot $pre
$wrongImage.jobs[0].image = (
    "europe-west1-docker.pkg.dev/meteo-friul/repo/image@sha256:" +
    ("a" * 64)
)
$wrongImageResult = Test-Snapshot $wrongImage
Assert-Contract (-not $wrongImageResult.ready) (
    "digest Job inattesa non deve passare"
)
Assert-Contract (Test-HasFinding $wrongImageResult "job_image_mismatch") (
    "manca il blocker digest Job"
)

$duplicateNamedJob = Copy-Snapshot $pre
$jobCopy = Copy-Snapshot $duplicateNamedJob.jobs[0]
$jobCopy.name = "meteofriul-community-moderation-digest-old"
$duplicateNamedJob.jobs += $jobCopy
$duplicateNamedJobResult = Test-Snapshot $duplicateNamedJob
Assert-Contract (-not $duplicateNamedJobResult.ready) (
    "un job Moderazione correlato con nome diverso non deve passare"
)
Assert-Contract (Test-HasFinding (
    $duplicateNamedJobResult
) "job_related_inventory_mismatch") "manca il blocker job correlato extra"

$wrongEntrypoint = Copy-Snapshot $pre
$wrongEntrypoint.jobs[0].args = @(
    "-m", "app.jobs.emit_community_moderation_digest"
)
$wrongEntrypointResult = Test-Snapshot $wrongEntrypoint
Assert-Contract (-not $wrongEntrypointResult.ready) (
    "Job senza --apply non deve passare"
)
Assert-Contract (Test-HasFinding $wrongEntrypointResult "job_args_mismatch") (
    "manca il blocker args Job"
)

$extraEnvironment = Copy-Snapshot $pre
$extraEnvironment.jobs[0].env += [PSCustomObject]@{
    name = "EXTRA_SETTING"
    value = "1"
}
$extraEnvironmentResult = Test-Snapshot $extraEnvironment
Assert-Contract (-not $extraEnvironmentResult.ready) (
    "env extra non deve passare"
)
Assert-Contract (Test-HasFinding (
    $extraEnvironmentResult
) "job_environment_mismatch") "manca il blocker env Job"

$duplicateEnvironment = Copy-Snapshot $pre
$duplicateEnvironment.jobs[0].env += Copy-Snapshot (
    $duplicateEnvironment.jobs[0].env[0]
)
$duplicateEnvironmentResult = Test-Snapshot $duplicateEnvironment
Assert-Contract (-not $duplicateEnvironmentResult.ready) (
    "env duplicata non deve passare"
)
Assert-Contract (Test-HasFinding (
    $duplicateEnvironmentResult
) "job_environment_mismatch") "manca il blocker env duplicata"

$sidecarJob = Copy-Snapshot $pre
$sidecarJob.jobs[0].containerCount = 2
$sidecarJobResult = Test-Snapshot $sidecarJob
Assert-Contract (-not $sidecarJobResult.ready) (
    "un sidecar inatteso non deve passare"
)
Assert-Contract (Test-HasFinding (
    $sidecarJobResult
) "job_container_shape_mismatch") "manca il blocker sidecar"

$missingRetry = Copy-Snapshot $pre
$missingRetry.jobs[0].PSObject.Properties.Remove("maxRetries")
$missingRetryResult = Test-Snapshot $missingRetry
Assert-Contract (-not $missingRetryResult.ready) (
    "maxRetries omesso non deve essere interpretato come zero"
)
Assert-Contract (Test-HasFinding (
    $missingRetryResult
) "job_retry_mismatch") "manca il blocker retry omesso"

$wrongResources = Copy-Snapshot $pre
$wrongResources.jobs[0].memory = "1Gi"
$wrongResources.jobs[0].maxRetries = 1
$wrongResourcesResult = Test-Snapshot $wrongResources
Assert-Contract (-not $wrongResourcesResult.ready) (
    "risorse o retry diversi non devono passare"
)
Assert-Contract (Test-HasFinding (
    $wrongResourcesResult
) "job_resources_mismatch") "manca il blocker risorse Job"
Assert-Contract (Test-HasFinding (
    $wrongResourcesResult
) "job_retry_mismatch") "manca il blocker retry Job"

$broadRuntime = Copy-Snapshot $pre
$broadRuntime.projectIamBindings += [PSCustomObject]@{
    role = "roles/viewer"
    members = @(
        "serviceAccount:community-moderation-digest@meteo-friul.iam.gserviceaccount.com"
    )
}
$broadRuntimeResult = Test-Snapshot $broadRuntime
Assert-Contract (-not $broadRuntimeResult.ready) (
    "ruolo progetto runtime extra non deve passare"
)
Assert-Contract (Test-HasFinding (
    $broadRuntimeResult
) "runtime_project_roles_not_minimal") "manca il blocker IAM runtime"

$publicProjectIam = Copy-Snapshot $pre
$publicProjectIam.projectIamBindings[0].members += "allUsers"
$publicProjectIamResult = Test-Snapshot $publicProjectIam
Assert-Contract (-not $publicProjectIamResult.ready) (
    "un principal pubblico nella policy progetto non deve passare"
)
Assert-Contract (Test-HasFinding (
    $publicProjectIamResult
) "project_public_principal_present") "manca il blocker IAM pubblico"

$schedulerProjectRole = Copy-Snapshot $pre
$schedulerProjectRole.projectIamBindings += [PSCustomObject]@{
    role = "roles/viewer"
    members = @(
        "serviceAccount:community-moderation-scheduler@meteo-friul.iam.gserviceaccount.com"
    )
}
$schedulerProjectRoleResult = Test-Snapshot $schedulerProjectRole
Assert-Contract (-not $schedulerProjectRoleResult.ready) (
    "ruolo progetto Scheduler non deve passare"
)
Assert-Contract (Test-HasFinding (
    $schedulerProjectRoleResult
) "scheduler_project_role_present") "manca il blocker IAM Scheduler"

$missingServiceAgent = Copy-Snapshot $pre
$missingServiceAgent.projectIamBindings = @(
    $missingServiceAgent.projectIamBindings | Where-Object {
        $_.role -cne "roles/cloudscheduler.serviceAgent"
    }
)
$missingServiceAgentResult = Test-Snapshot $missingServiceAgent
Assert-Contract (-not $missingServiceAgentResult.ready) (
    "service agent Scheduler senza ruolo non deve passare"
)
Assert-Contract (Test-HasFinding (
    $missingServiceAgentResult
) "scheduler_service_agent_role_missing") (
    "manca il blocker service agent Scheduler"
)

$broadServiceAgent = Copy-Snapshot $pre
$broadServiceAgent.projectIamBindings += [PSCustomObject]@{
    role = "roles/viewer"
    members = @(
        "serviceAccount:service-49007668366@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
    )
}
$broadServiceAgentResult = Test-Snapshot $broadServiceAgent
Assert-Contract (-not $broadServiceAgentResult.ready) (
    "service agent Scheduler con ruolo extra non deve passare"
)
Assert-Contract (Test-HasFinding (
    $broadServiceAgentResult
) "scheduler_service_agent_role_missing") (
    "manca il blocker ruolo extra service agent"
)

$publicJob = Copy-Snapshot $pre
$publicJob.jobs[0].iamBindings[0].members += "allUsers"
$publicJobResult = Test-Snapshot $publicJob
Assert-Contract (-not $publicJobResult.ready) (
    "Job pubblico non deve passare"
)
Assert-Contract (Test-HasFinding (
    $publicJobResult
) "job_public_invoker_present") "manca il blocker Job pubblico"
Assert-Contract (Test-HasFinding $publicJobResult "job_invoker_mismatch") (
    "un invoker extra deve rompere il contratto minimo"
)

$wrongSchedulerAuth = Copy-Snapshot $pre
$wrongSchedulerAuth.schedulers[0].authType = "oidc"
$wrongSchedulerAuth.schedulers[0].scope = ""
$wrongSchedulerAuthResult = Test-Snapshot $wrongSchedulerAuth
Assert-Contract (-not $wrongSchedulerAuthResult.ready) (
    "OIDC verso run.googleapis.com non deve passare"
)
Assert-Contract (Test-HasFinding (
    $wrongSchedulerAuthResult
) "scheduler_auth_mismatch") "manca il blocker OAuth Scheduler"

$wrongSchedule = Copy-Snapshot $pre
$wrongSchedule.schedulers[0].schedule = "*/5 * * * *"
$wrongScheduleResult = Test-Snapshot $wrongSchedule
Assert-Contract (-not $wrongScheduleResult.ready) (
    "cron troppo frequente non deve passare"
)
Assert-Contract (Test-HasFinding (
    $wrongScheduleResult
) "scheduler_schedule_mismatch") "manca il blocker cron"

$duplicateNamedScheduler = Copy-Snapshot $pre
$schedulerCopy = Copy-Snapshot $duplicateNamedScheduler.schedulers[0]
$schedulerCopy.name = "community-moderation-digest-copy"
$duplicateNamedScheduler.schedulers += $schedulerCopy
$duplicateNamedSchedulerResult = Test-Snapshot $duplicateNamedScheduler
Assert-Contract (-not $duplicateNamedSchedulerResult.ready) (
    "uno scheduler Moderazione correlato con nome diverso non deve passare"
)
Assert-Contract (Test-HasFinding (
    $duplicateNamedSchedulerResult
) "scheduler_related_inventory_mismatch") (
    "manca il blocker scheduler correlato extra"
)

$schedulerPayload = Copy-Snapshot $pre
$schedulerPayload.schedulers[0].body = "e30="
$schedulerPayload.schedulers[0].headers = @("Content-Type=application/json")
$schedulerPayloadResult = Test-Snapshot $schedulerPayload
Assert-Contract (-not $schedulerPayloadResult.ready) (
    "body o header Scheduler inattesi non devono passare"
)
Assert-Contract (Test-HasFinding (
    $schedulerPayloadResult
) "scheduler_request_shape_mismatch") "manca il blocker richiesta Scheduler"

$disabledChannel = Copy-Snapshot $pre
$disabledChannel.notificationChannel.enabled = $false
$disabledChannelResult = Test-Snapshot $disabledChannel
Assert-Contract (-not $disabledChannelResult.ready) (
    "canale email disabilitato non deve passare"
)
Assert-Contract (Test-HasFinding (
    $disabledChannelResult
) "notification_channel_mismatch") "manca il blocker canale"

$unverifiedChannel = Copy-Snapshot $pre
$unverifiedChannel.notificationChannel.verificationStatus = "UNVERIFIED"
$unverifiedChannelResult = Test-Snapshot $unverifiedChannel
Assert-Contract (-not $unverifiedChannelResult.ready) (
    "canale email non verificato non deve passare"
)
Assert-Contract (Test-HasFinding (
    $unverifiedChannelResult
) "notification_channel_mismatch") "manca il blocker verifica canale"

$apiWithoutVerificationField = Copy-Snapshot $pre
$apiWithoutVerificationField.notificationChannel.verificationStatus = ""
$apiWithoutVerificationFieldResult = Test-Snapshot $apiWithoutVerificationField
Assert-Contract $apiWithoutVerificationFieldResult.ready (
    "l'API Monitoring reale non espone verificationStatus per il canale email"
)

$duplicatePolicy = Copy-Snapshot $pre
$duplicatePolicy.alertPolicies += Copy-Snapshot (
    $duplicatePolicy.alertPolicies[0]
)
$duplicatePolicyResult = Test-Snapshot $duplicatePolicy
Assert-Contract (-not $duplicatePolicyResult.ready) (
    "policy duplicata non deve passare"
)
Assert-Contract (Test-HasFinding (
    $duplicatePolicyResult
) "monitoring_policy_inventory_mismatch") "manca il blocker policy duplicata"

$relatedPolicyCopy = Copy-Snapshot $pre
$renamedPolicy = Copy-Snapshot $relatedPolicyCopy.alertPolicies[0]
$renamedPolicy.displayName = "Copia digest moderazione Community"
$relatedPolicyCopy.alertPolicies += $renamedPolicy
$relatedPolicyCopyResult = Test-Snapshot $relatedPolicyCopy
Assert-Contract (-not $relatedPolicyCopyResult.ready) (
    "una terza policy correlata con nome diverso non deve passare"
)
Assert-Contract (Test-HasFinding (
    $relatedPolicyCopyResult
) "monitoring_related_policy_inventory_mismatch") (
    "manca il blocker policy correlata extra"
)

$labelOnlyPolicyCopy = Copy-Snapshot $pre
$labelOnlyPolicy = Copy-Snapshot $labelOnlyPolicyCopy.alertPolicies[0]
$labelOnlyPolicy.displayName = "Policy tecnica ausiliaria"
$labelOnlyPolicy.conditions[0].filter = 'severity=INFO AND textPayload="altro"'
$labelOnlyPolicy.userLabels.service = "community-moderation"
$labelOnlyPolicy.userLabels.signal = "other"
$labelOnlyPolicyCopy.alertPolicies += $labelOnlyPolicy
$labelOnlyPolicyCopyResult = Test-Snapshot $labelOnlyPolicyCopy
Assert-Contract (-not $labelOnlyPolicyCopyResult.ready) (
    "una policy correlata soltanto dai label non deve passare"
)
Assert-Contract (Test-HasFinding (
    $labelOnlyPolicyCopyResult
) "monitoring_related_policy_inventory_mismatch") (
    "manca il blocker policy correlata tramite label"
)

$wrongFilter = Copy-Snapshot $pre
$wrongFilter.alertPolicies[0].conditions[0].filter = (
    'log_id("meteofriul-community-moderation-digest")'
)
$wrongFilterResult = Test-Snapshot $wrongFilter
Assert-Contract (-not $wrongFilterResult.ready) (
    "filtro Monitoring parziale non deve passare"
)
Assert-Contract (Test-HasFinding (
    $wrongFilterResult
) "monitoring_policy_condition_mismatch") "manca il blocker filtro"

$labelExtractor = Copy-Snapshot $pre
$labelExtractor.alertPolicies[0].conditions[0].labelExtractors = @(
    "device_id=EXTRACT(jsonPayload.device_id)"
)
$labelExtractorResult = Test-Snapshot $labelExtractor
Assert-Contract (-not $labelExtractorResult.ready) (
    "label extractor Monitoring non deve passare"
)
Assert-Contract (Test-HasFinding (
    $labelExtractorResult
) "monitoring_policy_label_extractors_present") (
    "manca il blocker label extractor"
)

$extraPolicyLabel = Copy-Snapshot $pre
$extraPolicyLabel.alertPolicies[0].userLabels | Add-Member `
    -NotePropertyName extra -NotePropertyValue "unexpected"
$extraPolicyLabelResult = Test-Snapshot $extraPolicyLabel
Assert-Contract (-not $extraPolicyLabelResult.ready) (
    "user label Monitoring extra non deve passare"
)
Assert-Contract (Test-HasFinding (
    $extraPolicyLabelResult
) "monitoring_policy_labels_mismatch") "manca il blocker label extra"

$wrongStrategy = Copy-Snapshot $pre
$wrongStrategy.alertPolicies[1].notificationRateLimitPeriod = "300s"
$wrongStrategy.alertPolicies[1].notificationPrompts = @(
    "OPENED", "CLOSED"
)
$wrongStrategyResult = Test-Snapshot $wrongStrategy
Assert-Contract (-not $wrongStrategyResult.ready) (
    "rate o prompt inattesi non devono passare"
)
Assert-Contract (Test-HasFinding (
    $wrongStrategyResult
) "monitoring_policy_strategy_mismatch") "manca il blocker rate"
Assert-Contract (Test-HasFinding (
    $wrongStrategyResult
) "monitoring_policy_prompt_mismatch") "manca il blocker prompt"

$unexpectedMetric = Copy-Snapshot $pre
$unexpectedMetric.logMetrics = @([PSCustomObject]@{
    name = "community-moderation-count"
    description = "Community moderation metric"
    filter = ""
})
$unexpectedMetricResult = Test-Snapshot $unexpectedMetric
Assert-Contract (-not $unexpectedMetricResult.ready) (
    "log metric ridondante non deve passare"
)
Assert-Contract (Test-HasFinding (
    $unexpectedMetricResult
) "moderation_log_metric_present") "manca il blocker log metric"

$neutralMetric = Copy-Snapshot $pre
$neutralMetric.logMetrics = @([PSCustomObject]@{
    name = "counter-1"
    description = "Generic counter"
    filter = 'log_id("meteofriul-community-moderation-digest")'
})
$neutralMetricResult = Test-Snapshot $neutralMetric
Assert-Contract (-not $neutralMetricResult.ready) (
    "metrica dal nome neutro sul log Moderazione non deve passare"
)
Assert-Contract (Test-HasFinding (
    $neutralMetricResult
) "moderation_log_metric_present") "manca il blocker filtro log metric"

# Fixture mode deve funzionare anche con un path gcloud inesistente: prova che
# il collector Live non viene neppure risolto o invocato.
$auditScript = Join-Path $PSScriptRoot (
    "audit-community-moderation-runtime.ps1"
)
$fixturePath = Join-Path $PSScriptRoot (
    "fixtures\community-moderation-runtime-preactivation.json"
)
$finalFixturePath = Join-Path $PSScriptRoot (
    "fixtures\community-moderation-runtime-final.json"
)
$hostExecutable = (Get-Process -Id $PID).Path
$wrapperOutput = @(& $hostExecutable -NoProfile -File $auditScript `
    -Mode Fixture -Stage PreActivation -SnapshotFixturePath $fixturePath `
    -GcloudPath "Z:\definitely-not-present\gcloud.cmd")
Assert-Contract ($LASTEXITCODE -eq 0) (
    "il wrapper Fixture verde deve uscire con codice zero"
)
$wrapperResult = ($wrapperOutput -join [Environment]::NewLine) |
    ConvertFrom-Json
Assert-Contract ($wrapperResult.ready -eq $true -and
    $wrapperResult.mode -ceq "Fixture") (
    "il wrapper deve restituire evidenza Fixture pronta"
)
$passThruResult = @(& $auditScript -Mode Fixture -Stage Final `
    -SnapshotFixturePath $finalFixturePath `
    -GcloudPath "Z:\definitely-not-present\gcloud.cmd" -PassThru
)
$passThruCapturedAt = [DateTimeOffset]::MinValue
$passThruCapturedAtValid = [DateTimeOffset]::TryParseExact(
    [string]$passThruResult[0].capturedAtUtc,
    "o",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::RoundtripKind,
    [ref]$passThruCapturedAt
)
Assert-Contract ($passThruResult.Count -eq 1 -and
    $passThruResult[0] -is [PSCustomObject] -and
    $passThruResult[0].schemaVersion -ceq
        "community-moderation-runtime-audit-v1" -and
    $passThruResult[0].event -ceq "community_moderation_runtime_audit" -and
    $passThruCapturedAtValid -and
    $passThruCapturedAt.Offset -eq [TimeSpan]::Zero -and
    $passThruResult[0].ready -eq $true -and
    $passThruResult[0].mode -ceq "Fixture" -and
    $passThruResult[0].stage -ceq "Final" -and
    $passThruResult[0].expectedImage -ceq $ExpectedImage -and
    $passThruResult[0].observed.jobImage -ceq $ExpectedImage) (
    "PassThru deve restituire l'oggetto senza terminare il processo chiamante"
)
$lowerCaseWrapperResult = & $auditScript -Mode fixture -Stage preactivation `
    -SnapshotFixturePath $fixturePath `
    -GcloudPath "Z:\definitely-not-present\gcloud.cmd" -PassThru
Assert-Contract ($lowerCaseWrapperResult.ready -eq $true -and
    $lowerCaseWrapperResult.mode -ceq "Fixture" -and
    $lowerCaseWrapperResult.stage -ceq "PreActivation") (
    "il wrapper deve normalizzare Mode e Stage senza dipendere dal case"
)
$failedPassThru = @(& $auditScript -Mode Fixture -Stage Final `
    -SnapshotFixturePath (Join-Path $PSScriptRoot "fixtures\missing.json") `
    -PassThru
)
Assert-Contract ($failedPassThru.Count -eq 1 -and
    $failedPassThru[0] -is [PSCustomObject] -and
    $failedPassThru[0].schemaVersion -ceq
        "community-moderation-runtime-audit-v1" -and
    $failedPassThru[0].mode -ceq "Fixture" -and
    $failedPassThru[0].stage -ceq "Final" -and
    $failedPassThru[0].expectedImage -ceq $ExpectedImage -and
    $failedPassThru[0].ready -eq $false -and
    $failedPassThru[0].blockingCount -eq 1 -and
    $failedPassThru[0].findings[0].code -ceq "audit_failed") (
    "PassThru deve restituire un blocker stabile per errori del collector"
)

$blockedWrapperOutput = @(& $hostExecutable -NoProfile -File $auditScript `
    -Mode Fixture -Stage Final -SnapshotFixturePath $fixturePath)
Assert-Contract ($LASTEXITCODE -eq 2) (
    "un contratto Fixture bloccato deve uscire con codice due"
)
$blockedWrapperResult = ($blockedWrapperOutput -join [Environment]::NewLine) |
    ConvertFrom-Json
Assert-Contract ($blockedWrapperResult.ready -eq $false -and
    $blockedWrapperResult.blockingCount -gt 0) (
    "il wrapper bloccato deve serializzare i finding"
)
$failedWrapperOutput = @(& $hostExecutable -NoProfile -File $auditScript `
    -Mode Fixture -Stage Final `
    -SnapshotFixturePath (Join-Path $PSScriptRoot "fixtures\missing.json"))
Assert-Contract ($LASTEXITCODE -eq 1) (
    "un errore collector deve uscire con codice uno"
)
$failedWrapperResult = ($failedWrapperOutput -join [Environment]::NewLine) |
    ConvertFrom-Json
Assert-Contract ($failedWrapperResult.ready -eq $false -and
    $failedWrapperResult.findings[0].code -ceq "audit_failed") (
    "l'errore collector deve serializzare un blocker stabile"
)

$sourceText = (@(
    Get-Content -LiteralPath $auditScript -Raw
    Get-Content -LiteralPath (
        Join-Path $PSScriptRoot "community-moderation-runtime-audit.psm1"
    ) -Raw
) -join [Environment]::NewLine).ToLowerInvariant()
$forbiddenMutations = @(
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "set-iam-policy",
    "service-accounts create",
    "service-accounts keys create",
    "service-accounts delete",
    "service-accounts keys delete",
    "run jobs create",
    "run jobs update",
    "run jobs replace",
    "run jobs execute",
    "run jobs run",
    "run jobs delete",
    "scheduler jobs create",
    "scheduler jobs update",
    "scheduler jobs resume",
    "scheduler jobs pause",
    "scheduler jobs run",
    "scheduler jobs delete",
    "services enable",
    "services disable",
    "logging metrics create",
    "logging metrics update",
    "logging metrics delete",
    "logging write",
    "-method post",
    "-method patch",
    "-method put",
    "-method delete"
)
foreach ($token in $forbiddenMutations) {
    Assert-Contract (-not $sourceText.Contains($token.ToLowerInvariant())) (
        "l'audit-only contiene il token mutante: $token"
    )
}
Assert-Contract $sourceText.Contains("nextpagetoken") (
    "il collector Monitoring deve gestire la paginazione"
)
Assert-Contract ($sourceText.Contains("candidateserviceaccount") -and
    $sourceText.Contains("candidatetokens")) (
    "il collector deve correlare job dal service account e da tutti i container"
)
$jobListCall = [regex]::Match(
    $sourceText,
    '(?s)"run",\s*"jobs",\s*"list".*?' +
        'community_moderation_runtime_job_list_failed'
).Value
Assert-Contract (-not [string]::IsNullOrWhiteSpace($jobListCall) -and
    -not $jobListCall.Contains('"--region=')) (
    "l'inventario Cloud Run Job deve coprire tutte le regioni del progetto"
)
$schedulerLocationInventory = [regex]::Match(
    $sourceText,
    '(?s)"scheduler",\s*"locations",\s*"list".*?' +
        'community_moderation_runtime_scheduler_locations_failed'
).Value
$schedulerProjectInventory = [regex]::Match(
    $sourceText,
    '(?s)function\s+get-allcloudschedulerjobs.*?' +
        'locations/\$locationid/jobs\?pagesize=500.*?' +
        'nextpagetoken'
).Value
Assert-Contract (
    -not [string]::IsNullOrWhiteSpace($schedulerLocationInventory) -and
    -not [string]::IsNullOrWhiteSpace($schedulerProjectInventory) -and
    -not $schedulerLocationInventory.Contains('"--location=')
) (
    "l'inventario Scheduler deve coprire tutte le regioni del progetto"
)
Assert-Contract $sourceText.Contains(
    'community_moderation_runtime_scheduler_list_failed:" +'
) (
    "un errore Scheduler deve identificare la regione senza serializzare la risposta"
)

Write-Host "Community moderation runtime audit contract tests: OK"
