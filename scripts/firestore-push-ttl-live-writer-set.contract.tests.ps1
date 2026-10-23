$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "firestore-push-ttl-audit.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "firestore-push-ttl-live-writer-set.psm1") -Force

function Assert-Case {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Live writer set contract test failed: $Message" }
}

function Copy-Case {
    param([object]$Value)
    return ($Value | ConvertTo-Json -Depth 30 | ConvertFrom-Json)
}

$root = Split-Path -Parent $PSScriptRoot
foreach ($contractName in @("play-0.1.13-20261009.json", "play-services-notices-20261023.json")) {
    $contractPath = Join-Path $root "release-history\firestore-ttl\runtime-writer-sets\$contractName"
    $contract = Get-Content -LiteralPath $contractPath -Raw | ConvertFrom-Json
    $specs = @(Get-FirestorePushTtlScheduledWriterTargets)
    Assert-Case ($specs.Count -eq 4) "four scheduled writers required"
    Assert-Case ($specs[0].jobRegion -ceq "europe-west8") "official alert target must be europe-west8"
    $gitStatus = [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 1 }
    $sourceStatus = [PSCustomObject]@{
        tracked = $true
        clean = $true
        sourceCommitExists = $true
        matchesSourceCommit = $true
    }
    $inventory = [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-runtime-writers-v2"
        projectId = "meteo-friul"
        serviceRegion = "europe-west1"
        releaseApiTag = "play-b6fbe4d"
        service = [PSCustomObject]@{
            name = "meteofriul-api"
            traffic = @(
                [PSCustomObject]@{ revisionName = "api-default"; percent = 100; tag = "" },
                [PSCustomObject]@{ revisionName = "api-release"; percent = $null; tag = "play-b6fbe4d" }
            )
            revisions = @(
                [PSCustomObject]@{ name = "api-default"; ready = $true; imageDigest = $contract.targets.serviceDefault },
                [PSCustomObject]@{ name = "api-release"; ready = $true; imageDigest = $contract.targets.releaseApi }
            )
        }
        jobs = @($specs | ForEach-Object {
            $spec = $_
            $target = @($contract.targets.jobs | Where-Object { $_.name -ceq $spec.name })[0]
            [PSCustomObject]@{
                name = $spec.name
                region = $spec.jobRegion
                ready = $true
                imageDigest = $target.imageDigest
                scheduler = [PSCustomObject]@{
                    name = $spec.name
                    region = "europe-west1"
                    state = "ENABLED"
                    schedule = $spec.schedule
                    timeZone = "Europe/Rome"
                    targetUri = "https://run.googleapis.com/v2/projects/meteo-friul/locations/$($spec.jobRegion)/jobs/$($spec.name):run"
                }
            }
        })
    }
    $proofs = @($contract.images | ForEach-Object {
        [PSCustomObject]@{
            imageDigest = $_.imageDigest
            buildVerification = [PSCustomObject]@{
                schemaVersion = "firestore-push-ttl-cloud-build-verification-v1"
                id = $_.cloudBuildId
                region = $_.cloudBuildRegion
                status = "SUCCESS"
                canonicalImageDigests = @($_.imageDigest)
                sourceArchiveSha256Base64 = $_.cloudBuildSourceArchiveSha256Base64
            }
            pushRepositoryGitStatus = $sourceStatus
        }
    })
    $good = @{
        Inventory = $inventory
        Contract = $contract
        ContractGitStatus = $gitStatus
        ImageProofs = $proofs
        PushRepositorySha256 = $contract.pushRepositorySha256
        ExpectedJobs = $specs
        ExpectedReleaseApiTag = "play-b6fbe4d"
    }
    $findings = @(Test-FirestorePushTtlLiveWriterSet @good)
    Assert-Case ($findings.Count -eq 0) "fully attested distinct images must pass"

    $sourcePath = Join-Path $root "backend\app\repositories\push.py"
    $policyFixture = Get-Content -LiteralPath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-active.json") -Raw | ConvertFrom-Json
    $activePolicies = @()
    foreach ($policy in $policyFixture) { $activePolicies += $policy }
    $integrated = Test-FirestorePushTtlState `
        -TtlPolicies $activePolicies `
        -PushRepositorySource (Get-Content -LiteralPath $sourcePath -Raw) `
        -PushRepositorySha256 ((Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()) `
        -CurrentReadback (Get-Content -LiteralPath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-readback-clean.json") -Raw | ConvertFrom-Json) `
        -HistoricalEvidence (Get-Content -LiteralPath (Join-Path $PSScriptRoot "fixtures\firestore-push-ttl-history-complete.json") -Raw | ConvertFrom-Json) `
        -EvidenceGitStatus $gitStatus `
        -RuntimeWriters $inventory `
        -RuntimeWriterSetContract $contract `
        -RuntimeWriterSetGitStatus $gitStatus `
        -RuntimeWriterSetProofs $proofs `
        -ExpectedReleaseApiTag "play-b6fbe4d"
    Assert-Case ($integrated.ready -eq $true) ("main TTL gate must dispatch the attested live writer set: " + (@($integrated.findings | ForEach-Object { $_.code }) -join ","))
    Assert-Case ($integrated.semantics.runtimeWriterEachDigestAttestedRequired -eq $true) "v2 gate must require every digest proof"

    $wrong = Copy-Case $inventory
    $wrong.jobs[0].scheduler.targetUri = $wrong.jobs[0].scheduler.targetUri.Replace("europe-west8", "europe-west1")
    $case = $good.Clone(); $case.Inventory = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_scheduler_target_mismatch" }).Count -gt 0) "wrong Scheduler target must fail"

    $wrong = Copy-Case $inventory
    $wrong.jobs[1].scheduler.state = "PAUSED"
    $case = $good.Clone(); $case.Inventory = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_scheduler_target_mismatch" }).Count -gt 0) "paused Scheduler must fail"

    $wrong = Copy-Case $inventory
    $wrong.service.traffic[1].tag = "wrong-play-tag"
    $case = $good.Clone(); $case.Inventory = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_release_tag_unresolved" }).Count -gt 0) "wrong release tag must fail"

    $wrong = Copy-Case $inventory
    $wrong.jobs[2].imageDigest = "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    $case = $good.Clone(); $case.Inventory = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_digest_mismatch" }).Count -gt 0) "unattested job image must fail"

    $wrong = Copy-Case $contract
    $wrong.images[1].sourceArchivePushRepositorySha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    $case = $good.Clone(); $case.Contract = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_image_attestation_invalid" }).Count -gt 0) "wrong archived writer source must fail"

    $wrong = Copy-Case $proofs
    $wrong[2].buildVerification.canonicalImageDigests = @("europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
    $case = $good.Clone(); $case.ImageProofs = $wrong
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_build_verification_mismatch" }).Count -gt 0) "wrong Cloud Build digest must fail"

    # One attested build can emit a candidate and its compatible rollback.
    $multi = Copy-Case $proofs
    $otherDigest = "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    $multi[2].buildVerification.canonicalImageDigests = @($otherDigest, $proofs[2].imageDigest)
    $case = $good.Clone(); $case.ImageProofs = $multi
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case).Count -eq 0) "multi-image build must attest the exact deployed digest regardless of result order"

    $missing = Copy-Case $multi
    $missing[2].buildVerification.canonicalImageDigests = @($otherDigest, "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    $case = $good.Clone(); $case.ImageProofs = $missing
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_build_verification_mismatch" }).Count -gt 0) "multiple images without the deployed digest must fail"

    $wrongArchive = Copy-Case $multi
    $wrongArchive[2].buildVerification.sourceArchiveSha256Base64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    $case = $good.Clone(); $case.ImageProofs = $wrongArchive
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_build_verification_mismatch" }).Count -gt 0) "multi-image build with wrong source archive must still fail"

    $case = $good.Clone(); $case.ContractGitStatus = [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 2 }
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_set_contract_not_immutable" }).Count -gt 0) "rewritten contract must fail"

    $case = $good.Clone(); $case.ImageProofs = @($proofs | Select-Object -Skip 1)
    Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_image_proof_missing" }).Count -gt 0) "missing image proof must fail"

}

$staleContract = Get-Content -LiteralPath (Join-Path $root "release-history\firestore-ttl\runtime-writer-sets\play-services-fvg-20261020.json") -Raw | ConvertFrom-Json
$case = $good.Clone(); $case.Contract = $staleContract
Assert-Case (@(Test-FirestorePushTtlLiveWriterSet @case | Where-Object { $_.code -ceq "runtime_writer_digest_mismatch" }).Count -gt 0) "old attestation must reject the updated local notice image"

$buildSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot "build-play-aab.ps1") -Raw
Assert-Case $buildSource.Contains('Get-ReleaseApiTag -ApiBase $normalizedApiBase') "AAB gate must receive actual release tag"

Write-Host "Firestore push TTL live writer set contract tests: OK"
