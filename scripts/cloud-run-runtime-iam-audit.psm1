Set-StrictMode -Version Latest

$script:ExpectedProjectId = "meteo-friul"
$script:ExpectedProjectNumber = "49007668366"
$script:ExpectedAccount = "meteofriul@gmail.com"
$script:ExpectedRegion = "europe-west1"
$script:ExpectedService = "meteofriul-api"
$script:ExpectedEventServiceAccount = "event-source-monitor@meteo-friul.iam.gserviceaccount.com"
$script:ExpectedJobs = [ordered]@{
    "meteofriul-official-alert-sync" = "python|-m app.jobs.sync_official_alerts"
    "meteofriul-event-source-publication-control" = "python|-m app.jobs.control_event_source_publication"
    "meteofriul-event-source-shadow" = "python|-m app.jobs.sync_event_sources"
    "meteofriul-local-notice" = "python|-m app.jobs.send_local_weather_notices"
}

function Get-StringValues {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { [string]$_ })
}

function Get-IamMembers {
    param([object]$Snapshot, [string]$Role)
    $binding = @($Snapshot.iamBindings | Where-Object { [string]$_.role -ceq $Role })
    return @($binding | ForEach-Object { Get-StringValues $_.members } | Sort-Object -Unique)
}

function Test-HasIamMember {
    param([object]$Snapshot, [string]$Role, [string]$Member)
    return @(Get-IamMembers -Snapshot $Snapshot -Role $Role) -ccontains $Member
}

