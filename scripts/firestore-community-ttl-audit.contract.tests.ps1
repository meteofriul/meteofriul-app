$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "firestore-community-ttl-audit.psm1") -Force

function Assert-Test {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "assertion_failed:$Message" }
}

function Assert-Finding {
    param([object]$Audit, [string]$Code, [string]$Message)
    Assert-Test (
        @($Audit.findings | Where-Object { [string]$_.code -ceq $Code }).Count -gt 0
    ) $Message
}

function Assert-ThrowsLike {
    param([scriptblock]$Operation, [string]$Pattern)
    try {
        & $Operation
    } catch {
        if ($_.Exception.Message -like $Pattern) { return }
        throw "assertion_failed:expected=$Pattern actual=$($_.Exception.Message)"
    }
    throw "assertion_failed:missing_exception:$Pattern"
}

function New-Identity {
    param(
        [string[]]$ActiveAccounts = @("meteofriul@gmail.com"),
        [string]$ConfiguredAccount = "meteofriul@gmail.com",
        [string]$ConfiguredProject = "meteo-friul",
        [string]$ProjectId = "meteo-friul",
        [string]$ProjectNumber = "49007668366",
        [string]$ProjectState = "ACTIVE",
        [string]$DatabaseName = "projects/meteo-friul/databases/(default)",
        [string]$DatabaseType = "FIRESTORE_NATIVE"
    )
    return [PSCustomObject]@{
        activeAccounts = $ActiveAccounts
        configuredAccount = $ConfiguredAccount
        configuredProject = $ConfiguredProject
        projectId = $ProjectId
        projectNumber = $ProjectNumber
        projectState = $ProjectState
        databaseName = $DatabaseName
        databaseType = $DatabaseType
    }
}

function New-Policies {
    foreach ($contract in @(Get-CommunityTtlAuditContract)) {
        [PSCustomObject]@{
            name = (
                "projects/meteo-friul/databases/(default)/collectionGroups/" +
                "$($contract.collectionGroup)/fields/$($contract.field)"
            )
            ttlConfig = [PSCustomObject]@{ state = "ACTIVE" }
        }
    }
}

function New-Documents {
    $base = [DateTimeOffset]"2026-08-24T10:00:00Z"
    $horizons = @{
        community_reports = 3600
        community_report_cooldowns = 2700
        community_report_confirmations = 3000
        community_report_flags = 86400
        community_report_moderation = 86400
        community_source_blocks = 7200
        community_report_rate_limits = 120
        community_moderation_digest_state = 172800
        community_reputation = 31536000
        community_reputation_awards = 31536000
    }
    $index = 0
    foreach ($contract in @(Get-CommunityTtlAuditContract)) {
        $baseline = $base.AddMinutes($index)
        $seconds = [double]$horizons[[string]$contract.collectionGroup]
        [PSCustomObject]@{
            collectionGroup = [string]$contract.collectionGroup
            expiryType = "timestampValue"
            expiresAt = $baseline.AddSeconds($seconds).ToString("o")
            baselineType = "timestampValue"
            baselineAt = $baseline.ToString("o")
            documentName = "private-document-name-must-not-escape"
            owner_key = "owner-secret-marker"
            client_key = "client-secret-marker"
        }
        $index += 1
    }
}

