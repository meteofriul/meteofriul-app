$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$modulePath = Join-Path $PSScriptRoot "release-api-preflight.psm1"
Import-Module $modulePath -Force

$serviceName = "meteofriul-api"
$revisionName = "meteofriul-api-eventsfix-ffa0514"
$backendCommit = "ffa051493f3d7e990ffbce8c799007278c04d3c3"
$apiBase = "https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api"
$tagUrl = "https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app"
$imageDigest = (
    "europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/" +
    "meteofriul-api@sha256:" + ("a" * 64)
)

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Equal {
    param([object]$Actual, [object]$Expected, [string]$Message)
    if ([string]$Actual -cne [string]$Expected) {
        throw "$Message Expected=[$Expected] Actual=[$Actual]"
    }
}

function Assert-ThrowsLike {
    param(
        [scriptblock]$Action,
        [string]$Pattern,
        [string]$Message
    )

    $matched = $false
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -like $Pattern) {
            $matched = $true
        } else {
            throw "$Message Unexpected=[$($_.Exception.Message)]"
        }
    }

    if (-not $matched) {
        throw "$Message No exception was raised."
    }
}

function New-ServiceDescription {
    param(
        [string]$Revision = $revisionName,
        [string]$ResolvedTagUrl = $tagUrl,
        [string]$Tag = "cfweb-bcee09e",
        [string]$Name = $serviceName
    )

    return [PSCustomObject]@{
        metadata = [PSCustomObject]@{ name = $Name }
        status = [PSCustomObject]@{
            traffic = @(
                [PSCustomObject]@{
                    percent = 100
                    revisionName = $Revision
                    tag = "eventsfix-ffa0514"
                    url = "https://eventsfix-ffa0514---meteofriul-api-bx24xqvcda-ew.a.run.app"
                },
                [PSCustomObject]@{
                    revisionName = $Revision
                    tag = $Tag
                    url = $ResolvedTagUrl
                }
            )
        }
    }
}

function New-RevisionDescription {
    param(
        [string]$Name = $revisionName,
        [string]$Service = $serviceName,
        [string]$ReadyStatus = "True",
        [string]$Digest = $imageDigest
    )

    $description = [PSCustomObject]@{
        metadata = [PSCustomObject]@{
            name = $Name
            labels = @{
                "serving.knative.dev/service" = $Service
            }
        }
        status = [PSCustomObject]@{
            conditions = @(
                [PSCustomObject]@{
                    status = $ReadyStatus
                    type = "Ready"
                }
            )
            imageDigest = $Digest
        }
    }

    return ($description | ConvertTo-Json -Depth 8 | ConvertFrom-Json)
}

$state = Assert-CloudRunReleaseState `
    -ApiBase $apiBase `
    -ExpectedRevision $revisionName `
    -ExpectedBackendCommit $backendCommit `
    -ServiceName $serviceName `
    -ServiceDescription (New-ServiceDescription) `
    -RevisionDescription (New-RevisionDescription)

Assert-Equal $state.ApiBase $apiBase "ApiBase normalizzata errata."
Assert-Equal $state.ApiTag "cfweb-bcee09e" "Tag estratto errato."
Assert-Equal $state.Revision $revisionName "Revisione verificata errata."
Assert-Equal $state.BackendCommit $backendCommit "Commit backend registrato errato."
Assert-Equal $state.ImageDigest $imageDigest "Digest immagine errato."
Assert-Equal (Assert-ReleaseHealthPayload -Payload ([PSCustomObject]@{ status = "ok" })) "ok" "Health valida respinta."

$eightCharRevision = "meteofriul-api-natistat-da3e711d"
$eightCharCommit = "da3e711de85dfd4c7799e0a2a8465b9ce576d2fd"
$eightCharArgs = @{
    ApiBase = $apiBase
    ExpectedRevision = $eightCharRevision
    ExpectedBackendCommit = $eightCharCommit
    ServiceName = $serviceName
    ServiceDescription = (New-ServiceDescription -Revision $eightCharRevision)
    RevisionDescription = (New-RevisionDescription -Name $eightCharRevision)
}
$eightCharState = Assert-CloudRunReleaseState @eightCharArgs
Assert-Equal $eightCharState.CommitBinding "revision-name" "Prefisso commit a 8 caratteri respinto."

