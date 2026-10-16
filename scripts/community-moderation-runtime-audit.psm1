Set-StrictMode -Version Latest

$script:ExpectedAccount = "meteofriul@gmail.com"
$script:ExpectedProjectId = "meteo-friul"
$script:ExpectedProjectNumber = "49007668366"
$script:ExpectedProjectState = "ACTIVE"
$script:ExpectedRegion = "europe-west1"
$script:ExpectedJobName = "meteofriul-community-moderation-digest"
$script:ExpectedSchedulerName = "community-moderation-digest"
$script:ExpectedRuntimeServiceAccount = (
    "community-moderation-digest@meteo-friul.iam.gserviceaccount.com"
)
$script:ExpectedSchedulerServiceAccount = (
    "community-moderation-scheduler@meteo-friul.iam.gserviceaccount.com"
)
$script:ExpectedSchedulerServiceAgent = (
    "service-49007668366@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
)
$script:ExpectedNotificationChannel = (
    "projects/meteo-friul/notificationChannels/11334808831344967323"
)
$script:ExpectedEnabledApis = @(
    "cloudscheduler.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com"
)
$script:ExpectedJobCommand = @("python")
$script:ExpectedJobArgs = @(
    "-m",
    "app.jobs.emit_community_moderation_digest",
    "--apply"
)
$script:ExpectedJobEnvironment = [ordered]@{
    COMMUNITY_STORAGE = "firestore"
    FIREBASE_PROJECT_ID = "meteo-friul"
}
$script:ExpectedSchedulerCron = "40 8,20 * * *"
$script:ExpectedSchedulerTimeZone = "Europe/Rome"
$script:ExpectedSchedulerUri = (
    "https://run.googleapis.com/v2/projects/meteo-friul/locations/" +
    "europe-west1/jobs/meteofriul-community-moderation-digest:run"
)
$script:ExpectedOauthScope = "https://www.googleapis.com/auth/cloud-platform"
$script:ReadyPolicyDisplayName = "Meteo Friul - digest moderazione Community"
$script:FailurePolicyDisplayName = (
    "Meteo Friul - circuito moderazione Community fallito"
)
$script:ReadyConditionDisplayName = "Digest moderazione pronto"
$script:FailureConditionDisplayName = "Errore job o scheduler moderazione"
$script:ReadyFilter = (
    'log_id("meteofriul-community-moderation-digest") AND ' +
    'jsonPayload.event="community_moderation_digest_ready" AND ' +
    'severity=WARNING'
)
$script:FailureFilter = (
    'severity>=ERROR AND ((resource.type="cloud_run_job" AND ' +
    'resource.labels.job_name="meteofriul-community-moderation-digest") ' +
    'OR (resource.type="cloud_scheduler_job" AND ' +
    'resource.labels.job_id="community-moderation-digest"))'
)
$script:ReadyDocumentation = (
    "Nuove segnalazioni Territorio raggruppate in un digest sanitizzato. " +
    "Usare il ``group_ref`` solo per correlare il gruppo tramite lo strumento " +
    "operatore privato. Il log non contiene ID installazione, chiavi private " +
    "o coordinate GPS."
)
$script:FailureDocumentation = (
    "Errore del job o dello scheduler di moderazione Territorio. Controllare " +
    "l'esecuzione ``meteofriul-community-moderation-digest``; il digest non " +
    "viene riconosciuto come consegnato finche' Cloud Logging non lo accetta."
)

function Get-ModerationRuntimeProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-ModerationRuntimeStrings {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { [string]$_ })
}

function Test-ModerationRuntimeSequence {
    param([object]$Actual, [object]$Expected)
    $actualStrings = @(Get-ModerationRuntimeStrings $Actual)
    $expectedStrings = @(Get-ModerationRuntimeStrings $Expected)
    return (($actualStrings -join "`n") -ceq ($expectedStrings -join "`n"))
}

function Get-ModerationRuntimeBindingsForMember {
    param([object]$Bindings, [string]$Member)
    return @(@($Bindings) | Where-Object {
        $Member -cin @(Get-ModerationRuntimeStrings (
            Get-ModerationRuntimeProperty $_ "members"
        ))
    })
}

