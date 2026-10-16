[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("staged", "active")]
    [string]$Phase,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedPlaySigningSha256,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedEnrollmentGeneration,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedVersionName,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$ExpectedVersionCode,

    [string[]]$ExpectedAllowedAppVersions,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 500)]
    [int]$ExpectedMaxDevices,

    [string]$DebugTokenRevocationEvidence,

    [string]$LegacyPushCleanupEvidence,

    [string[]]$RuntimeRevisionEvidencePaths,

    [string]$AabReleaseManifestPath,

    [string]$SnapshotPath,

    [switch]$FixtureMode,

    [string]$ExpectedAccount = "meteofriul@gmail.com",

    [string]$ProjectId = "meteo-friul",

    [string]$ProjectNumber = "49007668366",

    [string]$Region = "europe-west1",

    [string]$FirebaseAppId = "1:49007668366:android:725bf6f8b339177a852ddf",

    [string]$AndroidPackage = "com.meteofriul.app",

    [string]$ServiceName = "meteofriul-api",

    [string]$OfficialAlertsJobName = "meteofriul-official-alert-sync",

    [string]$LocalNoticesJobName = "meteofriul-local-notice",

    [string]$GcloudPath,

    [datetimeoffset]$NowUtc = [datetimeoffset]::UtcNow
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Import-Module (Join-Path $PSScriptRoot "play-notification-cutover-audit.psm1") -Force

function Get-AuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) {
        return $null
    }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Resolve-AuditGcloudPath {
    param([string]$Candidate)
    if ($Candidate) {
        $resolved = [IO.Path]::GetFullPath($Candidate)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "cutover_gcloud_not_found: $resolved"
        }
        return $resolved
    }
    foreach ($name in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    throw "cutover_gcloud_not_found"
}

function Invoke-AuditGcloudText {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureCode`: $($output -join ' ')"
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Invoke-AuditGcloudJson {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)
    $text = Invoke-AuditGcloudText -Executable $Executable -Arguments $Arguments -FailureCode $FailureCode
    if (-not $text) {
        throw "$FailureCode`: empty_json"
    }
    try {
        return $text | ConvertFrom-Json
    } catch {
        throw "$FailureCode`: invalid_json"
    }
}

function Invoke-AuditGoogleGet {
    param(
        [string]$Uri,
        [string]$AccessToken,
        [string]$QuotaProject,
        [string]$FailureCode
    )
    try {
        return Invoke-RestMethod `
            -Method Get `
            -Uri $Uri `
            -Headers @{
                Authorization = "Bearer $AccessToken"
                "x-goog-user-project" = $QuotaProject
            }
    } catch {
        throw "$FailureCode`: $($_.Exception.Message)"
    }
}

function Get-AuditNestedValue {
    param([object]$InputObject, [string[]]$Path)
    $current = $InputObject
    foreach ($segment in $Path) {
        $current = Get-AuditProperty -InputObject $current -Name $segment
        if ($null -eq $current) {
            return $null
        }
    }
    return $current
}

function Get-AuditContainer {
    param([object]$Description, [string]$ResourceKind)
    $paths = [Collections.Generic.List[string[]]]::new()
    if ($ResourceKind -ceq "revision") {
        $paths.Add([string[]]@("spec", "containers"))
    } else {
        $paths.Add([string[]]@("spec", "template", "spec", "template", "spec", "containers"))
        $paths.Add([string[]]@("spec", "template", "spec", "containers"))
        $paths.Add([string[]]@("template", "template", "containers"))
        $paths.Add([string[]]@("template", "containers"))
    }
    foreach ($path in $paths) {
        $containers = @(Get-AuditNestedValue -InputObject $Description -Path $path)
        if ($containers.Count -eq 1 -and $null -ne $containers[0]) {
            return $containers[0]
        }
        if ($containers.Count -gt 1) {
            throw "cutover_cloud_container_count_invalid: kind=$ResourceKind count=$($containers.Count)"
        }
    }
    throw "cutover_cloud_container_missing: kind=$ResourceKind"
}

function Get-AuditEnvironment {
    param([object]$Container, [string]$TargetName)
    $environment = [ordered]@{}
    foreach ($entry in @(Get-AuditProperty -InputObject $Container -Name "env")) {
        $name = [string](Get-AuditProperty -InputObject $entry -Name "name")
        if (-not $name -or $environment.Contains($name)) {
            throw "cutover_cloud_env_invalid: target=$TargetName"
        }
        $value = Get-AuditProperty -InputObject $entry -Name "value"
        if ($null -eq $value) {
            $environment[$name] = "<value-from-secret-or-reference>"
            continue
        }
        $environment[$name] = [string]$value
    }
    return [PSCustomObject]$environment
}

