Set-StrictMode -Version Latest

function Get-NormalizedReleaseApiBase {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $candidate = $Value.Trim()
    $uri = $null
    if (-not [Uri]::TryCreate($candidate, [UriKind]::Absolute, [ref]$uri)) {
        throw "release_api_base_must_be_absolute_https"
    }

    $separatorIndex = $uri.DnsSafeHost.IndexOf("---", [StringComparison]::Ordinal)
    $tag = if ($separatorIndex -gt 0) {
        $uri.DnsSafeHost.Substring(0, $separatorIndex)
    } else {
        ""
    }
    $serviceHostPrefix = "$tag---$ServiceName-"

    if (
        $uri.Scheme -cne "https" -or
        $uri.UserInfo -or
        $uri.Port -ne 443 -or
        $uri.Query -or
        $uri.Fragment -or
        $uri.AbsolutePath.TrimEnd('/') -cne "/api" -or
        $uri.DnsSafeHost -notmatch '^[a-z0-9-]+---[a-z0-9-]+-[a-z0-9]+\.a\.run\.app$' -or
        -not $tag -or
        -not $uri.DnsSafeHost.StartsWith($serviceHostPrefix, [StringComparison]::Ordinal)
    ) {
        throw "release_api_base_must_match_tagged_cloud_run_service"
    }

    return "https://$($uri.DnsSafeHost)/api"
}

function Get-ReleaseApiTag {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ApiBase,

        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $normalized = Get-NormalizedReleaseApiBase -Value $ApiBase -ServiceName $ServiceName
    $hostName = ([Uri]$normalized).DnsSafeHost
    return $hostName.Substring(0, $hostName.IndexOf("---", [StringComparison]::Ordinal))
}

function Get-ObjectPropertyValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Assert-ReleaseHealthPayload {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Payload
    )

    $status = [string](Get-ObjectPropertyValue -InputObject $Payload -Name "status")
    if ($status -cne "ok") {
        throw "release_api_health_not_ok: status=$status"
    }

    return "ok"
}

function Assert-ReleaseBackendImageEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$EvidencePath,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedBackendCommit,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedImageDigest
    )

    $resolvedPath = [IO.Path]::GetFullPath($EvidencePath)
    if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
        throw "release_backend_evidence_not_found: $resolvedPath"
    }
    try {
        $evidence = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json
    } catch {
        throw "release_backend_evidence_invalid_json: $resolvedPath"
    }

    $sourceCommit = ([string](
        Get-ObjectPropertyValue -InputObject $evidence -Name "sourceCommit"
    )).Trim().ToLowerInvariant()
    $recordedExpectedDigest = ([string](
        Get-ObjectPropertyValue -InputObject $evidence -Name "expectedImageDigest"
    )).Trim()
    $resultDigest = ([string](
        Get-ObjectPropertyValue -InputObject $evidence -Name "cloudBuildResultImageDigest"
    )).Trim()
    $buildStatus = ([string](
        Get-ObjectPropertyValue -InputObject $evidence -Name "cloudBuildStatus"
    )).Trim().ToUpperInvariant()
    $expectedCommit = $ExpectedBackendCommit.Trim().ToLowerInvariant()
    $expectedDigest = $ExpectedImageDigest.Trim()

    if ($sourceCommit -cne $expectedCommit) {
        throw "release_backend_evidence_commit_mismatch"
    }
    if (
        $expectedDigest -notmatch '@sha256:[0-9a-f]{64}$' -or
        $recordedExpectedDigest -cne $expectedDigest -or
        $resultDigest -cne $expectedDigest
    ) {
        throw "release_backend_evidence_digest_mismatch"
    }
    if ($buildStatus -cne "SUCCESS") {
        throw "release_backend_evidence_build_not_successful"
    }

    return [PSCustomObject]@{
        EvidencePath = $resolvedPath
        ImageDigest = $expectedDigest
        SourceCommit = $expectedCommit
    }
}

