[CmdletBinding()]
param(
    [string]$ProjectId = "meteo-friul",
    [string]$DatabaseId = "(default)",
    [string]$PolicyFixturePath = "",
    [string]$ReadbackFixturePath = "",
    [string]$HistoricalEvidencePath = "",
    [string]$RuntimeFixturePath = "",
    [string]$RuntimeWriterContractPath = "",
    [string]$RuntimeWriterSetContractPath = "",
    [string]$ReleaseApiTag = "play-b6fbe4d",
    [string]$RuntimeBuildFixturePath = "",
    [string]$PushRepositoryPath = "",
    [string]$GcloudPath = "",
    [switch]$PassThru
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "firestore-push-ttl-audit.psm1") -Force

function Resolve-GcloudExecutable {
    if ($GcloudPath) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) { throw "gcloud_not_found" }
        return (Resolve-Path -LiteralPath $GcloudPath).Path
    }
    $command = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    $fallback = Join-Path $env:LOCALAPPDATA "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) { throw "gcloud_not_found" }
    return $fallback
}

function Invoke-GcloudTtlList {
    $gcloud = Resolve-GcloudExecutable
    $arguments = @(
        "firestore", "fields", "ttls", "list",
        "--project=$ProjectId",
        "--database=$DatabaseId",
        "--format=json",
        "--quiet",
        "--verbosity=error"
    )
    $output = & $gcloud @arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gcloud_ttl_list_failed" }
    $text = [string]($output -join [Environment]::NewLine)
    try { return @($text | ConvertFrom-Json) }
    catch { throw "gcloud_ttl_list_invalid_json" }
}

function Invoke-GcloudJson {
    param([string[]]$Arguments, [string]$FailureCode)
    $gcloud = Resolve-GcloudExecutable
    $output = & $gcloud @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw $FailureCode }
    $text = [string]($output -join [Environment]::NewLine)
    try { return ($text | ConvertFrom-Json) }
    catch { throw "$FailureCode`_invalid_json" }
}

function Get-AuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-AuditNestedValue {
    param([object]$InputObject, [string[]]$Path)
    $current = $InputObject
    foreach ($segment in $Path) {
        $current = Get-AuditProperty -InputObject $current -Name $segment
        if ($null -eq $current) { return $null }
    }
    return $current
}

function Test-AuditReadyCondition {
    param([object]$Description)
    $conditions = @(Get-AuditNestedValue -InputObject $Description -Path @("status", "conditions"))
    $matches = @($conditions | Where-Object {
        [string](Get-AuditProperty -InputObject $_ -Name "type") -ceq "Ready" -and
        [string](Get-AuditProperty -InputObject $_ -Name "status") -ceq "True"
    })
    return $matches.Count -eq 1
}

function Get-AuditJobContainer {
    param([object]$Description)
    $paths = @(
        @("spec", "template", "spec", "template", "spec", "containers"),
        @("template", "template", "containers"),
        @("spec", "template", "template", "containers")
    )
    foreach ($path in $paths) {
        $containers = @(Get-AuditNestedValue -InputObject $Description -Path $path)
        if ($containers.Count -eq 1 -and $null -ne $containers[0]) {
            return $containers[0]
        }
    }
    throw "cloud_run_job_container_not_unique"
}