function Test-CloudRunRuntimeIamState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Snapshot,
        [ValidateSet("Baseline", "TargetReady", "Cutover", "Final")][string]$Stage = "Baseline",
        [string]$TargetServiceAccount = "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com",
        [string]$FcmCustomRole = "projects/meteo-friul/roles/meteofriulFcmSender"
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param([string]$Code, [string]$Message, [bool]$Blocking)
        $findings.Add([PSCustomObject]@{ code = $Code; message = $Message; blocking = $Blocking })
    }

    if ([string]$Snapshot.account -cne $script:ExpectedAccount) {
        & $addFinding "account_mismatch" "Account gcloud inatteso." $true
    }
    if ([string]$Snapshot.project.projectId -cne $script:ExpectedProjectId -or
        [string]$Snapshot.project.projectNumber -cne $script:ExpectedProjectNumber) {
        & $addFinding "project_mismatch" "Progetto o project number inatteso." $true
    }
    $defaultServiceAccount = "$($script:ExpectedProjectNumber)-compute@developer.gserviceaccount.com"
    if ($TargetServiceAccount -ceq $defaultServiceAccount -or
        $TargetServiceAccount -ceq $script:ExpectedEventServiceAccount) {
        & $addFinding "target_service_account_not_dedicated" "Il runtime push deve usare un SA distinto da Compute default e SA Eventi." $true
    }

    $services = @($Snapshot.services)
    if ($services.Count -ne 1 -or [string]$services[0].name -cne $script:ExpectedService) {
        & $addFinding "service_inventory_mismatch" "L'inventario deve contenere solo meteofriul-api." $true
    }
    $jobs = @($Snapshot.jobs)
    $actualJobNames = @($jobs | ForEach-Object { [string]$_.name } | Sort-Object)
    $expectedJobNames = @($script:ExpectedJobs.Keys | Sort-Object)
    if (($actualJobNames -join "|") -cne ($expectedJobNames -join "|")) {
        & $addFinding "job_inventory_mismatch" "L'inventario dei quattro Cloud Run Job non coincide." $true
    }

    foreach ($resource in @($services + $jobs)) {
        if ([string]$resource.region -cne $script:ExpectedRegion) {
            & $addFinding "region_mismatch" "Regione inattesa per $($resource.name)." $true
        }
        if ($resource.PSObject.Properties.Name -contains "ready" -and $resource.ready -ne $true) {
            & $addFinding "resource_not_ready" "$($resource.name) non e' Ready." $true
        }
        if (-not ($resource.PSObject.Properties.Name -contains "envNames")) {
            & $addFinding "runtime_env_inventory_missing" "Nomi env non inventariati per $($resource.name)." $true
        } else {
            $explicitCredentialNames = @(
                "FIREBASE_SERVICE_ACCOUNT_JSON",
                "FIREBASE_SERVICE_ACCOUNT_B64",
                "FIREBASE_CREDENTIALS_PATH",
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            $presentCredentialNames = @(Get-StringValues $resource.envNames | Where-Object { $_ -in $explicitCredentialNames })
            if ($presentCredentialNames.Count -gt 0) {
                & $addFinding "explicit_firebase_credentials_present" "Credenziali esplicite scavalcano la service identity su $($resource.name)." $true
            }
        }
        $imagePinned = $resource.PSObject.Properties.Name -contains "image" -and
            [string]$resource.image -cmatch '@sha256:[0-9a-f]{64}$'
        if (-not $imagePinned) {
            & $addFinding "image_not_digest_pinned" "Immagine non fissata per digest su $($resource.name)." ($Stage -ne "Baseline")
        }
    }

    if ($services.Count -eq 1) {
        $service = $services[0]
        $trafficInventoryPresent = $service.PSObject.Properties.Name -contains "traffic" -and
            $service.PSObject.Properties.Name -contains "revisions" -and
            $service.PSObject.Properties.Name -contains "latestReadyRevision"
        if (-not $trafficInventoryPresent) {
            & $addFinding "service_traffic_inventory_missing" "Traffico e revisioni Cloud Run non sono stati inventariati." $true
        } else {
            $traffic = @($service.traffic)
            $revisions = @($service.revisions)
            if ($traffic.Count -eq 0) {
                & $addFinding "service_traffic_empty" "Cloud Run non espone alcuna allocazione di traffico." $true
            }
            $trafficTotal = 0
            foreach ($allocation in $traffic) {
                $revisionName = [string]$allocation.revisionName
                $percent = -1
                try { $percent = [int]$allocation.percent } catch { $percent = -1 }
                if (-not $revisionName -or $percent -lt 0 -or $percent -gt 100) {
                    & $addFinding "service_traffic_entry_invalid" "Allocazione traffico Cloud Run invalida." $true
                    continue
                }
                $trafficTotal += $percent
                $resolved = @($revisions | Where-Object { [string]$_.name -ceq $revisionName })
                if ($resolved.Count -ne 1) {
                    & $addFinding "traffic_revision_unresolved" "La revisione $revisionName referenziata dal traffico non e' risolta una sola volta." $true
                    continue
                }
                $revision = $resolved[0]
                if ($revision.ready -ne $true) {
                    & $addFinding "traffic_revision_not_ready" "La revisione $revisionName non e' Ready." $true
                }
                if ([string]$revision.image -cnotmatch '@sha256:[0-9a-f]{64}$') {
                    & $addFinding "traffic_revision_image_not_digest_pinned" "La revisione $revisionName non espone un digest immutabile." $true
                }
                if ($Stage -in @("Cutover", "Final") -and $percent -gt 0 -and
                    [string]$revision.serviceAccount -cne $TargetServiceAccount) {
                    & $addFinding "traffic_revision_identity_mismatch" "Traffico nonzero sulla revisione $revisionName con identita' diversa dal target." $true
                }
            }
            if ($trafficTotal -ne 100) {
                & $addFinding "service_traffic_total_invalid" "Le allocazioni di traffico non sommano a 100%." $true
            }

            $latestReadyRevision = [string]$service.latestReadyRevision
            if (-not $latestReadyRevision -or
                @($revisions | Where-Object { [string]$_.name -ceq $latestReadyRevision }).Count -ne 1) {
                & $addFinding "latest_ready_revision_unresolved" "latestReadyRevision non e' risolta una sola volta." $true
            }

            if ($Stage -in @("Cutover", "Final")) {
                $rollbackRevision = if ($service.PSObject.Properties.Name -contains "rollbackRevision") {
                    [string]$service.rollbackRevision
                } else { "" }
                $rollbackAllocations = @($traffic | Where-Object { [string]$_.revisionName -ceq $rollbackRevision })
                $rollbackResolved = @($revisions | Where-Object { [string]$_.name -ceq $rollbackRevision })
                if (-not $rollbackRevision -or $rollbackAllocations.Count -eq 0 -or $rollbackResolved.Count -ne 1) {
                    & $addFinding "rollback_revision_not_explicit" "La revisione rollback legacy non e' dichiarata e risolta esplicitamente." $true
                } else {
                    $rollbackHasTraffic = @($rollbackAllocations | Where-Object { [int]$_.percent -ne 0 }).Count -gt 0
                    $rollbackHasTag = @($rollbackAllocations | Where-Object { [string]$_.tag }).Count -gt 0
                    if ($rollbackHasTraffic -or -not $rollbackHasTag) {
                        & $addFinding "rollback_revision_not_zero_traffic" "La revisione rollback deve avere tag esplicito e traffico zero." $true
                    }
                    if ([string]$rollbackResolved[0].serviceAccount -cne $defaultServiceAccount) {
                        & $addFinding "rollback_revision_identity_mismatch" "La revisione rollback dichiarata non e' la revisione legacy sul Compute default." $true
                    }
                }
            }
        }
    }

    foreach ($jobName in $script:ExpectedJobs.Keys) {
        $job = @($jobs | Where-Object { [string]$_.name -ceq $jobName })
        if ($job.Count -ne 1) { continue }
        $actualEntrypoint = "$(Get-StringValues $job[0].command -join ' ')|$(Get-StringValues $job[0].args -join ' ')"
        if ($actualEntrypoint -cne [string]$script:ExpectedJobs[$jobName]) {
            & $addFinding "job_entrypoint_mismatch" "Entrypoint inatteso per $jobName." $true
        }
    }

    $expectedMainIdentity = if ($Stage -in @("Cutover", "Final")) { $TargetServiceAccount } else { $defaultServiceAccount }
    if ($services.Count -eq 1 -and [string]$services[0].serviceAccount -cne $expectedMainIdentity) {
        & $addFinding "service_identity_mismatch" "Identita' runtime inattesa per meteofriul-api nello stage $Stage." $true
    }

    foreach ($job in $jobs) {
        $name = [string]$job.name
        $expectedIdentity = if ($name -in @(
            "meteofriul-event-source-publication-control",
            "meteofriul-event-source-shadow"
        )) {
            $script:ExpectedEventServiceAccount
        } else {
            $expectedMainIdentity
        }
        if ([string]$job.serviceAccount -cne $expectedIdentity) {
            & $addFinding "job_identity_mismatch" "Identita' runtime inattesa per $name nello stage $Stage." $true
        }
    }

    $targetMember = "serviceAccount:$TargetServiceAccount"
    $eventMember = "serviceAccount:$($script:ExpectedEventServiceAccount)"
    $defaultMember = "serviceAccount:$defaultServiceAccount"
    $privilegedRoles = @("roles/owner", "roles/editor")

    if ($Stage -ne "Baseline") {
        if (-not (Test-HasIamMember $Snapshot "roles/datastore.user" $targetMember)) {
            & $addFinding "target_firestore_role_missing" "Il target non ha roles/datastore.user." $true
        }
        if (-not (Test-HasIamMember $Snapshot $FcmCustomRole $targetMember)) {
            & $addFinding "target_fcm_role_missing" "Il target non ha il ruolo custom FCM sender." $true
        }
        $rolePermissions = @($Snapshot.rolePermissions | Where-Object { [string]$_.role -ceq $FcmCustomRole })
        $permissions = @($rolePermissions | ForEach-Object { Get-StringValues $_.permissions } | Sort-Object -Unique)
        if (($permissions -join "|") -cne "cloudmessaging.messages.create") {
            & $addFinding "fcm_custom_role_not_minimal" "Il ruolo custom FCM deve contenere solo cloudmessaging.messages.create." $true
        }
    }

    if (-not (Test-HasIamMember $Snapshot "roles/datastore.user" $eventMember)) {
        & $addFinding "event_firestore_role_missing" "L'identita' Eventi non ha roles/datastore.user." $true
    }
    foreach ($role in $privilegedRoles) {
        if (Test-HasIamMember $Snapshot $role $targetMember) {
            & $addFinding "target_primitive_role_present" "Il target conserva il ruolo primitivo $role." $true
        }
        if (Test-HasIamMember $Snapshot $role $eventMember) {
            & $addFinding "event_primitive_role_present" "L'identita' Eventi conserva il ruolo primitivo $role." $true
        }
    }
    if (Test-HasIamMember $Snapshot $FcmCustomRole $eventMember) {
        & $addFinding "event_fcm_role_present" "I job Eventi non devono poter inviare FCM." $true
    }
    foreach ($role in @("roles/editor", "roles/owner")) {
        if (-not (Test-HasIamMember $Snapshot $role $defaultMember)) { continue }
        $roleLabel = ($role -split '/')[-1]
        if ($Stage -eq "Final") {
            & $addFinding "default_${roleLabel}_still_present" "$role sul Compute default deve essere assente al gate Final." $true
        } else {
            & $addFinding "default_${roleLabel}_legacy" "$role sul Compute default e' ancora presente; conservarlo solo fino al gate Final." $false
        }
    }

    $cloudBuildVerified = $Snapshot.PSObject.Properties.Name -contains "cloudBuild" -and
        $null -ne $Snapshot.cloudBuild -and
        $Snapshot.cloudBuild.PSObject.Properties.Name -contains "defaultServiceAccount"
    if (-not $cloudBuildVerified) {
        & $addFinding "cloud_build_identity_unverified" "L'identita' predefinita Cloud Build non e' stata inventariata." ($Stage -eq "Final")
    } else {
        $cloudBuildServiceAccount = [string]$Snapshot.cloudBuild.defaultServiceAccount
        if ($cloudBuildServiceAccount -ceq $defaultServiceAccount) {
            & $addFinding "cloud_build_uses_default_compute" "Cloud Build usa ancora il Compute default SA." ($Stage -eq "Final")
        } elseif ($cloudBuildServiceAccount -ceq $TargetServiceAccount) {
            & $addFinding "cloud_build_uses_runtime_identity" "Cloud Build non deve riutilizzare il runtime push SA." ($Stage -eq "Final")
        } elseif ($cloudBuildServiceAccount -ceq $script:ExpectedEventServiceAccount) {
            & $addFinding "cloud_build_uses_event_identity" "Cloud Build non deve riutilizzare il SA Eventi." ($Stage -eq "Final")
        } elseif ($cloudBuildServiceAccount -cnotmatch '^[a-z][a-z0-9-]{4,28}[a-z0-9]@meteo-friul\.iam\.gserviceaccount\.com$') {
            & $addFinding "cloud_build_identity_invalid" "Cloud Build non espone un SA dedicato valido del progetto." ($Stage -eq "Final")
        }
    }

    $schedulerVerified = $Snapshot.PSObject.Properties.Name -contains "schedulerServiceAccounts"
    if (-not $schedulerVerified) {
        & $addFinding "scheduler_identities_unverified" "Le identita' Cloud Scheduler non sono state inventariate." ($Stage -eq "Final")
    } elseif (@(Get-StringValues $Snapshot.schedulerServiceAccounts) -ccontains $defaultServiceAccount) {
        & $addFinding "scheduler_uses_default_compute" "Un invocatore Cloud Scheduler usa il Compute default SA." ($Stage -eq "Final")
    }

    $blocking = @($findings | Where-Object { $_.blocking -eq $true })
    $serviceEvidence = $null
    if ($services.Count -eq 1) {
        $serviceItem = $services[0]
        $evidenceTraffic = if ($serviceItem.PSObject.Properties.Name -contains "traffic") {
            @($serviceItem.traffic | ForEach-Object {
                [PSCustomObject]@{
                    revisionName = [string]$_.revisionName
                    percent = [int]$_.percent
                    tag = [string]$_.tag
                }
            })
        } else { @() }
        $evidenceRevisions = if ($serviceItem.PSObject.Properties.Name -contains "revisions") {
            @($serviceItem.revisions | ForEach-Object {
                [PSCustomObject]@{
                    name = [string]$_.name
                    serviceAccount = [string]$_.serviceAccount
                    image = [string]$_.image
                    ready = $_.ready -eq $true
                }
            })
        } else { @() }
        $serviceEvidence = [PSCustomObject]@{
            templateServiceAccount = [string]$serviceItem.serviceAccount
            latestReadyRevision = if ($serviceItem.PSObject.Properties.Name -contains "latestReadyRevision") { [string]$serviceItem.latestReadyRevision } else { "" }
            rollbackRevision = if ($serviceItem.PSObject.Properties.Name -contains "rollbackRevision") { [string]$serviceItem.rollbackRevision } else { "" }
            traffic = @($evidenceTraffic)
            revisions = @($evidenceRevisions)
        }
    }
    return [PSCustomObject]@{
        schemaVersion = "cloud-run-runtime-iam-audit-v1"
        stage = $Stage
        ready = ($blocking.Count -eq 0)
        blockingCount = $blocking.Count
        findings = $findings.ToArray()
        observed = [PSCustomObject]@{
            service = $serviceEvidence
            cloudBuildDefaultServiceAccount = if ($cloudBuildVerified) { [string]$Snapshot.cloudBuild.defaultServiceAccount } else { "" }
        }
        expected = [PSCustomObject]@{
            targetServiceAccount = $TargetServiceAccount
            eventServiceAccount = $script:ExpectedEventServiceAccount
            firestoreRole = "roles/datastore.user"
            fcmCustomRole = $FcmCustomRole
            fcmPermission = "cloudmessaging.messages.create"
        }
    }
}

Export-ModuleMember -Function Test-CloudRunRuntimeIamState
