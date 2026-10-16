$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$auditModule = Join-Path $PSScriptRoot "firestore-community-ttl-audit.psm1"
$evidenceModule = Join-Path $PSScriptRoot "firestore-community-ttl-evidence.psm1"
$recorderScript = Join-Path $PSScriptRoot (
    "record-firestore-community-ttl-evidence.ps1"
)
Import-Module $evidenceModule -Force
Import-Module $auditModule -Force

function Assert-Test {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "assertion_failed:$Message" }
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

function Copy-TestObject {
    param([object]$Value)
    return $Value | ConvertTo-Json -Depth 12 | ConvertFrom-Json -DateKind String
}

$recorderTokens = $null
$recorderParseErrors = $null
$recorderAst = [Management.Automation.Language.Parser]::ParseFile(
    $recorderScript,
    [ref]$recorderTokens,
    [ref]$recorderParseErrors
)
Assert-Test ($recorderParseErrors.Count -eq 0) "recorder PowerShell valido"
foreach ($functionName in @(
    "Resolve-RecorderGcloudPythonEntrypoint",
    "Invoke-RecorderGcloudCapture"
)) {
    $functionAst = $recorderAst.Find(
        {
            param($node)
            return ($node -is [Management.Automation.Language.FunctionDefinitionAst] -and
                $node.Name -ceq $functionName)
        },
        $true
    )
    Assert-Test ($null -ne $functionAst) "helper recorder presente: $functionName"
    . ([ScriptBlock]::Create($functionAst.Extent.Text))
}

function New-TestIdentity {
    return [PSCustomObject]@{
        activeAccounts = @("meteofriul@gmail.com")
        configuredAccount = "meteofriul@gmail.com"
        configuredProject = "meteo-friul"
        projectId = "meteo-friul"
        projectNumber = "49007668366"
        projectState = "ACTIVE"
        databaseName = "projects/meteo-friul/databases/(default)"
        databaseType = "FIRESTORE_NATIVE"
        privateIdentityMarker = "must-not-escape"
    }
}

