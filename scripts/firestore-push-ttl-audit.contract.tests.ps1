$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Import-Module (Join-Path $PSScriptRoot "firestore-push-ttl-audit.psm1") -Force

function Assert-Contract {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Contract test fallito: $Message" }
}

function Read-Fixture {
    param([string]$Name)
    return (Get-Content -LiteralPath (Join-Path $PSScriptRoot "fixtures\$Name") -Raw | ConvertFrom-Json)
}

function Copy-Value {
    param([object]$Value)
    return ($Value | ConvertTo-Json -Depth 20 | ConvertFrom-Json)
}

function Has-Finding {
    param([object]$Result, [string]$Code)
    return @($Result.findings | Where-Object { [string]$_.code -ceq $Code }).Count -gt 0
}

$source = Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) "backend\app\repositories\push.py") -Raw
$active = @(Read-Fixture "firestore-push-ttl-active.json")
$history = Read-Fixture "firestore-push-ttl-history-complete.json"
$readback = Read-Fixture "firestore-push-ttl-readback-clean.json"
$gitStatus = [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 1 }
$runtime = Read-Fixture "firestore-push-ttl-runtime-writers-active.json"
$runtimeContract = Read-Fixture "firestore-push-ttl-runtime-writer-contract.json"
$sourceSha256 = (Get-FileHash -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) "backend\app\repositories\push.py") -Algorithm SHA256).Hash.ToLowerInvariant()
$runtimeContract.pushRepositorySha256 = $sourceSha256
$runtimeGitStatus = [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 1 }
$runtimeBuild = Read-Fixture "firestore-push-ttl-cloud-build-success.json"
$pushRepositoryGitStatus = [PSCustomObject]@{
    tracked = $true
    clean = $true
    sourceCommitExists = $true
    matchesSourceCommit = $true
}
$runtimeGate = @{
    PushRepositorySha256 = $sourceSha256
    RuntimeWriters = $runtime
    RuntimeWriterContract = $runtimeContract
    RuntimeContractGitStatus = $runtimeGitStatus
    RuntimeBuildVerification = $runtimeBuild
    PushRepositoryGitStatus = $pushRepositoryGitStatus
}

$olderRuntimeContract = Copy-Value $runtimeContract
$olderRuntimeContract.expectedImageDigest = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
$contractCandidates = @(
    [PSCustomObject]@{ path = "older.json"; contract = $olderRuntimeContract },
    [PSCustomObject]@{ path = "serving.json"; contract = $runtimeContract }
)
$selectedContract = Resolve-RuntimeWriterContractCandidate -Candidates $contractCandidates `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime
Assert-Contract ([string]$selectedContract.path -ceq "serving.json") "piu' build dello stesso writer devono risolversi sul digest servente al 100%"

$splitSelectionRuntime = Copy-Value $runtime
$splitSelectionRuntime.service.traffic[0].percent = 50
$splitSelectionRuntime.service.traffic += [PSCustomObject]@{
    revisionName = "meteofriul-api-other-abcdef0"
    percent = 50
    tag = ""
}
$splitSelectionBlocked = $false
try {
    $null = Resolve-RuntimeWriterContractCandidate -Candidates $contractCandidates `
        -PushRepositorySha256 $sourceSha256 -RuntimeWriters $splitSelectionRuntime
} catch {
    $splitSelectionBlocked = $_.Exception.Message -ceq "runtime_writer_contract_service_traffic_not_unique"
}
Assert-Contract $splitSelectionBlocked "la selezione del contratto deve fallire con traffico diviso"

$missingServingContract = Copy-Value $runtimeContract
$missingServingContract.expectedImageDigest = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
$missingServingBlocked = $false
try {
    $null = Resolve-RuntimeWriterContractCandidate -Candidates @(
        [PSCustomObject]@{ path = "older.json"; contract = $olderRuntimeContract },
        [PSCustomObject]@{ path = "missing.json"; contract = $missingServingContract }
    ) -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime
} catch {
    $missingServingBlocked = $_.Exception.Message -ceq "runtime_writer_contract_for_serving_digest_missing"
}
Assert-Contract $missingServingBlocked "piu' contratti senza il digest servente devono fallire chiusi"