$capturedAt = [DateTimeOffset]"2026-08-24T10:30:00Z"
$contractRows = @(Get-CommunityTtlAuditContract)
$expectedContract = [ordered]@{
    community_reports = @("created_at_timestamp", 3600.0, 3600.0)
    community_report_cooldowns = @("updated_at", 2700.0, 2700.0)
    community_report_confirmations = @("updated_at", 0.0, 3600.0)
    community_report_flags = @("created_at_timestamp", 86400.0, 86400.0)
    community_report_moderation = @("updated_at", 0.0, 86400.0)
    community_source_blocks = @("updated_at", 3600.0, 86400.0)
    community_report_rate_limits = @("updated_at", 0.0, 7200.0)
    community_moderation_digest_state = @(
        "updated_at_timestamp", 172800.0, 172800.0
    )
    community_reputation = @("updated_at", 31536000.0, 31536000.0)
    community_reputation_awards = @("updated_at", 31536000.0, 31536000.0)
}
Assert-Test ($contractRows.Count -eq 10) "contratto di dieci collection group"
foreach ($entry in $expectedContract.GetEnumerator()) {
    $contractRow = @($contractRows | Where-Object {
        [string]$_.collectionGroup -ceq [string]$entry.Key
    })
    Assert-Test ($contractRow.Count -eq 1) "collection contract $($entry.Key)"
    Assert-Test (
        [string]$contractRow[0].baselineField -ceq [string]$entry.Value[0]
    ) "baseline contract $($entry.Key)"
    Assert-Test (
        [double]$contractRow[0].minimumHorizonSeconds -eq [double]$entry.Value[1]
    ) "minimo contract $($entry.Key)"
    Assert-Test (
        [double]$contractRow[0].maximumHorizonSeconds -eq [double]$entry.Value[2]
    ) "massimo contract $($entry.Key)"
}
$clean = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) `
    -Policies @(New-Policies) `
    -Documents @(New-Documents) `
    -CapturedAtUtc $capturedAt `
    -SourceMode "live-read-only"
Assert-Test $clean.ready "snapshot completo conforme"
Assert-Test $clean.identityReady "identita conforme"
Assert-Test $clean.policyReady "policy conformi"
Assert-Test $clean.documentReady "documenti conformi"
Assert-Test $clean.sampleCoverageComplete "campioni completi"
Assert-Test ($clean.policies.Count -eq 10) "dieci policy"
Assert-Test ($clean.collections.Count -eq 10) "dieci collection group"
Assert-Test ($clean.blockingCount -eq 0) "nessun finding bloccante"
Assert-Test ($clean.ttlDeletionGraceSeconds -eq 86400) "grace TTL esplicita 24h"
Assert-Test ($clean.clockSkewToleranceSeconds -eq 300) (
    "tolleranza clock skew esplicita 5 minuti"
)
$recentRateLimit = @($clean.collections | Where-Object {
    $_.collectionGroup -ceq "community_report_rate_limits"
})[0]
Assert-Test ($recentRateLimit.expiredDocumentCount -eq 1) (
    "campione scaduto entro grace rilevato"
)
Assert-Test ($recentRateLimit.expiredBeyondGraceCount -eq 0) (
    "campione entro grace non e' stale"
)
Assert-Test ($recentRateLimit.recentHorizonSampleCount -eq 1) (
    "campione entro grace attesta l'orizzonte"
)
$cleanJson = $clean | ConvertTo-Json -Depth 10
foreach ($privateMarker in @(
    "private-document-name-must-not-escape",
    "owner-secret-marker",
    "client-secret-marker",
    "documentName",
    "owner_key",
    "client_key"
)) {
    Assert-Test (-not $cleanJson.Contains($privateMarker)) (
        "evidenza aggregata non espone $privateMarker"
    )
}

$wrongAccount = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -ActiveAccounts @("other@example.com")) `
    -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Test (-not $wrongAccount.ready) "account errato blocca"
Assert-Finding $wrongAccount "community_ttl_active_account_mismatch" "finding account"

$multipleAccounts = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -ActiveAccounts @(
        "meteofriul@gmail.com", "other@example.com"
    )) -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Finding $multipleAccounts "community_ttl_active_account_mismatch" (
    "account attivo non univoco"
)

$configuredAccount = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -ConfiguredAccount "other@example.com") `
    -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Finding $configuredAccount "community_ttl_configured_account_mismatch" (
    "account configurato errato"
)

$configuredProject = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -ConfiguredProject "wrong-project") `
    -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Finding $configuredProject "community_ttl_configured_project_mismatch" (
    "progetto configurato errato"
)

$projectIdentity = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -ProjectNumber "1") `
    -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Finding $projectIdentity "community_ttl_project_identity_mismatch" (
    "numero progetto errato"
)

