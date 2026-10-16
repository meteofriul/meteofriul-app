$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $scriptRoot "notification-runtime-iam.psm1") -Force
$prepareSource = Get-Content -LiteralPath (
    Join-Path $scriptRoot "prepare-notification-runtime-iam.ps1"
) -Raw

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "contract_failed: $Message" }
}

$target = "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com"
$role = "projects/meteo-friul/roles/meteofriulFcmSender"
$member = "serviceAccount:$target"
$ready = [PSCustomObject]@{
    account = "meteofriul@gmail.com"
    project = [PSCustomObject]@{
        projectId = "meteo-friul"
        projectNumber = "49007668366"
    }
    serviceAccounts = @([PSCustomObject]@{
        email = $target
        disabled = $false
    })
    roles = @([PSCustomObject]@{
        name = $role
        includedPermissions = @("cloudmessaging.messages.create")
    })
    iamBindings = @(
        [PSCustomObject]@{ role = "roles/datastore.user"; members = @($member) },
        [PSCustomObject]@{ role = $role; members = @($member) }
    )
}

$readyResult = Test-NotificationRuntimeIamState -Snapshot $ready
Assert-Contract $readyResult.ready "stato minimo atteso non accettato"

$missing = $ready.PSObject.Copy()
$missing.serviceAccounts = @()
$missing.roles = @()
$missing.iamBindings = @()
$missingResult = Test-NotificationRuntimeIamState -Snapshot $missing
$missingCodes = @($missingResult.findings | ForEach-Object code)
foreach ($code in @(
    "service_account_missing",
    "custom_role_missing",
    "datastore_binding_missing",
    "fcm_binding_missing"
)) {
    Assert-Contract ($missingCodes -ccontains $code) "finding mancante: $code"
}

$overprivileged = $ready.PSObject.Copy()
$overprivileged.roles = @([PSCustomObject]@{
    name = $role
    includedPermissions = @(
        "cloudmessaging.messages.create",
        "firebasenotifications.messages.create"
    )
})
$overprivileged.iamBindings = @($ready.iamBindings) + @(
    [PSCustomObject]@{ role = "roles/editor"; members = @($member) }
)
$overprivilegedResult = Test-NotificationRuntimeIamState -Snapshot $overprivileged
$overprivilegedCodes = @($overprivilegedResult.findings | ForEach-Object code)
Assert-Contract (-not $overprivilegedResult.ready) (
    "runtime sovraprivilegiato accettato"
)
Assert-Contract (
    $overprivilegedCodes -ccontains "custom_role_permissions_mismatch"
) "permission FCM aggiuntiva non rilevata"
Assert-Contract (
    $overprivilegedCodes -ccontains "unexpected_target_binding"
) "ruolo di progetto inatteso non rilevato"

foreach ($required in @(
    '[ValidateSet("Audit", "Apply")]',
    'service-accounts", "create"',
    'roles", "create"',
    'cloudmessaging.messages.create',
    'roles/datastore.user',
    'roles", "describe"',
    'Get-NotificationRuntimeSnapshot'
)) {
    Assert-Contract ($prepareSource.Contains($required)) (
        "prepare IAM privo del contratto richiesto: $required"
    )
}
foreach ($forbidden in @(
    'remove-iam-policy-binding',
    'service-accounts", "delete"',
    'roles", "update"',
    'roles", "delete"',
    'run", "jobs"',
    'scheduler", "jobs"',
    'run", "deploy"',
    'projects", "set-iam-policy"'
)) {
    Assert-Contract (-not $prepareSource.Contains($forbidden)) (
        "prepare IAM contiene mutazione fuori scope: $forbidden"
    )
}

Write-Output "PASS notification runtime IAM contracts"
