$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$fixturePath = Join-Path $scriptRoot "fixtures\play-notification-cutover\staged-pass.json"
$auditScript = Join-Path $scriptRoot "audit-play-notification-cutover.ps1"
Import-Module (Join-Path $scriptRoot "play-notification-cutover-audit.psm1") -Force

$expectedSha = "A" * 64
$common = @{
    ExpectedAccount = "meteofriul@gmail.com"
    ExpectedAndroidPackage = "com.meteofriul.app"
    ExpectedAllowedAppVersions = @(
        "1.0.0+300011",
        "1.0.1+300012"
    )
    ExpectedEnrollmentGeneration = "play-beta-v1"
    ExpectedFirebaseAppId = "1:49007668366:android:725bf6f8b339177a852ddf"
    ExpectedMaxDevices = 1
    ExpectedPlaySigningSha256 = $expectedSha
    ExpectedProjectId = "meteo-friul"
    ExpectedProjectNumber = "49007668366"
    ExpectedVersionCode = 300011
    ExpectedVersionName = "1.0.0"
    NowUtc = [datetimeoffset]"2026-08-23T10:00:00Z"
    Phase = "staged"
}

function Get-TestSnapshot {
    return Get-Content -LiteralPath $fixturePath -Raw | ConvertFrom-Json
}

function Assert-Test {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw "contract_assertion_failed: $Message"
    }
}

function Assert-ThrowsLike {
    param([scriptblock]$Action, [string]$Pattern, [string]$Message)
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -like "*$Pattern*") {
            return
        }
        throw "contract_wrong_failure: $Message expected=$Pattern actual=$($_.Exception.Message)"
    }
    throw "contract_missing_failure: $Message expected=$Pattern"
}

$auditScriptSource = Get-Content -LiteralPath $auditScript -Raw
Assert-Test ($auditScriptSource -match '"x-goog-user-project"\s*=\s*\$QuotaProject') `
    "le richieste Firebase live devono attribuire la quota al progetto verificato"
Assert-Test ($auditScriptSource -match 'Generic\.List\[string\[\]\]\]') `
    "i percorsi Cloud Run devono restare liste di segmenti senza appiattimento PowerShell"
Assert-Test ($auditScriptSource -match '\[string\[\]\]\$RuntimeRevisionEvidencePaths') `
    "l'audit live deve accettare una catena ordinata di evidenze runtime"
Assert-Test ($auditScriptSource -match '\[string\[\]\]\$ExpectedAllowedAppVersions') `
    "l'audit live deve accettare una allowlist ordinata di versioni in coesistenza"
Assert-Test ($auditScriptSource -match '"revisions", "describe", \$trafficRevision') `
    "lo snapshot live deve descrivere la revisione realmente servita dal tag"

$pass = Assert-PlayNotificationCutoverSnapshot -Snapshot (Get-TestSnapshot) @common
Assert-Test ($pass.Status -ceq "PASS") "la fixture staged valida deve passare"
Assert-Test ($pass.DebugTokenCount -eq 0) "la fixture valida deve attestare zero token Debug"
Assert-Test ($pass.Digest -match '@sha256:a{64}$') "il digest deve essere risolto e immutabile"
Assert-Test ($pass.AabRevision -ceq "meteofriul-api-play-beta-abcdef0") `
    "l'audit deve preservare la revisione immutabile registrata nel manifesto AAB"
Assert-Test ($pass.Revision -ceq "meteofriul-api-play-beta-runtime-1234567") `
    "l'audit deve risolvere la revisione runtime realmente servita dal tag"
Assert-Test ($pass.ApiTagRetarget -ceq "VERIFIED") `
    "un retarget post-AAB deve essere coperto da evidenza append-only"
Assert-Test ($pass.RuntimeRevisionEvidenceCount -eq 1 -and
    $pass.RuntimeRevisionLineage.Count -eq 2) `
    "l'output deve esporre la catena AAB -> runtime"
Assert-Test (($pass.AllowedAppVersions -join ",") -ceq
    "1.0.0+300011,1.0.1+300012") `
    "l'output deve esporre l'allowlist completa e normalizzata"