$databaseIdentity = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity -DatabaseName "projects/meteo-friul/databases/other") `
    -Policies @(New-Policies) -Documents @(New-Documents)
Assert-Finding $databaseIdentity "community_ttl_database_identity_mismatch" (
    "database errato"
)

$missingPolicyRows = @(New-Policies | Where-Object {
    [string]$_.name -notlike "*/community_report_flags/*"
})
$missingPolicy = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies $missingPolicyRows -Documents @(New-Documents)
Assert-Test (-not $missingPolicy.policyReady) "policy mancante blocca"
Assert-Finding $missingPolicy "community_ttl_policy_missing_or_ambiguous" (
    "finding policy mancante"
)

$duplicatePolicyRows = @(New-Policies)
$duplicatePolicyRows += $duplicatePolicyRows[0]
$duplicatePolicy = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies $duplicatePolicyRows `
    -Documents @(New-Documents)
Assert-Finding $duplicatePolicy "community_ttl_policy_missing_or_ambiguous" (
    "policy duplicata o ambigua blocca"
)

$wrongFieldRows = @(New-Policies)
$wrongFieldRows[0].name = $wrongFieldRows[0].name.Replace(
    "/fields/expires_at_timestamp", "/fields/expires_at"
)
$wrongField = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies $wrongFieldRows -Documents @(New-Documents)
Assert-Finding $wrongField "community_ttl_policy_field_mismatch" "campo TTL errato"

$creatingRows = @(New-Policies)
$creatingRows[1].ttlConfig.state = "CREATING"
$creating = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies $creatingRows -Documents @(New-Documents)
Assert-Finding $creating "community_ttl_policy_not_active" "CREATING blocca"

$offsetRows = @(New-Policies)
$offsetRows[2].ttlConfig | Add-Member -NotePropertyName expirationOffset -NotePropertyValue "1h"
$offset = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies $offsetRows -Documents @(New-Documents)
Assert-Finding $offset "community_ttl_policy_offset_not_zero" "offset non zero blocca"

$missingExpiryRows = @(New-Documents)
$missingExpiryRows[0].expiryType = "missing"
$missingExpiryRows[0].expiresAt = $null
$missingExpiry = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $missingExpiryRows
Assert-Test (-not $missingExpiry.documentReady) "expiry mancante blocca"
Assert-Finding $missingExpiry "community_ttl_document_expiry_missing" (
    "finding expiry mancante"
)

$wrongTypeRows = @(New-Documents)
$wrongTypeRows[1].expiryType = "stringValue"
$wrongTypeRows[1].expiresAt = $null
$wrongType = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $wrongTypeRows
Assert-Finding $wrongType "community_ttl_document_expiry_wrong_type" (
    "tipo expiry errato"
)

$invalidTimestampRows = @(New-Documents)
$invalidTimestampRows[2].expiresAt = "not-a-timestamp"
$invalidTimestamp = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $invalidTimestampRows
Assert-Finding $invalidTimestamp "community_ttl_document_expiry_invalid" (
    "timestamp expiry invalido"
)

$missingBaselineRows = @(New-Documents)
$missingBaselineRows[3].baselineType = "missing"
$missingBaselineRows[3].baselineAt = $null
$missingBaseline = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $missingBaselineRows
Assert-Finding $missingBaseline "community_ttl_document_baseline_missing" (
    "baseline mancante"
)

$wrongBaselineTypeRows = @(New-Documents)
$wrongBaselineTypeRows[4].baselineType = "integerValue"
$wrongBaselineTypeRows[4].baselineAt = $null
$wrongBaselineType = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $wrongBaselineTypeRows
Assert-Finding $wrongBaselineType "community_ttl_document_baseline_wrong_type" (
    "tipo baseline errato"
)

$invalidBaselineRows = @(New-Documents)
$invalidBaselineRows[5].baselineAt = "not-a-timestamp"
$invalidBaseline = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $invalidBaselineRows
Assert-Finding $invalidBaseline "community_ttl_document_baseline_invalid" (
    "timestamp baseline invalido"
)