function New-TestPolicies {
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

function New-TestDocuments {
    param([DateTimeOffset]$BaseUtc)
    $horizons = @{
        community_reports = 3600
        community_report_cooldowns = 2700
        community_report_confirmations = 3000
        community_report_flags = 86400
        community_report_moderation = 7200
        community_source_blocks = 7200
        community_report_rate_limits = 120
        community_moderation_digest_state = 172800
        community_reputation = 31536000
        community_reputation_awards = 31536000
    }
    $index = 0
    foreach ($contract in @(Get-CommunityTtlAuditContract)) {
        $baseline = $BaseUtc.AddSeconds($index)
        $horizon = [double]$horizons[[string]$contract.collectionGroup]
        [PSCustomObject]@{
            collectionGroup = [string]$contract.collectionGroup
            expiryType = "timestampValue"
            expiresAt = $baseline.AddSeconds($horizon).ToString("o")
            baselineType = "timestampValue"
            baselineAt = $baseline.ToString("o")
            documentName = "private-document-id-must-not-escape"
            owner_key = "private-owner-key-must-not-escape"
            coordinates = "private-coordinates-must-not-escape"
        }
        $index += 1
    }
}

function New-TestAudit {
    param(
        [DateTimeOffset]$CapturedAtUtc,
        [string]$SourceMode = "live-read-only",
        [object[]]$Documents = @(New-TestDocuments -BaseUtc $CapturedAtUtc)
    )
    return Test-FirestoreCommunityTtlSnapshot `
        -Identity (New-TestIdentity) `
        -Policies @(New-TestPolicies) `
        -Documents $Documents `
        -CapturedAtUtc $CapturedAtUtc `
        -SourceMode $SourceMode
}

$capturedAt = [DateTimeOffset]"2026-08-24T12:00:00Z"
$recordedAt = $capturedAt.AddMinutes(1)
$audit = New-TestAudit -CapturedAtUtc $capturedAt
Assert-Test $audit.ready "audit LIVE fixture comportamentale verde"
Assert-Test $audit.sampleCoverageComplete "dieci campioni presenti"

$contractOne = Get-CommunityTtlWriterContract -RepositoryRoot $workspaceRoot
$contractTwo = Get-CommunityTtlWriterContract -RepositoryRoot $workspaceRoot
Assert-Test ($contractOne.algorithm -ceq "sha256") "algoritmo SHA-256"
Assert-Test ($contractOne.sha256 -cmatch '^[0-9a-f]{64}$') "digest canonico"
Assert-Test ($contractOne.sha256 -ceq $contractTwo.sha256) (
    "hash writer deterministico"
)
Assert-Test ($contractOne.files.Count -eq 10) (
    "dieci sorgenti writer/evidence producer/recorder/validator"
)
Assert-Test (
    @($contractOne.files | Where-Object {
        $_ -ceq "backend/tools/seed_community_ttl_evidence_live.py"
    }).Count -eq 1
) "seed LIVE incluso nel digest"
Assert-Test (
    @($contractOne.files | Where-Object {
        $_ -ceq "backend/tools/smoke_community_moderation_live.py"
    }).Count -eq 1
) "smoke LIVE incluso nel digest"

$evidenceCore = New-FirestoreCommunityTtlHistoricalEvidence `
    -Audit $audit `
    -RepositoryRoot $workspaceRoot `
    -RecordedAtUtc $recordedAt
$evidenceJson = $evidenceCore | ConvertTo-Json -Depth 12
foreach ($privateMarker in @(
    "private-document-id-must-not-escape",
    "private-owner-key-must-not-escape",
    "private-coordinates-must-not-escape",
    "privateIdentityMarker",
    "documentName",
    "owner_key",
    "coordinates"
)) {
    Assert-Test (-not $evidenceJson.Contains($privateMarker)) (
        "record aggregato non espone $privateMarker"
    )
}

$fixtureAudit = New-TestAudit `
    -CapturedAtUtc $capturedAt `
    -SourceMode "fixture-read-only"
Assert-ThrowsLike {
    New-FirestoreCommunityTtlHistoricalEvidence `
        -Audit $fixtureAudit `
        -RepositoryRoot $workspaceRoot `
        -RecordedAtUtc $recordedAt | Out-Null
} "community_ttl_historical_evidence_live_audit_required"

$emptyAudit = New-TestAudit -CapturedAtUtc $capturedAt -Documents @()
Assert-Test $emptyAudit.ready "audit fresco vuoto verde"
Assert-Test (-not $emptyAudit.sampleCoverageComplete) (
    "audit fresco vuoto senza copertura storica"
)
Assert-ThrowsLike {
    New-FirestoreCommunityTtlHistoricalEvidence `
        -Audit $emptyAudit `
        -RepositoryRoot $workspaceRoot `
        -RecordedAtUtc $recordedAt | Out-Null
} "community_ttl_historical_evidence_audit_not_ready"

$delayedAudit = Copy-TestObject $audit
$delayedAudit.capturedAtUtc = $capturedAt.AddHours(-1).ToString("o")
Assert-ThrowsLike {
    New-FirestoreCommunityTtlHistoricalEvidence `
        -Audit $delayedAudit `
        -RepositoryRoot $workspaceRoot `
        -RecordedAtUtc $recordedAt | Out-Null
} "community_ttl_historical_evidence_recording_delay_invalid"

$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "meteofriul-community-ttl-evidence-tests-$PID"
)
if (Test-Path -LiteralPath $temporaryRoot) {
    throw "unsafe_preexisting_test_directory"
}
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $argvEchoScript = Join-Path $temporaryRoot "argv-echo.ps1"
    $argvEchoResult = Join-Path $temporaryRoot "argv-echo.json"
    [IO.File]::WriteAllText(
        $argvEchoScript,
        @'
param(
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Remaining
)
$json = ConvertTo-Json -InputObject @($Remaining) -Compress
[IO.File]::WriteAllText(
    $OutputPath,
    $json,
    [Text.UTF8Encoding]::new($false)
)
'@,
        [Text.UTF8Encoding]::new($false)
    )
    $quotedPayload = '{"testo":"Meteo Friûl: spazi, \"virgolette\" e àèìòù"}'
    $pwshExecutable = (Get-Process -Id $PID).Path
    $captureResult = Invoke-RecorderGcloudCapture `
        -Executable $pwshExecutable `
        -Arguments @(
            "-NoLogo", "-NoProfile", "-File", $argvEchoScript,
            $argvEchoResult, $quotedPayload
        )
    Assert-Test ($captureResult.ExitCode -eq 0) (
        "helper nativo completa il processo di prova"
    )
    $capturedArguments = @(
        Get-Content -LiteralPath $argvEchoResult -Raw |
            ConvertFrom-Json -DateKind String
    )
    Assert-Test ($capturedArguments.Count -eq 1) (
        "helper nativo conserva un singolo argomento JSON"
    )
    Assert-Test ([string]$capturedArguments[0] -ceq $quotedPayload) (
        "helper nativo conserva virgolette, spazi e Unicode"
    )

    $fakeSdkRoot = Join-Path $temporaryRoot "fake-google-cloud-sdk"
    $fakeSdkBin = Join-Path $fakeSdkRoot "bin"
    $fakeBundledPython = Join-Path (
        $fakeSdkRoot
    ) "platform\bundledpython\python.exe"
    $fakeGcloudPython = Join-Path $fakeSdkRoot "lib\gcloud.py"
    [IO.Directory]::CreateDirectory((Split-Path -Parent $fakeBundledPython)) |
        Out-Null
    [IO.Directory]::CreateDirectory((Split-Path -Parent $fakeGcloudPython)) |
        Out-Null
    [IO.Directory]::CreateDirectory($fakeSdkBin) | Out-Null
    [IO.File]::WriteAllBytes($fakeBundledPython, [byte[]]@(0))
    [IO.File]::WriteAllBytes($fakeGcloudPython, [byte[]]@(0))
    $rootGcloud = Join-Path $fakeSdkRoot "gcloud.cmd"
    $binGcloud = Join-Path $fakeSdkBin "gcloud.cmd"
    [IO.File]::WriteAllBytes($rootGcloud, [byte[]]@(0))
    [IO.File]::WriteAllBytes($binGcloud, [byte[]]@(0))
    foreach ($fakeGcloudPath in @($rootGcloud, $binGcloud)) {
        $fakeEntrypoint = Resolve-RecorderGcloudPythonEntrypoint `
            -Executable $fakeGcloudPath
        Assert-Test (
            [IO.Path]::GetFullPath($fakeEntrypoint.SdkRoot) -ceq
                [IO.Path]::GetFullPath($fakeSdkRoot)
        ) "helper risolve gcloud.cmd dalla root e da bin"
    }

    foreach ($relativePath in @($contractOne.files)) {
        $destination = Join-Path $temporaryRoot (
            $relativePath.Replace('/', [IO.Path]::DirectorySeparatorChar)
        )
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) |
            Out-Null
        $source = Join-Path $workspaceRoot (
            $relativePath.Replace('/', [IO.Path]::DirectorySeparatorChar)
        )
        [IO.File]::WriteAllBytes(
            $destination,
            [IO.File]::ReadAllBytes($source)
        )
    }
    $fixtureContract = Get-CommunityTtlWriterContract `
        -RepositoryRoot $temporaryRoot
    Assert-Test ($fixtureContract.sha256 -ceq $contractOne.sha256) (
        "stessi byte producono lo stesso hash"
    )
    foreach ($gitArguments in @(
        @('init'),
        @('config', 'user.email', 'contract@example.invalid'),
        @('config', 'user.name', 'Contract Test'),
        @('add', 'backend', 'scripts'),
        @('commit', '-m', 'add writer contract fixture')
    )) {
        & git -C $temporaryRoot @gitArguments | Out-Null
        Assert-Test ($LASTEXITCODE -eq 0) (
            "setup Git writer contract: $($gitArguments -join ' ')"
        )
    }
    $sourceCommit = (& git -C $temporaryRoot rev-parse HEAD).Trim()
    Assert-Test ($LASTEXITCODE -eq 0 -and
        $sourceCommit -cmatch '^[0-9a-f]{40}$') "commit sorgente fixture"
    $sourceContract = Get-CommunityTtlWriterContractFromGitCommit `
        -RepositoryRoot $temporaryRoot `
        -Commit $sourceCommit
    Assert-Test ($sourceContract.sha256 -ceq $fixtureContract.sha256) (
        "hash blob Git coincide con gli stessi byte locali"
    )
    $sourceBoundCore = New-FirestoreCommunityTtlHistoricalEvidence `
        -Audit $audit `
        -RepositoryRoot $temporaryRoot `
        -SourceCommit $sourceCommit `
        -RecordedAtUtc $recordedAt
    Assert-Test (
        [string]$sourceBoundCore.writerContract.sourceCommit -ceq
            $sourceCommit
    ) "record conserva il commit sorgente verificato"
    $nonce = "a" * 64
    $attestationEvent = New-CommunityTtlCloudAttestationEvent `
        -EvidenceCore $sourceBoundCore `
        -Nonce $nonce
    $logEntry = [PSCustomObject]@{
        logName = (
            "projects/meteo-friul/logs/" +
            "meteofriul-community-ttl-evidence"
        )
        timestamp = $recordedAt.AddSeconds(1).ToString("o")
        jsonPayload = $attestationEvent
        insertId = "allowed-remote-metadata"
    }
    $sourceBoundEvidence = Complete-FirestoreCommunityTtlHistoricalEvidence `
        -EvidenceCore $sourceBoundCore `
        -CloudLogEntry $logEntry `
        -ExpectedNonce $nonce
    $validated = Assert-FirestoreCommunityTtlHistoricalEvidence `
        -Evidence $sourceBoundEvidence `
        -RepositoryRoot $temporaryRoot `
        -ExpectedWriterContract $sourceContract `
        -NowUtc $recordedAt.AddDays(1)
    Assert-Test ($validated.CollectionCount -eq 10) "dieci collection storiche"
    Assert-Test ($validated.MaxAgeSeconds -eq 2592000) (
        "scadenza esplicita 30 giorni"
    )
    Assert-Test ($validated.WriterContractSha256 -ceq $sourceContract.sha256) (
        "evidenza legata agli writer correnti"
    )
    $remoteValidated = Assert-CommunityTtlCloudAttestationReadBack `
        -Evidence $sourceBoundEvidence `
        -Entries @($logEntry)
    Assert-Test ($remoteValidated.Nonce -ceq $nonce) (
        "attestation remota letta e correlata"
    )
    Assert-ThrowsLike {
        Assert-CommunityTtlJsonNoDuplicateProperties `
            -Json '{"sourceMode":"private-id","sourceMode":"live-read-only"}'
    } "community_ttl_json_duplicate_property"
    $fakeGcloudResult = Join-Path $temporaryRoot "fake-gcloud-result.json"
    [IO.File]::WriteAllText(
        $fakeGcloudResult,
        (@($logEntry) | ConvertTo-Json -Depth 12),
        [Text.UTF8Encoding]::new($false)
    )
    $fakeGcloud = Join-Path $temporaryRoot "fake-gcloud.ps1"
    [IO.File]::WriteAllText(
        $fakeGcloud,
        @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
Get-Content -LiteralPath $env:METEO_TTL_FAKE_GCLOUD_RESULT -Raw
exit 0
'@,
        [Text.UTF8Encoding]::new($false)
    )
    $previousFakeGcloudResult = $env:METEO_TTL_FAKE_GCLOUD_RESULT
    try {
        $env:METEO_TTL_FAKE_GCLOUD_RESULT = $fakeGcloudResult
        $mockedEntries = @(Read-CommunityTtlCloudAttestationLive `
            -Attestation $sourceBoundEvidence.cloudAttestation `
            -GcloudPath $fakeGcloud)
        Assert-Test ($mockedEntries.Count -eq 1) (
            "read-back gcloud e' mockabile nei contract"
        )
    } finally {
        if ($null -eq $previousFakeGcloudResult) {
            Remove-Item Env:METEO_TTL_FAKE_GCLOUD_RESULT `
                -ErrorAction SilentlyContinue
        } else {
            $env:METEO_TTL_FAKE_GCLOUD_RESULT = $previousFakeGcloudResult
        }
    }

    foreach ($mutation in @(
        [PSCustomObject]@{ level = "root"; name = "unexpectedRoot" },
        [PSCustomObject]@{ level = "identity"; name = "deviceId" },
        [PSCustomObject]@{ level = "policy"; name = "documentId" },
        [PSCustomObject]@{ level = "collection"; name = "coordinates" },
        [PSCustomObject]@{ level = "writer"; name = "owner_key" },
        [PSCustomObject]@{ level = "attestation"; name = "latitude" }
    )) {
        $extra = Copy-TestObject $sourceBoundEvidence
        $target = switch ($mutation.level) {
            "root" { $extra }
            "identity" { $extra.identity }
            "policy" { $extra.policies[0] }
            "collection" { $extra.collections[0] }
            "writer" { $extra.writerContract }
            "attestation" { $extra.cloudAttestation }
        }
        $target | Add-Member -NotePropertyName $mutation.name `
            -NotePropertyValue "must-be-rejected"
        Assert-ThrowsLike {
            Assert-FirestoreCommunityTtlHistoricalEvidence `
                -Evidence $extra `
                -RepositoryRoot $temporaryRoot `
                -ExpectedWriterContract $sourceContract `
                -NowUtc $recordedAt.AddDays(1) | Out-Null
        } "community_ttl_*schema_invalid"
    }

    $nanEvidence = Copy-TestObject $sourceBoundEvidence
    $nanEvidence.collections[0].minimumObservedHorizonSeconds = "NaN"
    $nanEvidence.collections[0].maximumObservedHorizonSeconds = "NaN"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $nanEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_sample_coverage_invalid"
    $stringCountEvidence = Copy-TestObject $sourceBoundEvidence
    $stringCountEvidence.collections[0].documentCount = "1"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $stringCountEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_sample_coverage_invalid"
    $stringBooleanEvidence = Copy-TestObject $sourceBoundEvidence
    $stringBooleanEvidence.ready = "true"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $stringBooleanEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_root_schema_invalid"
    $stringIdentityCountEvidence = Copy-TestObject $sourceBoundEvidence
    $stringIdentityCountEvidence.identity.activeAccountCount = "1"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $stringIdentityCountEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_identity_schema_invalid"
    $numericPolicyEvidence = Copy-TestObject $sourceBoundEvidence
    $numericPolicyEvidence.policies[0].state = 1
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $numericPolicyEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_policy_schema_invalid"
    $numericWriterFileEvidence = Copy-TestObject $sourceBoundEvidence
    $numericWriterFileEvidence.writerContract.files[0] = 1
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $numericWriterFileEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_historical_evidence_writer_contract_schema_invalid"
    $numericAttestationEvidence = Copy-TestObject $sourceBoundEvidence
    $numericAttestationEvidence.cloudAttestation.nonce = 1
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $numericAttestationEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt.AddDays(1) | Out-Null
    } "community_ttl_cloud_attestation_schema_invalid"

    $fixtureEvidence = Copy-TestObject $sourceBoundEvidence
    $fixtureEvidence.sourceMode = "fixture-read-only"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $fixtureEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_fixture_rejected"
    $wrongIdentityEvidence = Copy-TestObject $sourceBoundEvidence
    $wrongIdentityEvidence.identity.projectId = "other-project"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $wrongIdentityEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_identity_mismatch"
    $wrongHashEvidence = Copy-TestObject $sourceBoundEvidence
    $wrongHashEvidence.writerContract.sha256 = "0" * 64
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $wrongHashEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_writer_contract_hash_mismatch"
    $missingCoverageEvidence = Copy-TestObject $sourceBoundEvidence
    $missingCoverageEvidence.collections[0].validHorizonSampleCount = 0
    $missingCoverageEvidence.collections[0].recentHorizonSampleCount = 0
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $missingCoverageEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_sample_coverage_invalid"
    Assert-ThrowsLike {
        Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $sourceBoundEvidence `
            -RepositoryRoot $temporaryRoot `
            -ExpectedWriterContract $sourceContract `
            -NowUtc $capturedAt.AddDays(31) | Out-Null
    } "community_ttl_historical_evidence_stale"
    $forgedEntry = Copy-TestObject $logEntry
    $forgedEntry.jsonPayload.evidenceCoreSha256 = "0" * 64
    Assert-ThrowsLike {
        Assert-CommunityTtlCloudAttestationReadBack `
            -Evidence $sourceBoundEvidence `
            -Entries @($forgedEntry) | Out-Null
    } "community_ttl_cloud_attestation_event_mismatch:evidenceCoreSha256"
    $wrongNonceEntry = Copy-TestObject $logEntry
    $wrongNonceEntry.jsonPayload.nonce = "b" * 64
    Assert-ThrowsLike {
        Assert-CommunityTtlCloudAttestationReadBack `
            -Evidence $sourceBoundEvidence `
            -Entries @($wrongNonceEntry) | Out-Null
    } "community_ttl_cloud_attestation_event_mismatch:nonce"
    $extraRemoteEntry = Copy-TestObject $logEntry
    $extraRemoteEntry.jsonPayload | Add-Member `
        -NotePropertyName "deviceId" `
        -NotePropertyValue "must-be-rejected"
    Assert-ThrowsLike {
        Assert-CommunityTtlCloudAttestationReadBack `
            -Evidence $sourceBoundEvidence `
            -Entries @($extraRemoteEntry) | Out-Null
    } "community_ttl_cloud_attestation_event_schema_invalid"
    $numericRemoteEntry = Copy-TestObject $logEntry
    $numericRemoteEntry.jsonPayload.projectId = 1
    Assert-ThrowsLike {
        Assert-CommunityTtlCloudAttestationReadBack `
            -Evidence $sourceBoundEvidence `
            -Entries @($numericRemoteEntry) | Out-Null
    } "community_ttl_cloud_attestation_event_schema_invalid"
    $seedWriter = Join-Path $temporaryRoot (
        "backend\tools\seed_community_ttl_evidence_live.py"
    )
    $seedWriterOriginal = [IO.File]::ReadAllBytes($seedWriter)
    [IO.File]::AppendAllText(
        $seedWriter,
        "`n# contract-test-seed-tamper`n",
        [Text.UTF8Encoding]::new($false)
    )
    $tamperedSeedContract = Get-CommunityTtlWriterContract `
        -RepositoryRoot $temporaryRoot
    Assert-Test (
        $tamperedSeedContract.sha256 -cne $fixtureContract.sha256
    ) "tamper del seed invalida il digest"
    & git -C $temporaryRoot update-index --assume-unchanged `
        backend/tools/seed_community_ttl_evidence_live.py
    Assert-Test ($LASTEXITCODE -eq 0) "imposta assume-unchanged"
    $hiddenSeedStatus = (& git -C $temporaryRoot status --porcelain -- `
        backend/tools/seed_community_ttl_evidence_live.py | Out-String).Trim()
    Assert-Test (-not $hiddenSeedStatus) (
        "git status non vede il tamper assume-unchanged"
    )
    Assert-ThrowsLike {
        New-FirestoreCommunityTtlHistoricalEvidence `
            -Audit $audit `
            -RepositoryRoot $temporaryRoot `
            -SourceCommit $sourceCommit `
            -RecordedAtUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_source_commit_writer_contract_mismatch"
    & git -C $temporaryRoot update-index --no-assume-unchanged `
        backend/tools/seed_community_ttl_evidence_live.py
    Assert-Test ($LASTEXITCODE -eq 0) "rimuove assume-unchanged"
    [IO.File]::WriteAllBytes($seedWriter, $seedWriterOriginal)
    $smokeWriter = Join-Path $temporaryRoot (
        "backend\tools\smoke_community_moderation_live.py"
    )
    $smokeWriterOriginal = [IO.File]::ReadAllBytes($smokeWriter)
    [IO.File]::AppendAllText(
        $smokeWriter,
        "`n# contract-test-smoke-tamper`n",
        [Text.UTF8Encoding]::new($false)
    )
    $tamperedSmokeContract = Get-CommunityTtlWriterContract `
        -RepositoryRoot $temporaryRoot
    Assert-Test (
        $tamperedSmokeContract.sha256 -cne $fixtureContract.sha256
    ) "tamper dello smoke invalida il digest"
    & git -C $temporaryRoot update-index --skip-worktree `
        backend/tools/smoke_community_moderation_live.py
    Assert-Test ($LASTEXITCODE -eq 0) "imposta skip-worktree"
    $hiddenSmokeStatus = (& git -C $temporaryRoot status --porcelain -- `
        backend/tools/smoke_community_moderation_live.py | Out-String).Trim()
    Assert-Test (-not $hiddenSmokeStatus) (
        "git status non vede il tamper skip-worktree"
    )
    Assert-ThrowsLike {
        New-FirestoreCommunityTtlHistoricalEvidence `
            -Audit $audit `
            -RepositoryRoot $temporaryRoot `
            -SourceCommit $sourceCommit `
            -RecordedAtUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_source_commit_writer_contract_mismatch"
    & git -C $temporaryRoot update-index --no-skip-worktree `
        backend/tools/smoke_community_moderation_live.py
    Assert-Test ($LASTEXITCODE -eq 0) "rimuove skip-worktree"
    [IO.File]::WriteAllBytes($smokeWriter, $smokeWriterOriginal)
    $changedWriter = Join-Path $temporaryRoot (
        "backend\app\repositories\community.py"
    )
    [IO.File]::AppendAllText(
        $changedWriter,
        "`n# contract-test-writer-change`n",
        [Text.UTF8Encoding]::new($false)
    )
    $changedContract = Get-CommunityTtlWriterContract `
        -RepositoryRoot $temporaryRoot
    Assert-Test ($changedContract.sha256 -cne $fixtureContract.sha256) (
        "qualsiasi modifica writer invalida il digest"
    )
    Assert-ThrowsLike {
        New-FirestoreCommunityTtlHistoricalEvidence `
            -Audit $audit `
            -RepositoryRoot $temporaryRoot `
            -SourceCommit $sourceCommit `
            -RecordedAtUtc $recordedAt | Out-Null
    } "community_ttl_historical_evidence_source_commit_writer_contract_mismatch"

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

$recorderSource = Get-Content -LiteralPath $recorderScript -Raw
Assert-Test ($recorderSource.Contains('[switch]$RecordLiveEvidence')) (
    "recorder richiede conferma esplicita"
)
Assert-Test ($recorderSource.Contains('[string]$SourceCommit')) (
    "recorder richiede commit backend sorgente"
)
Assert-Test ($recorderSource.Contains('[IO.FileMode]::CreateNew')) (
    "recorder non sovrascrive"
)
Assert-Test (-not $recorderSource.Contains('SnapshotFixturePath')) (
    "recorder operativo non espone un parametro fixture"
)
Assert-Test (
    $recorderSource.Contains('"logging", "write", "meteofriul-community-ttl-evidence"')
) (
    "recorder scrive l'attestation remota con argomenti separati"
)
Assert-Test ($recorderSource.Contains('[Diagnostics.ProcessStartInfo]::new()')) (
    "recorder deve evitare il quoting JSON del wrapper gcloud.cmd"
)
Assert-Test ($recorderSource.Contains('$startInfo.ArgumentList.Add($argument)')) (
    "recorder deve passare ogni argomento gcloud senza ricomporre una shell string"
)
Assert-Test (-not $recorderSource.Contains('& $gcloud logging write')) (
    "recorder non deve inviare JSON direttamente attraverso gcloud.cmd"
)
Assert-Test ($recorderSource.Contains('Read-CommunityTtlCloudAttestationLive')) (
    "recorder fa read-back dell'attestation remota"
)

Write-Host "Firestore community TTL historical evidence contract tests: OK"