function Invoke-CloudRunWriterInventory {
    $serviceName = "meteofriul-api"
    $region = "europe-west1"
    $service = Invoke-GcloudJson -Arguments @(
        "run", "services", "describe", $serviceName,
        "--project=$ProjectId", "--region=$region", "--platform=managed",
        "--format=json", "--quiet"
    ) -FailureCode "cloud_run_service_describe_failed"
    $traffic = @(@(Get-AuditNestedValue -InputObject $service -Path @("status", "traffic")) | ForEach-Object {
        [PSCustomObject]@{
            revisionName = [string](Get-AuditProperty -InputObject $_ -Name "revisionName")
            percent = Get-AuditProperty -InputObject $_ -Name "percent"
            tag = [string](Get-AuditProperty -InputObject $_ -Name "tag")
        }
    })
    $activeRevisionNames = @($traffic | Where-Object {
        $_.revisionName -and (
            ($null -ne $_.percent -and [int]$_.percent -gt 0) -or
            $_.tag -ceq $ReleaseApiTag
        )
    } | ForEach-Object { [string]$_.revisionName } | Sort-Object -Unique)
    $revisions = foreach ($revisionName in $activeRevisionNames) {
        $revision = Invoke-GcloudJson -Arguments @(
            "run", "revisions", "describe", $revisionName,
            "--project=$ProjectId", "--region=$region",
            "--format=json", "--quiet"
        ) -FailureCode "cloud_run_revision_describe_failed"
        [PSCustomObject]@{
            name = [string](Get-AuditNestedValue -InputObject $revision -Path @("metadata", "name"))
            ready = Test-AuditReadyCondition -Description $revision
            imageDigest = [string](Get-AuditNestedValue -InputObject $revision -Path @("status", "imageDigest"))
        }
    }

    $jobs = foreach ($spec in @(Get-FirestorePushTtlScheduledWriterTargets)) {
        $jobName = [string]$spec.name
        $jobRegion = [string]$spec.jobRegion
        $scheduler = Invoke-GcloudJson -Arguments @(
            "scheduler", "jobs", "describe", $jobName,
            "--project=$ProjectId", "--location=europe-west1",
            "--format=json", "--quiet"
        ) -FailureCode "cloud_scheduler_job_describe_failed"
        $job = Invoke-GcloudJson -Arguments @(
            "run", "jobs", "describe", $jobName,
            "--project=$ProjectId", "--region=$jobRegion",
            "--format=json", "--quiet"
        ) -FailureCode "cloud_run_job_describe_failed"
        $container = Get-AuditJobContainer -Description $job
        $schedulerName = [string](Get-AuditProperty -InputObject $scheduler -Name "name")
        [PSCustomObject]@{
            name = [string](Get-AuditNestedValue -InputObject $job -Path @("metadata", "name"))
            region = $jobRegion
            ready = Test-AuditReadyCondition -Description $job
            imageDigest = [string](Get-AuditProperty -InputObject $container -Name "image")
            scheduler = [PSCustomObject]@{
                name = $schedulerName.Split("/")[-1]
                region = "europe-west1"
                state = [string](Get-AuditProperty -InputObject $scheduler -Name "state")
                schedule = [string](Get-AuditProperty -InputObject $scheduler -Name "schedule")
                timeZone = [string](Get-AuditProperty -InputObject $scheduler -Name "timeZone")
                targetUri = [string](Get-AuditNestedValue -InputObject $scheduler -Path @("httpTarget", "uri"))
            }
        }
    }
    return [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-runtime-writers-v2"
        projectId = $ProjectId
        serviceRegion = $region
        releaseApiTag = $ReleaseApiTag
        service = [PSCustomObject]@{
            name = [string](Get-AuditNestedValue -InputObject $service -Path @("metadata", "name"))
            traffic = @($traffic)
            revisions = @($revisions)
        }
        jobs = @($jobs)
    }
}

function Invoke-CloudBuildVerification {
    param([string]$BuildId, [ValidateSet("europe-west1", "global")][string]$BuildRegion = "europe-west1")
    if ($BuildId -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
        throw "runtime_writer_build_id_invalid"
    }
    $build = Invoke-GcloudJson -Arguments @(
        "builds", "describe", $BuildId,
        "--project=$ProjectId", "--region=$BuildRegion",
        "--format=json", "--quiet"
    ) -FailureCode "cloud_build_describe_failed"
    $canonicalImageDigests = @(@(Get-AuditNestedValue -InputObject $build -Path @("results", "images")) | ForEach-Object {
        $name = [string](Get-AuditProperty -InputObject $_ -Name "name")
        $digest = [string](Get-AuditProperty -InputObject $_ -Name "digest")
        if ($name -and $digest -cmatch '^sha256:[0-9a-f]{64}$') {
            $packageName = [regex]::Replace($name, ':[^/:]+$', '')
            "$packageName@$digest"
        }
    } | Where-Object { $_ })
    $sourceHashes = Get-AuditNestedValue -InputObject $build -Path @("sourceProvenance", "fileHashes")
    $sourceArchiveSha256 = ""
    if ($null -ne $sourceHashes) {
        foreach ($sourceProperty in @($sourceHashes.PSObject.Properties)) {
            foreach ($hash in @(Get-AuditProperty -InputObject $sourceProperty.Value -Name "fileHash")) {
                if ([string](Get-AuditProperty -InputObject $hash -Name "type") -ceq "SHA256") {
                    $sourceArchiveSha256 = [string](Get-AuditProperty -InputObject $hash -Name "value")
                }
            }
        }
    }
    return [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-cloud-build-verification-v1"
        id = [string](Get-AuditProperty -InputObject $build -Name "id")
        region = $BuildRegion
        status = [string](Get-AuditProperty -InputObject $build -Name "status")
        canonicalImageDigests = @($canonicalImageDigests)
        sourceArchiveSha256Base64 = $sourceArchiveSha256
    }
}