function Assert-CloudRunReleaseState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ApiBase,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedRevision,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedBackendCommit,

        [Parameter(Mandatory = $true)]
        [string]$ServiceName,

        [Parameter(Mandatory = $true)]
        [object]$ServiceDescription,

        [Parameter(Mandatory = $true)]
        [object]$RevisionDescription,

        [string]$ExpectedImageDigest,

        [switch]$BackendCommitBoundByEvidence
    )

    $normalizedApiBase = Get-NormalizedReleaseApiBase -Value $ApiBase -ServiceName $ServiceName
    $tag = Get-ReleaseApiTag -ApiBase $normalizedApiBase -ServiceName $ServiceName
    $revision = $ExpectedRevision.Trim().ToLowerInvariant()
    $backendCommit = $ExpectedBackendCommit.Trim().ToLowerInvariant()

    if ($revision -notmatch '^[a-z][a-z0-9-]{1,62}$' -or -not $revision.StartsWith("$ServiceName-")) {
        throw "release_expected_revision_invalid: $revision"
    }
    if ($backendCommit -notmatch '^[0-9a-f]{7,40}$') {
        throw "release_expected_backend_commit_invalid"
    }

    $shortBackendCommit = $backendCommit.Substring(0, 7)
    $revisionIdentifiesCommit = $false
    $commitTokens = [regex]::Matches(
        $revision, "(?:^|-)([0-9a-f]{7,40})(?=-|$)"
    )
    foreach ($match in $commitTokens) {
        $token = $match.Groups[1].Value
        if ($backendCommit.StartsWith($token, [StringComparison]::Ordinal)) {
            $revisionIdentifiesCommit = $true
            break
        }
    }
    if (-not $revisionIdentifiesCommit -and -not $BackendCommitBoundByEvidence) {
        throw "release_revision_does_not_identify_backend_commit: revision=$revision commit=$shortBackendCommit"
    }
    if (-not $revisionIdentifiesCommit -and -not $ExpectedImageDigest) {
        throw "release_backend_evidence_digest_required"
    }

    $actualServiceName = [string](Get-ObjectPropertyValue -InputObject $ServiceDescription.metadata -Name "name")
    if ($actualServiceName -cne $ServiceName) {
        throw "release_cloud_run_service_mismatch: expected=$ServiceName actual=$actualServiceName"
    }

    $traffic = @(Get-ObjectPropertyValue -InputObject $ServiceDescription.status -Name "traffic")
    $tagMatches = @(
        $traffic | Where-Object {
            [string](Get-ObjectPropertyValue -InputObject $_ -Name "tag") -ceq $tag
        }
    )
    if ($tagMatches.Count -ne 1) {
        throw "release_api_tag_resolution_invalid: tag=$tag matches=$($tagMatches.Count)"
    }

    $tagEntry = $tagMatches[0]
    $actualRevision = [string](Get-ObjectPropertyValue -InputObject $tagEntry -Name "revisionName")
    if ($actualRevision -cne $revision) {
        throw "release_api_tag_revision_mismatch: tag=$tag expected=$revision actual=$actualRevision"
    }

    $tagUrl = [string](Get-ObjectPropertyValue -InputObject $tagEntry -Name "url")
    try {
        $resolvedApiBase = Get-NormalizedReleaseApiBase `
            -Value ($tagUrl.TrimEnd('/') + "/api") `
            -ServiceName $ServiceName
    } catch {
        throw "release_api_tag_url_invalid: tag=$tag"
    }
    if ($resolvedApiBase -cne $normalizedApiBase) {
        throw "release_api_tag_url_mismatch: expected=$normalizedApiBase actual=$resolvedApiBase"
    }

    $describedRevision = [string](Get-ObjectPropertyValue -InputObject $RevisionDescription.metadata -Name "name")
    if ($describedRevision -cne $revision) {
        throw "release_revision_description_mismatch: expected=$revision actual=$describedRevision"
    }

    $revisionLabels = Get-ObjectPropertyValue -InputObject $RevisionDescription.metadata -Name "labels"
    $revisionService = [string](Get-ObjectPropertyValue -InputObject $revisionLabels -Name "serving.knative.dev/service")
    if ($revisionService -cne $ServiceName) {
        throw "release_revision_service_mismatch: expected=$ServiceName actual=$revisionService"
    }

    $conditions = @(Get-ObjectPropertyValue -InputObject $RevisionDescription.status -Name "conditions")
    $ready = @(
        $conditions | Where-Object {
            [string](Get-ObjectPropertyValue -InputObject $_ -Name "type") -ceq "Ready" -and
            [string](Get-ObjectPropertyValue -InputObject $_ -Name "status") -ceq "True"
        }
    )
    if ($ready.Count -ne 1) {
        throw "release_revision_not_ready: revision=$revision"
    }

    $imageDigest = [string](Get-ObjectPropertyValue -InputObject $RevisionDescription.status -Name "imageDigest")
    if (-not $imageDigest -or $imageDigest -notmatch '@sha256:[0-9a-f]{64}$') {
        throw "release_revision_image_digest_missing: revision=$revision"
    }
    if ($ExpectedImageDigest -and $imageDigest -cne $ExpectedImageDigest.Trim()) {
        throw "release_revision_image_digest_mismatch: revision=$revision"
    }

    return [PSCustomObject]@{
        ApiBase = $normalizedApiBase
        ApiTag = $tag
        BackendCommit = $backendCommit
        ImageDigest = $imageDigest
        CommitBinding = if ($revisionIdentifiesCommit) {
            "revision-name"
        } else {
            "verified-image-evidence"
        }
        Revision = $revision
        Service = $ServiceName
    }
}