$duplicateServingBlocked = $false
try {
    $duplicateServingContract = Copy-Value $runtimeContract
    $null = Resolve-RuntimeWriterContractCandidate -Candidates @(
        [PSCustomObject]@{ path = "serving-a.json"; contract = $runtimeContract },
        [PSCustomObject]@{ path = "serving-b.json"; contract = $duplicateServingContract }
    ) -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime
} catch {
    $duplicateServingBlocked = $_.Exception.Message -ceq "runtime_writer_contract_for_serving_digest_ambiguous"
}
Assert-Contract $duplicateServingBlocked "due attestazioni dello stesso digest servente devono restare ambigue"

$missingRevisionRuntime = Copy-Value $runtime
$missingRevisionRuntime.service.revisions = @()
$missingRevisionBlocked = $false
try {
    $null = Resolve-RuntimeWriterContractCandidate -Candidates $contractCandidates `
        -PushRepositorySha256 $sourceSha256 -RuntimeWriters $missingRevisionRuntime
} catch {
    $missingRevisionBlocked = $_.Exception.Message -ceq "runtime_writer_contract_service_revision_unresolved"
}
Assert-Contract $missingRevisionBlocked "la revisione servente deve essere risolta in modo univoco"

$taggedRevisionRuntime = Copy-Value $runtime
$taggedRevisionRuntime.service.revisions[0].imageDigest = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api:latest"
$taggedRevisionBlocked = $false
try {
    $null = Resolve-RuntimeWriterContractCandidate -Candidates $contractCandidates `
        -PushRepositorySha256 $sourceSha256 -RuntimeWriters $taggedRevisionRuntime
} catch {
    $taggedRevisionBlocked = $_.Exception.Message -ceq "runtime_writer_contract_service_digest_invalid"
}
Assert-Contract $taggedRevisionBlocked "un tag mobile non deve selezionare un'attestazione runtime"

$noContractSelected = Resolve-RuntimeWriterContractCandidate -Candidates @() `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime
Assert-Contract ($null -eq $noContractSelected) "senza contratti compatibili il gate principale deve poter segnalare l'attestazione mancante"
$auditScript = Join-Path $PSScriptRoot "audit-firestore-push-ttl.ps1"
$temporaryContract = Join-Path ([IO.Path]::GetTempPath()) "meteofriul-firestore-ttl-runtime-writer-contract-$PID.json"
[IO.File]::WriteAllText(
    $temporaryContract,
    ($runtimeContract | ConvertTo-Json -Depth 12),
    [Text.UTF8Encoding]::new($false)
)

$entrypointReady = & $auditScript -PassThru `
    -PolicyFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-active.json") `
    -ReadbackFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-readback-clean.json") `
    -HistoricalEvidencePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-history-complete.json") `
    -RuntimeFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-runtime-writers-active.json") `
    -RuntimeWriterContractPath $temporaryContract `
    -RuntimeBuildFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-cloud-build-success.json")
Assert-Contract $entrypointReady.ready "l'entrypoint PassThru deve restituire il risultato pronto senza terminare il processo chiamante"

$entrypointBlocked = & $auditScript -PassThru `
    -PolicyFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-missing-local.json") `
    -ReadbackFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-readback-clean.json") `
    -HistoricalEvidencePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-history-complete.json") `
    -RuntimeFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-runtime-writers-active.json") `
    -RuntimeWriterContractPath $temporaryContract `
    -RuntimeBuildFixturePath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-cloud-build-success.json")
Assert-Contract (-not $entrypointBlocked.ready) "l'entrypoint PassThru deve restituire il blocker senza terminare il processo chiamante"

$ready = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract $ready.ready "policy ACTIVE, orizzonti applicativi e bonifica storica devono passare"
Assert-Contract ($ready.blockingCount -eq 0) "la fixture completa non deve avere blocker"
Assert-Contract ($ready.expected.policies[0].appHorizonDays -eq 30) "orizzonte ufficiale non registrato"
Assert-Contract ($ready.expected.policies[1].appHorizonDays -eq 14) "orizzonte locale non registrato"
Assert-Contract $ready.semantics.missingOrNullFieldNeverExpires "la semantica dei campi assenti deve restare esplicita"
$expectedJobNames = @(
    "meteofriul-official-alert-sync",
    "meteofriul-local-notice",
    "meteofriul-morning-forecast",
    "meteofriul-evening-forecast"
)
Assert-Contract (@($ready.expected.runtimeWriters).Count -eq 5) "il gate deve censire API e quattro job writer"
Assert-Contract (@(Get-FirestorePushTtlWriterJobNames).Count -eq 4) "l'inventario dei job writer deve essere condiviso"
foreach ($expectedJobName in $expectedJobNames) {
    Assert-Contract (@($ready.expected.runtimeWriters | Where-Object { $_.name -ceq $expectedJobName }).Count -eq 1) `
        "writer non censito: $expectedJobName"
}