function Test-ModerationRuntimeBindingUnconditional {
    param([object]$Binding)
    $condition = Get-ModerationRuntimeProperty $Binding "condition"
    if ($null -eq $condition) { return $true }
    return $false
}

function Get-ModerationRuntimeLabelValue {
    param([object]$Labels, [string]$Name)
    if ($null -eq $Labels) { return "" }
    if ($Labels -is [System.Collections.IDictionary]) {
        if ($Labels.Contains($Name)) { return [string]$Labels[$Name] }
        return ""
    }
    return [string](Get-ModerationRuntimeProperty $Labels $Name)
}

function Test-CommunityModerationRuntimeSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Snapshot,
        [ValidateSet("PreActivation", "Final")]
        [string]$Stage = "PreActivation",
        [Parameter(Mandatory = $true)]
        [ValidatePattern('@sha256:[0-9a-f]{64}$')]
        [string]$ExpectedImage
    )

    $Stage = if ($Stage -ieq "PreActivation") {
        "PreActivation"
    } else {
        "Final"
    }

    $findings = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param([string]$Code, [string]$Message)
        $findings.Add([PSCustomObject]@{
            code = $Code
            message = $Message
            blocking = $true
        })
    }

    if ([string](Get-ModerationRuntimeProperty $Snapshot "account") -cne
        $script:ExpectedAccount) {
        & $addFinding "account_mismatch" "Account gcloud inatteso."
    }
    if ([string](Get-ModerationRuntimeProperty $Snapshot "configuredProject") -cne
        $script:ExpectedProjectId) {
        & $addFinding "configured_project_mismatch" (
            "Il progetto attivo nella configurazione gcloud e' inatteso."
        )
    }
    $project = Get-ModerationRuntimeProperty $Snapshot "project"
    if ([string](Get-ModerationRuntimeProperty $project "projectId") -cne
            $script:ExpectedProjectId -or
        [string](Get-ModerationRuntimeProperty $project "projectNumber") -cne
            $script:ExpectedProjectNumber -or
        [string](Get-ModerationRuntimeProperty $project "state") -cne
            $script:ExpectedProjectState) {
        & $addFinding "project_mismatch" (
            "Project ID, number o stato non corrispondono al contratto."
        )
    }

    $enabledApis = @(
        Get-ModerationRuntimeStrings (
            Get-ModerationRuntimeProperty $Snapshot "enabledApis"
        ) | Sort-Object -Unique
    )
    $missingApis = @($script:ExpectedEnabledApis | Where-Object {
        $_ -cnotin $enabledApis
    })
    if ($missingApis.Count -gt 0) {
        & $addFinding "required_api_missing" (
            "API richieste non abilitate: $($missingApis -join ', ')."
        )
    }

    $serviceAccounts = @(
        Get-ModerationRuntimeProperty $Snapshot "serviceAccounts"
    )
    foreach ($expectedAccount in @(
        $script:ExpectedRuntimeServiceAccount,
        $script:ExpectedSchedulerServiceAccount
    )) {
        $matches = @($serviceAccounts | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "email") -ceq
                $expectedAccount
        })
        if ($matches.Count -ne 1) {
            & $addFinding "service_account_inventory_mismatch" (
                "Il service account $expectedAccount deve comparire una volta."
            )
            continue
        }
        if ((Get-ModerationRuntimeProperty $matches[0] "disabled") -ne $false) {
            & $addFinding "service_account_disabled" (
                "Il service account $expectedAccount non risulta esplicitamente abilitato."
            )
        }
        $keyCount = Get-ModerationRuntimeProperty $matches[0] (
            "userManagedKeyCount"
        )
        if ($null -eq $keyCount -or [int]$keyCount -ne 0) {
            & $addFinding "service_account_user_key_present" (
                "Il service account $expectedAccount deve avere zero chiavi " +
                "gestite dall'utente."
            )
        }
    }

    $jobs = @(Get-ModerationRuntimeProperty $Snapshot "jobs")
    $jobMatches = @($jobs | Where-Object {
        [string](Get-ModerationRuntimeProperty $_ "name") -ceq
            $script:ExpectedJobName
    })
    $job = if ($jobMatches.Count -eq 1) { $jobMatches[0] } else { $null }
    if ($jobMatches.Count -ne 1) {
        & $addFinding "job_inventory_mismatch" (
            "Il job Moderazione deve comparire esattamente una volta."
        )
    } else {
        if ([string](Get-ModerationRuntimeProperty $job "region") -cne
                $script:ExpectedRegion) {
            & $addFinding "job_region_mismatch" "Regione Job inattesa."
        }
        if ((Get-ModerationRuntimeProperty $job "ready") -ne $true) {
            & $addFinding "job_not_ready" "Il job Moderazione non e' Ready."
        }
        if ([string](Get-ModerationRuntimeProperty $job "image") -cne
                $ExpectedImage) {
            & $addFinding "job_image_mismatch" (
                "Il job non usa la digest immutabile approvata."
            )
        }
        if ([string](Get-ModerationRuntimeProperty $job "serviceAccount") -cne
                $script:ExpectedRuntimeServiceAccount) {
            & $addFinding "job_identity_mismatch" (
                "Il job non usa il runtime SA dedicato."
            )
        }
        if (-not (Test-ModerationRuntimeSequence (
            Get-ModerationRuntimeProperty $job "command"
        ) $script:ExpectedJobCommand)) {
            & $addFinding "job_command_mismatch" "Command Job inatteso."
        }
        if (-not (Test-ModerationRuntimeSequence (
            Get-ModerationRuntimeProperty $job "args"
        ) $script:ExpectedJobArgs)) {
            & $addFinding "job_args_mismatch" "Argomenti Job inattesi."
        }

        $actualEnvironmentEntries = @(
            Get-ModerationRuntimeProperty $job "env"
        )
        $actualEnvironment = [ordered]@{}
        foreach ($item in $actualEnvironmentEntries) {
            $name = [string](Get-ModerationRuntimeProperty $item "name")
            if ($name) {
                $actualEnvironment[$name] = [string](
                    Get-ModerationRuntimeProperty $item "value"
                )
            }
        }
        $actualEnvironmentPairs = @($actualEnvironment.GetEnumerator() |
            Sort-Object Key | ForEach-Object { "$($_.Key)=$($_.Value)" })
        $expectedEnvironmentPairs = @(
            $script:ExpectedJobEnvironment.GetEnumerator() |
                Sort-Object Key | ForEach-Object { "$($_.Key)=$($_.Value)" }
        )
        $actualEnvironmentNames = @($actualEnvironmentEntries |
            ForEach-Object {
                [string](Get-ModerationRuntimeProperty $_ "name")
            })
        $uniqueEnvironmentNames = @($actualEnvironmentNames |
            Sort-Object -Unique)
        if ($actualEnvironmentEntries.Count -ne
                $script:ExpectedJobEnvironment.Count -or
            $uniqueEnvironmentNames.Count -ne $actualEnvironmentEntries.Count -or
            ($actualEnvironmentPairs -join "`n") -cne
            ($expectedEnvironmentPairs -join "`n")) {
            & $addFinding "job_environment_mismatch" (
                "Le variabili del Job non sono esattamente quelle approvate."
            )
        }
        if ([int](Get-ModerationRuntimeProperty $job "containerCount") -ne
                1 -or
            [int](Get-ModerationRuntimeProperty $job "volumeCount") -ne 0 -or
            [int](Get-ModerationRuntimeProperty $job "volumeMountCount") -ne
                0) {
            & $addFinding "job_container_shape_mismatch" (
                "Il job deve avere un solo container e nessun volume o mount."
            )
        }
        if ([int](Get-ModerationRuntimeProperty $job "taskCount") -ne 1 -or
            [int](Get-ModerationRuntimeProperty $job "parallelism") -ne 1) {
            & $addFinding "job_task_shape_mismatch" (
                "Il job deve avere taskCount e parallelism pari a uno."
            )
        }
        $jobMaxRetries = Get-ModerationRuntimeProperty $job "maxRetries"
        if ($null -eq $jobMaxRetries -or [int]$jobMaxRetries -ne 0) {
            & $addFinding "job_retry_mismatch" "Il job deve avere zero retry."
        }
        if ([int](Get-ModerationRuntimeProperty $job "timeoutSeconds") -ne
            120) {
            & $addFinding "job_timeout_mismatch" (
                "Il timeout Job deve essere 120 secondi."
            )
        }
        if ([string](Get-ModerationRuntimeProperty $job "cpu") -cne "1" -or
            [string](Get-ModerationRuntimeProperty $job "memory") -cne
                "512Mi") {
            & $addFinding "job_resources_mismatch" (
                "Il job deve usare 1 CPU e 512Mi."
            )
        }
    }
    if ($jobs.Count -gt 1) {
        & $addFinding "job_related_inventory_mismatch" (
            "Il circuito deve comprendere un solo job Moderazione; sono " +
            "state rilevate risorse correlate aggiuntive."
        )
    }

    $projectBindings = @(
        Get-ModerationRuntimeProperty $Snapshot "projectIamBindings"
    )
    $publicProjectBindings = @($projectBindings | Where-Object {
        $members = @(Get-ModerationRuntimeStrings (
            Get-ModerationRuntimeProperty $_ "members"
        ))
        $members -ccontains "allUsers" -or
            $members -ccontains "allAuthenticatedUsers"
    })
    if ($publicProjectBindings.Count -gt 0) {
        & $addFinding "project_public_principal_present" (
            "La policy IAM progetto non deve contenere principal pubblici."
        )
    }
    $runtimeMember = "serviceAccount:$($script:ExpectedRuntimeServiceAccount)"
    $runtimeBindings = @(
        Get-ModerationRuntimeBindingsForMember $projectBindings $runtimeMember
    )
    $runtimeRoles = @($runtimeBindings | ForEach-Object {
        [string](Get-ModerationRuntimeProperty $_ "role")
    } | Sort-Object -Unique)
    $expectedRuntimeRoles = @(
        "roles/datastore.user",
        "roles/logging.logWriter"
    )
    $runtimeRoleCountsAreExact = $true
    foreach ($role in $expectedRuntimeRoles) {
        if (@($runtimeBindings | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "role") -ceq $role
        }).Count -ne 1) {
            $runtimeRoleCountsAreExact = $false
        }
    }
    if ($runtimeBindings.Count -ne $expectedRuntimeRoles.Count -or
        -not $runtimeRoleCountsAreExact -or
        ($runtimeRoles -join "`n") -cne
        (($expectedRuntimeRoles | Sort-Object) -join "`n")) {
        & $addFinding "runtime_project_roles_not_minimal" (
            "Il runtime SA deve avere solo datastore.user e logging.logWriter."
        )
    }
    if (@($runtimeBindings | Where-Object {
        -not (Test-ModerationRuntimeBindingUnconditional $_)
    }).Count -gt 0) {
        & $addFinding "runtime_project_role_conditional" (
            "I due ruoli runtime attesi devono essere incondizionati."
        )
    }

    $schedulerMember = (
        "serviceAccount:$($script:ExpectedSchedulerServiceAccount)"
    )
    $schedulerProjectBindings = @(
        Get-ModerationRuntimeBindingsForMember $projectBindings $schedulerMember
    )
    if ($schedulerProjectBindings.Count -gt 0) {
        & $addFinding "scheduler_project_role_present" (
            "Lo scheduler SA non deve avere ruoli a livello progetto."
        )
    }

    $schedulerAgentMember = (
        "serviceAccount:$($script:ExpectedSchedulerServiceAgent)"
    )
    $schedulerAgentAllBindings = @(
        Get-ModerationRuntimeBindingsForMember (
            $projectBindings
        ) $schedulerAgentMember
    )
    $schedulerAgentBindings = @(
        $schedulerAgentAllBindings | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "role") -ceq
                "roles/cloudscheduler.serviceAgent"
        }
    )
    $schedulerAgentMembers = @($schedulerAgentBindings | ForEach-Object {
        Get-ModerationRuntimeStrings (
            Get-ModerationRuntimeProperty $_ "members"
        )
    } | Sort-Object -Unique)
    if ($schedulerAgentAllBindings.Count -ne 1 -or
        $schedulerAgentBindings.Count -ne 1 -or
        $schedulerAgentMembers.Count -ne 1 -or
        $schedulerAgentMembers[0] -cne $schedulerAgentMember -or
        -not (Test-ModerationRuntimeBindingUnconditional (
            $schedulerAgentBindings[0]
        ))) {
        & $addFinding "scheduler_service_agent_role_missing" (
            "Il service agent Google Scheduler non conserva il ruolo atteso."
        )
    }

    if ($null -ne $job) {
        $jobBindings = @(Get-ModerationRuntimeProperty $job "iamBindings")
        $allJobMembers = @($jobBindings | ForEach-Object {
            Get-ModerationRuntimeStrings (
                Get-ModerationRuntimeProperty $_ "members"
            )
        })
        if ($allJobMembers -ccontains "allUsers" -or
            $allJobMembers -ccontains "allAuthenticatedUsers") {
            & $addFinding "job_public_invoker_present" (
                "Il job Moderazione non deve essere pubblico."
            )
        }
        $unexpectedJobRoles = @($jobBindings | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "role") -cne
                "roles/run.invoker"
        })
        if ($unexpectedJobRoles.Count -gt 0) {
            & $addFinding "job_iam_role_unexpected" (
                "La policy IAM del Job contiene ruoli inattesi."
            )
        }
        $invokerBindings = @($jobBindings | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "role") -ceq
                "roles/run.invoker"
        })
        $invokerMembers = @($invokerBindings | ForEach-Object {
            Get-ModerationRuntimeStrings (
                Get-ModerationRuntimeProperty $_ "members"
            )
        } | Sort-Object -Unique)
        if ($invokerBindings.Count -ne 1 -or
            ($invokerMembers -join "`n") -cne $schedulerMember -or
            -not (Test-ModerationRuntimeBindingUnconditional (
                $invokerBindings[0]
            ))) {
            & $addFinding "job_invoker_mismatch" (
                "Solo lo scheduler SA deve invocare il singolo Job."
            )
        }
    }

    $schedulers = @(Get-ModerationRuntimeProperty $Snapshot "schedulers")
    $schedulerMatches = @($schedulers | Where-Object {
        [string](Get-ModerationRuntimeProperty $_ "name") -ceq
            $script:ExpectedSchedulerName
    })
    $scheduler = if ($schedulerMatches.Count -eq 1) {
        $schedulerMatches[0]
    } else { $null }
    if ($schedulerMatches.Count -ne 1) {
        & $addFinding "scheduler_inventory_mismatch" (
            "Lo scheduler Moderazione deve comparire esattamente una volta."
        )
    } else {
        $expectedState = if ($Stage -ceq "PreActivation") {
            "PAUSED"
        } else { "ENABLED" }
        if ([string](Get-ModerationRuntimeProperty $scheduler "state") -cne
                $expectedState) {
            & $addFinding "scheduler_state_mismatch" (
                "Stato scheduler inatteso per lo stage $Stage."
            )
        }
        if ([string](Get-ModerationRuntimeProperty $scheduler "region") -cne
                $script:ExpectedRegion -or
            [string](Get-ModerationRuntimeProperty $scheduler "schedule") -cne
                $script:ExpectedSchedulerCron -or
            [string](Get-ModerationRuntimeProperty $scheduler "timeZone") -cne
                $script:ExpectedSchedulerTimeZone) {
            & $addFinding "scheduler_schedule_mismatch" (
                "Regione, cron o timezone Scheduler inattesi."
            )
        }
        if ([string](Get-ModerationRuntimeProperty $scheduler "uri") -cne
                $script:ExpectedSchedulerUri -or
            [string](Get-ModerationRuntimeProperty $scheduler "httpMethod") -cne
                "POST") {
            & $addFinding "scheduler_target_mismatch" (
                "Target HTTP Scheduler inatteso."
            )
        }
        if ([string](Get-ModerationRuntimeProperty $scheduler "authType") -cne
                "oauth" -or
            [string](Get-ModerationRuntimeProperty (
                $scheduler
            ) "serviceAccount") -cne
                $script:ExpectedSchedulerServiceAccount -or
            [string](Get-ModerationRuntimeProperty $scheduler "scope") -cne
                $script:ExpectedOauthScope) {
            & $addFinding "scheduler_auth_mismatch" (
                "Scheduler deve usare OAuth con il SA dedicato e scope atteso."
            )
        }
        if ([int](Get-ModerationRuntimeProperty (
            $scheduler
        ) "attemptDeadlineSeconds") -ne 120) {
            & $addFinding "scheduler_deadline_mismatch" (
                "Attempt deadline Scheduler deve essere 120 secondi."
            )
        }
        $schedulerRetries = Get-ModerationRuntimeProperty (
            $scheduler
        ) "maxRetryAttempts"
        if ($null -ne $schedulerRetries -and [int]$schedulerRetries -ne 0) {
            & $addFinding "scheduler_retry_mismatch" (
                "Scheduler deve avere zero retry o campo omesso equivalente."
            )
        }
        if (-not [string]::IsNullOrWhiteSpace([string](
            Get-ModerationRuntimeProperty $scheduler "body"
        )) -or
            @(Get-ModerationRuntimeProperty $scheduler "headers").Count -ne
                0) {
            & $addFinding "scheduler_request_shape_mismatch" (
                "Scheduler non deve inviare body o header personalizzati."
            )
        }
    }
    if ($schedulers.Count -gt 1) {
        & $addFinding "scheduler_related_inventory_mismatch" (
            "Il circuito deve comprendere un solo scheduler Moderazione; " +
            "sono state rilevate risorse correlate aggiuntive."
        )
    }

    $channel = Get-ModerationRuntimeProperty $Snapshot "notificationChannel"
    $channelVerificationStatus = [string](
        Get-ModerationRuntimeProperty $channel "verificationStatus"
    )
    if ([string](Get-ModerationRuntimeProperty $channel "name") -cne
            $script:ExpectedNotificationChannel -or
        [string](Get-ModerationRuntimeProperty $channel "type") -cne "email" -or
        (Get-ModerationRuntimeProperty $channel "enabled") -ne $true -or
        (-not [string]::IsNullOrWhiteSpace($channelVerificationStatus) -and
            $channelVerificationStatus -cne "VERIFIED") -or
        [string](Get-ModerationRuntimeProperty $channel "emailAddress") -cne
            "info@meteofriul.it") {
        & $addFinding "notification_channel_mismatch" (
            "Il canale Monitoring deve essere l'email info@meteofriul.it " +
            "attiva; uno stato di verifica esposto deve essere VERIFIED."
        )
    }

    $policyContracts = @(
        [PSCustomObject]@{
            displayName = $script:ReadyPolicyDisplayName
            severity = "WARNING"
            conditionDisplayName = $script:ReadyConditionDisplayName
            filter = $script:ReadyFilter
            documentation = $script:ReadyDocumentation
            signal = "digest-ready"
        },
        [PSCustomObject]@{
            displayName = $script:FailurePolicyDisplayName
            severity = "ERROR"
            conditionDisplayName = $script:FailureConditionDisplayName
            filter = $script:FailureFilter
            documentation = $script:FailureDocumentation
            signal = "runtime-failure"
        }
    )
    $policies = @(Get-ModerationRuntimeProperty $Snapshot "alertPolicies")
    $relatedPolicies = @($policies | Where-Object {
        $policyDisplayName = [string](
            Get-ModerationRuntimeProperty $_ "displayName"
        )
        $conditionText = @(
            @(Get-ModerationRuntimeProperty $_ "conditions") |
                ForEach-Object {
                    [string](Get-ModerationRuntimeProperty $_ "filter")
                }
        ) -join " "
        $policyLabels = Get-ModerationRuntimeProperty $_ "userLabels"
        $policyServiceLabel = Get-ModerationRuntimeLabelValue (
            $policyLabels
        ) "service"
        $policySignalLabel = Get-ModerationRuntimeLabelValue (
            $policyLabels
        ) "signal"
        $policyDisplayName -ceq $script:ReadyPolicyDisplayName -or
            $policyDisplayName -ceq $script:FailurePolicyDisplayName -or
            $policyDisplayName -match (
                '(?i)community.*moderation|moderation.*community'
            ) -or
            $conditionText -match (
                '(?i)meteofriul-community-moderation-digest|' +
                'community-moderation-digest|' +
                'community_moderation_digest'
            ) -or
            $policyServiceLabel -ceq "community-moderation" -or
            $policySignalLabel -cin @("digest-ready", "runtime-failure")
    })
    $relatedPolicyNames = @($relatedPolicies | ForEach-Object {
        [string](Get-ModerationRuntimeProperty $_ "displayName")
    } | Sort-Object)
    $expectedPolicyNames = @(
        $script:ReadyPolicyDisplayName,
        $script:FailurePolicyDisplayName
    ) | Sort-Object
    if ($relatedPolicies.Count -ne 2 -or
        ($relatedPolicyNames -join "`n") -cne
            ($expectedPolicyNames -join "`n")) {
        & $addFinding "monitoring_related_policy_inventory_mismatch" (
            "Il circuito deve avere soltanto le due policy Monitoring " +
            "approvate, senza copie o policy correlate aggiuntive."
        )
    }
    foreach ($contract in $policyContracts) {
        $matches = @($policies | Where-Object {
            [string](Get-ModerationRuntimeProperty $_ "displayName") -ceq
                [string]$contract.displayName
        })
        if ($matches.Count -ne 1) {
            & $addFinding "monitoring_policy_inventory_mismatch" (
                "Policy assente o duplicata: $($contract.displayName)."
            )
            continue
        }
        $policy = $matches[0]
        if ((Get-ModerationRuntimeProperty $policy "enabled") -ne $true -or
            [string](Get-ModerationRuntimeProperty $policy "severity") -cne
                [string]$contract.severity -or
            [string](Get-ModerationRuntimeProperty $policy "combiner") -cne
                "OR") {
            & $addFinding "monitoring_policy_state_mismatch" (
                "Stato, severity o combiner errati: $($contract.displayName)."
            )
        }
        $conditions = @(Get-ModerationRuntimeProperty $policy "conditions")
        if ($conditions.Count -ne 1 -or
            [string](Get-ModerationRuntimeProperty (
                $conditions[0]
            ) "type") -cne "conditionMatchedLog" -or
            [string](Get-ModerationRuntimeProperty (
                $conditions[0]
            ) "displayName") -cne [string]$contract.conditionDisplayName -or
            [string](Get-ModerationRuntimeProperty (
                $conditions[0]
            ) "filter") -cne [string]$contract.filter) {
            & $addFinding "monitoring_policy_condition_mismatch" (
                "Condition log-match errata: $($contract.displayName)."
            )
        }
        if ($conditions.Count -eq 1 -and
            @(Get-ModerationRuntimeProperty (
                $conditions[0]
            ) "labelExtractors").Count -ne 0) {
            & $addFinding "monitoring_policy_label_extractors_present" (
                "La policy non deve estrarre etichette dai log: " +
                "$($contract.displayName)."
            )
        }
        $channels = @(
            Get-ModerationRuntimeStrings (
                Get-ModerationRuntimeProperty $policy "notificationChannels"
            ) | Sort-Object -Unique
        )
        if ($channels.Count -ne 1 -or
            $channels[0] -cne $script:ExpectedNotificationChannel) {
            & $addFinding "monitoring_policy_channel_mismatch" (
                "Canale inatteso: $($contract.displayName)."
            )
        }
        if ([string](Get-ModerationRuntimeProperty (
            $policy
        ) "notificationRateLimitPeriod") -cne "3600s" -or
            [string](Get-ModerationRuntimeProperty $policy "autoClose") -cne
                "1800s") {
            & $addFinding "monitoring_policy_strategy_mismatch" (
                "Rate limit o autoClose errati: $($contract.displayName)."
            )
        }
        $prompts = @(
            Get-ModerationRuntimeStrings (
                Get-ModerationRuntimeProperty $policy "notificationPrompts"
            )
        )
        if ($prompts.Count -ne 1 -or $prompts[0] -cne "OPENED") {
            & $addFinding "monitoring_policy_prompt_mismatch" (
                "Le log-match policy devono notificare solo OPENED."
            )
        }
        $documentation = Get-ModerationRuntimeProperty (
            $policy
        ) "documentation"
        if ([string](Get-ModerationRuntimeProperty (
            $documentation
        ) "mimeType") -cne "text/markdown" -or
            [string](Get-ModerationRuntimeProperty (
            $documentation
        ) "content") -cne [string]$contract.documentation) {
            & $addFinding "monitoring_policy_documentation_mismatch" (
                "Documentazione policy inattesa: $($contract.displayName)."
            )
        }
        $labels = Get-ModerationRuntimeProperty $policy "userLabels"
        $labelNames = if ($labels -is [System.Collections.IDictionary]) {
            @($labels.Keys | ForEach-Object { [string]$_ } | Sort-Object)
        } elseif ($null -ne $labels) {
            @($labels.PSObject.Properties.Name | ForEach-Object {
                [string]$_
            } | Sort-Object)
        } else { @() }
        if (($labelNames -join "`n") -cne "service`nsignal" -or
            (Get-ModerationRuntimeLabelValue $labels "service") -cne
                "community-moderation" -or
            (Get-ModerationRuntimeLabelValue $labels "signal") -cne
                [string]$contract.signal) {
            & $addFinding "monitoring_policy_labels_mismatch" (
                "User labels policy inattese: $($contract.displayName)."
            )
        }
    }

    $unexpectedMetrics = @(
        @(Get-ModerationRuntimeProperty $Snapshot "logMetrics") |
            Where-Object {
                $text = (
                    [string](Get-ModerationRuntimeProperty $_ "name") + " " +
                    [string](Get-ModerationRuntimeProperty $_ "description") +
                    " " + [string](Get-ModerationRuntimeProperty $_ "filter")
                )
                $text -cmatch (
                    '(?i)community.*moderation|moderation.*community|' +
                    'meteofriul-community-moderation-digest|' +
                    'community_moderation_digest'
                )
            }
    )
    if ($unexpectedMetrics.Count -gt 0) {
        & $addFinding "moderation_log_metric_present" (
            "Le policy devono essere log-match dirette, senza log metric."
        )
    }

    $blocking = @($findings | Where-Object { $_.blocking -eq $true })
    return [PSCustomObject]@{
        schemaVersion = "community-moderation-runtime-audit-v1"
        event = "community_moderation_runtime_audit"
        capturedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        stage = $Stage
        ready = ($blocking.Count -eq 0)
        blockingCount = $blocking.Count
        warningCount = 0
        findings = $findings.ToArray()
        observed = [PSCustomObject]@{
            jobName = if ($null -ne $job) {
                [string](Get-ModerationRuntimeProperty $job "name")
            } else { "" }
            jobImage = if ($null -ne $job) {
                [string](Get-ModerationRuntimeProperty $job "image")
            } else { "" }
            schedulerName = if ($null -ne $scheduler) {
                [string](Get-ModerationRuntimeProperty $scheduler "name")
            } else { "" }
            schedulerState = if ($null -ne $scheduler) {
                [string](Get-ModerationRuntimeProperty $scheduler "state")
            } else { "" }
            policyDisplayNames = @($relatedPolicies | ForEach-Object {
                [string](Get-ModerationRuntimeProperty $_ "displayName")
            } | Sort-Object)
        }
    }
}

Export-ModuleMember -Function Test-CommunityModerationRuntimeSnapshot
