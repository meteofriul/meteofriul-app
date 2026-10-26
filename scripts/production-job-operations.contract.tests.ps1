$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptRoot
$config = Get-Content -LiteralPath (
    Join-Path $scriptRoot "cloud-run-job-monitoring-policies.json"
) -Raw | ConvertFrom-Json
$deploySource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "deploy-national-official-alert-job.ps1"
) -Raw
$morningDeploySource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "deploy-morning-forecast-job.ps1"
) -Raw
$eveningDeploySource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "deploy-evening-forecast-job.ps1"
) -Raw
$localNoticeDeploySource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "deploy-local-notice-job.ps1"
) -Raw
$monitoringSource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "sync-cloud-run-job-monitoring.ps1"
) -Raw
$envSource = Get-Content -LiteralPath (
    Join-Path $repoRoot "backend\national-official-alert-production.env.yaml"
) -Raw
$morningEnvSource = Get-Content -LiteralPath (
    Join-Path $repoRoot "backend\morning-forecast-production.env.yaml"
) -Raw
$eveningEnvSource = Get-Content -LiteralPath (
    Join-Path $repoRoot "backend\evening-forecast-production.env.yaml"
) -Raw
$localNoticeEnvSource = Get-Content -LiteralPath (
    Join-Path $repoRoot "backend\local-notice-production.env.yaml"
) -Raw

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "contract_failed: $Message" }
}