$missing = @(Read-Fixture "firestore-push-ttl-missing-local.json")
$missingResult = Test-FirestorePushTtlState -TtlPolicies $missing -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $missingResult.ready) "una policy mancante non deve passare"
Assert-Contract (Has-Finding $missingResult "ttl_policy_missing") "manca il blocker per policy assente"

$configuring = Copy-Value $active
$configuring[0].ttlConfig.state = "CREATING"
$configuringResult = Test-FirestorePushTtlState -TtlPolicies $configuring -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $configuringResult.ready) "una policy non ancora ACTIVE non deve passare"
Assert-Contract (Has-Finding $configuringResult "ttl_policy_not_active") "manca il blocker per policy non attiva"

$offset = Copy-Value $active
$offset[1].ttlConfig | Add-Member -NotePropertyName expirationOffset -NotePropertyValue "86400s"
$offsetResult = Test-FirestorePushTtlState -TtlPolicies $offset -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $offsetResult.ready) "un offset TTL aggiuntivo non deve passare"
Assert-Contract (Has-Finding $offsetResult "ttl_expiration_offset_not_zero") "manca il blocker per offset TTL"

$zeroOffset = Copy-Value $active
$zeroOffset[0].ttlConfig | Add-Member -NotePropertyName expirationOffset -NotePropertyValue "0s"
$zeroOffsetResult = Test-FirestorePushTtlState -TtlPolicies $zeroOffset -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract $zeroOffsetResult.ready "l'offset TTL esplicito zero deve passare"

$wrongHorizonSource = $source -replace "PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS = 30", "PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS = 31"
$wrongHorizon = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $wrongHorizonSource `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $wrongHorizon.ready) "un orizzonte applicativo diverso non deve passare"
Assert-Contract (Has-Finding $wrongHorizon "app_retention_horizon_mismatch") "manca il blocker per orizzonte applicativo"

$missingHistory = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback @runtimeGate
Assert-Contract (-not $missingHistory.ready) "la policy non copre i record storici senza expires_at"
Assert-Contract (Has-Finding $missingHistory "historical_cleanup_evidence_missing") "manca il blocker per evidenza storica"

$incompleteHistory = Copy-Value $history
$incompleteHistory.collections[0].missingOrInvalidExpiresAt = 2
$incompleteHistoryResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $incompleteHistory -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $incompleteHistoryResult.ready) "record storici senza expires_at non devono passare"
Assert-Contract (Has-Finding $incompleteHistoryResult "historical_rows_without_expiry") "manca il blocker per record storici"

$freeTextProvenance = Copy-Value $history
$freeTextProvenance.collections[0].PSObject.Properties.Remove("provenance")
$freeTextProvenance.collections[0] | Add-Member -NotePropertyName evidenceReference -NotePropertyValue "verificato manualmente"
$freeTextProvenanceResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $freeTextProvenance -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $freeTextProvenanceResult.ready) "una nota libera non deve sostituire la provenienza del read-back"
Assert-Contract (Has-Finding $freeTextProvenanceResult "historical_cleanup_provenance_missing") "manca il blocker per provenienza strutturata"

$invalidReadbackDigest = Copy-Value $history
$invalidReadbackDigest.collections[1].provenance.postReadbackSha256 = "digest-manuale"
$invalidReadbackDigestResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $invalidReadbackDigest -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $invalidReadbackDigestResult.ready) "un digest post-readback non verificabile non deve passare"
Assert-Contract (Has-Finding $invalidReadbackDigestResult "historical_cleanup_readback_digest_invalid") "manca il blocker per digest post-readback"

$invalidPolicySnapshot = Copy-Value $history
$invalidPolicySnapshot.ttlPolicies[0].state = "CREATING"
$invalidPolicySnapshotResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $invalidPolicySnapshot -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $invalidPolicySnapshotResult.ready) "uno snapshot storico TTL non ACTIVE non deve passare"
Assert-Contract (Has-Finding $invalidPolicySnapshotResult "historical_ttl_policy_invalid") "manca il blocker per snapshot TTL storico"

$wrongTarget = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -ProjectId "altro-progetto" @runtimeGate
Assert-Contract (-not $wrongTarget.ready) "un progetto diverso non deve passare"
Assert-Contract (Has-Finding $wrongTarget "firestore_target_mismatch") "manca il blocker progetto"

$dirtyEvidence = [PSCustomObject]@{ tracked = $true; clean = $false; commitCount = 1 }
$dirtyEvidenceResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $dirtyEvidence @runtimeGate
Assert-Contract (-not $dirtyEvidenceResult.ready) "un'evidenza modificata dopo il commit non deve passare"
Assert-Contract (Has-Finding $dirtyEvidenceResult "historical_cleanup_evidence_not_immutable") "manca il blocker immutabilita' evidenza"

$rewrittenEvidence = [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 2 }
$rewrittenEvidenceResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $rewrittenEvidence @runtimeGate
Assert-Contract (-not $rewrittenEvidenceResult.ready) "un'evidenza riscritta in Git non deve passare"
Assert-Contract (Has-Finding $rewrittenEvidenceResult "historical_cleanup_evidence_not_immutable") "manca il blocker single-add"

$dirtyReadback = Copy-Value $readback
$dirtyReadback.collections[0].validExpiresAtCount = 0
$dirtyReadback.collections[0].missingOrInvalidExpiresAt = 1
$dirtyReadbackResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $dirtyReadback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus @runtimeGate
Assert-Contract (-not $dirtyReadbackResult.ready) "un documento corrente privo di expires_at non deve passare"
Assert-Contract (Has-Finding $dirtyReadbackResult "firestore_current_rows_without_expiry") "manca il blocker read-back corrente"

$missingRuntimeContract = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -PushRepositorySha256 $sourceSha256 -CurrentReadback $readback `
    -HistoricalEvidence $history -EvidenceGitStatus $gitStatus -RuntimeWriters $runtime `
    -RuntimeBuildVerification $runtimeBuild -PushRepositoryGitStatus $pushRepositoryGitStatus
Assert-Contract (-not $missingRuntimeContract.ready) "il runtime non deve passare senza attestazione immutabile"
Assert-Contract (Has-Finding $missingRuntimeContract "runtime_writer_contract_missing") "manca il blocker attestazione runtime"

$wrongSourceContract = Copy-Value $runtimeContract
$wrongSourceContract.pushRepositorySha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
$wrongSourceResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime `
    -RuntimeWriterContract $wrongSourceContract -RuntimeContractGitStatus $runtimeGitStatus