function Resolve-MeteoFriulGcloudPath {
    [CmdletBinding()]
    param([string]$GcloudPath)

    if ($GcloudPath) {
        $resolved = [IO.Path]::GetFullPath($GcloudPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "release_gcloud_not_found: $resolved"
        }
        return $resolved
    }

    foreach ($commandName in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    if ($env:LOCALAPPDATA) {
        $bundledPath = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
        if (Test-Path -LiteralPath $bundledPath -PathType Leaf) {
            return $bundledPath
        }
    }

    throw "release_gcloud_not_found"
}

function Invoke-GcloudJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$GcloudPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [string]$FailureCode
    )

    $rawOutput = (& $GcloudPath @Arguments 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "${FailureCode}: gcloud_exit=$LASTEXITCODE"
    }

    $jsonStart = $rawOutput.IndexOf('{')
    if ($jsonStart -lt 0) {
        throw "${FailureCode}: invalid_json"
    }

    try {
        return $rawOutput.Substring($jsonStart) | ConvertFrom-Json
    } catch {
        throw "${FailureCode}: invalid_json"
    }
}

function Assert-ReleaseGitState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $dirty = & git -C $RepositoryRoot status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "release_git_status_failed"
    }
    if ($dirty) {
        throw "release_git_worktree_not_clean"
    }

    $head = (& git -C $RepositoryRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') {
        throw "release_git_head_invalid"
    }

    $upstream = (& git -C $RepositoryRoot rev-parse '@{u}' 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $upstream -notmatch '^[0-9a-f]{40}$') {
        throw "release_git_upstream_missing"
    }
    if ($head -cne $upstream) {
        throw "release_git_head_not_pushed: head=$head upstream=$upstream"
    }

    return [PSCustomObject]@{
        Commit = $head
        UpstreamCommit = $upstream
    }
}

function Assert-AndroidReleaseVersionHistory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$CandidateVersionCode,

        [Parameter(Mandatory = $true)]
        [string]$CandidateVersionName,

        [object[]]$ExistingReleases = @()
    )

    $candidateName = $CandidateVersionName.Trim()
    if ($CandidateVersionCode -le 0 -or -not $candidateName) {
        throw "release_android_candidate_version_invalid"
    }

    $normalizedReleases = @()
    foreach ($release in @($ExistingReleases)) {
        $existingCodeText = [string](Get-ObjectPropertyValue -InputObject $release -Name "VersionCode")
        $existingName = ([string](Get-ObjectPropertyValue -InputObject $release -Name "VersionName")).Trim()
        $existingPath = [string](Get-ObjectPropertyValue -InputObject $release -Name "Path")
        $existingCode = 0
        if (-not [int]::TryParse($existingCodeText, [ref]$existingCode) -or $existingCode -le 0 -or -not $existingName) {
            throw "release_android_existing_artifact_invalid: path=$existingPath"
        }

        $retryableName = Get-ObjectPropertyValue -InputObject $release -Name "RetryableVersionName"
        $canRetryName = $retryableName -is [bool] -and $retryableName -eq $true
        if ($existingCode -eq $CandidateVersionCode -or
            ($existingName -eq $candidateName -and -not $canRetryName)) {
            throw "release_android_version_already_exists: versionCode=$CandidateVersionCode versionName=$candidateName path=$existingPath"
        }

        $normalizedReleases += [PSCustomObject]@{
            CertificateSha256 = [string](Get-ObjectPropertyValue -InputObject $release -Name "CertificateSha256")
            Path = $existingPath
            VersionCode = $existingCode
            VersionName = $existingName
        }
    }

    $latest = $normalizedReleases | Sort-Object VersionCode -Descending | Select-Object -First 1
    if ($latest -and $CandidateVersionCode -le $latest.VersionCode) {
        throw "release_android_version_not_incremented: candidate=$CandidateVersionCode latest=$($latest.VersionCode) path=$($latest.Path)"
    }

    return [PSCustomObject]@{
        CandidateVersionCode = $CandidateVersionCode
        CandidateVersionName = $candidateName
        ExistingCount = $normalizedReleases.Count
        LatestRelease = $latest
    }
}