$withinClockSkewRows = @(New-Documents)
$withinClockSkewReport = @($withinClockSkewRows | Where-Object {
    $_.collectionGroup -ceq "community_reports"
})[0]
$withinClockSkewReport.baselineAt = $capturedAt.AddMinutes(4).ToString("o")
$withinClockSkewReport.expiresAt = $capturedAt.AddMinutes(64).ToString("o")
$withinClockSkew = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $withinClockSkewRows -CapturedAtUtc $capturedAt
Assert-Test $withinClockSkew.ready "baseline entro clock skew ammesso"

$futureBaselineRows = @(New-Documents)
$futureBaselineReport = @($futureBaselineRows | Where-Object {
    $_.collectionGroup -ceq "community_reports"
})[0]
$futureBaselineReport.baselineAt = $capturedAt.AddMinutes(6).ToString("o")
$futureBaselineReport.expiresAt = $capturedAt.AddMinutes(66).ToString("o")
$futureBaseline = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $futureBaselineRows -CapturedAtUtc $capturedAt
Assert-Test (-not $futureBaseline.ready) "baseline futura oltre skew blocca"
Assert-Test (-not $futureBaseline.documentReady) (
    "baseline futura rende i documenti non conformi"
)
Assert-Finding $futureBaseline "community_ttl_document_baseline_in_future" (
    "finding baseline futura"
)

$tooShortRows = @(New-Documents)
$tooShortRows[0].expiresAt = (
    ([DateTimeOffset]$tooShortRows[0].baselineAt).AddMinutes(30).ToString("o")
)
$tooShort = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $tooShortRows
Assert-Finding $tooShort "community_ttl_document_horizon_too_short" (
    "orizzonte report troppo corto"
)

$tooLongRows = @(New-Documents)
$rateRow = @($tooLongRows | Where-Object {
    $_.collectionGroup -ceq "community_report_rate_limits"
})[0]
$rateRow.expiresAt = (
    ([DateTimeOffset]$rateRow.baselineAt).AddHours(3).ToString("o")
)
$tooLong = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $tooLongRows
Assert-Finding $tooLong "community_ttl_document_horizon_too_long" (
    "orizzonte rate limit troppo lungo"
)

$zeroHorizonRows = @(New-Documents)
$confirmationRow = @($zeroHorizonRows | Where-Object {
    $_.collectionGroup -ceq "community_report_confirmations"
})[0]
$confirmationRow.expiresAt = $confirmationRow.baselineAt
$zeroHorizon = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $zeroHorizonRows -CapturedAtUtc $capturedAt
Assert-Finding $zeroHorizon "community_ttl_document_horizon_too_short" (
    "orizzonte zero vietato anche quando il minimo contrattuale e' zero"
)

$moderationRetryRows = @(New-Documents)
$moderationRetry = @($moderationRetryRows | Where-Object {
    $_.collectionGroup -ceq "community_report_moderation"
})[0]
$moderationRetry.baselineAt = (
    ([DateTimeOffset]$moderationRetry.baselineAt).AddMinutes(30).ToString("o")
)
$moderationRetryAudit = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $moderationRetryRows -CapturedAtUtc $capturedAt
Assert-Test $moderationRetryAudit.ready (
    "retry idempotente moderazione puo preservare expiry e ridurre l'orizzonte"
)
Assert-Test (
    @($moderationRetryAudit.findings | Where-Object {
        $_.collectionGroup -ceq "community_report_moderation" -and
        $_.code -like "community_ttl_document_horizon_*"
    }).Count -eq 0
) "moderation retry entro 24h conforme"

$staleOnly = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents @(New-Documents) `
    -CapturedAtUtc ([DateTimeOffset]"2026-08-28T12:00:00Z")
Assert-Test (-not $staleOnly.ready) "fixture stale-only fail-closed"
Assert-Test (-not $staleOnly.documentReady) "stale oltre grace non conforme"
Assert-Test (-not $staleOnly.sampleCoverageComplete) (
    "stale-only non attesta copertura recente"
)
Assert-Finding $staleOnly "community_ttl_document_expired_beyond_grace" (
    "record oltre grace rilevati"
)
Assert-Finding $staleOnly "community_ttl_horizon_sample_missing" (
    "record stale non valgono come campione"
)

$emptyRows = @(New-Documents | Where-Object {
    $_.collectionGroup -cne "community_moderation_digest_state"
})
$emptySample = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) `
    -Documents $emptyRows -CapturedAtUtc $capturedAt