$wrongEighthCharArgs = $eightCharArgs.Clone()
$wrongEighthCharArgs.ExpectedBackendCommit = "da3e7110e85dfd4c7799e0a2a8465b9ce576d2fd"
Assert-ThrowsLike -Pattern "release_revision_does_not_identify_backend_commit*" -Message "Ottavo carattere incoerente accettato." -Action {
    Assert-CloudRunReleaseState @wrongEighthCharArgs
}

$tooShortCommitArgs = $eightCharArgs.Clone()
$tooShortCommitArgs.ExpectedBackendCommit = "da3e711"
Assert-ThrowsLike -Pattern "release_revision_does_not_identify_backend_commit*" -Message "Commit atteso più corto del token revisione accettato." -Action {
    Assert-CloudRunReleaseState @tooShortCommitArgs
}

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$runtimeEvidencePath = Join-Path $workspaceRoot (
    "release-history\firestore-ttl\runtime-writer-images\" +
    "beab6438c164af521853d8c99b31a1de10f0c5211ee493fb649d730a192d4c95.json"
)
$runtimeCommit = "ca201f081c343f6d709141cfd311190c5c93a140"
$runtimeDigest = (
    "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:" +
    "beab6438c164af521853d8c99b31a1de10f0c5211ee493fb649d730a192d4c95"
)
$runtimeEvidence = Assert-ReleaseBackendImageEvidence `
    -EvidencePath $runtimeEvidencePath `
    -ExpectedBackendCommit $runtimeCommit `
    -ExpectedImageDigest $runtimeDigest
Assert-Equal $runtimeEvidence.SourceCommit $runtimeCommit "Commit evidenza backend errato."
Assert-Equal $runtimeEvidence.ImageDigest $runtimeDigest "Digest evidenza backend errato."

$configurationRevision = "meteofriul-api-push014-0927"
$configurationState = Assert-CloudRunReleaseState `
    -ApiBase $apiBase `
    -ExpectedRevision $configurationRevision `
    -ExpectedBackendCommit $runtimeCommit `
    -ExpectedImageDigest $runtimeDigest `
    -BackendCommitBoundByEvidence `
    -ServiceName $serviceName `
    -ServiceDescription (New-ServiceDescription -Revision $configurationRevision) `
    -RevisionDescription (New-RevisionDescription -Name $configurationRevision -Digest $runtimeDigest)
Assert-Equal $configurationState.CommitBinding "verified-image-evidence" "Binding evidenza non registrato."

Assert-ThrowsLike -Pattern "release_revision_does_not_identify_backend_commit*" -Message "Revisione di configurazione senza evidenza accettata." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $configurationRevision `
        -ExpectedBackendCommit $runtimeCommit `
        -ExpectedImageDigest $runtimeDigest `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription -Revision $configurationRevision) `
        -RevisionDescription (New-RevisionDescription -Name $configurationRevision -Digest $runtimeDigest)
}

Assert-ThrowsLike -Pattern "release_backend_evidence_digest_mismatch*" -Message "Evidenza con digest errato accettata." -Action {
    Assert-ReleaseBackendImageEvidence `
        -EvidencePath $runtimeEvidencePath `
        -ExpectedBackendCommit $runtimeCommit `
        -ExpectedImageDigest ($runtimeDigest -replace 'beab', 'dead')
}

Assert-ThrowsLike -Pattern "release_api_base_must_match_tagged_cloud_run_service*" -Message "Endpoint generico accettato." -Action {
    Get-NormalizedReleaseApiBase `
        -Value "https://meteofriul-api-bx24xqvcda-ew.a.run.app/api" `
        -ServiceName $serviceName
}