$expectedJobs = @(
    "meteofriul-morning-forecast",
    "meteofriul-evening-forecast",
    "meteofriul-local-notice",
    "meteofriul-official-alert-sync",
    "meteofriul-national-official-alert-sync",
    "meteofriul-icon",
    "meteofriul-national-icon",
    "meteofriul-cams",
    "meteofriul-events-refresh"
)
$actualJobs = @($config.policies | ForEach-Object jobName)
Assert-Contract (@($actualJobs | Sort-Object -Unique).Count -eq $expectedJobs.Count) (
    "catalogo monitoring incompleto"
)
foreach ($job in $expectedJobs) {
    Assert-Contract ($actualJobs -ccontains $job) "policy mancante per $job"
}
$expectedPolicyKeys = @(
    "morning-forecast-failures",
    "morning-forecast-last-success",
    "morning-forecast-scheduler-failures",
    "evening-forecast-failures",
    "evening-forecast-last-success",
    "evening-forecast-scheduler-failures",
    "local-notice-failures",
    "local-notice-last-success",
    "local-notice-scheduler-failures",
    "official-alert-failures",
    "national-official-alert-failures",
    "icon-fvg-failures",
    "icon-fvg-last-success",
    "icon-national-failures",
    "icon-national-last-success",
    "cams-failures",
    "events-failures",
    "events-candidate-watch"
)
$actualPolicyKeys = @($config.policies | ForEach-Object policyKey)
Assert-Contract ($actualPolicyKeys.Count -eq $expectedPolicyKeys.Count) (
    "catalogo monitoring senza tutte le policy"
)
foreach ($policyKey in $expectedPolicyKeys) {
    Assert-Contract ($actualPolicyKeys -ccontains $policyKey) (
        "policy monitoring mancante per $policyKey"
    )
}
Assert-Contract (
    @($actualPolicyKeys | Group-Object | Where-Object Count -ne 1).Count -eq 0
) "chiavi policy monitoring duplicate"
Assert-Contract ($deploySource.Contains('"35 */2 * * *"')) (
    "scheduler nazionale non biorario con offset"
)
Assert-Contract ($deploySource.Contains("sync_national_official_alerts")) (
    "entrypoint nazionale errato"
)
Assert-Contract (-not $deploySource.Contains('sync_official_alerts"')) (
    "deploy nazionale non deve puntare al job FVG"
)
Assert-Contract ($deploySource.Contains(
    '"run", "jobs", "add-iam-policy-binding"'
)) "job nazionale senza binding invoker limitato al job"
Assert-Contract ($deploySource.Contains(
    '"run", "jobs", "get-iam-policy"'
)) "job nazionale senza readback del binding invoker"
Assert-Contract ($deploySource.Contains('roles/run.invoker')) (
    "job nazionale senza ruolo invoker"
)
Assert-Contract ($deploySource.Contains('schedulerInvokerReady')) (
    "audit nazionale non espone lo stato del permesso invoker"
)
Assert-Contract ($morningDeploySource.Contains('"30 7 * * *"')) (
    "scheduler sintesi mattutina non impostato alle 07:30"
)
Assert-Contract ($morningDeploySource.Contains("send_morning_forecast")) (
    "entrypoint sintesi mattutina errato"
)
Assert-Contract ($morningDeploySource.Contains(
    'meteofriul-runtime@meteo-friul.iam.gserviceaccount.com'
)) "sintesi mattutina non collegata al runtime IAM dedicato"
Assert-Contract (-not $morningDeploySource.Contains(
    '49007668366-compute@developer.gserviceaccount.com'
)) "sintesi mattutina non deve usare il Compute default"
Assert-Contract ($morningDeploySource.Contains(
    '"run", "jobs", "add-iam-policy-binding"'
)) "sintesi mattutina senza binding invoker limitato al job"
Assert-Contract ($morningDeploySource.Contains(
    '"run", "jobs", "get-iam-policy"'
)) "sintesi mattutina senza readback del binding invoker"
Assert-Contract ($morningDeploySource.Contains('roles/run.invoker')) (
    "sintesi mattutina senza ruolo invoker"
)
Assert-Contract ($morningEnvSource.Contains(
    'MORNING_FORECAST_DELIVERY_MODE: send'
)) "sintesi mattutina non attiva nella configurazione produzione"
Assert-Contract ($morningEnvSource.Contains(
    'MORNING_FORECAST_REQUIRE_SINGLE_TARGET: "false"'
)) "gate singolo dispositivo non disattivato in produzione"
Assert-Contract (-not $morningEnvSource.Contains(
    'MORNING_FORECAST_TEST_PLATFORM'
)) "piattaforma owner di collaudo non deve essere persistita nel job"
Assert-Contract ($eveningDeploySource.Contains('"45 20 * * *"')) (
    "scheduler anticipazione serale non impostato alle 20:45"
)
Assert-Contract ($eveningDeploySource.Contains("send_evening_forecast")) (
    "entrypoint anticipazione serale errato"
)
Assert-Contract ($eveningDeploySource.Contains(
    'meteofriul-runtime@meteo-friul.iam.gserviceaccount.com'
)) "anticipazione serale non collegata al runtime IAM dedicato"
Assert-Contract (-not $eveningDeploySource.Contains(
    '49007668366-compute@developer.gserviceaccount.com'
)) "anticipazione serale non deve usare il Compute default"
Assert-Contract ($eveningDeploySource.Contains(
    '"run", "jobs", "add-iam-policy-binding"'
)) "anticipazione serale senza binding invoker limitato al job"
Assert-Contract ($eveningDeploySource.Contains(
    '"run", "jobs", "get-iam-policy"'
)) "anticipazione serale senza readback del binding invoker"
Assert-Contract ($eveningDeploySource.Contains('roles/run.invoker')) (
    "anticipazione serale senza ruolo invoker"
)
Assert-Contract ($eveningEnvSource.Contains(
    'EVENING_FORECAST_DELIVERY_MODE: send'
)) "anticipazione serale non attiva nella configurazione promossa"
Assert-Contract ($eveningEnvSource.Contains(
    'EVENING_FORECAST_REQUIRE_SINGLE_TARGET: "false"'
)) "gate singolo dispositivo non disattivato dopo il collaudo reale"
Assert-Contract (-not $eveningEnvSource.Contains(
    'EVENING_FORECAST_TEST_INSTALLATION_HASH'
)) "hash owner di collaudo non deve essere persistito nel job"
Assert-Contract ($eveningEnvSource.Contains(
    'LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS: "30"'
)) "timeout ICON dell'anticipazione serale non resiliente ai cold start"
Assert-Contract ($morningEnvSource.Contains(
    'LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS: "30"'
)) "timeout ICON della sintesi mattutina non resiliente ai cold start"
Assert-Contract ($localNoticeEnvSource.Contains(
    'LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS: "30"'
)) "timeout ICON degli avvisi locali non resiliente ai cold start"
Assert-Contract ($localNoticeDeploySource.Contains('"0 * * * *"')) (
    "scheduler avvisi locali non impostato ogni ora"
)
Assert-Contract ($localNoticeDeploySource.Contains(
    "send_local_weather_notices"
)) "entrypoint avvisi locali errato"
Assert-Contract ($localNoticeDeploySource.Contains(
    'meteofriul-runtime@meteo-friul.iam.gserviceaccount.com'
)) "avvisi locali non collegati al runtime IAM dedicato"
Assert-Contract (-not $localNoticeDeploySource.Contains(
    '49007668366-compute@developer.gserviceaccount.com'
)) "avvisi locali non devono usare il Compute default"
Assert-Contract ($localNoticeDeploySource.Contains(
    '"run", "jobs", "add-iam-policy-binding"'
)) "avvisi locali senza binding invoker limitato al job"
Assert-Contract ($localNoticeDeploySource.Contains(
    '"run", "jobs", "get-iam-policy"'
)) "avvisi locali senza readback del binding invoker"
Assert-Contract ($localNoticeDeploySource.Contains('roles/run.invoker')) (
    "avvisi locali senza ruolo invoker"
)
Assert-Contract ($envSource.Contains(
    'NATIONAL_OFFICIAL_ALERTS_REQUIRE_PERSISTENT_STORAGE: "true"'
)) "persistenza nazionale non obbligatoria"
Assert-Contract (-not $envSource.Contains("PUSH_OFFICIAL_ALERTS_MODE")) (
    "job nazionale non deve configurare push"
)
Assert-Contract ($monitoringSource.Contains('[ValidateSet("Audit", "Apply")]')) (
    "sync monitoring deve essere fail-safe in Audit"
)
Assert-Contract ($monitoringSource.Contains('[string]$PolicyKey') -and
    $monitoringSource.Contains('monitoring_policy_key_not_found')) (
    "sync monitoring deve consentire un aggiornamento mirato a una policy"
)
Assert-Contract ($monitoringSource.Contains('notificationChannels')) (
    "policy monitoring senza canale"
)
Assert-Contract ($monitoringSource.Contains('conditionAbsent')) (
    "monitoring senza controllo dell'ultima esecuzione riuscita"
)
Assert-Contract ($monitoringSource.Contains('conditionMatchedLog')) (
    "monitoring senza controllo degli errori Cloud Scheduler"
)
Assert-Contract ($monitoringSource.Contains('notificationRateLimit')) (
    "monitoring log-based senza limite di notifica"
)
Assert-Contract ($monitoringSource.Contains(
    'EVALUATION_MISSING_DATA_ACTIVE'
)) "monitoring giornaliero senza trattamento dell'assenza dati"
Assert-Contract ($monitoringSource.Contains('"succeeded"')) (
    "monitoring senza filtro sulle esecuzioni riuscite"
)
$absencePolicies = @(
    $config.policies | Where-Object {
        $null -ne $_.PSObject.Properties["conditionType"] -and
        [string]$_.conditionType -ceq "successful_execution_absent"
    }
)
Assert-Contract ($absencePolicies.Count -eq 3) (
    "policy di freschezza/ultimo successo incomplete"
)
foreach ($policy in $absencePolicies) {
    Assert-Contract ([int]$policy.absenceDurationSeconds -ge 10800) (
        "finestra di assenza troppo aggressiva per $($policy.policyKey)"
    )
    Assert-Contract ([bool]$policy.notifyOnRecovery) (
        "recovery reale non notificata per $($policy.policyKey)"
    )
}
$successWindowPolicies = @(
    $config.policies | Where-Object {
        $null -ne $_.PSObject.Properties["conditionType"] -and
        [string]$_.conditionType -ceq "successful_execution_window"
    }
)
Assert-Contract ($successWindowPolicies.Count -eq 2) (
    "policy giornaliere di ultimo successo incomplete"
)
foreach ($policy in $successWindowPolicies) {
    Assert-Contract ([int]$policy.alignmentPeriodSeconds -eq 90000) (
        "finestra di ultimo successo non pari a 25 ore per $($policy.policyKey)"
    )
    Assert-Contract ([bool]$policy.notifyOnRecovery) (
        "recovery giornaliero non notificato per $($policy.policyKey)"
    )
}
$schedulerPolicies = @(
    $config.policies | Where-Object {
        $null -ne $_.PSObject.Properties["conditionType"] -and
        [string]$_.conditionType -ceq "scheduler_log_failure"
    }
)
Assert-Contract ($schedulerPolicies.Count -eq 3) (
    "policy degli scheduler notifiche incomplete"
)
foreach ($policy in $schedulerPolicies) {
    Assert-Contract ([int]$policy.notificationRateLimitSeconds -ge 3600) (
        "rate limit scheduler troppo aggressivo per $($policy.policyKey)"
    )
}
$eventsWatchPolicy = @(
    $config.policies | Where-Object policyKey -CEQ "events-candidate-watch"
)
Assert-Contract ($eventsWatchPolicy.Count -eq 1) (
    "allarme separato dei siti Eventi candidati mancante"
)
Assert-Contract (
    [string]$eventsWatchPolicy[0].conditionType -ceq "job_log_match" -and
    [string]$eventsWatchPolicy[0].logEvent -ceq "event_candidate_watch_alert" -and
    [int]$eventsWatchPolicy[0].notificationRateLimitSeconds -ge 3600
) "allarme candidati Eventi senza filtro o limite di notifica"
Assert-Contract ($monitoringSource.Contains('jsonPayload.event=')) (
    "monitoring senza filtro del log strutturato dei candidati Eventi"
)

