[CmdletBinding()]
param([switch]$SkipGradleExecution)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($PSVersionTable.PSVersion.Major -lt 7 -or
    -not (Get-Command ConvertFrom-Json).Parameters.ContainsKey("DateKind")) {
    throw "build_play_aab_contract_requires_powershell_7_datekind"
}

# Load the assembly that defines ZipArchiveMode explicitly. This contract now
# runs only under PowerShell 7, matching the protected build entry point.
Add-Type -AssemblyName System.IO.Compression

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$buildScript = Join-Path $PSScriptRoot "build-play-aab.ps1"
$communityTtlAuditScript = Join-Path $PSScriptRoot "audit-firestore-community-ttl.ps1"
$communityTtlAuditModule = Join-Path $PSScriptRoot (
    "firestore-community-ttl-audit.psm1"
)
$communityTtlEvidenceModule = Join-Path $PSScriptRoot (
    "firestore-community-ttl-evidence.psm1"
)
$communityTtlRecorder = Join-Path $PSScriptRoot (
    "record-firestore-community-ttl-evidence.ps1"
)
$communityTtlEvidenceDirectory = Join-Path $workspaceRoot (
    "release-history\firestore-community-ttl"
)
$ledgerAuditScript = Join-Path $PSScriptRoot "audit-play-release-ledger.ps1"
$evidenceScript = Join-Path $PSScriptRoot "record-play-release-evidence.ps1"
$securityModule = Join-Path $PSScriptRoot "play-aab-security.psm1"
$verifierSource = Join-Path $PSScriptRoot "java\VerifySignedArchive.java"
$gradleWrapper = Join-Path $workspaceRoot "frontend\android\gradlew.bat"
$notificationIconGuardScript = Join-Path $PSScriptRoot (
    "package-android-notification-icon.ps1"
)

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ThrowsCode {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Action,
        [Parameter(Mandatory = $true)][string]$Expected
    )
    try {
        & $Action
    } catch {
        if ($_.Exception.Message.Contains($Expected)) { return }
        throw "Expected failure '$Expected', received '$($_.Exception.Message)'"
    }
    throw "Expected failure '$Expected', but the action succeeded."
}

function Write-TestJson {
    param([string]$Path, $Payload)
    $json = $Payload | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
}

function Resolve-JavaExecutable {
    param([string]$Name)
    if ($env:JAVA_HOME) {
        $javaHomeTool = Join-Path $env:JAVA_HOME "bin\$Name.exe"
        if (Test-Path -LiteralPath $javaHomeTool -PathType Leaf) {
            return $javaHomeTool
        }
    }
    $androidStudioTool = Join-Path "C:\Program Files\Android\Android Studio\jbr\bin" "$Name.exe"
    if (Test-Path -LiteralPath $androidStudioTool -PathType Leaf) {
        return $androidStudioTool
    }
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Source }
    throw "Java tool unavailable: $Name"
}

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][object[]]$Arguments
    )
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = (& $Executable @Arguments 2>&1 | Out-String)
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
    }
}

foreach ($path in @(
    $buildScript,
    $communityTtlAuditScript,
    $communityTtlAuditModule,
    $communityTtlEvidenceModule,
    $communityTtlRecorder,
    $ledgerAuditScript,
    $evidenceScript,
    $securityModule,
    $verifierSource,
    $gradleWrapper,
    $notificationIconGuardScript
)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) "Required Play file missing: $path"
}