Assert-ThrowsLike -Pattern "release_api_tag_revision_mismatch*" -Message "Tag vecchio accettato." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit $backendCommit `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription -Revision "meteofriul-api-hourly-c6ca7a8") `
        -RevisionDescription (New-RevisionDescription)
}

Assert-ThrowsLike -Pattern "release_api_tag_resolution_invalid*" -Message "Tag mancante accettato." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit $backendCommit `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription -Tag "altro-tag") `
        -RevisionDescription (New-RevisionDescription)
}

Assert-ThrowsLike -Pattern "release_api_tag_url_mismatch*" -Message "URL risolto incoerente accettato." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit $backendCommit `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription -ResolvedTagUrl "https://altro-tag---meteofriul-api-bx24xqvcda-ew.a.run.app") `
        -RevisionDescription (New-RevisionDescription)
}

Assert-ThrowsLike -Pattern "release_revision_does_not_identify_backend_commit*" -Message "Commit backend incoerente accettato." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit "1234567890abcdef1234567890abcdef12345678" `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription) `
        -RevisionDescription (New-RevisionDescription)
}

Assert-ThrowsLike -Pattern "release_revision_not_ready*" -Message "Revisione non pronta accettata." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit $backendCommit `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription) `
        -RevisionDescription (New-RevisionDescription -ReadyStatus "False")
}

Assert-ThrowsLike -Pattern "release_revision_image_digest_missing*" -Message "Revisione senza digest accettata." -Action {
    Assert-CloudRunReleaseState `
        -ApiBase $apiBase `
        -ExpectedRevision $revisionName `
        -ExpectedBackendCommit $backendCommit `
        -ServiceName $serviceName `
        -ServiceDescription (New-ServiceDescription) `
        -RevisionDescription (New-RevisionDescription -Digest "")
}

Assert-ThrowsLike -Pattern "release_api_health_not_ok*" -Message "Health KO accettata." -Action {
    Assert-ReleaseHealthPayload -Payload ([PSCustomObject]@{ status = "degraded" })
}

$emptyVersionHistory = Assert-AndroidReleaseVersionHistory `
    -CandidateVersionCode 300010 `
    -CandidateVersionName "3.0.0-pilot.10-private.4"
Assert-Equal $emptyVersionHistory.ExistingCount 0 "Cronologia APK vuota interpretata male."