$reverseVersionOrder = Get-TestSnapshot
$reverseVersionOrder.cloudRun.service.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.1+300012, 1.0.0+300011"
$reverseVersionOrder.cloudRun.officialAlertsJob.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.1+300012, 1.0.0+300011"
$reverseVersionOrder.cloudRun.localNoticesJob.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.1+300012, 1.0.0+300011"
$reverseVersionPass = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $reverseVersionOrder @common
Assert-Test (($reverseVersionPass.AllowedAppVersions -join ",") -ceq
    "1.0.0+300011,1.0.1+300012") `
    "l'ordine e gli spazi della variabile Cloud Run non devono cambiare il set autorizzato"

$singleVersion = Get-TestSnapshot
$singleVersion.cloudRun.service.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.0+300011"
$singleVersion.cloudRun.officialAlertsJob.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.0+300011"
$singleVersion.cloudRun.localNoticesJob.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = `
    "1.0.0+300011"
$singleVersionArgs = $common.Clone()
$singleVersionArgs.Remove("ExpectedAllowedAppVersions") | Out-Null
$singleVersionPass = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $singleVersion @singleVersionArgs
Assert-Test (($singleVersionPass.AllowedAppVersions -join ",") -ceq
    "1.0.0+300011") `
    "senza parametro esplicito l'audit deve restare compatibile con il solo candidato corrente"

$directAabRevision = Get-TestSnapshot
$directAabRevision.runtimeRevisionEvidence = @()
$directAabRevision.cloudRun.service.revision = "meteofriul-api-play-beta-abcdef0"
$directAabRevision.cloudRun.service.trafficRevision = "meteofriul-api-play-beta-abcdef0"
$directPass = Assert-PlayNotificationCutoverSnapshot -Snapshot $directAabRevision @common
Assert-Test ($directPass.ApiTagRetarget -ceq "NOT_REQUIRED" -and
    $directPass.RuntimeRevisionEvidenceCount -eq 0 -and
    $directPass.RuntimeRevisionLineage.Count -eq 1) `
    "nessuna evidenza deve essere richiesta quando il tag serve ancora la revisione AAB"

$twoHop = Get-TestSnapshot
$secondHop = $twoHop.runtimeRevisionEvidence[0] | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$secondHop.path = "release-history/play-notification-cutover/evidence/20260823T095500Z-runtime-revision-retarget-verified.json"
$secondHop.addCommitTimeUtc = "2026-08-23T09:56:00Z"
$secondHop.record.recordedAtUtc = "2026-08-23T09:55:00Z"
$secondHop.record.retargetedAtUtc = "2026-08-23T09:50:00Z"
$secondHop.record.previousEvidencePath = $twoHop.runtimeRevisionEvidence[0].path
$secondHop.record.fromRevision = "meteofriul-api-play-beta-runtime-1234567"
$secondHop.record.toRevision = "meteofriul-api-play-beta-runtime-2345678"
$twoHop.runtimeRevisionEvidence = @($twoHop.runtimeRevisionEvidence[0], $secondHop)
$twoHop.cloudRun.service.revision = "meteofriul-api-play-beta-runtime-2345678"
$twoHop.cloudRun.service.trafficRevision = "meteofriul-api-play-beta-runtime-2345678"
$twoHopPass = Assert-PlayNotificationCutoverSnapshot -Snapshot $twoHop @common
Assert-Test ($twoHopPass.RuntimeRevisionEvidenceCount -eq 2 -and
    $twoHopPass.RuntimeRevisionLineage.Count -eq 3 -and
    $twoHopPass.Revision -ceq "meteofriul-api-play-beta-runtime-2345678") `
    "la catena deve supportare piu retarget ordinati senza cambiare immagine"

$nullRuntimeEvidence = $directAabRevision | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$nullRuntimeEvidence.runtimeRevisionEvidence = $null
$nullRuntimePass = Assert-PlayNotificationCutoverSnapshot -Snapshot $nullRuntimeEvidence @common
Assert-Test ($nullRuntimePass.RuntimeRevisionEvidenceCount -eq 0) `
    "runtimeRevisionEvidence nullo deve essere normalizzato a lista vuota"