function Get-Sha256Text {
    param([string]$Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Invoke-FirestoreReadback {
    $gcloud = Resolve-GcloudExecutable
    $tokenOutput = & $gcloud auth print-access-token "--project=$ProjectId" --quiet --verbosity=error 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gcloud_access_token_failed" }
    $accessToken = [string]($tokenOutput -join "").Trim()
    if ([string]::IsNullOrWhiteSpace($accessToken)) { throw "gcloud_access_token_empty" }

    $headers = @{ Authorization = "Bearer $accessToken" }
    $uri = "https://firestore.googleapis.com/v1/projects/$ProjectId/databases/$DatabaseId/documents:runQuery"
    $collectionRows = foreach ($collectionGroup in @(
        "push_official_alert_outbox",
        "push_local_notice_outbox"
    )) {
        $request = [ordered]@{
            structuredQuery = [ordered]@{
                select = [ordered]@{ fields = @([ordered]@{ fieldPath = "expires_at" }) }
                from = @([ordered]@{ collectionId = $collectionGroup; allDescendants = $true })
            }
        }
        try {
            $rawResponse = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers `
                -ContentType "application/json" -Body ($request | ConvertTo-Json -Depth 8)
        } catch {
            throw "firestore_readback_failed:$collectionGroup"
        }
        # PowerShell 7 intentionally preserves a top-level JSON array as one
        # object while Windows PowerShell 5.1 enumerates it. foreach normalizes
        # both representations without depending on pipeline unrolling.
        $response = @()
        foreach ($responseItem in $rawResponse) { $response += $responseItem }
        $documents = @($response | Where-Object {
            $null -ne $_ -and $_.PSObject.Properties.Name -ccontains "document"
        } | ForEach-Object { $_.document })
        $canonicalRows = New-Object System.Collections.Generic.List[string]
        $validCount = 0
        foreach ($document in $documents) {
            $timestamp = $null
            if ($document.PSObject.Properties.Name -ccontains "fields" -and
                $null -ne $document.fields -and
                $document.fields.PSObject.Properties.Name -ccontains "expires_at" -and
                $null -ne $document.fields.expires_at -and
                $document.fields.expires_at.PSObject.Properties.Name -ccontains "timestampValue") {
                $timestamp = [string]$document.fields.expires_at.timestampValue
            }
            if (-not [string]::IsNullOrWhiteSpace($timestamp)) { $validCount += 1 }
            $canonicalRows.Add("$([string]$document.name)|$timestamp")
        }
        $documentSetDigest = Get-Sha256Text -Value ((@($canonicalRows) | Sort-Object) -join "`n")
        [PSCustomObject]@{
            collectionGroup = $collectionGroup
            field = "expires_at"
            documentCount = $documents.Count
            validExpiresAtCount = $validCount
            missingOrInvalidExpiresAt = $documents.Count - $validCount
            documentSetSha256 = $documentSetDigest
        }
    }
    return [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-readback-v1"
        projectId = $ProjectId
        databaseId = $DatabaseId
        method = "firestore.runQuery.expires_at-projection"
        collections = @($collectionRows)
    }
}

function Get-EvidenceGitStatus {
    param([string]$RepositoryRoot, [string]$EvidencePath)
    $trimChars = [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path.TrimEnd($trimChars)
    $resolvedEvidence = (Resolve-Path -LiteralPath $EvidencePath -ErrorAction Stop).Path
    $prefix = "$resolvedRoot$([IO.Path]::DirectorySeparatorChar)"
    if (-not $resolvedEvidence.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "historical_evidence_outside_repository"
    }
    $relativePath = $resolvedEvidence.Substring($prefix.Length).Replace('\', '/')

    $trackedOutput = @(& git -C $resolvedRoot ls-files -- $relativePath 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git_evidence_tracked_check_failed" }
    $tracked = @($trackedOutput | Where-Object {
        [string]$_ -ceq $relativePath
    }).Count -eq 1
    $statusOutput = @(& git -C $resolvedRoot status --porcelain -- $relativePath 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git_evidence_status_failed" }
    # Evidence paths are immutable identifiers. Disable rename inference here:
    # highly similar append-only JSON contracts must not inherit the history of
    # a previous digest file merely because Git detects a probable rename.
    $historyOutput = @(& git -C $resolvedRoot log --no-renames --format=%H -- $relativePath 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git_evidence_history_failed" }
    return [PSCustomObject]@{
        tracked = $tracked
        clean = (@($statusOutput | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }).Count -eq 0)
        commitCount = @($historyOutput | Where-Object { [string]$_ -cmatch '^[0-9a-f]{40}$' }).Count
    }
}

function Get-PushRepositoryGitStatus {
    param(
        [string]$RepositoryRoot,
        [string]$PushRepositoryPath,
        [string]$SourceCommit
    )
    $relativePath = "backend/app/repositories/push.py"
    $expectedPath = [IO.Path]::GetFullPath((Join-Path $RepositoryRoot $relativePath.Replace('/', '\')))
    $resolvedPath = (Resolve-Path -LiteralPath $PushRepositoryPath -ErrorAction Stop).Path
    if (-not $resolvedPath.Equals($expectedPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw "push_repository_path_unexpected"
    }
    $trackedOutput = @(& git -C $RepositoryRoot ls-files -- $relativePath 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git_push_repository_tracked_check_failed" }
    $tracked = @($trackedOutput | Where-Object { [string]$_ -ceq $relativePath }).Count -eq 1
    $statusOutput = @(& git -C $RepositoryRoot status --porcelain -- $relativePath 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "git_push_repository_status_failed" }
    $null = & git -C $RepositoryRoot cat-file -e "$SourceCommit`^{commit}" 2>&1
    $sourceCommitExists = $LASTEXITCODE -eq 0
    $matchesSourceCommit = $false
    if ($sourceCommitExists) {
        $null = & git -C $RepositoryRoot diff --quiet $SourceCommit -- $relativePath 2>&1
        $matchesSourceCommit = $LASTEXITCODE -eq 0
    }
    return [PSCustomObject]@{
        tracked = $tracked
        clean = (@($statusOutput | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) }).Count -eq 0)
        sourceCommitExists = $sourceCommitExists
        matchesSourceCommit = $matchesSourceCommit
    }
}

try {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    if (-not $PushRepositoryPath) {
        $PushRepositoryPath = Join-Path $repositoryRoot "backend\app\repositories\push.py"
    }
    if (-not $HistoricalEvidencePath) {
        $HistoricalEvidencePath = Join-Path $repositoryRoot "release-history\firestore-ttl\push-outbox-history.json"
    }

    $resolvedPushRepository = (Resolve-Path -LiteralPath $PushRepositoryPath -ErrorAction Stop).Path
    $source = Get-Content -LiteralPath $resolvedPushRepository -Raw
    $sourceSha256 = (Get-FileHash -LiteralPath $resolvedPushRepository -Algorithm SHA256).Hash.ToLowerInvariant()
    $policies = if ($PolicyFixturePath) {
        $resolvedFixture = (Resolve-Path -LiteralPath $PolicyFixturePath -ErrorAction Stop).Path
        @(Get-Content -LiteralPath $resolvedFixture -Raw | ConvertFrom-Json)
    } else {
        @(Invoke-GcloudTtlList)
    }
    $readback = if ($ReadbackFixturePath) {
        $resolvedReadbackFixture = (Resolve-Path -LiteralPath $ReadbackFixturePath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedReadbackFixture -Raw | ConvertFrom-Json
    } elseif ($PolicyFixturePath) {
        throw "readback_fixture_required_with_policy_fixture"
    } else {
        Invoke-FirestoreReadback
    }
    $history = if (Test-Path -LiteralPath $HistoricalEvidencePath -PathType Leaf) {
        $resolvedHistory = (Resolve-Path -LiteralPath $HistoricalEvidencePath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedHistory -Raw | ConvertFrom-Json
    } else {
        $null
    }
    $evidenceGitStatus = if ($null -eq $history) {
        $null
    } elseif ($PolicyFixturePath) {
        [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 1 }
    } else {
        Get-EvidenceGitStatus -RepositoryRoot $repositoryRoot -EvidencePath $HistoricalEvidencePath
    }
    $runtimeWriters = if ($RuntimeFixturePath) {
        $resolvedRuntimeFixture = (Resolve-Path -LiteralPath $RuntimeFixturePath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedRuntimeFixture -Raw | ConvertFrom-Json
    } elseif ($PolicyFixturePath) {
        throw "runtime_fixture_required_with_policy_fixture"
    } else {
        Invoke-CloudRunWriterInventory
    }
    if ([string](Get-AuditProperty -InputObject $runtimeWriters -Name "schemaVersion") -ceq "firestore-push-ttl-runtime-writers-v2") {
        if ($RuntimeWriterContractPath -or $RuntimeBuildFixturePath -or $PolicyFixturePath -or $RuntimeFixturePath) {
            throw "runtime_writer_set_live_fixture_mix_forbidden"
        }
        if (-not $RuntimeWriterSetContractPath) {
            $RuntimeWriterSetContractPath = Join-Path $repositoryRoot "release-history\firestore-ttl\runtime-writer-sets\play-services-fvg-20261020.json"
        }
        if (-not (Test-Path -LiteralPath $RuntimeWriterSetContractPath -PathType Leaf)) {
            throw "runtime_writer_set_contract_missing"
        }
        $setPath = (Resolve-Path -LiteralPath $RuntimeWriterSetContractPath -ErrorAction Stop).Path
        $setContract = Get-Content -LiteralPath $setPath -Raw | ConvertFrom-Json
        $setGitStatus = Get-EvidenceGitStatus -RepositoryRoot $repositoryRoot -EvidencePath $setPath
        $imageProofs = foreach ($image in @(Get-AuditProperty -InputObject $setContract -Name "images")) {
            $sourceCommit = [string](Get-AuditProperty -InputObject $image -Name "sourceCommit")
            $buildId = [string](Get-AuditProperty -InputObject $image -Name "cloudBuildId")
            $buildRegion = [string](Get-AuditProperty -InputObject $image -Name "cloudBuildRegion")
            [PSCustomObject]@{
                imageDigest = [string](Get-AuditProperty -InputObject $image -Name "imageDigest")
                buildVerification = Invoke-CloudBuildVerification -BuildId $buildId -BuildRegion $buildRegion
                pushRepositoryGitStatus = Get-PushRepositoryGitStatus -RepositoryRoot $repositoryRoot -PushRepositoryPath $resolvedPushRepository -SourceCommit $sourceCommit
            }
        }
        $liveArgs = @{
            TtlPolicies = $policies
            PushRepositorySource = $source
            PushRepositorySha256 = $sourceSha256
            CurrentReadback = $readback
            HistoricalEvidence = $history
            EvidenceGitStatus = $evidenceGitStatus
            RuntimeWriters = $runtimeWriters
            RuntimeWriterSetContract = $setContract
            RuntimeWriterSetGitStatus = $setGitStatus
            RuntimeWriterSetProofs = @($imageProofs)
            ExpectedReleaseApiTag = $ReleaseApiTag
            ProjectId = $ProjectId
            DatabaseId = $DatabaseId
        }
        $result = Test-FirestorePushTtlState @liveArgs
        if ($PassThru) { return $result }
        $result | ConvertTo-Json -Depth 12
        if (-not $result.ready) { exit 2 }
        exit 0
    }
    if (-not $RuntimeWriterContractPath) {
        $contractDirectory = Join-Path $repositoryRoot "release-history\firestore-ttl\runtime-writer-images"
        $contractCandidates = New-Object System.Collections.Generic.List[object]
        if (Test-Path -LiteralPath $contractDirectory -PathType Container) {
            foreach ($candidate in @(Get-ChildItem -LiteralPath $contractDirectory -Filter "*.json" -File)) {
                try {
                    $candidateContract = Get-Content -LiteralPath $candidate.FullName -Raw | ConvertFrom-Json
                    $contractCandidates.Add([PSCustomObject]@{
                        path = $candidate.FullName
                        contract = $candidateContract
                    })
                } catch {
                    throw "runtime_writer_contract_invalid_json:$($candidate.Name)"
                }
            }
        }
        $selectedContract = Resolve-RuntimeWriterContractCandidate `
            -Candidates $contractCandidates.ToArray() `
            -PushRepositorySha256 $sourceSha256 `
            -RuntimeWriters $runtimeWriters
        if ($null -ne $selectedContract) {
            $RuntimeWriterContractPath = [string](Get-AuditProperty -InputObject $selectedContract -Name "path")
        }
    }
    $runtimeContract = if ($RuntimeWriterContractPath -and
        (Test-Path -LiteralPath $RuntimeWriterContractPath -PathType Leaf)) {
        $resolvedRuntimeContract = (Resolve-Path -LiteralPath $RuntimeWriterContractPath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedRuntimeContract -Raw | ConvertFrom-Json
    } else {
        $null
    }
    $runtimeContractGitStatus = if ($null -eq $runtimeContract) {
        $null
    } elseif ($PolicyFixturePath) {
        [PSCustomObject]@{ tracked = $true; clean = $true; commitCount = 1 }
    } else {
        Get-EvidenceGitStatus -RepositoryRoot $repositoryRoot -EvidencePath $RuntimeWriterContractPath
    }
    $pushRepositoryGitStatus = if ($null -eq $runtimeContract) {
        $null
    } elseif ($PolicyFixturePath) {
        [PSCustomObject]@{
            tracked = $true
            clean = $true
            sourceCommitExists = $true
            matchesSourceCommit = $true
        }
    } else {
        Get-PushRepositoryGitStatus -RepositoryRoot $repositoryRoot `
            -PushRepositoryPath $resolvedPushRepository `
            -SourceCommit ([string](Get-AuditProperty -InputObject $runtimeContract -Name "sourceCommit"))
    }
    $runtimeBuildVerification = if ($RuntimeBuildFixturePath) {
        $resolvedBuildFixture = (Resolve-Path -LiteralPath $RuntimeBuildFixturePath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedBuildFixture -Raw | ConvertFrom-Json
    } elseif ($PolicyFixturePath) {
        throw "runtime_build_fixture_required_with_policy_fixture"
    } elseif ($null -ne $runtimeContract) {
        Invoke-CloudBuildVerification -BuildId ([string](Get-AuditProperty -InputObject $runtimeContract -Name "cloudBuildId"))
    } else {
        $null
    }

    $result = Test-FirestorePushTtlState -TtlPolicies $policies `
        -PushRepositorySource $source -PushRepositorySha256 $sourceSha256 `
        -CurrentReadback $readback `
        -HistoricalEvidence $history -EvidenceGitStatus $evidenceGitStatus `
        -RuntimeWriters $runtimeWriters `
        -RuntimeWriterContract $runtimeContract `
        -RuntimeContractGitStatus $runtimeContractGitStatus `
        -RuntimeBuildVerification $runtimeBuildVerification `
        -PushRepositoryGitStatus $pushRepositoryGitStatus `
        -ProjectId $ProjectId -DatabaseId $DatabaseId
    if ($PassThru) { return $result }
    $result | ConvertTo-Json -Depth 12
    if (-not $result.ready) { exit 2 }
    exit 0
} catch {
    $failure = [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-audit-v1"
        ready = $false
        blockingCount = 1
        findings = @([PSCustomObject]@{
            code = "audit_failed"
            message = $_.Exception.Message
            blocking = $true
        })
    }
    if ($PassThru) { return $failure }
    $failure | ConvertTo-Json -Depth 8
    exit 1
}