$existingAndroidReleases = @(
    [PSCustomObject]@{
        CertificateSha256 = "certificate-a"
        Path = "meteofriul-3.0.0-pilot.7-private.1.apk"
        VersionCode = 300007
        VersionName = "3.0.0-pilot.7-private.1"
    },
    [PSCustomObject]@{
        CertificateSha256 = "certificate-a"
        Path = "meteofriul-3.0.0-pilot.9-private.3.apk"
        VersionCode = 300009
        VersionName = "3.0.0-pilot.9-private.3"
    }
)
$incrementedVersionHistory = Assert-AndroidReleaseVersionHistory `
    -CandidateVersionCode 300010 `
    -CandidateVersionName "3.0.0-pilot.10-private.4" `
    -ExistingReleases $existingAndroidReleases
Assert-Equal $incrementedVersionHistory.ExistingCount 2 "Cronologia APK incompleta."
Assert-Equal $incrementedVersionHistory.LatestRelease.VersionCode 300009 "Ultima versione APK errata."

Assert-ThrowsLike -Pattern "release_android_version_already_exists*" -Message "versionCode Android riutilizzato accettato." -Action {
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode 300009 `
        -CandidateVersionName "3.0.0-pilot.10-private.4" `
        -ExistingReleases $existingAndroidReleases
}

Assert-ThrowsLike -Pattern "release_android_version_already_exists*" -Message "versionName Android riutilizzato accettato." -Action {
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode 300010 `
        -CandidateVersionName "3.0.0-PILOT.9-PRIVATE.3" `
        -ExistingReleases $existingAndroidReleases
}

Assert-ThrowsLike -Pattern "release_android_version_not_incremented*" -Message "versionCode Android arretrato accettato." -Action {
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode 300008 `
        -CandidateVersionName "3.0.0-pilot.8-private.2" `
        -ExistingReleases $existingAndroidReleases
}

Assert-ThrowsLike -Pattern "release_android_existing_artifact_invalid*" -Message "Artefatto Android senza metadati accettato." -Action {
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode 300010 `
        -CandidateVersionName "3.0.0-pilot.10-private.4" `
        -ExistingReleases @([PSCustomObject]@{ Path = "broken.apk"; VersionCode = ""; VersionName = "" })
}

$signingHistory = Assert-AndroidReleaseSigningHistory `
    -CandidateCertificateSha256 "CERTIFICATE-A" `
    -ExistingReleases $existingAndroidReleases
Assert-Equal $signingHistory.ExistingCount 2 "Cronologia firme APK incompleta."

Assert-ThrowsLike -Pattern "release_android_signing_certificate_changed*" -Message "Cambio firma Android accettato." -Action {
    Assert-AndroidReleaseSigningHistory `
        -CandidateCertificateSha256 "certificate-b" `
        -ExistingReleases $existingAndroidReleases
}

Assert-ThrowsLike -Pattern "release_android_candidate_certificate_invalid*" -Message "Firma Android candidata vuota accettata." -Action {
    Assert-AndroidReleaseSigningHistory `
        -CandidateCertificateSha256 " " `
        -ExistingReleases @()
}

$baselineManifestPath = Join-Path $workspaceRoot (
    "release-history\android-private-test\meteofriul-3.0.0-pilot.10-private.4.release.json"
)
$baselineManifest = Get-Content -LiteralPath $baselineManifestPath -Raw | ConvertFrom-Json
$baselineRelease = [PSCustomObject]@{
    CertificateSha256 = [string]$baselineManifest.CertificateSha256
    Path = $baselineManifestPath
    VersionCode = $baselineManifest.VersionCode
    VersionName = [string]$baselineManifest.VersionName
}
Assert-ThrowsLike -Pattern "release_android_version_already_exists*" -Message "Versione tester distribuita non riservata dal registro." -Action {
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode 300010 `
        -CandidateVersionName "3.0.0-pilot.10-private.4" `
        -ExistingReleases @($baselineRelease)
}
$nextBaselineVersion = Assert-AndroidReleaseVersionHistory `
    -CandidateVersionCode 300011 `
    -CandidateVersionName "3.0.0-pilot.11-private.5" `
    -ExistingReleases @($baselineRelease)
Assert-Equal $nextBaselineVersion.LatestRelease.VersionCode 300010 "Baseline tester non letta correttamente."
Assert-AndroidReleaseSigningHistory `
    -CandidateCertificateSha256 $baselineRelease.CertificateSha256 `
    -ExistingReleases @($baselineRelease) | Out-Null

$androidBuildScriptPath = Join-Path $PSScriptRoot "build-private-test-apk.ps1"
$androidBuildScriptSource = Get-Content -LiteralPath $androidBuildScriptPath -Raw
Assert-True `
    -Condition $androidBuildScriptSource.Contains('release-history\android-private-test') `
    -Message "Lo script APK non usa il registro permanente."
Assert-True `
    -Condition ($androidBuildScriptSource -notmatch '(?im)^\s*Copy-Item\b[^\r\n]*\s-Force(?:\s|$)') `
    -Message "Lo script APK contiene ancora una sovrascrittura forzata."

[PSCustomObject]@{
    CommitMismatch = "PASS"
    ConfigurationRevisionEvidence = "PASS"
    AndroidVersionHistory = "PASS"
    AndroidSigningHistory = "PASS"
    AndroidPersistentHistory = "PASS"
    AndroidNoForcedOverwrite = "PASS"
    HealthFailure = "PASS"
    InvalidApiBase = "PASS"
    MissingDigest = "PASS"
    MissingTag = "PASS"
    NotReady = "PASS"
    Result = "PASS"
    Success = "PASS"
    TagMismatch = "PASS"
    UrlMismatch = "PASS"
} | ConvertTo-Json -Compress