Assert-Contract (-not $wrongSourceResult.ready) "un'immagine attestata contro un push.py diverso non deve passare"
Assert-Contract (Has-Finding $wrongSourceResult "runtime_writer_source_digest_mismatch") "manca il blocker digest sorgente"

$mobileTagRuntime = Copy-Value $runtime
$mobileTagRuntime.jobs[0].imageDigest = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api:latest"
$mobileTagResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $mobileTagRuntime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus
Assert-Contract (-not $mobileTagResult.ready) "un job configurato con tag mobile non deve passare"
Assert-Contract (Has-Finding $mobileTagResult "runtime_writer_job_digest_not_immutable") "manca il blocker tag mobile"

foreach ($expectedJobName in $expectedJobNames) {
    $mismatchedJobRuntime = Copy-Value $runtime
    $jobToMismatch = @($mismatchedJobRuntime.jobs | Where-Object { $_.name -ceq $expectedJobName })[0]
    $jobToMismatch.imageDigest = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    $mismatchedJobResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
        -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
        -PushRepositorySha256 $sourceSha256 -RuntimeWriters $mismatchedJobRuntime `
        -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus
    Assert-Contract (-not $mismatchedJobResult.ready) "digest diverso non bloccato: $expectedJobName"
    Assert-Contract (Has-Finding $mismatchedJobResult "runtime_writer_digest_mismatch") `
        "manca il blocker parita' digest: $expectedJobName"

    $missingJobRuntime = Copy-Value $runtime
    $missingJobRuntime.jobs = @($missingJobRuntime.jobs | Where-Object { $_.name -cne $expectedJobName })
    $missingJobResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
        -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
        -PushRepositorySha256 $sourceSha256 -RuntimeWriters $missingJobRuntime `
        -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus
    Assert-Contract (-not $missingJobResult.ready) "job mancante non bloccato: $expectedJobName"
    Assert-Contract (Has-Finding $missingJobResult "runtime_writer_job_missing") `
        "manca il blocker job assente: $expectedJobName"
}

