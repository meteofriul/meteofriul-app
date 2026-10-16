Set-StrictMode -Version Latest

function Get-NotificationRuntimeIamValues {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    return @($Value | ForEach-Object { [string]$_ })
}

function Test-NotificationRuntimeIamState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Snapshot,
        [string]$ExpectedAccount = "meteofriul@gmail.com",
        [string]$ExpectedProjectId = "meteo-friul",
        [string]$ExpectedProjectNumber = "49007668366",
        [string]$TargetServiceAccount = (
            "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com"
        ),
        [string]$FcmCustomRole = (
            "projects/meteo-friul/roles/meteofriulFcmSender"
        )
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param([string]$Code, [string]$Message)
        $findings.Add([PSCustomObject]@{
            code = $Code
            message = $Message
            blocking = $true
        })
    }

    if ([string]$Snapshot.account -cne $ExpectedAccount) {
        & $addFinding "account_mismatch" "Account gcloud inatteso."
    }
    if ([string]$Snapshot.project.projectId -cne $ExpectedProjectId -or
        [string]$Snapshot.project.projectNumber -cne $ExpectedProjectNumber) {
        & $addFinding "project_mismatch" "Progetto Google Cloud inatteso."
    }

    $serviceAccounts = @($Snapshot.serviceAccounts)
    $targetAccounts = @($serviceAccounts | Where-Object {
        [string]$_.email -ceq $TargetServiceAccount
    })
    if ($targetAccounts.Count -eq 0) {
        & $addFinding "service_account_missing" (
            "Il service account runtime notifiche non esiste."
        )
    } elseif ($targetAccounts.Count -ne 1) {
        & $addFinding "service_account_ambiguous" (
            "Il service account runtime non e' univoco."
        )
    } elseif ($targetAccounts[0].disabled -eq $true) {
        & $addFinding "service_account_disabled" (
            "Il service account runtime e' disabilitato."
        )
    }

    $roles = @($Snapshot.roles)
    $targetRoles = @($roles | Where-Object {
        [string]$_.name -ceq $FcmCustomRole
    })
    if ($targetRoles.Count -eq 0) {
        & $addFinding "custom_role_missing" "Il ruolo FCM minimo non esiste."
    } elseif ($targetRoles.Count -ne 1) {
        & $addFinding "custom_role_ambiguous" "Il ruolo FCM non e' univoco."
    } elseif (-not (
        $targetRoles[0].PSObject.Properties.Name -contains "includedPermissions"
    )) {
        & $addFinding "custom_role_definition_incomplete" (
            "La definizione autorevole del ruolo FCM non e' disponibile."
        )
    } else {
        $permissions = @(
            Get-NotificationRuntimeIamValues $targetRoles[0].includedPermissions |
                Sort-Object -Unique
        )
        if (($permissions -join "|") -cne "cloudmessaging.messages.create") {
            & $addFinding "custom_role_permissions_mismatch" (
                "Il ruolo FCM deve contenere una sola permission."
            )
        }
    }

    $member = "serviceAccount:$TargetServiceAccount"
    $bindings = @($Snapshot.iamBindings)
    $targetBindings = @($bindings | Where-Object {
        @(Get-NotificationRuntimeIamValues $_.members) -ccontains $member
    })
    $actualRoles = @($targetBindings | ForEach-Object {
        [string]$_.role
    } | Sort-Object -Unique)
    $expectedRoles = @("roles/datastore.user", $FcmCustomRole)

    if ($actualRoles -cnotcontains "roles/datastore.user") {
        & $addFinding "datastore_binding_missing" (
            "Manca il ruolo Firestore runtime minimo."
        )
    }
    if ($actualRoles -cnotcontains $FcmCustomRole) {
        & $addFinding "fcm_binding_missing" (
            "Manca il ruolo FCM runtime minimo."
        )
    }
    $unexpectedRoles = @($actualRoles | Where-Object {
        $expectedRoles -cnotcontains $_
    })
    if ($unexpectedRoles.Count -gt 0) {
        & $addFinding "unexpected_target_binding" (
            "Il runtime notifiche possiede ruoli di progetto inattesi."
        )
    }

    return [PSCustomObject]@{
        schemaVersion = "notification-runtime-iam-audit-v1"
        ready = ($findings.Count -eq 0)
        blockingCount = $findings.Count
        findings = $findings.ToArray()
        targetServiceAccount = $TargetServiceAccount
        fcmCustomRole = $FcmCustomRole
    }
}

Export-ModuleMember -Function Test-NotificationRuntimeIamState