foreach ($script in @(
    $buildScript,
    $communityTtlEvidenceModule,
    $communityTtlRecorder,
    $ledgerAuditScript,
    $evidenceScript,
    $securityModule
)) {
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile(
        $script,
        [ref]$tokens,
        [ref]$parseErrors
    )
    Assert-True ($parseErrors.Count -eq 0) "PowerShell parse failed: $script"
    if ($script -eq $buildScript) {
        $commandNames = @(
            $ast.FindAll({
                param($node)
                $node -is [Management.Automation.Language.CommandAst]
            }, $true) | ForEach-Object { $_.GetCommandName() } | Where-Object { $_ }
        )
        foreach ($requiredCommand in @(
            'Assert-PlayBundletoolTrust',
            'Assert-PlayCandidateVersion',
            'Assert-PlayGoogleServicesConfiguration',
            'Assert-PlayR8BundleArtifacts',
            'Assert-FirestoreCommunityTtlGate',
            'Assert-CommunityEphemeralSafetyGate',
            'Assert-FirestoreCommunityTtlEvidenceGitImmutability',
            'Assert-FirestoreCommunityTtlHistoricalEvidenceGate',
            'Assert-FirestorePushTtlGate',
            'Assert-PlayPowerShell7Capabilities',
            'Assert-PlayReleaseLedgerGitImmutability',
            'Copy-NewPlayArtifact',
            'Get-CommunityTtlWriterContractFromGitCommit',
            'Get-NormalizedCommunityApiBase',
            'Invoke-PlaySignedArchiveVerifier',
            'New-PlayAabTemporaryLayout',
            'Resolve-PlayUploadCertificateTrust',
            'Write-NewPlayJsonFile'
        )) {
            Assert-True ($requiredCommand -in $commandNames) `
                "Protected build does not invoke $requiredCommand"
        }
        Assert-True ('jarsigner.exe' -notin $commandNames) `
            'Protected build must not rely on jarsigner summary output.'
        Assert-True ('keytool.exe' -notin $commandNames) `
            'Protected build must not derive trust from ad-hoc keytool output.'
        $buildSource = Get-Content -LiteralPath $buildScript -Raw
        Assert-True ($buildSource.Contains('release_android_play_firestore_ttl_gate_failed')) `
            'Protected build does not fail closed when the Firestore TTL gate blocks.'
        Assert-True ($buildSource.Contains('audit-firestore-push-ttl.ps1')) `
            'Protected build does not bind the authoritative Firestore TTL audit.'
        Assert-True ($buildSource.Contains('audit-firestore-community-ttl.ps1')) `
            'Protected build does not bind the authoritative community TTL audit.'
        Assert-True ($buildSource.Contains(
            'release_android_play_community_ephemeral_gate_failed'
        )) 'Protected build does not fail closed on ephemeral Community drift.'
        Assert-True (-not $buildSource.Contains(
            'audit-community-moderation-runtime.ps1'
        )) 'Protected build must not require a scheduled moderation runtime.'
        Assert-True ($buildSource.Contains('firestore-community-ttl-evidence.psm1')) `
            'Protected build does not bind historical community TTL evidence.'
        Assert-True ($buildSource.Contains('firestore-community-ttl-audit-v2')) `
            'Protected build does not require the empty-safe fresh audit schema.'
        Assert-True ($buildSource.Contains(
            '-AuthoritativeBackendCommit $releaseApiState.BackendCommit'
        )) 'Historical evidence is not bound to the tagged backend commit.'
        $historicalGateInvocation = [regex]::Match(
            $buildSource,
            '(?s)\$firestoreCommunityTtlHistoricalState\s*=\s*`?\s*' +
                'Assert-FirestoreCommunityTtlHistoricalEvidenceGate\s*`?' +
                '.*?-AuthoritativeBackendCommit\s+' +
                '\$releaseApiState\.BackendCommit\s*`?\s*' +
                '-GcloudPath\s+\$GcloudPath'
        )
        Assert-True ($historicalGateInvocation.Success) (
            'Historical evidence read-back must use the same explicit trusted ' +
            'gcloud executable as the other release gates.'
        )
        Assert-True ($buildSource.Contains(
            'backend_writer_contract_hash_mismatch'
        )) 'Protected build does not compare authoritative writer bytes.'
        Assert-True ($buildSource.Contains('source_mode=$sourceMode')) `
            'Protected build does not reject non-live community TTL evidence.'
        Assert-True ($buildSource.Contains('release_android_play_powershell_7_required')) `
            'Protected build does not reject Windows PowerShell 5.1.'
        Assert-True ($buildSource.Contains('convertfromjson_datekind_required')) `
            'Protected build does not pin ConvertFrom-Json DateKind support.'
        Assert-True ($buildSource.Contains('& npx cap update android')) `
            'Protected build does not regenerate the native Capacitor plugin registry.'
        Assert-True ($buildSource.Contains(
            'Capacitor update changed tracked Gradle integration'
        )) 'Protected build does not fail closed on unexpected plugin wiring drift.'
        Assert-True ($buildSource.Contains(
            '& node scripts/carto-basemap-guard.mjs --mode android'
        )) 'Protected build does not require CARTO before compiling Android.'
        Assert-True ($buildSource.Contains(
            '& node scripts/carto-basemap-guard.mjs --mode android --build-dir $buildDirectory'
        )) 'Protected build does not reject direct OSM tiles in the Android bundle.'
        Assert-True ($buildSource.Contains(
            '& $notificationIconGuardScript -CheckOnly'
        )) 'Protected build does not verify the approved Android notification icon.'
        foreach ($exactTarget in @(
            'meteofriul@gmail.com',
            'meteo-friul',
            '49007668366',
            'projects/meteo-friul/databases/(default)',
            'FIRESTORE_NATIVE'
        )) {
            Assert-True ($buildSource.Contains($exactTarget)) `
                "Protected build does not pin community TTL identity: $exactTarget"
        }
        $expectedCommunityCatalogSha256 = (
            'bd3a48e6359a8c1546bc442601e21a2c' +
            'de6982501e81f177a92039f83345caed'
        )
        $catalogDigestDeclaration = [regex]::Match(
            $buildSource,
            '(?s)\$expectedCommunityLocationCatalogSha256\s*=\s*`?\s*"' +
                $expectedCommunityCatalogSha256 + '"'
        )
        Assert-True ($catalogDigestDeclaration.Success) (
            'Protected build does not pin the authoritative 7894-location ' +
            'national Community catalog digest.'
        )
        $catalogDigestGateArguments = [regex]::Matches(
            $buildSource,
            '-ExpectedCatalogSha256\s+' +
                '\$expectedCommunityLocationCatalogSha256'
        )
        Assert-True ($catalogDigestGateArguments.Count -eq 2) (
            'Both initial and final Community safety gates must receive the ' +
            'authoritative catalog digest.'
        )
        $communityEndpointGateArguments = [regex]::Matches(
            $buildSource,
            '-ApiBase\s+\$normalizedCommunityApiBase'
        )
        Assert-True ($communityEndpointGateArguments.Count -eq 2) (
            'Both Community safety gates must audit the separately deployed ' +
            'Community API used by the application.'
        )
        Assert-True ($buildSource.Contains(
            '-ExpectedCommunityApiBase $normalizedCommunityApiBase'
        )) 'The packaged WebView must be checked for the Community API binding.'
        $communityGateOffset = $buildSource.IndexOf(
            '$firestoreCommunityTtlState = Assert-FirestoreCommunityTtlGate'
        )
        $ephemeralSafetyGateOffset = $buildSource.IndexOf(
            '$communityEphemeralSafetyState = Assert-CommunityEphemeralSafetyGate'
        )
        $releaseApiGateOffset = $buildSource.IndexOf(
            '$releaseApiState = Invoke-ReleaseApiPreflight'
        )
        $historicalGateOffset = $buildSource.IndexOf(
            '$firestoreCommunityTtlHistoricalState = `'
        )
        Assert-True (
            $historicalGateOffset -gt $communityGateOffset
        ) 'Fresh community TTL read-back must precede historical evidence.'
        Assert-True (
            $ephemeralSafetyGateOffset -gt $releaseApiGateOffset -and
            $ephemeralSafetyGateOffset -gt $communityGateOffset -and
            $historicalGateOffset -gt $ephemeralSafetyGateOffset
        ) (
            'The ephemeral Community gate must run after the fresh TTL ' +
            'read-back and before historical evidence.'
        )
        $capabilityGuardMatch = [regex]::Match(
            $buildSource,
            '(?m)^Assert-PlayPowerShell7Capabilities\r?$'
        )
        $capabilityGuardOffset = if ($capabilityGuardMatch.Success) {
            $capabilityGuardMatch.Index
        } else {
            -1
        }
        $releaseGitOffset = $buildSource.IndexOf(
            '$releaseGitState = Assert-ReleaseGitState'
        )
        Assert-True (
            $capabilityGuardOffset -ge 0 -and
            $releaseGitOffset -gt $capabilityGuardOffset
        ) 'PowerShell 7 capability guard must run before release preflight.'
        $cartoPreflightOffset = $buildSource.IndexOf(
            '& node (Join-Path $frontendRoot "scripts\carto-basemap-guard.mjs") --mode android'
        )
        $cartoFailureOffset = $buildSource.IndexOf(
            'if ($LASTEXITCODE -ne 0) { throw "release_android_carto_basemap_config_invalid" }',
            $cartoPreflightOffset
        )
        $reservationWriteOffset = $buildSource.IndexOf(
            'Write-NewPlayJsonFile -Path $reservationPath'
        )
        Assert-True (
            $cartoPreflightOffset -gt $capabilityGuardOffset -and
            $cartoFailureOffset -gt $cartoPreflightOffset -and
            $cartoFailureOffset -lt $releaseGitOffset -and
            $cartoPreflightOffset -lt $releaseGitOffset -and
            $reservationWriteOffset -gt $cartoPreflightOffset
        ) 'Missing CARTO configuration must fail before a Play reservation is written.'
        foreach ($laterOperation in @(
            '$temporaryLayout = New-PlayAabTemporaryLayout',
            '$reservationPath = Join-Path $playReleaseHistoryDirectory',
            '& npx vite build',
            '& .\gradlew.bat bundleRelease'
        )) {
            $laterOffset = $buildSource.IndexOf($laterOperation)
            Assert-True (
                $communityGateOffset -ge 0 -and
                $ephemeralSafetyGateOffset -gt $communityGateOffset -and
                $historicalGateOffset -gt $ephemeralSafetyGateOffset -and
                $laterOffset -gt $historicalGateOffset
            ) (
                'Fresh Community TTL, ephemeral safety and historical ' +
                "evidence gates must fail before: $laterOperation"
            )
        }
        $finalEphemeralGateOffset = $buildSource.LastIndexOf(
            '$finalCommunityEphemeralSafetyState = Assert-CommunityEphemeralSafetyGate'
        )
        $copyArtifactOffset = $buildSource.IndexOf(
            'Copy-NewPlayArtifact -Source $aab -Destination $releaseAab'
        )
        Assert-True (
            $finalEphemeralGateOffset -gt $ephemeralSafetyGateOffset -and
            $copyArtifactOffset -gt $finalEphemeralGateOffset
        ) 'The final ephemeral safety re-check must precede artifact copy.'
        foreach ($manifestField in @(
            'CommunitySafetyModel',
            'CommunitySafetyCapturedAtUtc',
            'CommunitySafetyEndpoint',
            'CommunitySafetyInputMode',
            'CommunitySafetyLocationPrecision',
            'CommunitySafetyLocationCount',
            'CommunityLocationCatalogSha256',
            'CommunityPublicContentTtlSeconds',
            'CommunityPublicIdentity',
            'CommunityReportTypeIds',
            'CommunityFlagReasonIds',
            'CommunityPublicReportFields',
            'CommunityPublicGroupFields',
            'R8Verification',
            'MappingFile',
            'MappingSha256',
            'BundleMappingEntry',
            'NativeLibraryCount',
            'NativeSymbolEntryCount',
            'NativeSymbolsStatus'
        )) {
            Assert-True ($buildSource.Contains($manifestField)) `
                "Play manifest does not record Community safety field: $manifestField"
        }
    }
}

$buildTokens = $null
$buildParseErrors = $null
$buildAst = [Management.Automation.Language.Parser]::ParseFile(
    $buildScript,
    [ref]$buildTokens,
    [ref]$buildParseErrors
)
foreach ($functionName in @(
    'Assert-PlayPowerShell7Capabilities',
    'Get-NormalizedCommunityApiBase',
    'Get-PlayCommunityTtlAuditProperty',
    'Assert-FirestoreCommunityTtlGate',
    'Assert-CommunityEphemeralSafetyGate',
    'Assert-FirestoreCommunityTtlEvidenceGitImmutability',
    'Assert-FirestoreCommunityTtlHistoricalEvidenceGate'
)) {
    $definitions = @($buildAst.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -ceq $functionName
    }, $true))
    Assert-True ($definitions.Count -eq 1) `
        "Protected build function definition missing: $functionName"
    Invoke-Expression $definitions[0].Extent.Text
}

Import-Module $securityModule -Force
Import-Module (Join-Path $PSScriptRoot "release-api-preflight.psm1") -Force
Import-Module $communityTtlEvidenceModule -Force
Import-Module $communityTtlAuditModule -Force
$expectedCommunityApiBase = (
    'https://meteofriul-community-49007668366.europe-west1.run.app/api'
)
Assert-PlayPowerShell7Capabilities
Assert-True (
    (Get-NormalizedCommunityApiBase -Value "$expectedCommunityApiBase/") -ceq
        $expectedCommunityApiBase
) 'The exact Community API base was not normalized.'
Assert-ThrowsCode {
    Get-NormalizedCommunityApiBase -Value 'https://example.invalid/api'
} 'release_android_play_community_api_base_invalid'
Assert-ThrowsCode {
    Assert-PlayPowerShell7Capabilities -PowerShellMajor 5
} 'release_android_play_powershell_7_required'
Assert-ThrowsCode {
    Assert-PlayPowerShell7Capabilities `
        -PowerShellMajor 7 `
        -ConvertFromJsonCommand ([PSCustomObject]@{ Parameters = @{} })
} 'release_android_play_convertfromjson_datekind_required'
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "meteofriul-play-contract-" + [Guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null

try {
    $ephemeralLocations = @(0..15 | ForEach-Object {
        [PSCustomObject]@{
            place = "Comune $_"
            istatCode = "{0:D6}" -f ($_ + 1)
            regionId = 'IT-36'
            provinceCode = 'PN'
            lat = 45.6 + ($_ / 1000)
            lon = 12.4 + ($_ / 1000)
        }
    })
    $ephemeralLocations[0] = [PSCustomObject]@{
        place = "Pordenone"
        istatCode = '093033'
        regionId = 'IT-36'
        provinceCode = 'PN'
        lat = 45.9567
        lon = 12.6605
    }
    $ephemeralCatalogSha256 = 'a' * 64
    Assert-True (
        $ephemeralCatalogSha256 -cmatch '^[0-9a-f]{64}$'
    ) 'The fake Community catalog digest is not canonical SHA-256.'

    $ephemeralAllowedTypes = @(
        'fog', 'hail', 'ice', 'quiet', 'rain', 'snow', 'storm', 'wind'
    )
    $ephemeralCreateFields = @(
        'type_id', 'lat', 'lon', 'selected_place', 'client_id',
        'accepted_terms', 'policy_version', 'identity', 'istat_code',
        'accuracy_m', 'age_ms', 'operation_id', 'replacement_token'
    )
    $ephemeralPublicReportFields = @(
        'id', 'typeId', 'typeCategory', 'groupId', 'place', 'lat', 'lon',
        'locationPrecision', 'x', 'y', 'createdAt', 'expiresAt', 'time',
        'source', 'sourceKey', 'identity', 'istatCode', 'regionId',
        'provinceCode'
    )
    $ephemeralPublicGroupFields = @(
        'id', 'typeId', 'typeCategory', 'groupId', 'place', 'lat', 'lon',
        'locationPrecision', 'x', 'y', 'createdAt', 'expiresAt', 'time',
        'source', 'sourceKey', 'identity', 'reportIds', 'sourceKeys',
        'identities', 'count', 'confirmations', 'istatCode', 'regionId',
        'provinceCode'
    )
    $ephemeralContract = [PSCustomObject]@{
        schema_version = 'community-pilot-national-safety-v2'
        guidelines_policy_version = 'community-guidelines-v2'
        allowed_report_types = $ephemeralAllowedTypes
        create_fields = $ephemeralCreateFields
        public_report_fields = $ephemeralPublicReportFields
        public_group_fields = $ephemeralPublicGroupFields
        confirmation_fields = @('yes', 'no')
        location_fields = @(
            'place', 'lat', 'lon', 'istatCode', 'regionId', 'provinceCode'
        )
        source_fields = @(
            'id', 'type', 'verified', 'storage', 'cooldown_storage'
        )
        flag_reasons = @('inaccurate', 'duplicate', 'misuse')
        ttl_seconds = 3600
        cooldown_seconds = 120
        max_distance_km = 5
        location_catalog_count = 7894
        location_catalog_sha256 = $ephemeralCatalogSha256
        location_catalog_digest_algorithm = (
            'sha256-ordered-istat-lat5-lon5-lines-v1'
        )
        location_precision = 'zone'
        accepts_free_text = $false
        accepts_media = $false
        requires_account = $false
        user_flag_visibility = 'local_only'
        automatic_global_hide = $false
        public_source_key = [PSCustomObject]@{
            algorithm = 'sha256-truncated-lower-hex'
            pattern = '^[0-9a-f]{24}$'
            length = 24
            rotation_bucket_seconds = 86400
        }
        minimum_interval_seconds = 120
        undo_window_seconds = 0
        hourly_limit = 4
        daily_limit = 12
        quota_windows = 'rolling-server-time'
        correction_window_seconds = 300
        uniqueness = 'installation-istat-phenomenon'
        update_fields = @(
            'client_id', 'operation_id', 'expected_revision', 'lat', 'lon',
            'accuracy_m', 'age_ms', 'accepted_terms', 'policy_version'
        )
        update_action = 'renew_same_observation'
        update_requires_fresh_gps = $true
        update_idempotency = 'report-operation-revision-v1'
        pilot_public_report_extension_fields = @(
            'updatedAt', 'revision', 'correctionUntil',
            'replacementAvailable', 'lineageGroupIds'
        )
        pilot_public_group_extension_fields = @(
            'updatedAt', 'lineageGroupIds'
        )
    }
    $reportId = 'community-0123456789abcdef'
    $groupId = 'group-rain:093033:12345'
    $sourceKey = '0123456789abcdef01234567'
    $ephemeralGeneratedAt = [DateTimeOffset]::Parse(
        '2026-08-25T12:00:00Z',
        [Globalization.CultureInfo]::InvariantCulture
    )
    $ephemeralCurrentTime = $ephemeralGeneratedAt.AddMinutes(2)
    $ephemeralCreatedAtMilliseconds = `
        $ephemeralGeneratedAt.ToUnixTimeMilliseconds() - 60000
    $ephemeralExpiresAtMilliseconds = `
        $ephemeralCreatedAtMilliseconds + 3600000
    $ephemeralIdentity = [PSCustomObject]@{ alias = 'Sentinella di Pordenone' }
    $ephemeralPayload = [PSCustomObject]@{
        reports = @([PSCustomObject]@{
            id = $reportId
            typeId = 'rain'
            typeCategory = 'phenomenon'
            groupId = $groupId
            place = 'Pordenone'
            lat = 45.9567
            lon = 12.6605
            locationPrecision = 'zone'
            x = 20
            y = 30
            createdAt = $ephemeralCreatedAtMilliseconds
            expiresAt = $ephemeralExpiresAtMilliseconds
            time = ''
            source = 'community'
            sourceKey = $sourceKey
            identity = $ephemeralIdentity
            istatCode = '093033'
            regionId = 'IT-36'
            provinceCode = 'PN'
            updatedAt = $ephemeralCreatedAtMilliseconds
            revision = 1
            correctionUntil = $ephemeralCreatedAtMilliseconds + 300000
            replacementAvailable = $true
            lineageGroupIds = @()
        })
        map_groups = @([PSCustomObject]@{
            id = $groupId
            typeId = 'rain'
            typeCategory = 'phenomenon'
            groupId = $groupId
            place = 'Pordenone'
            lat = 45.9567
            lon = 12.6605
            locationPrecision = 'zone'
            x = 20
            y = 30
            createdAt = $ephemeralCreatedAtMilliseconds
            expiresAt = $ephemeralExpiresAtMilliseconds
            time = ''
            source = 'community'
            sourceKey = $sourceKey
            identity = $ephemeralIdentity
            reportIds = @($reportId)
            sourceKeys = @($sourceKey)
            identities = @([PSCustomObject]@{
                sourceKey = $sourceKey
                identity = $ephemeralIdentity
            })
            count = 1
            confirmations = [PSCustomObject]@{ yes = 0; no = 0 }
            istatCode = '093033'
            regionId = 'IT-36'
            provinceCode = 'PN'
            updatedAt = $ephemeralCreatedAtMilliseconds
            lineageGroupIds = @()
        })
        ttl_seconds = 3600
        cooldown_seconds = 120
        max_distance_km = 5
        locations = $ephemeralLocations
        generated_at = $ephemeralGeneratedAt.ToString('o')
        source = [PSCustomObject]@{
            id = 'community_reports'
            type = 'informative_unverified'
            verified = $false
            storage = 'pilot-cloud'
        }
        scope = [PSCustomObject]@{ istatCode = '093033'; radiusKm = 30 }
        contract = $ephemeralContract
    }
    $ephemeralGate = Assert-CommunityEphemeralSafetyGate `
        -ApiBase 'https://example.test/api' `
        -ExpectedCatalogSha256 $ephemeralCatalogSha256 `
        -Payload $ephemeralPayload `
        -CurrentTimeUtc $ephemeralCurrentTime
    Assert-True ($ephemeralGate.ready -eq $true) `
        'Ephemeral Community gate rejected its authoritative contract.'
    Assert-True (
        $buildSource.Contains('ConvertFrom-Json -DateKind String')
    ) 'Live Community timestamps must preserve their explicit timezone offset.'
    Assert-True (
        $buildSource.Contains(
            '$writtenManifest = Get-Content -LiteralPath $releaseManifest -Raw |' +
            "`r`n    ConvertFrom-Json -DateKind String"
        ) -or
        $buildSource.Contains(
            '$writtenManifest = Get-Content -LiteralPath $releaseManifest -Raw |' +
            "`n    ConvertFrom-Json -DateKind String"
        )
    ) 'Play manifest timestamps must not be converted to local DateTime values.'
    $manifestTimestamp = (
        '{"CommunitySafetyCapturedAtUtc":"2026-08-25T16:30:06.8189735Z"}' |
            ConvertFrom-Json -DateKind String
    ).CommunitySafetyCapturedAtUtc
    Assert-True ($manifestTimestamp -is [string]) `
        'Play manifest timestamp must remain a string.'
    Assert-True (
        $manifestTimestamp -ceq '2026-08-25T16:30:06.8189735Z'
    ) 'Play manifest timestamp lost precision or its UTC suffix.'
    Assert-True (
        $ephemeralGate.observed.publicContentTtlSeconds -eq 3600 -and
        $ephemeralGate.observed.locationCount -eq 7894 -and
        $ephemeralGate.observed.scopedLocationCount -eq 16 -and
        $ephemeralGate.observed.locationCatalogSha256 -ceq
            $ephemeralCatalogSha256 -and
        $ephemeralGate.observed.inputMode -ceq 'closed-phenomena'
    ) 'Ephemeral Community evidence is incomplete.'

    $emptyEphemeralPayload = $ephemeralPayload | ConvertTo-Json -Depth 20 |
        ConvertFrom-Json -DateKind String
    $emptyEphemeralPayload.reports = @()
    $emptyEphemeralPayload.map_groups = @()
    $emptyEphemeralGate = Assert-CommunityEphemeralSafetyGate `
        -ApiBase 'https://example.test/api' `
        -ExpectedCatalogSha256 $ephemeralCatalogSha256 `
        -Payload $emptyEphemeralPayload `
        -CurrentTimeUtc $ephemeralCurrentTime
    Assert-True (
        $emptyEphemeralGate.ready -eq $true -and
        $emptyEphemeralGate.observed.locationCatalogSha256 -ceq
            $ephemeralCatalogSha256
    ) (
        'An empty Community feed must remain releasable only through its ' +
        'revision-owned safety contract.'
    )

    $ephemeralMutations = @(
        @{ Code = 'response_schema_changed'; Apply = {
            param($copy) $copy | Add-Member -NotePropertyName unexpected `
                -NotePropertyValue $true
        } },
        @{ Code = 'safety_contract_schema_changed'; Apply = {
            param($copy) $copy.contract | Add-Member `
                -NotePropertyName unexpected -NotePropertyValue $true
        } },
        @{ Code = 'source_key_contract_schema_changed'; Apply = {
            param($copy) $copy.contract.public_source_key | Add-Member `
                -NotePropertyName unexpected -NotePropertyValue $true
        } },
        @{ Code = 'safety_contract_version_changed'; Apply = {
            param($copy) $copy.contract.schema_version = 'community-v0'
        } },
        @{ Code = 'contract_allowed_report_types_changed'; Apply = {
            param($copy) $copy.contract.allowed_report_types[0] = 'free'
        } },
        @{ Code = 'contract_create_fields_changed'; Apply = {
            param($copy) $copy.contract.create_fields[0] = 'message'
        } },
        @{ Code = 'contract_public_report_fields_changed'; Apply = {
            param($copy) $copy.contract.public_report_fields[0] = 'owner'
        } },
        @{ Code = 'contract_confirmation_fields_changed'; Apply = {
            param($copy) $copy.contract.confirmation_fields[0] = 'maybe'
        } },
        @{ Code = 'contract_accepts_free_text_enabled'; Apply = {
            param($copy) $copy.contract.accepts_free_text = $true
        } },
        @{ Code = 'contract_user_flag_visibility_changed'; Apply = {
            param($copy) $copy.contract.user_flag_visibility = 'global'
        } },
        @{ Code = 'contract_automatic_global_hide_enabled'; Apply = {
            param($copy) $copy.contract.automatic_global_hide = $true
        } },
        @{ Code = 'contract_location_catalog_changed'; Apply = {
            param($copy) $copy.contract.location_catalog_sha256 = ('f' * 64)
        } },
        @{ Code = 'contract_catalog_digest_algorithm_changed'; Apply = {
            param($copy) $copy.contract.location_catalog_digest_algorithm = `
                'sha256-json-v0'
        } },
        @{ Code = 'municipality_scope_invalid'; Apply = {
            param($copy) $copy.locations[15].istatCode = '093033'
        } },
        @{ Code = 'public_ttl_not_one_hour'; Apply = {
            param($copy) $copy.ttl_seconds = 7200
        } },
        @{ Code = 'cooldown_contract_changed'; Apply = {
            param($copy) $copy.cooldown_seconds = 0
        } },
        @{ Code = 'distance_contract_changed'; Apply = {
            param($copy) $copy.max_distance_km = 20
        } },
        @{ Code = 'source_must_remain_unverified'; Apply = {
            param($copy) $copy.source.verified = $true
        } },
        @{ Code = 'source_schema_changed'; Apply = {
            param($copy) $copy.source | Add-Member -NotePropertyName owner `
                -NotePropertyValue 'device'
        } },
        @{ Code = 'source_id_changed'; Apply = {
            param($copy) $copy.source.id = 'legacy_reports'
        } },
        @{ Code = 'municipality_scope_changed'; Apply = {
            param($copy) $copy.locations = @()
        } },
        @{ Code = 'scope_contract_changed'; Apply = {
            param($copy) $copy.scope.radiusKm = 50
        } },
        @{ Code = 'open_or_unknown_report_type'; Apply = {
            param($copy) $copy.reports[0].typeId = 'free-text'
        } },
        @{ Code = 'public_location_not_zonal'; Apply = {
            param($copy) $copy.reports[0].locationPrecision = 'gps'
        } },
        @{ Code = 'precise_coordinates_exposed'; Apply = {
            param($copy) $copy.reports[0].lat = 45.9999
        } },
        @{ Code = 'public_item_ttl_changed'; Apply = {
            param($copy) $copy.reports[0].expiresAt += 3600000
        } },
        @{ Code = 'generated_at_stale'; Apply = {
            param($copy)
            $copy.generated_at = $ephemeralGeneratedAt.AddMinutes(-10).ToString('o')
        } },
        @{ Code = 'generated_at_future'; Apply = {
            param($copy)
            $copy.generated_at = $ephemeralCurrentTime.AddMinutes(10).ToString('o')
        } },
        @{ Code = 'public_item_not_active_at_generation'; Apply = {
            param($copy)
            $copy.reports[0].createdAt = `
                $ephemeralGeneratedAt.ToUnixTimeMilliseconds() + 1000
            $copy.reports[0].expiresAt = $copy.reports[0].createdAt + 3600000
        } },
        @{ Code = 'public_location_coordinate_invalid'; Apply = {
            param($copy) $copy.reports[0].lat = 'NaN'
        } },
        @{ Code = 'public_map_coordinate_invalid'; Apply = {
            param($copy) $copy.reports[0].x = 'Infinity'
        } },
        @{ Code = 'public_source_key_not_ephemeral_hash'; Apply = {
            param($copy) $copy.reports[0].sourceKey = 'device-one'
        } },
        @{ Code = 'public_report_id_invalid'; Apply = {
            param($copy) $copy.reports[0].id = 'community-one'
        } },
        @{ Code = 'public_group_id_invalid'; Apply = {
            param($copy)
            $copy.map_groups[0].id = 'group-one'
            $copy.map_groups[0].groupId = 'group-one'
        } },
        @{ Code = 'public_confirmation_schema_changed'; Apply = {
            param($copy) $copy.map_groups[0].confirmations | Add-Member `
                -NotePropertyName maybe -NotePropertyValue 0
        } },
        @{ Code = 'public_item_schema_changed'; Apply = {
            param($copy) $copy.reports[0] | Add-Member -NotePropertyName message `
                -NotePropertyValue 'testo libero'
        } }
    )
    foreach ($mutation in $ephemeralMutations) {
        $copy = $ephemeralPayload | ConvertTo-Json -Depth 12 |
            ConvertFrom-Json -DateKind String
        & $mutation.Apply $copy
        Assert-ThrowsCode {
            Assert-CommunityEphemeralSafetyGate `
                -ApiBase 'https://example.test/api' `
                -ExpectedCatalogSha256 $ephemeralCatalogSha256 `
                -Payload $copy `
                -CurrentTimeUtc $ephemeralCurrentTime | Out-Null
        } "release_android_play_community_ephemeral_gate_failed: $($mutation.Code)"
    }

    $communityGateTemporaryBase = Join-Path $temporaryRoot 'community-gate'
    New-Item -ItemType Directory -Path $communityGateTemporaryBase | Out-Null
    $fakeCommunityAudit = Join-Path $temporaryRoot 'fake-community-ttl-audit.ps1'
    [IO.File]::WriteAllText(
        $fakeCommunityAudit,
        @'
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$Account = "missing-account",
    [string]$ProjectId = "missing-project",
    [string]$DatabaseId = "missing-database",
    [string]$GcloudPath = ""
)
$sourceMode = if ($GcloudPath -ceq "fixture") {
    "fixture-read-only"
} else {
    "live-read-only"
}
$activeAccount = if ($GcloudPath -ceq "wrong-account") {
    "other@example.com"
} else {
    $Account
}
$evidenceProjectId = if ($GcloudPath -ceq "wrong-project") {
    "other-project"
} else {
    $ProjectId
}
$databaseName = if ($GcloudPath -ceq "wrong-database") {
    "projects/meteo-friul/databases/other"
} else {
    "projects/$ProjectId/databases/$DatabaseId"
}
$blocked = $GcloudPath -ceq "blocked"
$contracts = @(
    @("community_reports", "created_at_timestamp"),
    @("community_report_cooldowns", "updated_at"),
    @("community_report_confirmations", "updated_at"),
    @("community_report_flags", "created_at_timestamp"),
    @("community_report_moderation", "updated_at"),
    @("community_source_blocks", "updated_at"),
    @("community_report_rate_limits", "updated_at"),
    @("community_moderation_digest_state", "updated_at_timestamp"),
    @("community_reputation", "updated_at"),
    @("community_reputation_awards", "updated_at")
)
$policies = @($contracts | ForEach-Object {
    [ordered]@{
        collectionGroup = $_[0]
        field = "expires_at_timestamp"
        state = "ACTIVE"
        expirationOffset = "0s"
    }
})
$collections = @($contracts | ForEach-Object {
    [ordered]@{
        collectionGroup = $_[0]
        expiryField = "expires_at_timestamp"
        baselineField = $_[1]
        documentCount = 0
        validHorizonSampleCount = 0
    }
})
$payload = [ordered]@{
    schemaVersion = "firestore-community-ttl-audit-v2"
    sourceMode = $sourceMode
    ready = -not $blocked
    identityReady = $true
    policyReady = $true
    documentReady = $true
    sampleCoverageComplete = $false
    blockingCount = if ($blocked) { 1 } else { 0 }
    findings = if ($blocked) {
        @([ordered]@{ code = "contract_blocker"; blocking = $true })
    } else {
        @()
    }
    identity = [ordered]@{
        activeAccount = $activeAccount
        activeAccountCount = 1
        configuredAccount = $Account
        configuredProject = $ProjectId
        projectId = $evidenceProjectId
        projectNumber = "49007668366"
        projectState = "ACTIVE"
        databaseName = $databaseName
        databaseType = "FIRESTORE_NATIVE"
    }
    policies = $policies
    collections = $collections
    testOutputPath = $OutputPath
}
[IO.File]::WriteAllText(
    $OutputPath,
    ($payload | ConvertTo-Json -Depth 10),
    [Text.UTF8Encoding]::new($false)
)
'@,
        [Text.UTF8Encoding]::new($false)
    )
    $communityGate = Assert-FirestoreCommunityTtlGate `
        -AuditScriptPath $fakeCommunityAudit `
        -GcloudExecutable 'contract-live' `
        -TemporaryBasePath $communityGateTemporaryBase
    Assert-True ($communityGate.sourceMode -ceq 'live-read-only') `
        'Live community TTL evidence was not accepted.'
    Assert-True ($communityGate.sampleCoverageComplete -eq $false) `
        'Fresh gate incorrectly requires concurrent non-empty samples.'
    Assert-True (@($communityGate.collections | Where-Object {
        [int]$_.documentCount -ne 0
    }).Count -eq 0) 'Fresh gate fixture must exercise empty collections.'
    Assert-True (
        [IO.Path]::GetFullPath([string]$communityGate.testOutputPath).StartsWith(
            [IO.Path]::GetFullPath($communityGateTemporaryBase),
            [StringComparison]::OrdinalIgnoreCase
        )
    ) 'Community TTL gate did not use temporary evidence.'
    Assert-True (-not (Test-Path -LiteralPath $communityGate.testOutputPath)) `
        'Community TTL gate retained temporary evidence.'
    Assert-True (@(
        Get-ChildItem -LiteralPath $communityGateTemporaryBase -Force
    ).Count -eq 0) 'Community TTL gate retained its temporary directory.'

    foreach ($failClosedCase in @(
        @('fixture', 'source_mode=fixture-read-only'),
        @('wrong-account', 'identity_mismatch'),
        @('wrong-project', 'identity_mismatch'),
        @('wrong-database', 'identity_mismatch'),
        @('blocked', 'contract_blocker')
    )) {
        Assert-ThrowsCode {
            Assert-FirestoreCommunityTtlGate `
                -AuditScriptPath $fakeCommunityAudit `
                -GcloudExecutable $failClosedCase[0] `
                -TemporaryBasePath $communityGateTemporaryBase | Out-Null
        } $failClosedCase[1]
    }

    $historicalRoot = Join-Path $temporaryRoot 'community-history-repository'
    $historicalDirectory = Join-Path $historicalRoot (
        'release-history\firestore-community-ttl'
    )
    New-Item -ItemType Directory -Path $historicalDirectory | Out-Null
    foreach ($relativeSource in @(
        (Get-CommunityTtlWriterContract -RepositoryRoot $workspaceRoot).files
    )) {
        $source = Join-Path $workspaceRoot (
            $relativeSource.Replace('/', [IO.Path]::DirectorySeparatorChar)
        )
        $destination = Join-Path $historicalRoot (
            $relativeSource.Replace('/', [IO.Path]::DirectorySeparatorChar)
        )
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) |
            Out-Null
        [IO.File]::WriteAllBytes(
            $destination,
            [IO.File]::ReadAllBytes($source)
        )
    }
    foreach ($arguments in @(
        @('init'),
        @('config', 'user.email', 'contract@example.invalid'),
        @('config', 'user.name', 'Contract Test'),
        @('add', 'backend', 'scripts'),
        @('commit', '-m', 'add authoritative backend writers')
    )) {
        $gitResult = Invoke-NativeCapture `
            -Executable 'git' `
            -Arguments (@('-C', $historicalRoot) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) (
            "Community writer Git fixture setup failed: $($gitResult.Output)"
        )
    }
    $gitResult = Invoke-NativeCapture `
        -Executable 'git' `
        -Arguments @('-C', $historicalRoot, 'rev-parse', 'HEAD')
    Assert-True ($gitResult.ExitCode -eq 0) (
        "Community writer commit lookup failed: $($gitResult.Output)"
    )
    $authoritativeBackendCommit = $gitResult.Output.Trim()
    $historicalContract = Get-CommunityTtlWriterContractFromGitCommit `
        -RepositoryRoot $historicalRoot `
        -Commit $authoritativeBackendCommit
    $historicalCapturedAt = [DateTimeOffset]::UtcNow.AddDays(-1)
    $historicalRecordedAt = $historicalCapturedAt.AddMinutes(1)
    $historicalContracts = @(Get-CommunityTtlAuditContract)
    $historicalPolicies = @($historicalContracts | ForEach-Object {
        [ordered]@{
            collectionGroup = [string]$_.collectionGroup
            field = [string]$_.field
            state = 'ACTIVE'
            expirationOffset = '0s'
        }
    })
    $historicalCollections = @($historicalContracts | ForEach-Object {
        $sampleHorizon = if ([double]$_.minimumHorizonSeconds -gt 0) {
            [double]$_.minimumHorizonSeconds
        } else {
            [Math]::Min(60.0, [double]$_.maximumHorizonSeconds)
        }
        [ordered]@{
            collectionGroup = [string]$_.collectionGroup
            expiryField = [string]$_.field
            baselineField = [string]$_.baselineField
            contractualMinimumHorizonSeconds = [double]$_.minimumHorizonSeconds
            contractualMaximumHorizonSeconds = [double]$_.maximumHorizonSeconds
            documentCount = 1
            validHorizonSampleCount = 1
            recentHorizonSampleCount = 1
            missingExpiryCount = 0
            wrongExpiryTypeCount = 0
            invalidExpiryCount = 0
            missingBaselineCount = 0
            wrongBaselineTypeCount = 0
            invalidBaselineCount = 0
            futureBaselineCount = 0
            expiredDocumentCount = 0
            expiredBeyondGraceCount = 0
            belowMinimumHorizonCount = 0
            aboveMaximumHorizonCount = 0
            minimumObservedHorizonSeconds = $sampleHorizon
            maximumObservedHorizonSeconds = $sampleHorizon
        }
    })
    $historicalEvidenceCore = [PSCustomObject][ordered]@{
        schemaVersion = 'firestore-community-ttl-historical-evidence-v2'
        evidenceKind = 'historical-live-writer-samples'
        sourceMode = 'live-read-only'
        capturedAtUtc = $historicalCapturedAt.ToString('o')
        recordedAtUtc = $historicalRecordedAt.ToString('o')
        auditSchemaVersion = 'firestore-community-ttl-audit-v2'
        ready = $true
        identityReady = $true
        policyReady = $true
        documentReady = $true
        sampleCoverageComplete = $true
        blockingCount = 0
        identity = [ordered]@{
            activeAccount = 'meteofriul@gmail.com'
            activeAccountCount = 1
            configuredAccount = 'meteofriul@gmail.com'
            configuredProject = 'meteo-friul'
            projectId = 'meteo-friul'
            projectNumber = '49007668366'
            projectState = 'ACTIVE'
            databaseName = 'projects/meteo-friul/databases/(default)'
            databaseType = 'FIRESTORE_NATIVE'
        }
        policies = $historicalPolicies
        collections = $historicalCollections
        writerContract = $historicalContract
    }
    $historicalNonce = 'b' * 64
    $historicalAttestationEvent = New-CommunityTtlCloudAttestationEvent `
        -EvidenceCore $historicalEvidenceCore `
        -Nonce $historicalNonce
    $historicalLogEntry = [PSCustomObject]@{
        logName = (
            'projects/meteo-friul/logs/' +
            'meteofriul-community-ttl-evidence'
        )
        timestamp = $historicalRecordedAt.AddSeconds(1).ToString('o')
        jsonPayload = $historicalAttestationEvent
    }
    $historicalEvidence = Complete-FirestoreCommunityTtlHistoricalEvidence `
        -EvidenceCore $historicalEvidenceCore `
        -CloudLogEntry $historicalLogEntry `
        -ExpectedNonce $historicalNonce
    $historicalCloudReader = {
        param($Attestation)
        return @($historicalLogEntry)
    }
    $historicalPath = Join-Path $historicalDirectory (
        '20260824T120000000Z-community-ttl.evidence.json'
    )
    Write-TestJson -Path $historicalPath -Payload $historicalEvidence
    $historicalState = Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
        -RepositoryRoot $historicalRoot `
        -EvidenceDirectory $historicalDirectory `
        -AuthoritativeBackendCommit $authoritativeBackendCommit `
        -CloudAttestationReader $historicalCloudReader `
        -NowUtc ([DateTimeOffset]::UtcNow)
    Assert-True ($historicalState.CollectionCount -eq 10) (
        'Protected build did not accept complete historical sample coverage.'
    )
    Assert-True (
        $historicalState.WriterContractSha256 -ceq $historicalContract.sha256
    ) 'Protected build did not bind the current writer contract.'
    $validHistoricalJson = Get-Content -LiteralPath $historicalPath -Raw
    $duplicateHistoricalJson = (
        '{"sourceMode":"report_id=private;lat=46.1;lon=13.2",' +
        $validHistoricalJson.TrimStart().Substring(1)
    )
    [IO.File]::WriteAllText(
        $historicalPath,
        $duplicateHistoricalJson,
        [Text.UTF8Encoding]::new($false)
    )
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'invalid_json'
    Write-TestJson -Path $historicalPath -Payload $historicalEvidence
    $missingCloudReader = { param($Attestation); return @() }
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $missingCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'cloud_attestation_failed:community_ttl_cloud_attestation_readback_count_invalid'
    $forgedCloudEntry = $historicalLogEntry | ConvertTo-Json -Depth 12 |
        ConvertFrom-Json -DateKind String
    $forgedCloudEntry.jsonPayload.evidenceCoreSha256 = '0' * 64
    $forgedCloudReader = {
        param($Attestation)
        return @($forgedCloudEntry)
    }
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $forgedCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'cloud_attestation_failed:community_ttl_cloud_attestation_event_mismatch'

    $fixtureHistorical = $historicalEvidence | ConvertTo-Json -Depth 12 |
        ConvertFrom-Json -DateKind String
    $fixtureHistorical.sourceMode = 'fixture-read-only'
    Write-TestJson -Path $historicalPath -Payload $fixtureHistorical
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'fixture_rejected'

    $wrongIdentityHistorical = $historicalEvidence | ConvertTo-Json -Depth 12 |
        ConvertFrom-Json -DateKind String
    $wrongIdentityHistorical.identity.projectId = 'other-project'
    Write-TestJson -Path $historicalPath -Payload $wrongIdentityHistorical
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'identity_mismatch'

    $wrongHashHistorical = $historicalEvidence | ConvertTo-Json -Depth 12 |
        ConvertFrom-Json -DateKind String
    $wrongHashHistorical.writerContract.sha256 = '0' * 64
    Write-TestJson -Path $historicalPath -Payload $wrongHashHistorical
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'writer_contract_hash_mismatch'

    Write-TestJson -Path $historicalPath -Payload $historicalEvidence
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $authoritativeBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc $historicalCapturedAt.AddDays(31) | Out-Null
    } 'historical_evidence_stale'

    foreach ($arguments in @(
        @('add', 'release-history'),
        @('commit', '-m', 'add immutable community TTL evidence')
    )) {
        $gitResult = Invoke-NativeCapture `
            -Executable 'git' `
            -Arguments (@('-C', $historicalRoot) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) (
            "Community evidence Git fixture setup failed: $($gitResult.Output)"
        )
    }
    $immutableState = Assert-FirestoreCommunityTtlEvidenceGitImmutability `
        -RepositoryRoot $historicalRoot `
        -EvidenceDirectory $historicalDirectory
    Assert-True ($immutableState.RecordCount -eq 1) (
        'Committed add-only community evidence was not accepted.'
    )

    $gitResult = Invoke-NativeCapture `
        -Executable 'git' `
        -Arguments @('-C', $historicalRoot, 'rev-parse', 'HEAD')
    Assert-True ($gitResult.ExitCode -eq 0) (
        "Unchanged descendant commit lookup failed: $($gitResult.Output)"
    )
    $unchangedDescendantCommit = $gitResult.Output.Trim()
    $unchangedDescendantState = `
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $unchangedDescendantCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow)
    Assert-True (
        $unchangedDescendantState.AuthoritativeBackendCommit -ceq
            $unchangedDescendantCommit
    ) 'Backend descendant with unchanged writers must pass.'

    $changedBackendSource = Join-Path $temporaryRoot (
        'changed-backend-community.py'
    )
    $currentWriterPath = Join-Path $historicalRoot (
        'backend\app\repositories\community.py'
    )
    [IO.File]::WriteAllText(
        $changedBackendSource,
        ([IO.File]::ReadAllText($currentWriterPath) +
            "`n# authoritative-backend-mismatch-contract-test`n"),
        [Text.UTF8Encoding]::new($false)
    )
    $gitResult = Invoke-NativeCapture `
        -Executable 'git' `
        -Arguments @('-C', $historicalRoot, 'hash-object', '-w', '--', $changedBackendSource)
    Assert-True ($gitResult.ExitCode -eq 0) (
        "Changed backend blob creation failed: $($gitResult.Output)"
    )
    $changedBackendBlobRows = @(
        $gitResult.Output -split '\r?\n' |
            ForEach-Object { ([string]$_).Trim() } |
            Where-Object { $_ -cmatch '^[0-9a-f]{40}$' }
    )
    Assert-True ($changedBackendBlobRows.Count -eq 1) (
        "Changed backend blob digest invalid: $($gitResult.Output)"
    )
    $changedBackendBlob = $changedBackendBlobRows[0]
    $temporaryIndex = Join-Path $temporaryRoot 'changed-backend.index'
    $previousGitIndexFile = $env:GIT_INDEX_FILE
    try {
        $env:GIT_INDEX_FILE = $temporaryIndex
        foreach ($arguments in @(
            @('read-tree', $unchangedDescendantCommit),
            @(
                'update-index', '--add', '--cacheinfo', '100644',
                $changedBackendBlob, 'backend/app/repositories/community.py'
            )
        )) {
            $gitResult = Invoke-NativeCapture `
                -Executable 'git' `
                -Arguments (@('-C', $historicalRoot) + $arguments)
            Assert-True ($gitResult.ExitCode -eq 0) (
                "Changed backend tree setup failed: $($gitResult.Output)"
            )
        }
        $gitResult = Invoke-NativeCapture `
            -Executable 'git' `
            -Arguments @('-C', $historicalRoot, 'write-tree')
        Assert-True ($gitResult.ExitCode -eq 0) (
            "Changed backend tree write failed: $($gitResult.Output)"
        )
        $changedBackendTree = $gitResult.Output.Trim()
        $gitResult = Invoke-NativeCapture `
            -Executable 'git' `
            -Arguments @(
                '-C', $historicalRoot, 'commit-tree', $changedBackendTree,
                '-p', $unchangedDescendantCommit,
                '-m', 'changed authoritative backend writer'
            )
        Assert-True ($gitResult.ExitCode -eq 0) (
            "Changed backend commit creation failed: $($gitResult.Output)"
        )
        $changedBackendCommit = $gitResult.Output.Trim()
    } finally {
        if ($null -eq $previousGitIndexFile) {
            Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
        } else {
            $env:GIT_INDEX_FILE = $previousGitIndexFile
        }
        if (Test-Path -LiteralPath $temporaryIndex) {
            Remove-Item -LiteralPath $temporaryIndex -Force
        }
    }
    $changedWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
        -RepositoryRoot $historicalRoot `
        -Commit $changedBackendCommit
    Assert-True ($changedWriterContract.sha256 -cne $historicalContract.sha256) (
        'Backend writer fixture change did not change deterministic SHA-256.'
    )
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory `
            -AuthoritativeBackendCommit $changedBackendCommit `
            -CloudAttestationReader $historicalCloudReader `
            -NowUtc ([DateTimeOffset]::UtcNow) | Out-Null
    } 'backend_writer_contract_hash_mismatch'

    [IO.File]::AppendAllText(
        $historicalPath,
        [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlEvidenceGitImmutability `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory | Out-Null
    } 'worktree_not_clean'
    Write-TestJson -Path $historicalPath -Payload $historicalEvidence

    $untrackedHistorical = Join-Path $historicalDirectory (
        '20990101T000000000Z-community-ttl.evidence.json'
    )
    Write-TestJson -Path $untrackedHistorical -Payload $historicalEvidence
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlEvidenceGitImmutability `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory | Out-Null
    } 'worktree_not_clean'
    Remove-Item -LiteralPath $untrackedHistorical -Force

    [IO.File]::AppendAllText(
        $historicalPath,
        [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false)
    )
    foreach ($arguments in @(
        @(
            'add', '--',
            'release-history/firestore-community-ttl/20260824T120000000Z-community-ttl.evidence.json'
        ),
        @('commit', '-m', 'tamper immutable community TTL evidence')
    )) {
        $gitResult = Invoke-NativeCapture `
            -Executable 'git' `
            -Arguments (@('-C', $historicalRoot) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) (
            "Community evidence Git mutation failed: $($gitResult.Output)"
        )
    }
    Assert-ThrowsCode {
        Assert-FirestoreCommunityTtlEvidenceGitImmutability `
            -RepositoryRoot $historicalRoot `
            -EvidenceDirectory $historicalDirectory | Out-Null
    } 'record_was_modified'

    $dummyBundletool = Join-Path $temporaryRoot 'bundletool-test.jar'
    [IO.File]::WriteAllBytes($dummyBundletool, [byte[]](1, 3, 3, 7))
    $dummyHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dummyBundletool).Hash
    $trustedTool = Assert-PlayBundletoolTrust -Path $dummyBundletool -ExpectedSha256 $dummyHash
    Assert-True ($trustedTool.Sha256 -ceq $dummyHash.ToLowerInvariant()) `
        'Exact bundletool SHA-256 was not accepted.'
    Assert-ThrowsCode {
        Assert-PlayBundletoolTrust -Path $dummyBundletool -ExpectedSha256 ('0' * 64)
    } 'release_android_play_bundletool_sha256_mismatch'

    $validGoogleServices = [ordered]@{
        project_info = [ordered]@{
            project_number = '49007668366'
            project_id = 'meteo-friul'
        }
        client = @(
            [ordered]@{
                client_info = [ordered]@{
                    mobilesdk_app_id = '1:49007668366:android:725bf6f8b339177a852ddf'
                    android_client_info = [ordered]@{ package_name = 'com.meteofriul.app' }
                }
            }
        )
    }
    $googleServices = Join-Path $temporaryRoot 'google-services.json'
    Write-TestJson -Path $googleServices -Payload $validGoogleServices
    $firebaseIdentity = Assert-PlayGoogleServicesConfiguration -Path $googleServices
    Assert-True ($firebaseIdentity.ProjectId -ceq 'meteo-friul') `
        'Approved Firebase project was not accepted.'
    $validGoogleServices.project_info.project_id = 'wrong-project'
    Write-TestJson -Path $googleServices -Payload $validGoogleServices
    Assert-ThrowsCode {
        Assert-PlayGoogleServicesConfiguration -Path $googleServices
    } 'release_android_play_firebase_project_mismatch'

    $ledgerDirectory = Join-Path $temporaryRoot 'ledger'
    New-Item -ItemType Directory -Path $ledgerDirectory | Out-Null
    $certificateA = 'a' * 64
    $certificateB = 'b' * 64
    $certificateC = 'c' * 64
    $aabHash = 'd' * 64
    $reservation10 = Join-Path $ledgerDirectory 'meteofriul-10-1.0.0.reservation.json'
    Write-NewPlayJsonFile -Path $reservation10 -Payload ([ordered]@{
        Kind = 'play-version-reservation'
        Status = 'reserved'
        VersionCode = 10
        VersionName = '1.0.0'
    }) | Out-Null
    $release10 = Join-Path $ledgerDirectory 'meteofriul-10-1.0.0.release.json'
    Write-NewPlayJsonFile -Path $release10 -Payload ([ordered]@{
        Target = 'android-play'
        Status = 'built-not-uploaded'
        VersionCode = 10
        VersionName = '1.0.0'
        UploadCertificateSha256 = $certificateA
        AabSha256 = $aabHash
    }) | Out-Null
    $reservation12 = Join-Path $ledgerDirectory 'meteofriul-12-1.0.2.reservation.json'
    Write-NewPlayJsonFile -Path $reservation12 -Payload ([ordered]@{
        Kind = 'play-version-reservation'
        Status = 'reserved'
        VersionCode = 12
        VersionName = '1.0.2'
    }) | Out-Null
    $abandoned12 = Join-Path $ledgerDirectory '20260823T120000000Z-abandoned.evidence.json'
    Write-NewPlayJsonFile -Path $abandoned12 -Payload ([ordered]@{
        CreatedAtUtc = '2026-08-23T12:00:00Z'
        Event = 'abandoned'
        VersionCode = 12
        VersionName = '1.0.2'
        Reason = 'Contract fixture: candidate intentionally abandoned.'
    }) | Out-Null

    $ledger = Read-PlayReleaseLedger -Directory $ledgerDirectory
    $candidate = Assert-PlayCandidateVersion `
        -CandidateVersionCode 13 `
        -CandidateVersionName '1.0.3' `
        -LatestConsoleVersionCode 8 `
        -ExistingVersions $ledger.AllVersions
    Assert-True ($candidate.RequiredAboveVersionCode -eq 12) `
        'Candidate must be above every reserved/built version, even when Console is behind.'
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion `
            -CandidateVersionCode 10 `
            -CandidateVersionName '1.0.9' `
            -LatestConsoleVersionCode 8 `
            -ExistingVersions $ledger.AllVersions
    } 'release_android_play_candidate_version_reserved'
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion `
            -CandidateVersionCode 13 `
            -CandidateVersionName '1.0.3' `
            -LatestConsoleVersionCode 13 `
            -ExistingVersions $ledger.AllVersions
    } 'release_android_play_version_not_incremented'

    # Retry only the display name of a validated abandoned, unbuilt reservation.
    Assert-PlayCandidateVersion -CandidateVersionCode 13 -CandidateVersionName '1.0.2' `
        -LatestConsoleVersionCode 10 -ExistingVersions $ledger.AllVersions | Out-Null
    Assert-AndroidReleaseVersionHistory -CandidateVersionCode 13 -CandidateVersionName '1.0.2' `
        -ExistingReleases $ledger.AllVersions | Out-Null
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion -CandidateVersionCode 12 -CandidateVersionName '1.0.2' `
            -LatestConsoleVersionCode 10 -ExistingVersions $ledger.AllVersions
    } 'release_android_play_candidate_version_reserved'
    Assert-ThrowsCode {
        Assert-AndroidReleaseVersionHistory -CandidateVersionCode 12 -CandidateVersionName '1.0.2' `
            -ExistingReleases $ledger.AllVersions
    } 'release_android_version_already_exists'
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion -CandidateVersionCode 13 -CandidateVersionName '1.0.0' `
            -LatestConsoleVersionCode 10 -ExistingVersions $ledger.AllVersions
    } 'release_android_play_candidate_version_reserved'

    $retry13 = Join-Path $ledgerDirectory 'meteofriul-13-1.0.2.reservation.json'
    Write-NewPlayJsonFile -Path $retry13 -Payload ([ordered]@{
        Kind = 'play-version-reservation'; Status = 'reserved'
        VersionCode = 13; VersionName = '1.0.2'
    }) | Out-Null
    $retryLedger = Read-PlayReleaseLedger -Directory $ledgerDirectory
    Assert-True ($retryLedger.MaxReservedVersionCode -eq 13) 'Retry must preserve maximum code.'
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion -CandidateVersionCode 14 -CandidateVersionName '1.0.2' `
            -LatestConsoleVersionCode 10 -ExistingVersions $retryLedger.AllVersions
    } 'release_android_play_candidate_version_reserved'
    Assert-ThrowsCode {
        Assert-AndroidReleaseVersionHistory -CandidateVersionCode 14 -CandidateVersionName '1.0.2' `
            -ExistingReleases $retryLedger.AllVersions
    } 'release_android_version_already_exists'
    # Removing the terminal proof makes two open reservations conflict again.
    $abandoned12Bytes = [IO.File]::ReadAllBytes($abandoned12)
    Remove-Item -LiteralPath $abandoned12
    Assert-ThrowsCode { Read-PlayReleaseLedger -Directory $ledgerDirectory } `
        'release_android_play_version_name_conflict'
    [IO.File]::WriteAllBytes($abandoned12, $abandoned12Bytes)
    Remove-Item -LiteralPath $retry13
    # Even an abandoned version cannot retry its name once a bundle exists.
    $built12 = Join-Path $ledgerDirectory 'meteofriul-12-1.0.2.release.json'
    Write-NewPlayJsonFile -Path $built12 -Payload ([ordered]@{
        Target = 'android-play'; Status = 'built-not-uploaded'
        VersionCode = 12; VersionName = '1.0.2'
        UploadCertificateSha256 = $certificateA; AabSha256 = $aabHash
    }) | Out-Null
    $builtLedger = Read-PlayReleaseLedger -Directory $ledgerDirectory
    Assert-ThrowsCode {
        Assert-PlayCandidateVersion -CandidateVersionCode 13 -CandidateVersionName '1.0.2' `
            -LatestConsoleVersionCode 10 -ExistingVersions $builtLedger.AllVersions
    } 'release_android_play_candidate_version_reserved'
    Assert-ThrowsCode {
        Assert-AndroidReleaseVersionHistory -CandidateVersionCode 13 -CandidateVersionName '1.0.2' `
            -ExistingReleases $builtLedger.AllVersions
    } 'release_android_version_already_exists'
    Remove-Item -LiteralPath $built12
    $ledger = Read-PlayReleaseLedger -Directory $ledgerDirectory

    Assert-ThrowsCode {
        Resolve-PlayUploadCertificateTrust `
            -CandidateCertificateSha256 $certificateA `
            -Ledger $ledger
    } 'release_android_play_upload_trust_anchor_required'
    $explicitTrust = Resolve-PlayUploadCertificateTrust `
        -CandidateCertificateSha256 $certificateB `
        -ExplicitExpectedCertificateSha256 $certificateB `
        -Ledger $ledger
    Assert-True ($explicitTrust.Source -ceq 'explicit-first-upload-anchor') `
        'A built-not-uploaded certificate must not become a trust anchor.'

    $acceptance = Join-Path $ledgerDirectory '20260823T130000000Z-play-accepted.evidence.json'
    Write-NewPlayJsonFile -Path $acceptance -Payload ([ordered]@{
        CreatedAtUtc = '2026-08-23T13:00:00Z'
        Event = 'play-accepted'
        VersionCode = 10
        VersionName = '1.0.0'
        AabSha256 = $aabHash
        UploadCertificateSha256 = $certificateA
        LatestConsoleVersionCode = 10
        EvidenceReference = 'Play Console contract fixture'
    }) | Out-Null
    $ledger = Read-PlayReleaseLedger -Directory $ledgerDirectory
    $acceptedTrust = Resolve-PlayUploadCertificateTrust `
        -CandidateCertificateSha256 $certificateA `
        -Ledger $ledger
    Assert-True ($acceptedTrust.Source -ceq 'latest-play-accepted') `
        'Play-accepted evidence did not become the upload trust anchor.'

    $rotation = Join-Path $ledgerDirectory '20260823T140000000Z-upload-key-rotation.evidence.json'
    Write-NewPlayJsonFile -Path $rotation -Payload ([ordered]@{
        CreatedAtUtc = '2026-08-23T14:00:00Z'
        Event = 'upload-key-rotation'
        PreviousUploadCertificateSha256 = $certificateA
        NewUploadCertificateSha256 = $certificateB
        EvidenceReference = 'Play Console rotation contract fixture'
    }) | Out-Null
    $ledger = Read-PlayReleaseLedger -Directory $ledgerDirectory
    $rotatedTrust = Resolve-PlayUploadCertificateTrust `
        -CandidateCertificateSha256 $certificateB `
        -Ledger $ledger
    Assert-True ($rotatedTrust.Source -ceq 'append-only-rotation-evidence') `
        'Append-only rotation evidence was not followed.'
    Assert-ThrowsCode {
        Resolve-PlayUploadCertificateTrust `
            -CandidateCertificateSha256 $certificateC `
            -Ledger $ledger
    } 'release_android_play_upload_certificate_untrusted'

    # The trust ledger is append-only at the Git-history level, not merely at
    # write time. In particular, a previously accepted upload certificate must
    # never be replaceable by editing its old evidence record.
    $gitLedgerRepository = Join-Path $temporaryRoot 'git-ledger-repository'
    $gitLedgerDirectory = Join-Path $gitLedgerRepository 'release-history\android-play'
    New-Item -ItemType Directory -Path $gitLedgerDirectory | Out-Null
    foreach ($arguments in @(
        @('init'),
        @('config', 'user.email', 'contract-test@meteofriul.invalid'),
        @('config', 'user.name', 'Meteo Friul contract test')
    )) {
        $gitResult = Invoke-NativeCapture -Executable 'git' -Arguments (@('-C', $gitLedgerRepository) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) "Git fixture setup failed: $($gitResult.Output)"
    }
    $acceptedEvidencePath = Join-Path $gitLedgerDirectory '20260823T130000000Z-play-accepted.evidence.json'
    Write-NewPlayJsonFile -Path $acceptedEvidencePath -Payload ([ordered]@{
        CreatedAtUtc = '2026-08-23T13:00:00Z'
        Event = 'play-accepted'
        VersionCode = 10
        VersionName = '1.0.0'
        AabSha256 = $aabHash
        UploadCertificateSha256 = $certificateA
        LatestConsoleVersionCode = 10
        EvidenceReference = 'Immutable Git contract fixture'
    }) | Out-Null
    foreach ($arguments in @(
        @('add', '--all'),
        @('commit', '-m', 'add immutable Play acceptance evidence')
    )) {
        $gitResult = Invoke-NativeCapture -Executable 'git' -Arguments (@('-C', $gitLedgerRepository) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) "Git fixture commit failed: $($gitResult.Output)"
    }
    $immutableLedger = Assert-PlayReleaseLedgerGitImmutability `
        -RepositoryRoot $gitLedgerRepository `
        -LedgerDirectory $gitLedgerDirectory
    Assert-True ($immutableLedger.RecordCount -eq 1) `
        'A single add-only Play evidence record must pass Git immutability.'
    $ledgerAuditOutput = & $ledgerAuditScript `
        -RepositoryRoot $gitLedgerRepository `
        -LedgerDirectory $gitLedgerDirectory
    $ledgerAudit = ($ledgerAuditOutput -join "`n") | ConvertFrom-Json
    Assert-True ($ledgerAudit.Status -ceq 'PASS' -and $ledgerAudit.RecordCount -eq 1) `
        'The public ledger audit wrapper did not validate the real Git fixture.'

    $tamperedEvidence = Get-Content -LiteralPath $acceptedEvidencePath -Raw | ConvertFrom-Json
    $tamperedEvidence.UploadCertificateSha256 = $certificateB
    Write-TestJson -Path $acceptedEvidencePath -Payload $tamperedEvidence
    foreach ($arguments in @(
        @('add', '--all'),
        @('commit', '-m', 'tamper prior Play acceptance evidence')
    )) {
        $gitResult = Invoke-NativeCapture -Executable 'git' -Arguments (@('-C', $gitLedgerRepository) + $arguments)
        Assert-True ($gitResult.ExitCode -eq 0) "Git tamper fixture commit failed: $($gitResult.Output)"
    }
    Assert-ThrowsCode {
        Assert-PlayReleaseLedgerGitImmutability `
            -RepositoryRoot $gitLedgerRepository `
            -LedgerDirectory $gitLedgerDirectory
    } 'release_android_play_ledger_record_was_modified'

    $renamedEvidencePath = Join-Path $gitLedgerDirectory '20260823T130000000Z-renamed.evidence.json'
    $gitResult = Invoke-NativeCapture `
        -Executable 'git' `
        -Arguments @('-C', $gitLedgerRepository, 'mv', $acceptedEvidencePath, $renamedEvidencePath)
    Assert-True ($gitResult.ExitCode -eq 0) "Git rename fixture failed: $($gitResult.Output)"
    $gitResult = Invoke-NativeCapture `
        -Executable 'git' `
        -Arguments @('-C', $gitLedgerRepository, 'commit', '-m', 'rename prior Play evidence')
    Assert-True ($gitResult.ExitCode -eq 0) "Git rename commit failed: $($gitResult.Output)"
    Assert-ThrowsCode {
        Assert-PlayReleaseLedgerGitImmutability `
            -RepositoryRoot $gitLedgerRepository `
            -LedgerDirectory $gitLedgerDirectory
    } 'release_android_play_ledger_record_deleted_or_renamed'

    Assert-ThrowsCode {
        Write-NewPlayJsonFile -Path $reservation10 -Payload @{ overwritten = $true }
    } 'release_android_play_ledger_path_exists'
    $artifactSource = Join-Path $temporaryRoot 'source.aab'
    $artifactDestination = Join-Path $temporaryRoot 'archive.aab'
    [IO.File]::WriteAllBytes($artifactSource, [byte[]](4, 2, 0))
    Copy-NewPlayArtifact -Source $artifactSource -Destination $artifactDestination | Out-Null
    Assert-ThrowsCode {
        Copy-NewPlayArtifact -Source $artifactSource -Destination $artifactDestination
    } 'release_android_artifact_path_exists'

    $evidenceLedgerDirectory = Join-Path $temporaryRoot 'evidence-ledger'
    New-Item -ItemType Directory -Path $evidenceLedgerDirectory | Out-Null
    Write-NewPlayJsonFile `
        -Path (Join-Path $evidenceLedgerDirectory 'meteofriul-20-2.0.0.reservation.json') `
        -Payload ([ordered]@{
            Kind = 'play-version-reservation'
            Status = 'reserved'
            VersionCode = 20
            VersionName = '2.0.0'
        }) | Out-Null
    Write-NewPlayJsonFile `
        -Path (Join-Path $evidenceLedgerDirectory 'meteofriul-20-2.0.0.release.json') `
        -Payload ([ordered]@{
            Target = 'android-play'
            Status = 'built-not-uploaded'
            VersionCode = 20
            VersionName = '2.0.0'
            UploadCertificateSha256 = $certificateA
            AabSha256 = $aabHash
        }) | Out-Null
    & $evidenceScript `
        -Event play-accepted `
        -VersionCode 20 `
        -LatestConsoleVersionCode 20 `
        -EvidenceReference 'Behavioral contract fixture' `
        -LedgerDirectory $evidenceLedgerDirectory | Out-Null
    $recordedEvidence = @(
        Get-ChildItem -LiteralPath $evidenceLedgerDirectory -Filter '*.evidence.json' -File
    )
    Assert-True ($recordedEvidence.Count -eq 1) `
        'Acceptance evidence script did not append exactly one immutable record.'
    Assert-ThrowsCode {
        & $evidenceScript `
            -Event play-accepted `
            -VersionCode 20 `
            -LatestConsoleVersionCode 20 `
            -EvidenceReference 'Duplicate contract fixture' `
            -LedgerDirectory $evidenceLedgerDirectory | Out-Null
    } 'release_android_play_terminal_evidence_already_exists'

    $r8LedgerDirectory = Join-Path $temporaryRoot 'r8-ledger'
    New-Item -ItemType Directory -Path $r8LedgerDirectory | Out-Null
    Write-NewPlayJsonFile `
        -Path (Join-Path $r8LedgerDirectory 'meteofriul-30-3.0.0.reservation.json') `
        -Payload ([ordered]@{
            Kind = 'play-version-reservation'
            Status = 'reserved'
            VersionCode = 30
            VersionName = '3.0.0'
        }) | Out-Null
    $r8ReleasePath = Join-Path $r8LedgerDirectory (
        'meteofriul-30-3.0.0.release.json'
    )
    $r8ReleasePayload = [ordered]@{
        SchemaVersion = 3
        Target = 'android-play'
        Status = 'built-not-uploaded'
        VersionCode = 30
        VersionName = '3.0.0'
        UploadCertificateSha256 = $certificateA
        AabSha256 = $aabHash
        R8Verification = 'external-and-embedded-mapping-match'
        MappingFile = 'meteofriul-30-3.0.0.mapping.txt'
        BundleMappingEntry = `
            'BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map'
        NativeLibraryCount = 4
        NativeSymbolEntryCount = 0
        NativeSymbolsStatus = 'unavailable-transitive-native-libraries'
    }
    Write-TestJson -Path $r8ReleasePath -Payload $r8ReleasePayload
    Assert-ThrowsCode {
        Read-PlayReleaseLedger -Directory $r8LedgerDirectory
    } 'release_android_play_manifest_mapping_sha256_invalid'
    $r8ReleasePayload['MappingSha256'] = 'e' * 64
    Write-TestJson -Path $r8ReleasePath -Payload $r8ReleasePayload
    $r8Ledger = Read-PlayReleaseLedger -Directory $r8LedgerDirectory
    Assert-True ($r8Ledger.Releases[0].SchemaVersion -eq 3) `
        'R8 release manifest schema was not retained by the ledger reader.'
    Assert-True ($r8Ledger.Releases[0].MappingSha256 -ceq ('e' * 64)) `
        'R8 mapping hash was not retained by the ledger reader.'

    $archivePaths = Get-PlayReleaseArchivePaths `
        -WorkspaceRoot $workspaceRoot -VersionCode 13 -VersionName '1.0.3'
    $expectedArchiveRoot = [IO.Path]::GetFullPath(
        (Join-Path $workspaceRoot 'release-artifacts\android-play')
    )
    Assert-True ($archivePaths.Directory -ceq $expectedArchiveRoot) `
        'AAB archive must be durable and outside app/build.'
    Assert-True (-not $archivePaths.Aab.Contains('frontend\android\app\build')) `
        'AAB archive incorrectly points inside the transient Gradle output.'
    Assert-True (-not $archivePaths.Mapping.Contains('frontend\android\app\build')) `
        'R8 mapping archive incorrectly points inside the transient Gradle output.'
    Assert-True ($archivePaths.Mapping.EndsWith('meteofriul-13-1.0.3.mapping.txt')) `
        'R8 mapping archive name is not bound to the release identity.'

    $r8Mapping = Join-Path $temporaryRoot 'mapping.txt'
    [IO.File]::WriteAllText(
        $r8Mapping,
        "com.example.Source -> a:`n    void run() -> a`n",
        [Text.UTF8Encoding]::new($false)
    )
    $r8Bundle = Join-Path $temporaryRoot 'r8-valid.aab'
    $zip = [IO.Compression.ZipFile]::Open(
        $r8Bundle,
        [IO.Compression.ZipArchiveMode]::Create
    )
    try {
        $mappingEntry = $zip.CreateEntry(
            'BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map'
        )
        $mappingEntryStream = $mappingEntry.Open()
        try {
            $mappingBytes = [IO.File]::ReadAllBytes($r8Mapping)
            $mappingEntryStream.Write($mappingBytes, 0, $mappingBytes.Length)
        } finally {
            $mappingEntryStream.Dispose()
        }
        foreach ($entryPath in @(
            'base/lib/arm64-v8a/libfixture.so',
            'BUNDLE-METADATA/com.android.tools.build.debugsymbols/arm64-v8a/libfixture.so.sym'
        )) {
            $entry = $zip.CreateEntry($entryPath)
            $entryStream = $entry.Open()
            try { $entryStream.WriteByte(1) }
            finally { $entryStream.Dispose() }
        }
    } finally {
        $zip.Dispose()
    }
    $r8Artifacts = Assert-PlayR8BundleArtifacts `
        -BundlePath $r8Bundle -MappingPath $r8Mapping
    $expectedMappingSha256 = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $r8Mapping
    ).Hash.ToLowerInvariant()
    Assert-True ($r8Artifacts.MappingSha256 -ceq $expectedMappingSha256) `
        'R8 mapping hash was not computed from the archived mapping source.'
    Assert-True ($r8Artifacts.NativeLibraryCount -eq 1) `
        'R8 artifact verification did not inventory native libraries.'
    Assert-True ($r8Artifacts.NativeSymbolEntryCount -eq 1) `
        'R8 artifact verification did not inventory native debug symbols.'
    Assert-True ($r8Artifacts.NativeSymbolsStatus -ceq 'embedded') `
        'R8 artifact verification did not report embedded native symbols.'

    $r8MismatchedMapping = Join-Path $temporaryRoot 'mapping-mismatch.txt'
    [IO.File]::WriteAllText(
        $r8MismatchedMapping,
        'different mapping',
        [Text.UTF8Encoding]::new($false)
    )
    Assert-ThrowsCode {
        Assert-PlayR8BundleArtifacts `
            -BundlePath $r8Bundle -MappingPath $r8MismatchedMapping
    } 'release_android_play_r8_mapping_bundle_mismatch'

    $r8BundleWithoutMapping = Join-Path $temporaryRoot 'r8-no-mapping.aab'
    $zip = [IO.Compression.ZipFile]::Open(
        $r8BundleWithoutMapping,
        [IO.Compression.ZipArchiveMode]::Create
    )
    try {
        $entry = $zip.CreateEntry('base/manifest/AndroidManifest.xml')
        $entryStream = $entry.Open()
        try { $entryStream.WriteByte(1) }
        finally { $entryStream.Dispose() }
    } finally {
        $zip.Dispose()
    }
    Assert-ThrowsCode {
        Assert-PlayR8BundleArtifacts `
            -BundlePath $r8BundleWithoutMapping -MappingPath $r8Mapping
    } 'release_android_play_r8_bundle_mapping_invalid'

    foreach ($testCase in @(
        @('assembleRelease', $true),
        @('bundleRelease', $true),
        @('signReleaseBundle', $true),
        @('packageReleaseBundle', $true),
        @('finalizeBundleReleaseResources', $true),
        @('publishReleaseBundle', $true),
        @('compileReleaseJavaWithJavac', $false),
        @('assembleDebug', $false),
        @('printPlayReleaseIdentity', $false)
    )) {
        $actual = Test-PlayReleaseProducingTaskName -TaskName $testCase[0]
        Assert-True ($actual -eq $testCase[1]) `
            "Task classification mismatch: $($testCase[0])"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $unsignedArchive = Join-Path $temporaryRoot 'unsigned.aab'
    $zip = [IO.Compression.ZipFile]::Open(
        $unsignedArchive,
        [IO.Compression.ZipArchiveMode]::Create
    )
    try {
        $entry = $zip.CreateEntry('base/manifest/AndroidManifest.xml')
        $writer = [IO.StreamWriter]::new($entry.Open())
        try { $writer.Write('<manifest package="com.meteofriul.app"/>') }
        finally { $writer.Dispose() }
    } finally {
        $zip.Dispose()
    }
    $javac = Resolve-JavaExecutable -Name 'javac'
    $java = Resolve-JavaExecutable -Name 'java'
    $temporaryLayout = New-PlayAabTemporaryLayout -TemporaryBasePath $temporaryRoot
    $compile = Invoke-NativeCapture `
        -Executable $javac `
        -Arguments @('-d', $temporaryLayout.VerifierClasses, $verifierSource)
    Assert-True ($compile.ExitCode -eq 0) `
        "Java signed-archive verifier did not compile: $($compile.Output)"
    [IO.File]::WriteAllText(
        (Join-Path $temporaryLayout.WebAssets 'vite-marker.txt'),
        'transient Vite output'
    )
    Remove-Item -LiteralPath $temporaryLayout.WebAssets -Recurse -Force
    New-Item -ItemType Directory -Path $temporaryLayout.WebAssets | Out-Null
    $verifierClass = Join-Path $temporaryLayout.VerifierClasses 'VerifySignedArchive.class'
    Assert-True (Test-Path -LiteralPath $verifierClass -PathType Leaf) `
        'Emptying the Vite outDir deleted the compiled signature verifier.'
    $verification = Invoke-NativeCapture `
        -Executable $java `
        -Arguments @('-cp', $temporaryLayout.VerifierClasses, 'VerifySignedArchive', $unsignedArchive)
    Assert-True ($verification.ExitCode -ne 0) `
        'Unsigned AAB fixture was incorrectly accepted.'
    Assert-True ($verification.Output.Contains('SecurityException')) `
        "Unsigned AAB did not fail in the Java signature verifier: $($verification.Output)"

    if (-not $SkipGradleExecution) {
        $previousMarker = $env:METEO_PLAY_RELEASE_GUARD_MARKER
        try {
            Remove-Item Env:METEO_PLAY_RELEASE_GUARD_MARKER -ErrorAction SilentlyContinue
            $classification = Invoke-NativeCapture `
                -Executable $gradleWrapper `
                -Arguments @(
                    '-p', (Join-Path $workspaceRoot 'frontend\android'),
                    '-q', 'verifyPlayReleaseGuardTaskClassification'
                )
            Assert-True ($classification.ExitCode -eq 0) `
                "Gradle task classification contract failed: $($classification.Output)"
            $blocked = Invoke-NativeCapture `
                -Executable $gradleWrapper `
                -Arguments @(
                    '-p', (Join-Path $workspaceRoot 'frontend\android'),
                    '-q', 'signReleaseBundle'
                )
            Assert-True ($blocked.ExitCode -ne 0) `
                'signReleaseBundle unexpectedly bypassed the protected build marker.'
            Assert-True ($blocked.Output.Contains('protected build script marker')) `
                "signReleaseBundle failed for an unexpected reason: $($blocked.Output)"
        } finally {
            if ($null -eq $previousMarker) {
                Remove-Item Env:METEO_PLAY_RELEASE_GUARD_MARKER -ErrorAction SilentlyContinue
            } else {
                $env:METEO_PLAY_RELEASE_GUARD_MARKER = $previousMarker
            }
        }
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}

[PSCustomObject]@{
    AppendOnlyLedger = 'PASS'
    BundletoolTrust = 'PASS'
    DurableArchive = 'PASS'
    FirebaseIdentity = 'PASS'
    GradleReleaseGuard = if ($SkipGradleExecution) { 'SKIPPED' } else { 'PASS' }
    JavaPerEntrySignatureVerifier = 'PASS'
    LedgerGitImmutability = 'PASS'
    R8Artifacts = 'PASS'
    UploadCertificateTrust = 'PASS'
    VersionReservation = 'PASS'
} | ConvertTo-Json -Compress