$absentRuntimeEvidence = $directAabRevision | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$absentRuntimeEvidence.PSObject.Properties.Remove("runtimeRevisionEvidence")
$absentRuntimePass = Assert-PlayNotificationCutoverSnapshot -Snapshot $absentRuntimeEvidence @common
Assert-Test ($absentRuntimePass.RuntimeRevisionEvidenceCount -eq 0) `
    "runtimeRevisionEvidence assente deve essere normalizzato a lista vuota"

$wrapperOutput = & $auditScript `
    -SnapshotPath $fixturePath `
    -FixtureMode `
    -Phase staged `
    -ExpectedPlaySigningSha256 $expectedSha `
    -ExpectedEnrollmentGeneration "play-beta-v1" `
    -ExpectedVersionName "1.0.0" `
    -ExpectedVersionCode 300011 `
    -ExpectedAllowedAppVersions @("1.0.0+300011", "1.0.1+300012") `
    -ExpectedMaxDevices 1 `
    -NowUtc ([datetimeoffset]"2026-08-23T10:00:00Z")
$wrapperResult = ($wrapperOutput -join "`n") | ConvertFrom-Json
Assert-Test ($wrapperResult.Status -ceq "PASS") "lo script pubblico deve usare davvero il validatore"
Assert-Test ($wrapperResult.SnapshotSource -ceq "fixture-test-only") "la fixture non deve sembrare un audit live"