$splitTrafficRuntime = Copy-Value $runtime
$splitTrafficRuntime.service.traffic[0].percent = 50
$splitTrafficRuntime.service.traffic += [PSCustomObject]@{
    revisionName = "meteofriul-api-other-abcdef0"
    percent = 50
    tag = ""
}
$splitTrafficResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $splitTrafficRuntime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus
Assert-Contract (-not $splitTrafficResult.ready) "traffico diviso tra revisioni non deve passare il gate writer"
Assert-Contract (Has-Finding $splitTrafficResult "runtime_writer_service_traffic_not_100") "manca il blocker revisione al 100%"

$dirtyRuntimeContractStatus = [PSCustomObject]@{ tracked = $true; clean = $false; commitCount = 1 }
$dirtyRuntimeContractResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $dirtyRuntimeContractStatus
Assert-Contract (-not $dirtyRuntimeContractResult.ready) "un'attestazione runtime modificata dopo il commit non deve passare"
Assert-Contract (Has-Finding $dirtyRuntimeContractResult "runtime_writer_contract_not_immutable") "manca il blocker immutabilita' attestazione runtime"

$wrongBuild = Copy-Value $runtimeBuild
$wrongBuild.canonicalImageDigests[0] = "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
$wrongBuildResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus `
    -RuntimeBuildVerification $wrongBuild -PushRepositoryGitStatus $pushRepositoryGitStatus
Assert-Contract (-not $wrongBuildResult.ready) "un read-back Cloud Build su digest diverso non deve passare"
Assert-Contract (Has-Finding $wrongBuildResult "runtime_writer_build_digest_mismatch") "manca il blocker digest Cloud Build"

$duplicateAliasBuild = Copy-Value $runtimeBuild
$duplicateAliasBuild.canonicalImageDigests += $duplicateAliasBuild.canonicalImageDigests[0]
$duplicateAliasBuildResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus `
    -RuntimeBuildVerification $duplicateAliasBuild -PushRepositoryGitStatus $pushRepositoryGitStatus
Assert-Contract $duplicateAliasBuildResult.ready "due alias Cloud Build dello stesso digest devono essere normalizzati"

$ambiguousBuild = Copy-Value $runtimeBuild
$ambiguousBuild.canonicalImageDigests += "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
$ambiguousBuildResult = Test-FirestorePushTtlState -TtlPolicies $active -PushRepositorySource $source `
    -CurrentReadback $readback -HistoricalEvidence $history -EvidenceGitStatus $gitStatus `
    -PushRepositorySha256 $sourceSha256 -RuntimeWriters $runtime `
    -RuntimeWriterContract $runtimeContract -RuntimeContractGitStatus $runtimeGitStatus `
    -RuntimeBuildVerification $ambiguousBuild -PushRepositoryGitStatus $pushRepositoryGitStatus
Assert-Contract (-not $ambiguousBuildResult.ready) "due digest Cloud Build distinti non devono passare"
Assert-Contract (Has-Finding $ambiguousBuildResult "runtime_writer_build_digest_mismatch") "manca il blocker per digest Cloud Build distinti"

$auditSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "audit-firestore-push-ttl.ps1") -Raw
Assert-Contract $auditSource.Contains("Resolve-RuntimeWriterContractCandidate") "l'entrypoint deve usare la selezione fail-closed del contratto runtime"
Assert-Contract $auditSource.Contains("Get-FirestorePushTtlScheduledWriterTargets") "l'entrypoint live deve seguire i target degli Scheduler condivisi con il gate"
Assert-Contract $auditSource.Contains("log --no-renames --format=%H") "la cronologia append-only deve ignorare le rinomine inferite da Git"
Assert-Contract (-not $auditSource.Contains("log --follow --format=%H")) "--follow puo' fondere per errore la storia di contratti JSON simili"
$forbiddenMutations = @(
    "fields ttls update",
    "--enable-ttl",
    "--disable-ttl",
    "firestore delete",
    "documents delete",
    "documents patch",
    "documents commit",
    "run jobs update",
    "services update-traffic",
    "builds submit"
)
foreach ($token in $forbiddenMutations) {
    Assert-Contract (-not $auditSource.Contains($token)) "lo script audit-only contiene il token mutante: $token"
}

if (Test-Path -LiteralPath $temporaryContract -PathType Leaf) {
    Remove-Item -LiteralPath $temporaryContract -Force
}

Write-Host "Firestore push TTL audit contract tests: OK"