function Test-AuditReadyCondition {
    param([object]$Description)
    $conditions = @(Get-AuditNestedValue -InputObject $Description -Path @("status", "conditions"))
    $ready = @(
        $conditions | Where-Object {
            [string](Get-AuditProperty -InputObject $_ -Name "type") -ceq "Ready" -and
            [string](Get-AuditProperty -InputObject $_ -Name "status") -ceq "True"
        }
    )
    return $ready.Count -eq 1
}

function Get-AuditJobTarget {
    param(
        [string]$Executable,
        [string]$Name,
        [string]$Project,
        [string]$Location
    )
    $description = Invoke-AuditGcloudJson `
        -Executable $Executable `
        -Arguments @("run", "jobs", "describe", $Name, "--project", $Project, "--region", $Location, "--format=json", "--quiet") `
        -FailureCode "cutover_cloud_job_describe_failed"
    $container = Get-AuditContainer -Description $description -ResourceKind "job"
    $image = [string](Get-AuditProperty -InputObject $container -Name "image")
    return [PSCustomObject]@{
        env = Get-AuditEnvironment -Container $container -TargetName $Name
        imageDigest = $image.Trim()
        kind = "job"
        name = [string](Get-AuditNestedValue -InputObject $description -Path @("metadata", "name"))
        ready = Test-AuditReadyCondition -Description $description
    }
}

function Get-AuditServiceTarget {
    param(
        [string]$Executable,
        [string]$Name,
        [string]$Project,
        [string]$Location,
        [string]$ExpectedApiBase,
        [string]$ExpectedTag
    )
    $service = Invoke-AuditGcloudJson `
        -Executable $Executable `
        -Arguments @("run", "services", "describe", $Name, "--project", $Project, "--region", $Location, "--format=json", "--quiet") `
        -FailureCode "cutover_cloud_service_describe_failed"
    $latestReadyRevision = [string](Get-AuditNestedValue -InputObject $service -Path @("status", "latestReadyRevisionName"))
    if (-not $latestReadyRevision) {
        throw "cutover_cloud_service_latest_ready_revision_missing"
    }
    $trafficMatches = @(
        @(Get-AuditNestedValue -InputObject $service -Path @("status", "traffic")) |
            Where-Object {
                [string](Get-AuditProperty -InputObject $_ -Name "tag") -ceq $ExpectedTag
            }
    )
    if ($trafficMatches.Count -ne 1) {
        throw "cutover_cloud_tag_traffic_not_unique: tag=$ExpectedTag count=$($trafficMatches.Count)"
    }
    $tagTraffic = $trafficMatches[0]
    $trafficRevision = [string](Get-AuditProperty -InputObject $tagTraffic -Name "revisionName")
    $trafficUrl = [string](Get-AuditProperty -InputObject $tagTraffic -Name "url")
    if (-not $trafficRevision) {
        throw "cutover_cloud_tag_revision_missing: tag=$ExpectedTag"
    }
    try {
        $expectedApiUri = [Uri]$ExpectedApiBase
        $trafficUri = [Uri]$trafficUrl
    } catch {
        throw "cutover_cloud_tag_url_invalid"
    }
    if (-not $trafficUri.IsAbsoluteUri -or
        $trafficUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/') -cne
            $expectedApiUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/')) {
        throw "cutover_cloud_tag_url_mismatch"
    }
    $revision = Invoke-AuditGcloudJson `
        -Executable $Executable `
        -Arguments @("run", "revisions", "describe", $trafficRevision, "--project", $Project, "--region", $Location, "--format=json", "--quiet") `
        -FailureCode "cutover_cloud_revision_describe_failed"
    $container = Get-AuditContainer -Description $revision -ResourceKind "revision"
    return [PSCustomObject]@{
        env = Get-AuditEnvironment -Container $container -TargetName $Name
        imageDigest = [string](Get-AuditNestedValue -InputObject $revision -Path @("status", "imageDigest"))
        kind = "service"
        latestReadyRevision = $latestReadyRevision
        name = [string](Get-AuditNestedValue -InputObject $service -Path @("metadata", "name"))
        ready = Test-AuditReadyCondition -Description $revision
        revision = $trafficRevision
        trafficRevision = $trafficRevision
        trafficTag = $ExpectedTag
        trafficUrl = $trafficUrl
    }
}

function Get-AuditEvidenceState {
    param(
        [string]$EvidencePath,
        [Parameter(Mandatory = $true)]
        [ValidateSet(
            "debug-tokens-revoked",
            "legacy-push-cleanup-verified",
            "runtime-revision-retarget-verified",
            "android-play-release"
        )]
        [string]$EvidenceKind
    )
    $profile = switch ($EvidenceKind) {
        "debug-tokens-revoked" {
            [PSCustomObject]@{
                ErrorPrefix = "cutover_debug_revocation_evidence"
                Root = Join-Path $repositoryRoot "release-history\play-notification-cutover\evidence"
                Filename = '^\d{8}T\d{6}Z-debug-tokens-revoked\.json$'
            }
        }
        "legacy-push-cleanup-verified" {
            [PSCustomObject]@{
                ErrorPrefix = "cutover_legacy_push_cleanup_evidence"
                Root = Join-Path $repositoryRoot "release-history\play-notification-cutover\evidence"
                Filename = '^\d{8}T\d{6}Z-legacy-push-cleanup-verified\.json$'
            }
        }
        "runtime-revision-retarget-verified" {
            [PSCustomObject]@{
                ErrorPrefix = "cutover_runtime_revision_evidence"
                Root = Join-Path $repositoryRoot "release-history\play-notification-cutover\evidence"
                Filename = '^\d{8}T\d{6}Z-runtime-revision-retarget-verified\.json$'
            }
        }
        "android-play-release" {
            [PSCustomObject]@{
                ErrorPrefix = "cutover_aab_release_manifest"
                Root = Join-Path $repositoryRoot "release-history\android-play"
                Filename = '^meteofriul-[1-9][0-9]*-[0-9A-Za-z][0-9A-Za-z._-]{0,63}\.release\.json$'
            }
        }
    }
    $errorPrefix = $profile.ErrorPrefix
    if (-not $EvidencePath) {
        throw "${errorPrefix}_required"
    }
    $fullPath = [IO.Path]::GetFullPath($EvidencePath)
    $evidenceRoot = [IO.Path]::GetFullPath($profile.Root)
    if (-not $fullPath.StartsWith($evidenceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "${errorPrefix}_outside_ledger"
    }
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "${errorPrefix}_not_found: $fullPath"
    }
    if ([IO.Path]::GetFileName($fullPath) -notmatch $profile.Filename) {
        throw "${errorPrefix}_filename_invalid"
    }
    $relative = $fullPath.Substring($repositoryRoot.Length).TrimStart([char[]]"\/").Replace("\", "/")
    $record = Get-Content -LiteralPath $fullPath -Raw | ConvertFrom-Json
    $fileSha256 = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToUpperInvariant()

    $trackedText = & git -C $repositoryRoot ls-files --error-unmatch -- $relative 2>$null
    $tracked = $LASTEXITCODE -eq 0 -and [bool]$trackedText
    $statusText = (& git -C $repositoryRoot status --porcelain -- $relative 2>$null) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "${errorPrefix}_git_status_failed"
    }
    $addCommits = @(& git -C $repositoryRoot log --format=%H --diff-filter=A -- $relative 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "${errorPrefix}_git_log_failed"
    }
    $mutationCommits = @(& git -C $repositoryRoot log --format=%H --diff-filter=MRCD -- $relative 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "${errorPrefix}_git_log_failed"
    }
    $addCommitTimes = @(& git -C $repositoryRoot log --format=%cI --diff-filter=A -- $relative 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "${errorPrefix}_git_log_failed"
    }
    return [PSCustomObject]@{
        addCommitTimeUtc = if ($addCommitTimes.Count -eq 1) { [string]$addCommitTimes[0] } else { "" }
        addCommitCount = @($addCommits | Where-Object { $_ }).Count
        clean = -not [bool]$statusText.Trim()
        fileSha256 = $fileSha256
        mutationCommitCount = @($mutationCommits | Where-Object { $_ }).Count
        path = $relative
        record = $record
        tracked = $tracked
    }
}

function Get-LiveAuditSnapshot {
    $gcloud = Resolve-AuditGcloudPath -Candidate $GcloudPath
    $account = Invoke-AuditGcloudText `
        -Executable $gcloud `
        -Arguments @("auth", "list", "--filter=status:ACTIVE", "--format=value(account)", "--quiet") `
        -FailureCode "cutover_gcloud_active_account_failed"
    if (($account -split "`r?`n").Count -ne 1) {
        throw "cutover_gcloud_active_account_ambiguous"
    }
    $configuredProject = Invoke-AuditGcloudText `
        -Executable $gcloud `
        -Arguments @("config", "get-value", "project", "--quiet") `
        -FailureCode "cutover_gcloud_project_failed"
    $actualProjectNumber = Invoke-AuditGcloudText `
        -Executable $gcloud `
        -Arguments @("projects", "describe", $ProjectId, "--format=value(projectNumber)", "--quiet") `
        -FailureCode "cutover_gcloud_project_describe_failed"
    $accessToken = Invoke-AuditGcloudText `
        -Executable $gcloud `
        -Arguments @("auth", "print-access-token", "--quiet") `
        -FailureCode "cutover_gcloud_access_token_failed"

    $encodedAppId = [Uri]::EscapeDataString($FirebaseAppId)
    $androidAppUri = "https://firebase.googleapis.com/v1beta1/projects/$ProjectId/androidApps/$encodedAppId"
    $shaUri = "$androidAppUri/sha"
    $appCheckBase = "https://firebaseappcheck.googleapis.com/v1/projects/$ProjectNumber/apps/$encodedAppId"
    $androidApp = Invoke-AuditGoogleGet -Uri $androidAppUri -AccessToken $accessToken -QuotaProject $ProjectId -FailureCode "cutover_firebase_android_app_get_failed"
    $shaResponse = Invoke-AuditGoogleGet -Uri $shaUri -AccessToken $accessToken -QuotaProject $ProjectId -FailureCode "cutover_firebase_sha_list_failed"
    $playIntegrity = Invoke-AuditGoogleGet `
        -Uri "$appCheckBase/playIntegrityConfig" `
        -AccessToken $accessToken `
        -QuotaProject $ProjectId `
        -FailureCode "cutover_app_check_play_integrity_get_failed"

    $aabReleaseManifestEvidence = Get-AuditEvidenceState `
        -EvidencePath $AabReleaseManifestPath `
        -EvidenceKind "android-play-release"
    $aabReleaseManifest = $aabReleaseManifestEvidence.record
    $manifestApiBase = [string](Get-AuditProperty -InputObject $aabReleaseManifest -Name "ApiBase")
    $manifestApiTag = [string](Get-AuditProperty -InputObject $aabReleaseManifest -Name "ApiTag")

    $runtimeRevisionEvidence = [Collections.Generic.List[object]]::new()
    [string[]]$runtimeEvidenceInputPaths = @()
    if ($null -ne $RuntimeRevisionEvidencePaths) {
        [string[]]$runtimeEvidenceInputPaths = @($RuntimeRevisionEvidencePaths)
    }
    foreach ($runtimeEvidencePath in $runtimeEvidenceInputPaths) {
        if (-not $runtimeEvidencePath) {
            throw "cutover_runtime_revision_evidence_path_empty"
        }
        $runtimeRevisionEvidence.Add((Get-AuditEvidenceState `
            -EvidencePath $runtimeEvidencePath `
            -EvidenceKind "runtime-revision-retarget-verified"))
    }

    $debugPages = [Collections.Generic.List[object]]::new()
    $pageToken = ""
    $seenTokens = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    do {
        if (-not $seenTokens.Add($pageToken)) {
            throw "cutover_debug_token_pagination_cycle_live"
        }
        $debugUri = "$appCheckBase/debugTokens?pageSize=20"
        if ($pageToken) {
            $debugUri += "&pageToken=$([Uri]::EscapeDataString($pageToken))"
        }
        $response = Invoke-AuditGoogleGet -Uri $debugUri -AccessToken $accessToken -QuotaProject $ProjectId -FailureCode "cutover_debug_token_list_failed"
        $rawTokens = Get-AuditProperty -InputObject $response -Name "debugTokens"
        $tokens = @()
        if ($null -ne $rawTokens) {
            $tokens = @($rawTokens)
        }
        $nextToken = [string](Get-AuditProperty -InputObject $response -Name "nextPageToken")
        $debugPages.Add([PSCustomObject]@{
            debugTokens = $tokens
            nextPageToken = $nextToken
            requestPageToken = $pageToken
        })
        $pageToken = $nextToken
    } while ($pageToken)

    return [PSCustomObject]@{
        aabReleaseManifestEvidence = $aabReleaseManifestEvidence
        capturedAtUtc = [datetimeoffset]::UtcNow.ToString("o")
        cloudRun = [PSCustomObject]@{
            localNoticesJob = Get-AuditJobTarget -Executable $gcloud -Name $LocalNoticesJobName -Project $ProjectId -Location $Region
            officialAlertsJob = Get-AuditJobTarget -Executable $gcloud -Name $OfficialAlertsJobName -Project $ProjectId -Location $Region
            service = Get-AuditServiceTarget `
                -Executable $gcloud `
                -Name $ServiceName `
                -Project $ProjectId `
                -Location $Region `
                -ExpectedApiBase $manifestApiBase `
                -ExpectedTag $manifestApiTag
        }
        debugTokenRevocationEvidence = Get-AuditEvidenceState `
            -EvidencePath $DebugTokenRevocationEvidence `
            -EvidenceKind "debug-tokens-revoked"
        firebase = [PSCustomObject]@{
            androidApp = [PSCustomObject]@{
                appId = [string](Get-AuditProperty -InputObject $androidApp -Name "appId")
                name = [string](Get-AuditProperty -InputObject $androidApp -Name "name")
                packageName = [string](Get-AuditProperty -InputObject $androidApp -Name "packageName")
                shaCertificates = @(Get-AuditProperty -InputObject $shaResponse -Name "certificates")
                state = [string](Get-AuditProperty -InputObject $androidApp -Name "state")
            }
            appCheck = [PSCustomObject]@{
                debugTokenPages = $debugPages.ToArray()
                playIntegrityConfig = $playIntegrity
            }
        }
        identity = [PSCustomObject]@{
            activeAccount = $account
            projectId = $configuredProject
            projectNumber = $actualProjectNumber
        }
        legacyPushCleanupEvidence = if ($Phase -ceq "active") {
            Get-AuditEvidenceState `
                -EvidencePath $LegacyPushCleanupEvidence `
                -EvidenceKind "legacy-push-cleanup-verified"
        } else {
            $null
        }
        runtimeRevisionEvidence = $runtimeRevisionEvidence.ToArray()
        schemaVersion = 1
    }
}

$hasSnapshot = [bool]$SnapshotPath
if ($hasSnapshot -ne [bool]$FixtureMode) {
    throw "cutover_fixture_mode_requires_snapshot_and_explicit_switch"
}

$snapshot = if ($hasSnapshot) {
    $resolvedSnapshot = [IO.Path]::GetFullPath($SnapshotPath)
    if (-not (Test-Path -LiteralPath $resolvedSnapshot -PathType Leaf)) {
        throw "cutover_snapshot_not_found: $resolvedSnapshot"
    }
    Get-Content -LiteralPath $resolvedSnapshot -Raw | ConvertFrom-Json
} else {
    Get-LiveAuditSnapshot
}

$validationNowUtc = if ($PSBoundParameters.ContainsKey("NowUtc")) {
    $NowUtc
} else {
    [datetimeoffset]::UtcNow
}

$result = Assert-PlayNotificationCutoverSnapshot `
    -Snapshot $snapshot `
    -Phase $Phase `
    -ExpectedAccount $ExpectedAccount `
    -ExpectedProjectId $ProjectId `
    -ExpectedProjectNumber $ProjectNumber `
    -ExpectedFirebaseAppId $FirebaseAppId `
    -ExpectedAndroidPackage $AndroidPackage `
    -ExpectedPlaySigningSha256 $ExpectedPlaySigningSha256 `
    -ExpectedEnrollmentGeneration $ExpectedEnrollmentGeneration `
    -ExpectedVersionName $ExpectedVersionName `
    -ExpectedVersionCode $ExpectedVersionCode `
    -ExpectedAllowedAppVersions $ExpectedAllowedAppVersions `
    -ExpectedMaxDevices $ExpectedMaxDevices `
    -ExpectedRegion $Region `
    -ExpectedServiceName $ServiceName `
    -ExpectedOfficialJobName $OfficialAlertsJobName `
    -ExpectedLocalJobName $LocalNoticesJobName `
    -NowUtc $validationNowUtc

$result | Add-Member -NotePropertyName "SnapshotSource" -NotePropertyValue $(
    if ($FixtureMode) { "fixture-test-only" } else { "live-read-only" }
)
$result | ConvertTo-Json -Depth 8