Assert-ThrowsLike {
    & $auditScript `
        -SnapshotPath $fixturePath `
        -Phase staged `
        -ExpectedPlaySigningSha256 $expectedSha `
        -ExpectedEnrollmentGeneration "play-beta-v1" `
        -ExpectedVersionName "1.0.0" `
        -ExpectedVersionCode 300011 `
        -ExpectedAllowedAppVersions @("1.0.0+300011", "1.0.1+300012") `
        -ExpectedMaxDevices 1 `
        -NowUtc ([datetimeoffset]"2026-08-23T10:00:00Z")
} "cutover_fixture_mode_requires_snapshot_and_explicit_switch" "fixture usata senza marcatore test-only"

$active = Get-TestSnapshot
$activeHop = $active.runtimeRevisionEvidence[0] | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeHop.path = "release-history/play-notification-cutover/evidence/20260823T095500Z-runtime-revision-retarget-verified.json"
$activeHop.addCommitTimeUtc = "2026-08-23T09:56:00Z"
$activeHop.record.recordedAtUtc = "2026-08-23T09:55:00Z"
$activeHop.record.retargetedAtUtc = "2026-08-23T09:50:00Z"
$activeHop.record.previousEvidencePath = $active.runtimeRevisionEvidence[0].path
$activeHop.record.fromRevision = "meteofriul-api-play-beta-runtime-1234567"
$activeHop.record.toRevision = "meteofriul-api-play-beta-active-2345678"
$activeHop.record.configurationPurpose = "play-notification-cutover-active"
$active.runtimeRevisionEvidence = @($active.runtimeRevisionEvidence[0], $activeHop)
$active.cloudRun.service.revision = "meteofriul-api-play-beta-active-2345678"
$active.cloudRun.service.trafficRevision = "meteofriul-api-play-beta-active-2345678"
$active.cloudRun.service.env.PUSH_OFFICIAL_ALERTS_MODE = "send"
$active.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_MODE = "send"
$active.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_REQUIRED = "true"
$active.cloudRun.localNoticesJob.env.LOCAL_NOTICE_DELIVERY_MODE = "send"
$active.cloudRun.service.env.PUSH_PILOT_MAX_DEVICES = "200"
$active.cloudRun.officialAlertsJob.env.PUSH_PILOT_MAX_DEVICES = "200"
$active.cloudRun.localNoticesJob.env.PUSH_PILOT_MAX_DEVICES = "200"
$activeArgs = $common.Clone()
$activeArgs.Phase = "active"
$activeArgs.ExpectedMaxDevices = 200
$activePass = Assert-PlayNotificationCutoverSnapshot -Snapshot $active @activeArgs
Assert-Test ($activePass.Phase -ceq "active") "la fase active deve accettare solo send coerente"
Assert-Test ($activePass.LegacyPushCleanup -ceq "VERIFIED") `
    "la fase active deve attestare la bonifica dei record legacy"
Assert-Test ($activePass.RuntimeRevisionEvidenceCount -eq 2 -and
    $activePass.RuntimeRevisionLineage[-1].configurationPurpose -ceq
        "play-notification-cutover-active") `
    "la fase active deve terminare con un secondo retarget active"

$upgrade = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$upgrade.aabReleaseManifestEvidence.path = `
    "release-history/android-play/meteofriul-300012-1.0.1.release.json"
$upgrade.aabReleaseManifestEvidence.record.VersionName = "1.0.1"
$upgrade.aabReleaseManifestEvidence.record.VersionCode = 300012
foreach ($runtimeEvidence in @($upgrade.runtimeRevisionEvidence)) {
    $runtimeEvidence.record.versionName = "1.0.1"
    $runtimeEvidence.record.versionCode = 300012
    $runtimeEvidence.record.aabReleaseManifestPath = `
        "release-history/android-play/meteofriul-300012-1.0.1.release.json"
}
$upgradeArgs = $activeArgs.Clone()
$upgradeArgs.ExpectedVersionName = "1.0.1"
$upgradeArgs.ExpectedVersionCode = 300012
$upgradePass = Assert-PlayNotificationCutoverSnapshot -Snapshot $upgrade @upgradeArgs
Assert-Test ($upgradePass.Status -ceq "PASS" -and
    $upgradePass.AppVersion -ceq "1.0.1+300012" -and
    $upgradePass.LegacyPushCleanup -ceq "VERIFIED") `
    "la 300012 deve poter riusare l'evidenza di bonifica della 300011 nella stessa generazione"

$stagedWithoutCleanup = Get-TestSnapshot
$stagedWithoutCleanup.legacyPushCleanupEvidence = $null
$stagedWithoutCleanupPass = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $stagedWithoutCleanup @common
Assert-Test ($stagedWithoutCleanupPass.LegacyPushCleanup -ceq "NOT_YET_REQUIRED") `
    "la bonifica richiede prima la registrazione Play e non deve bloccare staged"

$activeWithoutCleanup = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithoutCleanup.cloudRun.service.env.PUSH_OFFICIAL_ALERTS_MODE = "send"
$activeWithoutCleanup.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_MODE = "send"
$activeWithoutCleanup.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_REQUIRED = "true"
$activeWithoutCleanup.cloudRun.localNoticesJob.env.LOCAL_NOTICE_DELIVERY_MODE = "send"
$activeWithoutCleanup.cloudRun.service.env.PUSH_PILOT_MAX_DEVICES = "200"
$activeWithoutCleanup.cloudRun.officialAlertsJob.env.PUSH_PILOT_MAX_DEVICES = "200"
$activeWithoutCleanup.cloudRun.localNoticesJob.env.PUSH_PILOT_MAX_DEVICES = "200"
$activeWithoutCleanup.legacyPushCleanupEvidence = $null
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithoutCleanup @activeArgs
} "cutover_legacy_push_cleanup_evidence_not_tracked" `
    "fase active senza prova della bonifica legacy"

$activeWithLegacyResidue = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithLegacyResidue.legacyPushCleanupEvidence.record.legacyPushDeviceCountAfterReadBack = 1
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithLegacyResidue @activeArgs
} "cutover_legacy_push_cleanup_residue_present" `
    "device legacy ancora presente dopo il read-back"

$activeWithMissingCleanupCount = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithMissingCleanupCount.legacyPushCleanupEvidence.record.PSObject.Properties.Remove(
    "legacyPushDeviceCountAfterReadBack"
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithMissingCleanupCount @activeArgs
} "cutover_legacy_push_cleanup_count_invalid" `
    "conteggio legacy assente non deve equivalere implicitamente a zero"

$activeWithPlayRecordDeleted = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithPlayRecordDeleted.legacyPushCleanupEvidence.record.currentPlayRecordPreserved = $false
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithPlayRecordDeleted @activeArgs
} "cutover_current_play_registration_not_preserved" `
    "bonifica che ha eliminato la registrazione Play corrente"

$activeWithWrongCleanupGeneration = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithWrongCleanupGeneration.legacyPushCleanupEvidence.record.currentEnrollmentGeneration = "play-beta-v0"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithWrongCleanupGeneration @activeArgs
} "cutover_legacy_push_cleanup_evidence_identity_mismatch" `
    "bonifica riferita a una generazione diversa"

$accountMismatch = Get-TestSnapshot
$accountMismatch.identity.activeAccount = "other@example.com"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $accountMismatch @common
} "cutover_active_account_mismatch" "account Google sbagliato"

$shaMissing = Get-TestSnapshot
$shaMissing.firebase.androidApp.shaCertificates = @()
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $shaMissing @common
} "cutover_play_signing_sha256_not_registered_in_firebase" "firma Play non registrata"

$unrecognizedAllowed = Get-TestSnapshot
$unrecognizedAllowed.firebase.appCheck.playIntegrityConfig.appIntegrity.allowUnrecognizedVersion = $true
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $unrecognizedAllowed @common
} "cutover_play_integrity_unrecognized_version_allowed" "versioni Play non riconosciute ammesse"