Assert-Test $emptySample.documentReady "collection vuota non contiene record invalidi"
Assert-Test (-not $emptySample.sampleCoverageComplete) "campione vuoto non completo"
Assert-Test $emptySample.ready "collection vuota ammessa dal read-back fresco"
Assert-Test ($emptySample.blockingCount -eq 0) (
    "assenza campione non blocca il read-back fresco"
)
Assert-Finding $emptySample "community_ttl_horizon_sample_missing" (
    "assenza campione corrente resta visibile"
)
$emptyFinding = @($emptySample.findings | Where-Object {
    [string]$_.code -ceq "community_ttl_horizon_sample_missing"
})[0]
Assert-Test ($emptyFinding.blocking -eq $false) (
    "assenza campione e' informativa nel read-back fresco"
)

$fullyEmpty = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents @()
Assert-Test $fullyEmpty.ready "dieci collection vuote ammesse"
Assert-Test $fullyEmpty.identityReady "identita ancora verificata a database vuoto"
Assert-Test $fullyEmpty.policyReady "dieci policy ancora verificate a database vuoto"
Assert-Test $fullyEmpty.documentReady "nessun documento corrente invalido"
Assert-Test (-not $fullyEmpty.sampleCoverageComplete) (
    "read-back vuoto non inventa copertura campioni"
)
Assert-Test ($fullyEmpty.collections.Count -eq 10) (
    "read-back vuoto conserva dieci righe aggregate"
)
Assert-Test (@($fullyEmpty.collections | Where-Object {
    [int]$_.documentCount -ne 0
}).Count -eq 0) "conteggi vuoti espliciti"

