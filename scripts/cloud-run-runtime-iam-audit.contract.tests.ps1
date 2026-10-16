$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Import-Module (Join-Path $PSScriptRoot "cloud-run-runtime-iam-audit.psm1") -Force

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Contract test fallito: $Message" }
}

function Read-Fixture {
    param([string]$Name)
    $path = Join-Path $PSScriptRoot "fixtures\$Name"
    return (Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
}

function Copy-Snapshot {
    param([object]$Snapshot)
    return ($Snapshot | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function Has-Finding {
    param([object]$Result, [string]$Code)
    return @($Result.findings | Where-Object { [string]$_.code -ceq $Code }).Count -gt 0
}

$baseline = Read-Fixture "cloud-run-runtime-iam-baseline.json"
$baselineResult = Test-CloudRunRuntimeIamState -Snapshot $baseline -Stage Baseline
Assert-Contract $baselineResult.ready "la fixture baseline verificata deve passare il gate inventario"
Assert-Contract (Has-Finding $baselineResult "default_editor_legacy") "la baseline deve evidenziare Editor come debito non bloccante"
Assert-Contract (Has-Finding $baselineResult "image_not_digest_pinned") "la baseline deve evidenziare il job ancora configurato con tag immagine"
Assert-Contract ($baselineResult.observed.service.traffic.Count -eq 1) "la baseline deve esporre l'allocazione di traffico osservata"
Assert-Contract ($baselineResult.observed.service.revisions.Count -eq 1) "la baseline deve esporre la revisione risolta"

$final = Read-Fixture "cloud-run-runtime-iam-final.json"
$finalResult = Test-CloudRunRuntimeIamState -Snapshot $final -Stage Final
Assert-Contract $finalResult.ready "la fixture least-privilege finale deve passare"
Assert-Contract ($finalResult.blockingCount -eq 0) "la fixture finale non deve avere blocker"
Assert-Contract ($final.jobs.Count -eq 4) "la fixture finale deve contenere esattamente i quattro job operativi"
Assert-Contract (-not (@($final.jobs.name) -ccontains "meteofriul-community-moderation-digest")) "il job Moderazione non appartiene all'inventario runtime attivo"

$targetReady = Copy-Snapshot $baseline
$targetReady.iamBindings = Copy-Snapshot $final.iamBindings
$targetReady.rolePermissions = Copy-Snapshot $final.rolePermissions
$targetReady.jobs[0].image = $final.jobs[0].image
$targetReadyResult = Test-CloudRunRuntimeIamState -Snapshot $targetReady -Stage TargetReady
Assert-Contract $targetReadyResult.ready "TargetReady deve passare con IAM pronto, identita' legacy e immagini fissate"

$cutover = Copy-Snapshot $final
$cutover.iamBindings += [PSCustomObject]@{
    role = "roles/editor"
    members = @("serviceAccount:49007668366-compute@developer.gserviceaccount.com")
}
$cutoverResult = Test-CloudRunRuntimeIamState -Snapshot $cutover -Stage Cutover
Assert-Contract $cutoverResult.ready "Cutover deve conservare temporaneamente Editor per rollback"
Assert-Contract (Has-Finding $cutoverResult "default_editor_legacy") "Cutover deve rendere visibile il privilegio temporaneo"
$prematureFinal = Test-CloudRunRuntimeIamState -Snapshot $cutover -Stage Final
Assert-Contract (-not $prematureFinal.ready) "Final non deve passare finche' Editor resta sul default SA"
Assert-Contract (Has-Finding $prematureFinal "default_editor_still_present") "manca il blocker Editor finale"

$ownerStillPresent = Copy-Snapshot $final
$ownerStillPresent.iamBindings += [PSCustomObject]@{
    role = "roles/owner"
    members = @("serviceAccount:49007668366-compute@developer.gserviceaccount.com")
}
$ownerStillPresentResult = Test-CloudRunRuntimeIamState -Snapshot $ownerStillPresent -Stage Final
Assert-Contract (-not $ownerStillPresentResult.ready) "Final non deve passare con Owner sul Compute default"
Assert-Contract (Has-Finding $ownerStillPresentResult "default_owner_still_present") "manca il blocker Owner finale"

$buildStillDefault = Copy-Snapshot $final
$buildStillDefault.cloudBuild.defaultServiceAccount = "49007668366-compute@developer.gserviceaccount.com"
$buildStillDefaultResult = Test-CloudRunRuntimeIamState -Snapshot $buildStillDefault -Stage Final
Assert-Contract (-not $buildStillDefaultResult.ready) "Final non deve passare se Cloud Build usa ancora il Compute default"
Assert-Contract (Has-Finding $buildStillDefaultResult "cloud_build_uses_default_compute") "manca il blocker Cloud Build"

$buildUsesRuntime = Copy-Snapshot $final
$buildUsesRuntime.cloudBuild.defaultServiceAccount = "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com"
$buildUsesRuntimeResult = Test-CloudRunRuntimeIamState -Snapshot $buildUsesRuntime -Stage Final
Assert-Contract (-not $buildUsesRuntimeResult.ready) "Final non deve passare se Cloud Build riusa il runtime SA"
Assert-Contract (Has-Finding $buildUsesRuntimeResult "cloud_build_uses_runtime_identity") "manca il blocker Cloud Build/runtime"

$buildUsesEvents = Copy-Snapshot $final
$buildUsesEvents.cloudBuild.defaultServiceAccount = "event-source-monitor@meteo-friul.iam.gserviceaccount.com"
$buildUsesEventsResult = Test-CloudRunRuntimeIamState -Snapshot $buildUsesEvents -Stage Final
Assert-Contract (-not $buildUsesEventsResult.ready) "Final non deve passare se Cloud Build riusa il SA Eventi"
Assert-Contract (Has-Finding $buildUsesEventsResult "cloud_build_uses_event_identity") "manca il blocker Cloud Build/Eventi"

$buildIdentityMissing = Copy-Snapshot $final
$buildIdentityMissing.cloudBuild.defaultServiceAccount = ""
$buildIdentityMissingResult = Test-CloudRunRuntimeIamState -Snapshot $buildIdentityMissing -Stage Final
Assert-Contract (-not $buildIdentityMissingResult.ready) "Final non deve passare senza un SA Cloud Build valido"
Assert-Contract (Has-Finding $buildIdentityMissingResult "cloud_build_identity_invalid") "manca il blocker identita' Cloud Build invalida"

$singleServiceAccount = Test-CloudRunRuntimeIamState -Snapshot $final -Stage Final `
    -TargetServiceAccount "event-source-monitor@meteo-friul.iam.gserviceaccount.com"
Assert-Contract (-not $singleServiceAccount.ready) "la topologia a SA unico non deve essere supportata"
Assert-Contract (Has-Finding $singleServiceAccount "target_service_account_not_dedicated") "manca il blocker SA dedicati"

$legacyTraffic = Read-Fixture "cloud-run-runtime-iam-latest-ready-target-legacy-traffic.json"
$legacyTrafficResult = Test-CloudRunRuntimeIamState -Snapshot $legacyTraffic -Stage Cutover
Assert-Contract (-not $legacyTrafficResult.ready) "latestReady target non deve mascherare traffico 100% sul legacy"
Assert-Contract (Has-Finding $legacyTrafficResult "traffic_revision_identity_mismatch") "manca il blocker identita' della revisione servente"
Assert-Contract (Has-Finding $legacyTrafficResult "rollback_revision_not_zero_traffic") "manca il blocker rollback con traffico"

$unresolvedTraffic = Copy-Snapshot $final
$unresolvedTraffic.services[0].revisions = @($unresolvedTraffic.services[0].revisions | Where-Object { $_.name -ne "meteofriul-api-iam-target" })
$unresolvedTrafficResult = Test-CloudRunRuntimeIamState -Snapshot $unresolvedTraffic -Stage Final
Assert-Contract (-not $unresolvedTrafficResult.ready) "una revisione servente non risolta non deve passare"
Assert-Contract (Has-Finding $unresolvedTrafficResult "traffic_revision_unresolved") "manca il blocker revisione non risolta"

$missingTrafficInventory = Copy-Snapshot $final
$missingTrafficInventory.services[0].PSObject.Properties.Remove("traffic")
$missingTrafficInventoryResult = Test-CloudRunRuntimeIamState -Snapshot $missingTrafficInventory -Stage Final
Assert-Contract (-not $missingTrafficInventoryResult.ready) "Final non deve passare senza status.traffic"
Assert-Contract (Has-Finding $missingTrafficInventoryResult "service_traffic_inventory_missing") "manca il blocker inventario traffico"

$wrongProject = Copy-Snapshot $baseline
$wrongProject.project.projectId = "altro-progetto"
$wrongProjectResult = Test-CloudRunRuntimeIamState -Snapshot $wrongProject -Stage Baseline
Assert-Contract (-not $wrongProjectResult.ready) "un progetto inatteso non deve passare"
Assert-Contract (Has-Finding $wrongProjectResult "project_mismatch") "manca il blocker progetto"

$missingJob = Copy-Snapshot $baseline
$missingJob.jobs = @($missingJob.jobs | Select-Object -Skip 1)
$missingJobResult = Test-CloudRunRuntimeIamState -Snapshot $missingJob -Stage Baseline
Assert-Contract (-not $missingJobResult.ready) "un inventario incompleto non deve passare"
Assert-Contract (Has-Finding $missingJobResult "job_inventory_mismatch") "manca il blocker inventario job"

$changedEntrypoint = Copy-Snapshot $baseline
$changedEntrypoint.jobs[0].args = @("-m", "app.jobs.send_push_pilot_test")
$changedEntrypointResult = Test-CloudRunRuntimeIamState -Snapshot $changedEntrypoint -Stage Baseline
Assert-Contract (-not $changedEntrypointResult.ready) "un entrypoint inatteso non deve passare"
Assert-Contract (Has-Finding $changedEntrypointResult "job_entrypoint_mismatch") "manca il blocker entrypoint"

$explicitCredentials = Copy-Snapshot $final
$explicitCredentials.services[0].envNames += "GOOGLE_APPLICATION_CREDENTIALS"
$explicitCredentialsResult = Test-CloudRunRuntimeIamState -Snapshot $explicitCredentials -Stage Final
Assert-Contract (-not $explicitCredentialsResult.ready) "credenziali esplicite non devono passare"
Assert-Contract (Has-Finding $explicitCredentialsResult "explicit_firebase_credentials_present") "manca il blocker credenziali esplicite"

$missingFcm = Copy-Snapshot $final
$missingFcm.iamBindings = @($missingFcm.iamBindings | Where-Object { $_.role -notlike "*/meteofriulFcmSender" })
$missingFcmResult = Test-CloudRunRuntimeIamState -Snapshot $missingFcm -Stage Final
Assert-Contract (-not $missingFcmResult.ready) "il target senza sender FCM non deve passare"
Assert-Contract (Has-Finding $missingFcmResult "target_fcm_role_missing") "manca il blocker ruolo FCM"

$broadFcm = Copy-Snapshot $final
$broadFcm.rolePermissions[0].permissions += "cloudmessaging.topicSubscriptions.create"
$broadFcmResult = Test-CloudRunRuntimeIamState -Snapshot $broadFcm -Stage Final
Assert-Contract (-not $broadFcmResult.ready) "un ruolo FCM piu' ampio non deve passare"
Assert-Contract (Has-Finding $broadFcmResult "fcm_custom_role_not_minimal") "manca il blocker ruolo FCM ampio"

$eventCanSend = Copy-Snapshot $final
$eventFcmBinding = @($eventCanSend.iamBindings | Where-Object { $_.role -like "*/meteofriulFcmSender" })[0]
$eventFcmBinding.members += "serviceAccount:event-source-monitor@meteo-friul.iam.gserviceaccount.com"
$eventCanSendResult = Test-CloudRunRuntimeIamState -Snapshot $eventCanSend -Stage Final
Assert-Contract (-not $eventCanSendResult.ready) "i job Eventi con FCM non devono passare"
Assert-Contract (Has-Finding $eventCanSendResult "event_fcm_role_present") "manca il blocker separazione Eventi/FCM"

$sourceText = @(
    Get-Content -LiteralPath (Join-Path $PSScriptRoot "audit-cloud-run-runtime-iam.ps1") -Raw
    Get-Content -LiteralPath (Join-Path $PSScriptRoot "cloud-run-runtime-iam-audit.psm1") -Raw
) -join [Environment]::NewLine
foreach ($retiredRuntimeToken in @(
    "meteofriul-community-moderation-digest",
    "community-moderation-digest@meteo-friul.iam.gserviceaccount.com",
    "community-moderation-scheduler@meteo-friul.iam.gserviceaccount.com"
)) {
    Assert-Contract (-not $sourceText.Contains($retiredRuntimeToken)) "l'audit runtime attivo richiede ancora la risorsa non provisionata: $retiredRuntimeToken"
}
$forbiddenMutations = @(
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "set-iam-policy",
    "service-accounts create",
    "run services update",
    "run jobs update",
    "run deploy",
    "run jobs execute"
)
foreach ($token in $forbiddenMutations) {
    Assert-Contract (-not $sourceText.Contains($token)) "lo script audit-only contiene il token mutante: $token"
}

Write-Host "Cloud Run runtime IAM audit contract tests: OK"