$unrecognizedDefaultFalse = Get-TestSnapshot
$unrecognizedDefaultFalse.firebase.appCheck.playIntegrityConfig.appIntegrity.PSObject.Properties.Remove(
    "allowUnrecognizedVersion"
)
$unrecognizedDefaultPass = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $unrecognizedDefaultFalse @common
Assert-Test ($unrecognizedDefaultPass.Status -ceq "PASS") `
    "Firebase omette il booleano false predefinito nella risposta protobuf JSON"

$licenseOptional = Get-TestSnapshot
$licenseOptional.firebase.appCheck.playIntegrityConfig.accountDetails.requireLicensed = $false
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $licenseOptional @common
} "cutover_play_integrity_license_not_required" "verdict LICENSED non obbligatorio"

$weakDevice = Get-TestSnapshot
$weakDevice.firebase.appCheck.playIntegrityConfig.deviceIntegrity.minDeviceRecognitionLevel = "NO_INTEGRITY"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $weakDevice @common
} "cutover_play_integrity_device_level_invalid" "device integrity debole"

$debugTokenOnSecondPage = Get-TestSnapshot
$debugTokenOnSecondPage.firebase.appCheck.debugTokenPages[1].debugTokens = @(
    [PSCustomObject]@{ name = "projects/49007668366/apps/app/debugTokens/token-id" }
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $debugTokenOnSecondPage @common
} "cutover_debug_tokens_present" "token Debug nascosto in una pagina successiva"

$emptyFirebaseDebugResponse = Get-TestSnapshot
foreach ($page in $emptyFirebaseDebugResponse.firebase.appCheck.debugTokenPages) {
    $page.PSObject.Properties.Remove("debugTokens")
}
$emptyFirebaseDebugPass = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $emptyFirebaseDebugResponse @common
Assert-Test ($emptyFirebaseDebugPass.DebugTokenCount -eq 0) `
    "una risposta Firebase senza debugTokens deve significare zero, non un token nullo"

$paginationTruncated = Get-TestSnapshot
$paginationTruncated.firebase.appCheck.debugTokenPages = @($paginationTruncated.firebase.appCheck.debugTokenPages[0])
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $paginationTruncated @common
} "cutover_debug_token_pagination_incomplete" "paginazione Debug interrotta"

$ttlNotElapsed = $common.Clone()
$ttlNotElapsed.NowUtc = [datetimeoffset]"2026-08-20T18:30:00Z"
$ttlSnapshot = Get-TestSnapshot
$ttlSnapshot.capturedAtUtc = "2026-08-20T18:30:00Z"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $ttlSnapshot @ttlNotElapsed
} "cutover_debug_token_ttl_not_elapsed" "TTL dei token Debug non trascorsa"

$dirtyEvidence = Get-TestSnapshot
$dirtyEvidence.debugTokenRevocationEvidence.clean = $false
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $dirtyEvidence @common
} "cutover_debug_revocation_evidence_dirty" "evidenza non committata o alterata"

$mutatedEvidence = Get-TestSnapshot
$mutatedEvidence.debugTokenRevocationEvidence.mutationCommitCount = 1
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $mutatedEvidence @common
} "cutover_debug_revocation_evidence_was_modified" "evidenza append-only riscritta"

$jobDigestMismatch = Get-TestSnapshot
$jobDigestMismatch.cloudRun.localNoticesJob.imageDigest = (
    "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/" +
    "meteofriul-api@sha256:" + ("b" * 64)
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $jobDigestMismatch @common
} "cutover_cloud_image_digest_mismatch" "job locale su immagine diversa"

$tagPointsElsewhere = Get-TestSnapshot
$tagPointsElsewhere.cloudRun.service.revision = "meteofriul-api-newer-1234567"
$tagPointsElsewhere.cloudRun.service.trafficRevision = "meteofriul-api-newer-1234567"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $tagPointsElsewhere @common
} "cutover_runtime_revision_lineage_incomplete" `
    "tag spostato su una revisione non coperta dalla catena append-only"

$runtimeDigestChanged = Get-TestSnapshot
$runtimeDigestChanged.runtimeRevisionEvidence[0].record.toImageDigest = (
    "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/" +
    "meteofriul-api@sha256:" + ("b" * 64)
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeDigestChanged @common
} "cutover_runtime_revision_evidence_digest_mismatch" `
    "retarget che cambia l'immagine backend registrata nell'AAB"

