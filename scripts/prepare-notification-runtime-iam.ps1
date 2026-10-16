[CmdletBinding()]
param(
    [ValidateSet("Audit", "Apply")]
    [string]$Mode = "Audit",

    [string]$ExpectedAccount = "meteofriul@gmail.com",
    [string]$ProjectId = "meteo-friul",
    [string]$ProjectNumber = "49007668366",
    [string]$TargetServiceAccountId = "meteofriul-runtime",
    [string]$FcmCustomRoleId = "meteofriulFcmSender",
    [string]$GcloudPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "notification-runtime-iam.psm1") -Force

$targetServiceAccount = (
    "$TargetServiceAccountId@$ProjectId.iam.gserviceaccount.com"
)
$fcmCustomRole = "projects/$ProjectId/roles/$FcmCustomRoleId"
$targetMember = "serviceAccount:$targetServiceAccount"

if ($TargetServiceAccountId -cnotmatch '^[a-z][a-z0-9-]{4,28}[a-z0-9]$') {
    throw "notification_runtime_service_account_id_invalid"
}
if ($FcmCustomRoleId -cnotmatch '^[A-Za-z0-9_.]{3,64}$') {
    throw "notification_runtime_role_id_invalid"
}

function Resolve-NotificationRuntimeGcloud {
    if ($GcloudPath) {
        $resolved = [IO.Path]::GetFullPath($GcloudPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "notification_runtime_gcloud_not_found"
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
    throw "notification_runtime_gcloud_not_found"
}

function Invoke-NotificationRuntimeGcloud {
    param(
        [string[]]$Arguments,
        [string]$FailureCode
    )
    $output = & $script:gcloud @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw $FailureCode }
    return [string](($output | Out-String).Trim())
}

function Invoke-NotificationRuntimeGcloudJson {
    param(
        [string[]]$Arguments,
        [string]$FailureCode
    )
    $text = Invoke-NotificationRuntimeGcloud `
        -Arguments $Arguments -FailureCode $FailureCode
    if (-not $text) { return @() }
    return @($text | ConvertFrom-Json)
}

function Get-NotificationRuntimeSnapshot {
    $accounts = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
        "auth", "list", "--filter=status:ACTIVE", "--format=json(account,status)"
    ) -FailureCode "notification_runtime_account_read_failed")
    $activeAccounts = @($accounts | Where-Object {
        [string]$_.status -ceq "ACTIVE"
    })
    if ($activeAccounts.Count -ne 1) {
        throw "notification_runtime_active_account_not_unique"
    }

    $projects = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
        "projects", "describe", $ProjectId,
        "--format=json(projectId,projectNumber)"
    ) -FailureCode "notification_runtime_project_read_failed")
    if ($projects.Count -ne 1) {
        throw "notification_runtime_project_not_unique"
    }

    $serviceAccounts = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
        "iam", "service-accounts", "list", "--project=$ProjectId",
        "--filter=email:$targetServiceAccount", "--format=json(email,disabled)"
    ) -FailureCode "notification_runtime_service_account_read_failed")
    $roleInventory = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
        "iam", "roles", "list", "--project=$ProjectId",
        "--format=json(name)"
    ) -FailureCode "notification_runtime_role_read_failed")
    $roleMatches = @($roleInventory | Where-Object {
        [string]$_.name -ceq $fcmCustomRole
    })
    $roles = @()
    if ($roleMatches.Count -eq 1) {
        $roles = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
            "iam", "roles", "describe", $FcmCustomRoleId,
            "--project=$ProjectId",
            "--format=json(name,includedPermissions,stage)"
        ) -FailureCode "notification_runtime_role_definition_read_failed")
    } elseif ($roleMatches.Count -gt 1) {
        $roles = @($roleMatches)
    }
    $policies = @(Invoke-NotificationRuntimeGcloudJson -Arguments @(
        "projects", "get-iam-policy", $ProjectId,
        "--format=json(bindings)"
    ) -FailureCode "notification_runtime_policy_read_failed")
    if ($policies.Count -ne 1) {
        throw "notification_runtime_policy_not_unique"
    }
    $bindings = if ($policies[0].PSObject.Properties.Name -contains "bindings") {
        @($policies[0].bindings)
    } else {
        @()
    }

    return [PSCustomObject]@{
        account = [string]$activeAccounts[0].account
        project = $projects[0]
        serviceAccounts = @($serviceAccounts)
        roles = @($roles)
        iamBindings = @($bindings)
    }
}

function Test-NotificationRuntimeSnapshot {
    param([object]$Snapshot)
    return Test-NotificationRuntimeIamState -Snapshot $Snapshot `
        -ExpectedAccount $ExpectedAccount -ExpectedProjectId $ProjectId `
        -ExpectedProjectNumber $ProjectNumber `
        -TargetServiceAccount $targetServiceAccount `
        -FcmCustomRole $fcmCustomRole
}

$script:gcloud = Resolve-NotificationRuntimeGcloud
$before = Get-NotificationRuntimeSnapshot
$result = Test-NotificationRuntimeSnapshot -Snapshot $before

if ($Mode -ceq "Audit") {
    $result | ConvertTo-Json -Depth 8
    if (-not $result.ready) { exit 2 }
    exit 0
}

$repairableCodes = @(
    "service_account_missing",
    "custom_role_missing",
    "datastore_binding_missing",
    "fcm_binding_missing"
)
$unsafeFindings = @($result.findings | Where-Object {
    $repairableCodes -cnotcontains [string]$_.code
})
if ($unsafeFindings.Count -gt 0) {
    throw "notification_runtime_apply_blocked_by_unsafe_state"
}

$actions = New-Object System.Collections.Generic.List[string]
$codes = @($result.findings | ForEach-Object { [string]$_.code })
if ($codes -ccontains "service_account_missing") {
    $null = Invoke-NotificationRuntimeGcloud -Arguments @(
        "iam", "service-accounts", "create", $TargetServiceAccountId,
        "--project=$ProjectId",
        "--display-name=Meteo Friul notification runtime",
        "--description=Firestore and FCM runtime for Meteo Friul notifications",
        "--quiet"
    ) -FailureCode "notification_runtime_service_account_create_failed"
    $actions.Add("service_account_created")
}
if ($codes -ccontains "custom_role_missing") {
    $null = Invoke-NotificationRuntimeGcloud -Arguments @(
        "iam", "roles", "create", $FcmCustomRoleId,
        "--project=$ProjectId", "--title=Meteo Friul FCM sender",
        "--description=Send Meteo Friul notifications through FCM",
        "--permissions=cloudmessaging.messages.create", "--stage=GA", "--quiet"
    ) -FailureCode "notification_runtime_role_create_failed"
    $actions.Add("custom_role_created")
}
if ($codes -ccontains "datastore_binding_missing") {
    $null = Invoke-NotificationRuntimeGcloud -Arguments @(
        "projects", "add-iam-policy-binding", $ProjectId,
        "--member=$targetMember", "--role=roles/datastore.user",
        "--condition=None", "--quiet"
    ) -FailureCode "notification_runtime_datastore_binding_failed"
    $actions.Add("datastore_binding_added")
}
if ($codes -ccontains "fcm_binding_missing") {
    $null = Invoke-NotificationRuntimeGcloud -Arguments @(
        "projects", "add-iam-policy-binding", $ProjectId,
        "--member=$targetMember", "--role=$fcmCustomRole",
        "--condition=None", "--quiet"
    ) -FailureCode "notification_runtime_fcm_binding_failed"
    $actions.Add("fcm_binding_added")
}

$after = Get-NotificationRuntimeSnapshot
$verified = Test-NotificationRuntimeSnapshot -Snapshot $after
[PSCustomObject]@{
    schemaVersion = "notification-runtime-iam-apply-v1"
    mode = $Mode
    ready = $verified.ready
    actions = $actions.ToArray()
    audit = $verified
} | ConvertTo-Json -Depth 10
if (-not $verified.ready) { exit 2 }