$unknownRows = @(
    @(New-Documents) +
    [PSCustomObject]@{
        collectionGroup = "unexpected_private_collection"
        expiryType = "timestampValue"
        expiresAt = "2026-08-24T11:00:00Z"
        baselineType = "timestampValue"
        baselineAt = "2026-08-24T10:00:00Z"
    }
)
$unknown = Test-FirestoreCommunityTtlSnapshot `
    -Identity (New-Identity) -Policies @(New-Policies) -Documents $unknownRows
Assert-Finding $unknown "community_ttl_snapshot_collection_unexpected" (
    "collection fuori contratto blocca"
)

$operationPath = Join-Path $PSScriptRoot "audit-firestore-community-ttl.ps1"
$operationSource = Get-Content -LiteralPath $operationPath -Raw
Assert-Test ($operationSource.Contains('documents:runQuery')) "sola query Firestore"
Assert-Test ($operationSource.Contains('[Parameter(Mandatory = $true)]')) (
    "output evidence obbligatorio"
)
Assert-Test ($operationSource.Contains('--account=$Account')) "account esplicito"
Assert-Test ($operationSource.Contains('--project=$ProjectId')) "progetto esplicito"
Assert-Test ($operationSource.Contains('--database=$DatabaseId')) "database esplicito"
Assert-Test ($operationSource.Contains('Parameters.ContainsKey("DateKind")')) (
    "feature detection ConvertFrom-Json DateKind"
)
Assert-Test (
    (Get-Command ConvertFrom-Json).Parameters.ContainsKey("DateKind")
) "runtime test supporta DateKind"
foreach ($forbidden in @(
    "--enable-ttl",
    "--disable-ttl",
    "documents:commit",
    "firestore fields ttls update",
    "Invoke-RestMethod -Method Delete"
)) {
    Assert-Test (-not $operationSource.Contains($forbidden)) (
        "script read-only non contiene $forbidden"
    )
}

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "meteofriul-community-ttl-audit-tests-$PID"
)
if (Test-Path -LiteralPath $temporaryRoot) {
    throw "unsafe_preexisting_test_directory"
}
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $fixturePath = Join-Path $temporaryRoot "clean-snapshot.json"
    $evidencePath = Join-Path $temporaryRoot "clean-evidence.json"
    $fixture = [PSCustomObject]@{
        capturedAtUtc = $capturedAt.ToString("o")
        identity = New-Identity
        policies = @(New-Policies)
        documents = @(New-Documents)
    }
    [IO.File]::WriteAllText(
        $fixturePath,
        ($fixture | ConvertTo-Json -Depth 10),
        [Text.UTF8Encoding]::new($false)
    )
    Assert-ThrowsLike {
        & $operationPath -OutputPath $evidencePath `
            -SnapshotFixturePath $fixturePath | Out-Null
    } "firestore_community_ttl_audit_failed:*"
    Assert-Test (Test-Path -LiteralPath $evidencePath -PathType Leaf) (
        "evidenza scritta nel path richiesto"
    )
    $evidence = Get-Content -LiteralPath $evidencePath -Raw |
        ConvertFrom-Json -DateKind String
    Assert-Test (-not $evidence.ready) "fixture non puo attestare il cloud"
    Assert-Test $evidence.identityReady "fixture valida il contratto identita"
    Assert-Test $evidence.policyReady "fixture valida il contratto policy"
    Assert-Test $evidence.documentReady "fixture valida il contratto documenti"
    Assert-Test $evidence.sampleCoverageComplete "fixture copre i campioni sintetici"
    Assert-Test ($evidence.sourceMode -ceq "fixture-read-only") "fixture marcata"
    Assert-Finding $evidence "community_ttl_fixture_evidence_not_live" (
        "gate rifiuta evidence fixture"
    )
    Assert-Test ($evidence.collections.Count -eq 10) "evidenza dieci collection"
    $evidenceText = Get-Content -LiteralPath $evidencePath -Raw
    Assert-Test (-not $evidenceText.Contains("owner-secret-marker")) (
        "evidenza su file priva di dati privati"
    )
    Assert-ThrowsLike {
        & $operationPath -OutputPath $evidencePath `
            -SnapshotFixturePath $fixturePath | Out-Null
    } "community_ttl_output_exists"

    $failingFixturePath = Join-Path $temporaryRoot "failing-snapshot.json"
    $failingEvidencePath = Join-Path $temporaryRoot "failing-evidence.json"
    $failingPolicies = @(New-Policies)
    $failingPolicies[0].ttlConfig.state = "CREATING"
    $failingFixture = [PSCustomObject]@{
        capturedAtUtc = $capturedAt.ToString("o")
        identity = New-Identity
        policies = $failingPolicies
        documents = @(New-Documents)
    }
    [IO.File]::WriteAllText(
        $failingFixturePath,
        ($failingFixture | ConvertTo-Json -Depth 10),
        [Text.UTF8Encoding]::new($false)
    )
    Assert-ThrowsLike {
        & $operationPath -OutputPath $failingEvidencePath `
            -SnapshotFixturePath $failingFixturePath | Out-Null
    } "firestore_community_ttl_audit_failed:*"
    Assert-Test (Test-Path -LiteralPath $failingEvidencePath -PathType Leaf) (
        "evidenza rossa scritta prima del fail"
    )
    $failedEvidence = Get-Content -LiteralPath $failingEvidencePath -Raw |
        ConvertFrom-Json -DateKind String
    Assert-Test (-not $failedEvidence.ready) "evidenza rossa non pronta"

    Assert-ThrowsLike {
        & $operationPath -OutputPath (Join-Path $temporaryRoot "wrong-target.json") `
            -SnapshotFixturePath $fixturePath -ProjectId "wrong-project" | Out-Null
    } "community_ttl_target_mismatch"
} finally {
    $resolvedTemporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolvedTemporaryRoot.StartsWith(
        $resolvedSystemTemp,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "unsafe_test_cleanup_target"
    }
    if (Test-Path -LiteralPath $resolvedTemporaryRoot) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}

Write-Host "Firestore community TTL audit contract tests: OK"