$runtimeChainGap = Get-TestSnapshot
$runtimeChainGap.runtimeRevisionEvidence[0].record.fromRevision = "meteofriul-api-unrelated-1234567"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeChainGap @common
} "cutover_runtime_revision_evidence_chain_gap" `
    "evidenza che non parte dall'ultimo anello della catena"

$runtimeWrongHost = Get-TestSnapshot
$runtimeWrongHost.runtimeRevisionEvidence[0].record.toTagUrl = "https://other-tag---meteofriul-api-example.a.run.app"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongHost @common
} "cutover_runtime_revision_evidence_tag_url_mismatch" `
    "retarget che cambia l'host incorporato nell'AAB"

$runtimeWrongTag = Get-TestSnapshot
$runtimeWrongTag.runtimeRevisionEvidence[0].record.toTag = "other-tag"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongTag @common
} "cutover_runtime_revision_evidence_tag_mismatch" `
    "retarget che cambia il tag incorporato nell'AAB"

$runtimeWrongAab = Get-TestSnapshot
$runtimeWrongAab.runtimeRevisionEvidence[0].record.aabSha256 = "C" * 64
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongAab @common
} "cutover_runtime_revision_evidence_aab_sha256_mismatch" `
    "evidenza riferita a un AAB diverso"

$runtimeWrongManifestPath = Get-TestSnapshot
$runtimeWrongManifestPath.runtimeRevisionEvidence[0].record.aabReleaseManifestPath = (
    "release-history/android-play/other.release.json"
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongManifestPath @common
} "cutover_runtime_revision_evidence_manifest_binding_mismatch" `
    "evidenza non legata al percorso esatto del manifesto AAB"

$runtimeWrongManifestHash = Get-TestSnapshot
$runtimeWrongManifestHash.runtimeRevisionEvidence[0].record.aabReleaseManifestSha256 = "E" * 64
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongManifestHash @common
} "cutover_runtime_revision_evidence_manifest_binding_mismatch" `
    "evidenza non legata ai byte esatti del manifesto AAB"

$runtimeWrongPreviousPath = Get-TestSnapshot
$runtimeWrongPreviousPath.runtimeRevisionEvidence[0].record.previousEvidencePath = (
    "release-history/play-notification-cutover/evidence/unrelated.json"
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeWrongPreviousPath @common
} "cutover_runtime_revision_evidence_previous_path_mismatch" `
    "primo anello che dichiara un predecessore inesistente"

$activePurposeInStaged = Get-TestSnapshot
$activePurposeInStaged.runtimeRevisionEvidence[0].record.configurationPurpose = (
    "play-notification-cutover-active"
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activePurposeInStaged @common
} "cutover_runtime_revision_evidence_purpose_invalid" `
    "retarget active non deve essere accettato da un audit staged"

$activeAuditWithoutActiveRetarget = Get-TestSnapshot
$activePurposeArgs = $common.Clone()
$activePurposeArgs.Phase = "active"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeAuditWithoutActiveRetarget @activePurposeArgs
} "cutover_runtime_revision_evidence_purpose_invalid" `
    "una catena active deve terminare con un retarget active"

$stagedAfterActive = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$lateStagedHop = $stagedAfterActive.runtimeRevisionEvidence[1] |
    ConvertTo-Json -Depth 20 | ConvertFrom-Json
$lateStagedHop.path = "release-history/play-notification-cutover/evidence/20260823T095800Z-runtime-revision-retarget-verified.json"
$lateStagedHop.addCommitTimeUtc = "2026-08-23T09:59:00Z"
$lateStagedHop.record.recordedAtUtc = "2026-08-23T09:58:00Z"
$lateStagedHop.record.retargetedAtUtc = "2026-08-23T09:57:00Z"
$lateStagedHop.record.previousEvidencePath = $stagedAfterActive.runtimeRevisionEvidence[1].path
$lateStagedHop.record.fromRevision = "meteofriul-api-play-beta-active-2345678"
$lateStagedHop.record.toRevision = "meteofriul-api-play-beta-staged-3456789"
$lateStagedHop.record.configurationPurpose = "play-notification-cutover-staged"
$stagedAfterActive.runtimeRevisionEvidence = @(
    $stagedAfterActive.runtimeRevisionEvidence[0],
    $stagedAfterActive.runtimeRevisionEvidence[1],
    $lateStagedHop
)
$stagedAfterActive.cloudRun.service.revision = "meteofriul-api-play-beta-staged-3456789"
$stagedAfterActive.cloudRun.service.trafficRevision = "meteofriul-api-play-beta-staged-3456789"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $stagedAfterActive @activeArgs
} "cutover_runtime_revision_evidence_purpose_invalid" `
    "la catena non deve tornare a staged dopo un retarget active"