function Assert-AndroidReleaseSigningHistory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidateCertificateSha256,

        [object[]]$ExistingReleases = @()
    )

    $candidateCertificate = $CandidateCertificateSha256.Trim()
    if (-not $candidateCertificate) {
        throw "release_android_candidate_certificate_invalid"
    }

    foreach ($release in @($ExistingReleases)) {
        $existingCertificate = ([string](
            Get-ObjectPropertyValue -InputObject $release -Name "CertificateSha256"
        )).Trim()
        $existingPath = [string](Get-ObjectPropertyValue -InputObject $release -Name "Path")
        if (-not $existingCertificate) {
            throw "release_android_existing_artifact_invalid: path=$existingPath"
        }
        if ($existingCertificate -ne $candidateCertificate) {
            throw "release_android_signing_certificate_changed: path=$existingPath"
        }
    }

    return [PSCustomObject]@{
        CandidateCertificateSha256 = $candidateCertificate
        ExistingCount = @($ExistingReleases).Count
    }
}

function Invoke-ReleaseApiPreflight {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ApiBase,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedRevision,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedBackendCommit,

        [string]$ProjectId = "meteo-friul",

        [string]$Region = "europe-west1",

        [string]$ServiceName = "meteofriul-api",

        [string]$ExpectedAccount = "meteofriul@gmail.com",

        [string]$GcloudPath,

        [string]$ExpectedImageDigest,

        [string]$BackendEvidencePath
    )

    $backendEvidence = $null
    if ($ExpectedImageDigest -or $BackendEvidencePath) {
        if (-not $ExpectedImageDigest -or -not $BackendEvidencePath) {
            throw "release_backend_evidence_arguments_incomplete"
        }
        $backendEvidence = Assert-ReleaseBackendImageEvidence `
            -EvidencePath $BackendEvidencePath `
            -ExpectedBackendCommit $ExpectedBackendCommit `
            -ExpectedImageDigest $ExpectedImageDigest
    }

    $resolvedGcloud = Resolve-MeteoFriulGcloudPath -GcloudPath $GcloudPath
    $accountOutput = (& $resolvedGcloud config get-value account --quiet 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "release_gcloud_account_check_failed"
    }
    $accountLines = @($accountOutput -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($ExpectedAccount -notin $accountLines) {
        throw "release_gcloud_account_mismatch: expected=$ExpectedAccount"
    }

    $serviceDescription = Invoke-GcloudJson -GcloudPath $resolvedGcloud -Arguments @(
        "run", "services", "describe", $ServiceName,
        "--project", $ProjectId,
        "--region", $Region,
        "--format=json",
        "--quiet"
    ) -FailureCode "release_cloud_run_service_describe_failed"

    $revisionDescription = Invoke-GcloudJson -GcloudPath $resolvedGcloud -Arguments @(
        "run", "revisions", "describe", $ExpectedRevision,
        "--project", $ProjectId,
        "--region", $Region,
        "--format=json",
        "--quiet"
    ) -FailureCode "release_cloud_run_revision_describe_failed"

    $state = Assert-CloudRunReleaseState `
        -ApiBase $ApiBase `
        -ExpectedRevision $ExpectedRevision `
        -ExpectedBackendCommit $ExpectedBackendCommit `
        -ServiceName $ServiceName `
        -ServiceDescription $serviceDescription `
        -RevisionDescription $revisionDescription `
        -ExpectedImageDigest $ExpectedImageDigest `
        -BackendCommitBoundByEvidence:($null -ne $backendEvidence)

    try {
        $healthPayload = Invoke-RestMethod `
            -Uri ($state.ApiBase + "/healthz") `
            -Method Get `
            -TimeoutSec 15 `
            -Headers @{ "User-Agent" = "Meteo-Friul-Release-Preflight/1.0" }
    } catch {
        throw "release_api_health_request_failed: tag=$($state.ApiTag)"
    }
    $health = Assert-ReleaseHealthPayload -Payload $healthPayload

    return [PSCustomObject]@{
        Account = $ExpectedAccount
        ApiBase = $state.ApiBase
        ApiTag = $state.ApiTag
        BackendCommit = $state.BackendCommit
        BackendCommitBinding = $state.CommitBinding
        BackendEvidencePath = if ($backendEvidence) {
            $backendEvidence.EvidencePath
        } else {
            ""
        }
        Health = $health
        ImageDigest = $state.ImageDigest
        ProjectId = $ProjectId
        Region = $Region
        Revision = $state.Revision
        Service = $state.Service
    }
}

Export-ModuleMember -Function @(
    "Assert-AndroidReleaseSigningHistory",
    "Assert-AndroidReleaseVersionHistory",
    "Assert-CloudRunReleaseState",
    "Assert-ReleaseGitState",
    "Assert-ReleaseHealthPayload",
    "Assert-ReleaseBackendImageEvidence",
    "Get-NormalizedReleaseApiBase",
    "Get-ReleaseApiTag",
    "Invoke-ReleaseApiPreflight",
    "Resolve-MeteoFriulGcloudPath"
)