# Exercise the policy builder locally: extract only its pure functions, never
# dot-source the script entrypoint (which reads auth and calls cloud APIs).
$parseTokens = $null
$parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput(
    $monitoringSource, [ref]$parseTokens, [ref]$parseErrors
)
Assert-Contract ($parseErrors.Count -eq 0) "monitoring script non parsabile"
foreach ($functionName in @(
    'Get-MonitoringPropertyValue', 'New-DesiredMonitoringPolicy', 'Test-PolicyMatches'
)) {
    $definition = $ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq $functionName
    }, $true)
    Assert-Contract ($definition.Count -eq 1) "funzione monitoring mancante"
    Invoke-Expression $definition[0].Extent.Text
}
$eventsFailure = @($config.policies | Where-Object policyKey -CEQ 'events-failures')[0]
Assert-Contract ($eventsFailure.notifyOnRecovery -ceq $false) (
    "la scadenza della finestra Eventi non deve notificare recupero"
)
$desired = New-DesiredMonitoringPolicy $eventsFailure 'synthetic-channel'
Assert-Contract ($desired.alertStrategy.notificationPrompts.Count -eq 1 -and
    $desired.alertStrategy.notificationPrompts[0] -ceq 'OPENED') (
    "Eventi deve mantenere email errore senza CLOSED fuorviante"
)
Assert-Contract ($desired.conditions[0].conditionThreshold.thresholdValue -eq 0 -and
    $desired.conditions[0].conditionThreshold.aggregations[0].alignmentPeriod -ceq '7200s') (
    "non allentare soglia e finestra dei fallimenti Eventi"
)
Assert-Contract ($desired.documentation.content.Contains('NON dimostra il recupero') -and
    $desired.documentation.content.Contains('event_source_recovered')) (
    "distinzione fra fine finestra e recupero dati non documentata"
)
$actual = $desired | ConvertTo-Json -Depth 20 | ConvertFrom-Json
Assert-Contract (Test-PolicyMatches $actual $desired) "readback policy corretta non riconosciuto"
$actual.alertStrategy.notificationPrompts = @('OPENED', 'CLOSED')
Assert-Contract (-not (Test-PolicyMatches $actual $desired)) (
    "audit non rileva riattivazione CLOSED Eventi"
)

Write-Output "PASS production job operations contracts"