$runtimeEvidenceMutated = Get-TestSnapshot
$runtimeEvidenceMutated.runtimeRevisionEvidence[0].mutationCommitCount = 1
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $runtimeEvidenceMutated @common
} "cutover_runtime_revision_evidence_was_modified" `
    "anello della catena riscritto dopo il primo commit"

$tamperedAabManifest = Get-TestSnapshot
$tamperedAabManifest.aabReleaseManifestEvidence.mutationCommitCount = 1
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $tamperedAabManifest @common
} "cutover_aab_release_manifest_not_append_only" `
    "manifesto AAB modificato dopo il primo commit"

$oldVersion = Get-TestSnapshot
$oldVersion.cloudRun.localNoticesJob.env.PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS = "1.0.0+300010"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $oldVersion @common
} "cutover_cloud_env_mismatch" "vecchia build Play con lo stesso App ID"

$missingCurrentVersion = $common.Clone()
$missingCurrentVersion.ExpectedAllowedAppVersions = @("1.0.1+300012")
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot (Get-TestSnapshot) `
        @missingCurrentVersion
} "cutover_expected_current_app_version_missing" `
    "allowlist deliberata senza il candidato corrente"

$duplicateVersion = $common.Clone()
$duplicateVersion.ExpectedAllowedAppVersions = @(
    "1.0.0+300011",
    "1.0.0+300011"
)
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot (Get-TestSnapshot) `
        @duplicateVersion
} "cutover_expected_app_versions_invalid" `
    "allowlist deliberata con identita duplicate"

$wrongGeneration = Get-TestSnapshot
$wrongGeneration.cloudRun.officialAlertsJob.env.PUSH_ENROLLMENT_GENERATION = "play-beta-v0"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $wrongGeneration @common
} "cutover_cloud_env_mismatch" "generazione diversa nel job ufficiale"

$ownerAllowlist = Get-TestSnapshot
$ownerAllowlist.cloudRun.service.env.PUSH_PILOT_ALLOWED_INSTALLATION_HASHES = "ABCDEF"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $ownerAllowlist @common
} "cutover_cloud_legacy_allowlist_not_empty" "allowlist owner residua"

$activeWithDryRun = $active | ConvertTo-Json -Depth 20 | ConvertFrom-Json
$activeWithDryRun.cloudRun.service.env.PUSH_OFFICIAL_ALERTS_MODE = "dry_run"
$activeWithDryRun.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_MODE = "dry_run"
$activeWithDryRun.cloudRun.officialAlertsJob.env.PUSH_OFFICIAL_ALERTS_REQUIRED = "false"
$activeWithDryRun.cloudRun.localNoticesJob.env.LOCAL_NOTICE_DELIVERY_MODE = "dry_run"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $activeWithDryRun @activeArgs
} "cutover_cloud_env_mismatch" "fase active con delivery dry_run"

$stagedCap = $common.Clone()
$stagedCap.ExpectedMaxDevices = 2
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot (Get-TestSnapshot) @stagedCap
} "cutover_staged_cap_must_be_one" "fase staged con cap maggiore di uno"

$staleSnapshot = Get-TestSnapshot
$staleSnapshot.capturedAtUtc = "2026-08-23T09:00:00Z"
Assert-ThrowsLike {
    Assert-PlayNotificationCutoverSnapshot -Snapshot $staleSnapshot @common
} "cutover_snapshot_not_fresh" "snapshot vecchio riutilizzato come audit corrente"

[PSCustomObject]@{
    ActivePhase = "PASS"
    AabManifestAndTaggedRevision = "PASS"
    AppCheckPolicy = "PASS"
    CloudDigestAndEnvironment = "PASS"
    DebugTokenPaginationAndTtl = "PASS"
    FirebasePlaySigningSha = "PASS"
    Identity = "PASS"
    LegacyPushCleanup = "PASS"
    RuntimeRevisionLineage = "PASS"
    StagedPhase = "PASS"
    Wrapper = "PASS"
} | ConvertTo-Json -Compress
