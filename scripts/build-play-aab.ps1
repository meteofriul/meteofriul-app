[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBase,

    [Parameter(Mandatory = $true)]
    [string]$CommunityApiBase,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedRevision,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBackendCommit,

    [Parameter(Mandatory = $true)]
    [ValidateRange(0, 2100000000)]
    [int]$ExpectedLatestPlayVersionCode,

    [Parameter(Mandatory = $true)]
    [string]$BundletoolPath,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBundletoolSha256,

    [string]$ExpectedUploadCertificateSha256,

    [string]$ExpectedImageDigest,

    [string]$BackendEvidencePath,

    [string]$GcloudPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$frontendRoot = Join-Path $workspaceRoot "frontend"
$androidRoot = Join-Path $frontendRoot "android"
$androidPublic = [IO.Path]::GetFullPath(
    (Join-Path $androidRoot "app\src\main\assets\public")
)
$capacitorSettingsPath = Join-Path $androidRoot "capacitor.settings.gradle"
$capacitorBuildPath = Join-Path $androidRoot "app\capacitor.build.gradle"
$guardScript = Join-Path $frontendRoot "scripts\runtime-api-binding.mjs"
$versionParityGuardScript = Join-Path $frontendRoot "scripts\assert-version-parity.mjs"
$releasePreflightModule = Join-Path $PSScriptRoot "release-api-preflight.psm1"
$playSecurityModule = Join-Path $PSScriptRoot "play-aab-security.psm1"
$nativeConfigurationModule = Join-Path $PSScriptRoot "play-native-configuration.psm1"
$nativeConfigurationSource = Join-Path $frontendRoot "capacitor.config.json"
$nativeAssetsDirectory = Join-Path $androidRoot "app\src\main\assets"
$firestoreTtlAuditScript = Join-Path $PSScriptRoot "audit-firestore-push-ttl.ps1"
$firestoreCommunityTtlAuditScript = Join-Path $PSScriptRoot "audit-firestore-community-ttl.ps1"
$firestoreCommunityTtlAuditModule = Join-Path $PSScriptRoot (
    "firestore-community-ttl-audit.psm1"
)
$firestoreCommunityTtlEvidenceModule = Join-Path $PSScriptRoot (
    "firestore-community-ttl-evidence.psm1"
)
$notificationIconGuardScript = Join-Path $PSScriptRoot (
    "package-android-notification-icon.ps1"
)
$firestoreCommunityTtlEvidenceDirectory = Join-Path $workspaceRoot (
    "release-history\firestore-community-ttl"
)
$playReleaseHistoryDirectory = Join-Path $workspaceRoot "release-history\android-play"
$privateReleaseHistoryDirectory = Join-Path $workspaceRoot "release-history\android-private-test"
$playReleaseArchiveDirectory = Join-Path $workspaceRoot "release-artifacts\android-play"
$playKeystoreProperties = Join-Path $androidRoot "play-keystore.properties"
$googleServicesPath = Join-Path $androidRoot "app\google-services.json"
$signedArchiveVerifierSource = Join-Path $PSScriptRoot "java\VerifySignedArchive.java"
$javaHome = "C:\Program Files\Android\Android Studio\jbr"
$androidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$expectedApplicationId = "com.meteofriul.app"
$expectedFirebaseAppId = "1:49007668366:android:725bf6f8b339177a852ddf"
$expectedFirebaseProjectId = "meteo-friul"
$expectedFirebaseProjectNumber = "49007668366"
$expectedCommunityLocationCatalogSha256 = `
    "bd3a48e6359a8c1546bc442601e21a2cde6982501e81f177a92039f83345caed"
$expectedCommunityApiBase = `
    "https://meteofriul-community-49007668366.europe-west1.run.app/api"

function Get-NormalizedCommunityApiBase {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim().TrimEnd("/")
    if ($normalized -cne $expectedCommunityApiBase) {
        throw "release_android_play_community_api_base_invalid"
    }
    return $normalized
}

function Assert-PlayPowerShell7Capabilities {
    [CmdletBinding()]
    param(
        [int]$PowerShellMajor = $PSVersionTable.PSVersion.Major,
        [object]$ConvertFromJsonCommand = $null
    )
    if ($PowerShellMajor -lt 7) {
        throw "release_android_play_powershell_7_required"
    }
    $convertFromJson = $ConvertFromJsonCommand
    if (-not $PSBoundParameters.ContainsKey("ConvertFromJsonCommand")) {
        $convertFromJson = Get-Command `
            ConvertFrom-Json -ErrorAction SilentlyContinue
    }
    if ($null -eq $convertFromJson -or
        -not $convertFromJson.Parameters.ContainsKey("DateKind")) {
        throw "release_android_play_convertfromjson_datekind_required"
    }
}

function Assert-FirestorePushTtlGate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$AuditScriptPath,
        [Parameter(Mandatory = $true)][string]$ExpectedReleaseApiTag,
        [string]$GcloudExecutable = ""
    )
    if (-not (Test-Path -LiteralPath $AuditScriptPath -PathType Leaf)) {
        throw "release_android_play_firestore_ttl_gate_missing"
    }
    $arguments = @{ PassThru = $true; ReleaseApiTag = $ExpectedReleaseApiTag }
    if (-not [string]::IsNullOrWhiteSpace($GcloudExecutable)) {
        $arguments.GcloudPath = $GcloudExecutable
    }
    $result = & $AuditScriptPath @arguments
    if ($null -eq $result -or
        -not ($result.PSObject.Properties.Name -ccontains "ready") -or
        $result.ready -ne $true -or
        [int]$result.blockingCount -ne 0) {
        $codes = if ($null -ne $result -and
            $result.PSObject.Properties.Name -ccontains "findings") {
            @($result.findings | ForEach-Object { [string]$_.code }) -join ","
        } else {
            "unreadable_result"
        }
        throw "release_android_play_firestore_ttl_gate_failed: $codes"
    }
    return $result
}

function Assert-CommunityEphemeralSafetyGate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$ApiBase,
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[0-9a-f]{64}$')]
        [string]$ExpectedCatalogSha256,
        [object]$Payload = $null,
        [DateTimeOffset]$CurrentTimeUtc = [DateTimeOffset]::UtcNow
    )
    $normalizedApiBase = $ApiBase.Trim().TrimEnd("/")
    if (-not $normalizedApiBase) {
        throw "release_android_play_community_ephemeral_gate_failed: api_base_missing"
    }
    $endpoint = (
        "$normalizedApiBase/community/reports?" +
        "istat_code=093033&radius_km=30"
    )
    if ($null -eq $Payload) {
        try {
            $response = Invoke-WebRequest -Method Get -Uri $endpoint `
                -TimeoutSec 30
            $Payload = $response.Content |
                ConvertFrom-Json -DateKind String
        } catch {
            throw (
                "release_android_play_community_ephemeral_gate_failed: " +
                "endpoint_unavailable"
            )
        }
    }

    $findings = [Collections.Generic.List[string]]::new()
    $exactProperties = {
        param([object]$Value, [string[]]$Expected)
        if ($null -eq $Value) { return $false }
        $actual = @($Value.PSObject.Properties.Name | Sort-Object)
        $wanted = @($Expected | Sort-Object)
        return ($actual -join "`n") -ceq ($wanted -join "`n")
    }
    $exactSequence = {
        param([object[]]$Value, [string[]]$Expected)
        $actual = @($Value | ForEach-Object { [string]$_ })
        return ($actual -join "`n") -ceq (@($Expected) -join "`n")
    }
    $finiteDouble = {
        param([object]$Value)
        try {
            $parsed = [double]$Value
        } catch {
            return $null
        }
        if (-not [double]::IsFinite($parsed)) { return $null }
        return [PSCustomObject]@{ Value = $parsed }
    }
    $expectedResponseFields = @(
        "reports", "map_groups", "ttl_seconds", "cooldown_seconds",
        "max_distance_km", "locations", "generated_at", "source", "scope",
        "contract"
    )
    if (-not (& $exactProperties $Payload $expectedResponseFields)) {
        $findings.Add("response_schema_changed")
    }
    $allowedTypes = @(
        "fog", "hail", "ice", "quiet", "rain", "snow", "storm", "wind"
    )
    $expectedCreateFields = @(
        "type_id", "lat", "lon", "selected_place", "client_id",
        "accepted_terms", "policy_version", "identity", "istat_code",
        "accuracy_m", "age_ms", "operation_id", "replacement_token"
    )
    $expectedPublicReportFields = @(
        "id", "typeId", "typeCategory", "groupId", "place", "lat", "lon",
        "locationPrecision", "x", "y", "createdAt", "expiresAt", "time",
        "source", "sourceKey", "identity", "istatCode", "regionId",
        "provinceCode"
    )
    $expectedPublicGroupFields = @(
        "id", "typeId", "typeCategory", "groupId", "place", "lat", "lon",
        "locationPrecision", "x", "y", "createdAt", "expiresAt", "time",
        "source", "sourceKey", "identity", "reportIds", "sourceKeys",
        "identities", "count", "confirmations", "istatCode", "regionId",
        "provinceCode"
    )
    $expectedPublicReportExtensionFields = @(
        "updatedAt", "revision", "correctionUntil", "replacementAvailable",
        "lineageGroupIds"
    )
    $expectedPublicGroupExtensionFields = @("updatedAt", "lineageGroupIds")
    $expectedPublishedReportFields = @(
        $expectedPublicReportFields + $expectedPublicReportExtensionFields
    )
    $expectedPublishedGroupFields = @(
        $expectedPublicGroupFields + $expectedPublicGroupExtensionFields
    )
    $expectedUpdateFields = @(
        "client_id", "operation_id", "expected_revision", "lat", "lon",
        "accuracy_m", "age_ms", "accepted_terms", "policy_version"
    )
    $expectedConfirmationFields = @("yes", "no")
    $expectedLocationFields = @(
        "place", "lat", "lon", "istatCode", "regionId", "provinceCode"
    )
    $expectedSourceModelFields = @(
        "id", "type", "verified", "storage", "cooldown_storage"
    )
    $expectedPublicSourceFields = @("id", "type", "verified", "storage")
    $expectedFlagReasons = @("inaccurate", "duplicate", "misuse")
    $expectedContractFields = @(
        "schema_version", "guidelines_policy_version", "allowed_report_types",
        "create_fields", "public_report_fields", "public_group_fields",
        "confirmation_fields", "location_fields", "source_fields",
        "flag_reasons", "ttl_seconds", "cooldown_seconds", "max_distance_km",
        "location_catalog_count", "location_catalog_sha256",
        "location_catalog_digest_algorithm", "location_precision",
        "accepts_free_text", "accepts_media", "requires_account",
        "user_flag_visibility", "automatic_global_hide",
        "public_source_key", "minimum_interval_seconds", "undo_window_seconds",
        "hourly_limit", "daily_limit", "quota_windows",
        "correction_window_seconds", "uniqueness", "update_fields",
        "update_action", "update_requires_fresh_gps", "update_idempotency",
        "pilot_public_report_extension_fields",
        "pilot_public_group_extension_fields"
    )

    $ttlSeconds = [int](Get-PlayCommunityTtlAuditProperty $Payload "ttl_seconds")
    $cooldownSeconds = [int](
        Get-PlayCommunityTtlAuditProperty $Payload "cooldown_seconds"
    )
    $maxDistanceKm = [int](
        Get-PlayCommunityTtlAuditProperty $Payload "max_distance_km"
    )
    if ($ttlSeconds -ne 3600) { $findings.Add("public_ttl_not_one_hour") }
    if ($cooldownSeconds -ne 120) { $findings.Add("cooldown_contract_changed") }
    if ($maxDistanceKm -ne 5) { $findings.Add("distance_contract_changed") }

    $contract = Get-PlayCommunityTtlAuditProperty $Payload "contract"
    if (-not (& $exactProperties $contract $expectedContractFields)) {
        $findings.Add("safety_contract_schema_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "schema_version") -cne "community-pilot-national-safety-v2") {
        $findings.Add("safety_contract_version_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "guidelines_policy_version") -cne "community-guidelines-v2") {
        $findings.Add("guidelines_policy_changed")
    }
    foreach ($sequenceCheck in @(
        @{ Name = "allowed_report_types"; Expected = $allowedTypes },
        @{ Name = "create_fields"; Expected = $expectedCreateFields },
        @{ Name = "public_report_fields"; Expected = $expectedPublicReportFields },
        @{ Name = "public_group_fields"; Expected = $expectedPublicGroupFields },
        @{ Name = "confirmation_fields"; Expected = $expectedConfirmationFields },
        @{ Name = "location_fields"; Expected = $expectedLocationFields },
        @{ Name = "source_fields"; Expected = $expectedSourceModelFields },
        @{ Name = "flag_reasons"; Expected = $expectedFlagReasons },
        @{ Name = "update_fields"; Expected = $expectedUpdateFields },
        @{
            Name = "pilot_public_report_extension_fields"
            Expected = $expectedPublicReportExtensionFields
        },
        @{
            Name = "pilot_public_group_extension_fields"
            Expected = $expectedPublicGroupExtensionFields
        }
    )) {
        if (-not (& $exactSequence `
            @(Get-PlayCommunityTtlAuditProperty $contract $sequenceCheck.Name) `
            $sequenceCheck.Expected)) {
            $findings.Add("contract_$($sequenceCheck.Name)_changed")
        }
    }
    if ([int](Get-PlayCommunityTtlAuditProperty $contract "ttl_seconds") -ne
        $ttlSeconds -or $ttlSeconds -ne 3600) {
        $findings.Add("contract_ttl_mismatch")
    }
    if ([int](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "cooldown_seconds") -ne $cooldownSeconds -or $cooldownSeconds -ne 120) {
        $findings.Add("contract_cooldown_mismatch")
    }
    if ([int](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "max_distance_km") -ne $maxDistanceKm -or $maxDistanceKm -ne 5) {
        $findings.Add("contract_distance_mismatch")
    }
    if ([int](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "location_catalog_count") -ne 7894) {
        $findings.Add("contract_location_count_changed")
    }
    $contractCatalogSha256 = [string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "location_catalog_sha256")
    if ($contractCatalogSha256 -cne $ExpectedCatalogSha256) {
        $findings.Add("contract_location_catalog_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "location_catalog_digest_algorithm") -cne
        "sha256-ordered-istat-lat5-lon5-lines-v1") {
        $findings.Add("contract_catalog_digest_algorithm_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "location_precision") -cne "zone") {
        $findings.Add("contract_location_precision_changed")
    }
    foreach ($falseCapability in @(
        "accepts_free_text", "accepts_media", "requires_account"
    )) {
        if ((Get-PlayCommunityTtlAuditProperty $contract $falseCapability) -ne
            $false) {
            $findings.Add("contract_$($falseCapability)_enabled")
        }
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "user_flag_visibility") -cne "local_only") {
        $findings.Add("contract_user_flag_visibility_changed")
    }
    $automaticGlobalHide = Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "automatic_global_hide"
    if ($automaticGlobalHide -isnot [bool] -or $automaticGlobalHide -ne $false) {
        $findings.Add("contract_automatic_global_hide_enabled")
    }
    foreach ($numericContract in @(
        @{ Name = "minimum_interval_seconds"; Expected = 120 },
        @{ Name = "undo_window_seconds"; Expected = 0 },
        @{ Name = "hourly_limit"; Expected = 4 },
        @{ Name = "daily_limit"; Expected = 12 },
        @{ Name = "correction_window_seconds"; Expected = 300 }
    )) {
        if ([int](Get-PlayCommunityTtlAuditProperty `
            $contract $numericContract.Name) -ne $numericContract.Expected) {
            $findings.Add("contract_$($numericContract.Name)_changed")
        }
    }
    foreach ($textContract in @(
        @{ Name = "quota_windows"; Expected = "rolling-server-time" },
        @{
            Name = "uniqueness"
            Expected = "installation-istat-phenomenon"
        },
        @{ Name = "update_action"; Expected = "renew_same_observation" },
        @{
            Name = "update_idempotency"
            Expected = "report-operation-revision-v1"
        }
    )) {
        if ([string](Get-PlayCommunityTtlAuditProperty `
            $contract $textContract.Name) -cne $textContract.Expected) {
            $findings.Add("contract_$($textContract.Name)_changed")
        }
    }
    if ((Get-PlayCommunityTtlAuditProperty `
        $contract "update_requires_fresh_gps") -ne $true) {
        $findings.Add("contract_update_requires_fresh_gps_disabled")
    }
    $sourceKeyContract = Get-PlayCommunityTtlAuditProperty (
        $contract
    ) "public_source_key"
    if (-not (& $exactProperties $sourceKeyContract @(
        "algorithm", "pattern", "length", "rotation_bucket_seconds"
    ))) {
        $findings.Add("source_key_contract_schema_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty (
        $sourceKeyContract
    ) "algorithm") -cne "sha256-truncated-lower-hex" -or
        [string](Get-PlayCommunityTtlAuditProperty (
            $sourceKeyContract
        ) "pattern") -cne '^[0-9a-f]{24}$' -or
        [int](Get-PlayCommunityTtlAuditProperty (
            $sourceKeyContract
        ) "length") -ne 24 -or
        [int](Get-PlayCommunityTtlAuditProperty (
            $sourceKeyContract
        ) "rotation_bucket_seconds") -ne 86400) {
        $findings.Add("source_key_contract_changed")
    }

    $source = Get-PlayCommunityTtlAuditProperty $Payload "source"
    if (-not (& $exactProperties $source $expectedPublicSourceFields)) {
        $findings.Add("source_schema_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty $source "id") -cne
        "community_reports") {
        $findings.Add("source_id_changed")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty $source "type") -cne
        "informative_unverified") {
        $findings.Add("source_type_changed")
    }
    if ((Get-PlayCommunityTtlAuditProperty $source "verified") -ne $false) {
        $findings.Add("source_must_remain_unverified")
    }
    if ([string](Get-PlayCommunityTtlAuditProperty $source "storage") -cne
        "pilot-cloud" -or $null -ne (Get-PlayCommunityTtlAuditProperty (
            $source
        ) "cooldown_storage")) {
        $findings.Add("source_storage_contract_changed")
    }

    $scope = Get-PlayCommunityTtlAuditProperty $Payload "scope"
    if (-not (& $exactProperties $scope @("istatCode", "radiusKm")) -or
        [string](Get-PlayCommunityTtlAuditProperty $scope "istatCode") -cne
            "093033" -or
        [double](Get-PlayCommunityTtlAuditProperty $scope "radiusKm") -ne 30) {
        $findings.Add("scope_contract_changed")
    }

    $locations = @(Get-PlayCommunityTtlAuditProperty $Payload "locations")
    if ($locations.Count -lt 1 -or $locations.Count -gt 16) {
        $findings.Add("municipality_scope_changed")
    }
    $locationByIstat = @{}
    foreach ($location in $locations) {
        if (-not (& $exactProperties $location $expectedLocationFields)) {
            $findings.Add("municipality_schema_changed")
        }
        $place = [string](Get-PlayCommunityTtlAuditProperty $location "place")
        $istatCode = [string](
            Get-PlayCommunityTtlAuditProperty $location "istatCode"
        )
        $regionId = [string](
            Get-PlayCommunityTtlAuditProperty $location "regionId"
        )
        $provinceCode = [string](
            Get-PlayCommunityTtlAuditProperty $location "provinceCode"
        )
        $lat = Get-PlayCommunityTtlAuditProperty $location "lat"
        $lon = Get-PlayCommunityTtlAuditProperty $location "lon"
        $finiteLat = & $finiteDouble $lat
        $finiteLon = & $finiteDouble $lon
        if (-not $place -or $istatCode -cnotmatch '^\d{6}$' -or
            $regionId -cnotmatch '^IT-\d{2}$' -or
            $provinceCode -cnotmatch '^[A-Z]{2}$' -or
            $locationByIstat.ContainsKey($istatCode) -or
            $null -eq $finiteLat -or $null -eq $finiteLon -or
            $finiteLat.Value -lt 35 -or $finiteLat.Value -gt 48 -or
            $finiteLon.Value -lt 6 -or $finiteLon.Value -gt 19) {
            $findings.Add("municipality_scope_invalid")
            continue
        }
        $locationByIstat[$istatCode] = $location
    }
    $catalogSha256 = $contractCatalogSha256

    $generatedAt = [DateTimeOffset]::MinValue
    $generatedAtValid = [DateTimeOffset]::TryParse(
        [string](Get-PlayCommunityTtlAuditProperty $Payload "generated_at"),
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$generatedAt
    )
    if (-not $generatedAtValid) {
        $findings.Add("generated_at_invalid")
    } else {
        $generatedAt = $generatedAt.ToUniversalTime()
        $currentTime = $CurrentTimeUtc.ToUniversalTime()
        $freshnessTolerance = [TimeSpan]::FromMinutes(5)
        if ($generatedAt -lt $currentTime.Subtract($freshnessTolerance)) {
            $findings.Add("generated_at_stale")
        }
        if ($generatedAt -gt $currentTime.Add($freshnessTolerance)) {
            $findings.Add("generated_at_future")
        }
    }

    $reports = @(Get-PlayCommunityTtlAuditProperty $Payload "reports")
    $groups = @(Get-PlayCommunityTtlAuditProperty $Payload "map_groups")
    foreach ($item in @($reports + $groups)) {
        $isGroup = $item.PSObject.Properties.Name -ccontains "reportIds"
        $expectedItemFields = if ($isGroup) {
            $expectedPublishedGroupFields
        } else { $expectedPublishedReportFields }
        if (-not (& $exactProperties $item $expectedItemFields)) {
            $findings.Add("public_item_schema_changed")
        }
        $typeId = [string](Get-PlayCommunityTtlAuditProperty $item "typeId")
        $place = [string](Get-PlayCommunityTtlAuditProperty $item "place")
        if ($typeId -cnotin $allowedTypes) {
            $findings.Add("open_or_unknown_report_type")
        }
        $expectedCategory = if ($typeId -ceq "quiet") {
            "status"
        } else { "phenomenon" }
        if ([string](Get-PlayCommunityTtlAuditProperty (
            $item
        ) "typeCategory") -cne $expectedCategory) {
            $findings.Add("public_type_category_changed")
        }
        if ([string](Get-PlayCommunityTtlAuditProperty $item "source") -cne
            "community" -or [string](Get-PlayCommunityTtlAuditProperty (
            $item
        ) "time") -cne "") {
            $findings.Add("public_semantic_field_changed")
        }
        $itemId = [string](Get-PlayCommunityTtlAuditProperty $item "id")
        $groupId = [string](Get-PlayCommunityTtlAuditProperty $item "groupId")
        $itemIstatCode = [string](
            Get-PlayCommunityTtlAuditProperty $item "istatCode"
        )
        if ($isGroup) {
            if ($itemId -cne $groupId -or
                $groupId -cnotmatch '^group-[a-z]+:\d{6}:[0-9]+$') {
                $findings.Add("public_group_id_invalid")
            }
        } elseif ($itemId -cnotmatch '^community-[0-9a-f]{16}$' -or
            $groupId -cnotmatch '^group-[a-z]+:\d{6}:[0-9]+$') {
            $findings.Add("public_report_id_invalid")
        }
        if ($itemIstatCode -cnotmatch '^\d{6}$' -or
            [string](Get-PlayCommunityTtlAuditProperty (
                $item
            ) "regionId") -cnotmatch '^IT-\d{2}$' -or
            [string](Get-PlayCommunityTtlAuditProperty (
                $item
            ) "provinceCode") -cnotmatch '^[A-Z]{2}$') {
            $findings.Add("noncanonical_public_municipality")
            continue
        }
        if ([string](Get-PlayCommunityTtlAuditProperty (
            $item
        ) "locationPrecision") -cne "zone") {
            $findings.Add("public_location_not_zonal")
        }
        $itemLat = & $finiteDouble (
            Get-PlayCommunityTtlAuditProperty $item "lat"
        )
        $itemLon = & $finiteDouble (
            Get-PlayCommunityTtlAuditProperty $item "lon"
        )
        if ($null -eq $itemLat -or $null -eq $itemLon -or
            $itemLat.Value -lt 35 -or $itemLat.Value -gt 48 -or
            $itemLon.Value -lt 6 -or $itemLon.Value -gt 19) {
            $findings.Add("public_location_coordinate_invalid")
        } elseif ($locationByIstat.ContainsKey($itemIstatCode)) {
            $canonical = $locationByIstat[$itemIstatCode]
            if ([string](Get-PlayCommunityTtlAuditProperty (
                $canonical
            ) "place") -cne $place) {
                $findings.Add("noncanonical_public_place")
            }
            $latDelta = [Math]::Abs(
                $itemLat.Value -
                [double](Get-PlayCommunityTtlAuditProperty $canonical "lat")
            )
            $lonDelta = [Math]::Abs(
                $itemLon.Value -
                [double](Get-PlayCommunityTtlAuditProperty $canonical "lon")
            )
            if ($latDelta -gt 0.000001 -or $lonDelta -gt 0.000001) {
                $findings.Add("precise_coordinates_exposed")
            }
        }
        $createdAt = [Int64](
            Get-PlayCommunityTtlAuditProperty $item "createdAt"
        )
        $expiresAt = [Int64](
            Get-PlayCommunityTtlAuditProperty $item "expiresAt"
        )
        if ($expiresAt - $createdAt -ne 3600000) {
            $findings.Add("public_item_ttl_changed")
        }
        if ($generatedAtValid) {
            $generatedAtMilliseconds = $generatedAt.ToUnixTimeMilliseconds()
            if ($createdAt -gt $generatedAtMilliseconds -or
                $generatedAtMilliseconds -ge $expiresAt) {
                $findings.Add("public_item_not_active_at_generation")
            }
        }
        foreach ($axis in @("x", "y")) {
            $value = & $finiteDouble (
                Get-PlayCommunityTtlAuditProperty $item $axis
            )
            if ($null -eq $value -or $value.Value -lt 0 -or
                $value.Value -gt 100) {
                $findings.Add("public_map_coordinate_invalid")
            }
        }
        $singleSourceKey = [string](Get-PlayCommunityTtlAuditProperty (
            $item
        ) "sourceKey")
        if ($singleSourceKey -cnotmatch '^[0-9a-f]{24}$') {
            $findings.Add("public_source_key_not_ephemeral_hash")
        }
        if ($isGroup) {
            $sourceKeys = @(Get-PlayCommunityTtlAuditProperty $item "sourceKeys")
            $reportIds = @(Get-PlayCommunityTtlAuditProperty $item "reportIds")
            if ($sourceKeys.Count -eq 0 -or $reportIds.Count -eq 0 -or
                [int](Get-PlayCommunityTtlAuditProperty $item "count") -ne
                    $reportIds.Count) {
                $findings.Add("public_group_membership_invalid")
            }
            foreach ($sourceKey in $sourceKeys) {
                if ([string]$sourceKey -cnotmatch '^[0-9a-f]{24}$') {
                    $findings.Add("public_source_key_not_ephemeral_hash")
                }
            }
            foreach ($reportId in $reportIds) {
                if ([string]$reportId -cnotmatch '^community-[0-9a-f]{16}$') {
                    $findings.Add("public_group_report_id_invalid")
                }
            }
            $confirmations = Get-PlayCommunityTtlAuditProperty (
                $item
            ) "confirmations"
            if (-not (& $exactProperties `
                $confirmations $expectedConfirmationFields) -or
                [int](Get-PlayCommunityTtlAuditProperty (
                    $confirmations
                ) "yes") -lt 0 -or
                [int](Get-PlayCommunityTtlAuditProperty (
                    $confirmations
                ) "no") -lt 0) {
                $findings.Add("public_confirmation_schema_changed")
            }
        }
    }

    $codes = @($findings | Select-Object -Unique)
    if ($codes.Count -gt 0) {
        throw (
            "release_android_play_community_ephemeral_gate_failed: " +
            ($codes -join ",")
        )
    }
    return [PSCustomObject]@{
        schemaVersion = "community-pilot-national-safety-v2"
        event = "community_ephemeral_safety_audit"
        capturedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        endpoint = $endpoint
        ready = $true
        blockingCount = 0
        findings = @()
        observed = [PSCustomObject]@{
            inputMode = "closed-phenomena"
            locationPrecision = "canonical-municipality"
            locationCount = 7894
            scopedLocationCount = $locations.Count
            locationCatalogSha256 = $catalogSha256
            publicContentTtlSeconds = $ttlSeconds
            publicIdentity = "ephemeral-pseudonymous-source-key"
            reportTypeIds = $allowedTypes
            flagReasonIds = $expectedFlagReasons
            publicReportFields = $expectedPublicReportFields
            publicGroupFields = $expectedPublicGroupFields
        }
    }
}

function Get-PlayCommunityTtlAuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Assert-FirestoreCommunityTtlGate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$AuditScriptPath,
        [string]$GcloudExecutable = "",
        [string]$TemporaryBasePath = [IO.Path]::GetTempPath()
    )
    if (-not (Test-Path -LiteralPath $AuditScriptPath -PathType Leaf)) {
        throw "release_android_play_firestore_community_ttl_gate_missing"
    }
    $resolvedTemporaryBase = [IO.Path]::GetFullPath($TemporaryBasePath)
    if (-not (Test-Path -LiteralPath $resolvedTemporaryBase -PathType Container)) {
        throw "release_android_play_firestore_community_ttl_gate_temp_missing"
    }
    $evidenceDirectory = Join-Path $resolvedTemporaryBase (
        "meteofriul-play-community-ttl-" + [Guid]::NewGuid().ToString("N")
    )
    $evidencePath = Join-Path $evidenceDirectory "community-ttl.evidence.json"
    New-Item -ItemType Directory -Path $evidenceDirectory | Out-Null
    try {
        $arguments = @{
            OutputPath = $evidencePath
            Account = "meteofriul@gmail.com"
            ProjectId = "meteo-friul"
            DatabaseId = "(default)"
        }
        if (-not [string]::IsNullOrWhiteSpace($GcloudExecutable)) {
            $arguments.GcloudPath = $GcloudExecutable
        }
        try {
            & $AuditScriptPath @arguments | Out-Null
        } catch {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "audit_error=$($_.Exception.Message)"
            )
        }
        if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "evidence_missing"
            )
        }
        try {
            $result = Get-Content -LiteralPath $evidencePath -Raw |
                ConvertFrom-Json -DateKind String
        } catch {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "evidence_invalid"
            )
        }
        $sourceMode = [string](
            Get-PlayCommunityTtlAuditProperty $result "sourceMode"
        )
        if ($sourceMode -cne "live-read-only") {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "source_mode=$sourceMode"
            )
        }
        $identity = Get-PlayCommunityTtlAuditProperty $result "identity"
        $identityMatches = (
            [string](Get-PlayCommunityTtlAuditProperty $identity "activeAccount") -ceq
                "meteofriul@gmail.com" -and
            [int](Get-PlayCommunityTtlAuditProperty $identity "activeAccountCount") -eq 1 -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "configuredAccount") -ceq
                "meteofriul@gmail.com" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "configuredProject") -ceq
                "meteo-friul" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "projectId") -ceq
                "meteo-friul" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "projectNumber") -ceq
                "49007668366" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "projectState") -ceq
                "ACTIVE" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "databaseName") -ceq
                "projects/meteo-friul/databases/(default)" -and
            [string](Get-PlayCommunityTtlAuditProperty $identity "databaseType") -ceq
                "FIRESTORE_NATIVE"
        )
        if (-not $identityMatches) {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "identity_mismatch"
            )
        }
        $ready = Get-PlayCommunityTtlAuditProperty $result "ready"
        $identityReady = Get-PlayCommunityTtlAuditProperty $result "identityReady"
        $policyReady = Get-PlayCommunityTtlAuditProperty $result "policyReady"
        $documentReady = Get-PlayCommunityTtlAuditProperty $result "documentReady"
        $blockingCount = [int](
            Get-PlayCommunityTtlAuditProperty $result "blockingCount"
        )
        if (
            [string](Get-PlayCommunityTtlAuditProperty $result "schemaVersion") -cne
                "firestore-community-ttl-audit-v2" -or
            $ready -ne $true -or
            $identityReady -ne $true -or
            $policyReady -ne $true -or
            $documentReady -ne $true -or
            $blockingCount -ne 0
        ) {
            $codes = @(
                @(Get-PlayCommunityTtlAuditProperty $result "findings") |
                    ForEach-Object {
                        [string](Get-PlayCommunityTtlAuditProperty $_ "code")
                    } |
                    Where-Object { $_ }
            ) -join ","
            if (-not $codes) { $codes = "unreadable_result" }
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: $codes"
            )
        }

        $contracts = @(Get-CommunityTtlAuditContract)
        $policyRows = @(
            Get-PlayCommunityTtlAuditProperty $result "policies"
        )
        $collectionRows = @(
            Get-PlayCommunityTtlAuditProperty $result "collections"
        )
        if ($contracts.Count -ne 10 -or
            $policyRows.Count -ne $contracts.Count -or
            $collectionRows.Count -ne $contracts.Count) {
            throw (
                "release_android_play_firestore_community_ttl_gate_failed: " +
                "fresh_coverage_invalid"
            )
        }
        foreach ($contract in $contracts) {
            $policyMatches = @($policyRows | Where-Object {
                [string](Get-PlayCommunityTtlAuditProperty `
                    $_ "collectionGroup") -ceq [string]$contract.collectionGroup
            })
            if ($policyMatches.Count -ne 1 -or
                [string](Get-PlayCommunityTtlAuditProperty `
                    $policyMatches[0] "field") -cne [string]$contract.field -or
                [string](Get-PlayCommunityTtlAuditProperty `
                    $policyMatches[0] "state") -cne "ACTIVE" -or
                [string](Get-PlayCommunityTtlAuditProperty `
                    $policyMatches[0] "expirationOffset") -cne "0s") {
                throw (
                    "release_android_play_firestore_community_ttl_gate_failed: " +
                    "fresh_policy_coverage_invalid"
                )
            }
            $collectionMatches = @($collectionRows | Where-Object {
                [string](Get-PlayCommunityTtlAuditProperty `
                    $_ "collectionGroup") -ceq [string]$contract.collectionGroup
            })
            if ($collectionMatches.Count -ne 1 -or
                [string](Get-PlayCommunityTtlAuditProperty `
                    $collectionMatches[0] "expiryField") -cne
                    [string]$contract.field -or
                [string](Get-PlayCommunityTtlAuditProperty `
                    $collectionMatches[0] "baselineField") -cne
                    [string]$contract.baselineField -or
                [int](Get-PlayCommunityTtlAuditProperty `
                    $collectionMatches[0] "documentCount") -ne
                    [int](Get-PlayCommunityTtlAuditProperty `
                        $collectionMatches[0] "validHorizonSampleCount")) {
                throw (
                    "release_android_play_firestore_community_ttl_gate_failed: " +
                    "fresh_document_coverage_invalid"
                )
            }
        }
        return $result
    } finally {
        if (Test-Path -LiteralPath $evidencePath -PathType Leaf) {
            Remove-Item -LiteralPath $evidencePath -Force
        }
        if (Test-Path -LiteralPath $evidenceDirectory -PathType Container) {
            Remove-Item -LiteralPath $evidenceDirectory -Force
        }
    }
}

function Assert-FirestoreCommunityTtlEvidenceGitImmutability {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$EvidenceDirectory
    )
    try {
        return Assert-PlayReleaseLedgerGitImmutability `
            -RepositoryRoot $RepositoryRoot `
            -LedgerDirectory $EvidenceDirectory
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "git_failed:$($_.Exception.Message)"
        )
    }
}

function Assert-FirestoreCommunityTtlHistoricalEvidenceGate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$EvidenceDirectory,
        [Parameter(Mandatory = $true)][string]$AuthoritativeBackendCommit,
        [scriptblock]$CloudAttestationReader = $null,
        [string]$GcloudPath = "",
        [DateTimeOffset]$NowUtc = [DateTimeOffset]::UtcNow
    )

    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char[]]"\/")
    $directory = [IO.Path]::GetFullPath($EvidenceDirectory).TrimEnd([char[]]"\/")
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "missing"
        )
    }
    if (-not $directory.StartsWith(
        $root + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "outside_repository"
        )
    }

    $files = @(Get-ChildItem -LiteralPath $directory -File)
    $unexpected = @($files | Where-Object {
        $_.Name -cne "README.md" -and
        $_.Name -cnotmatch '^\d{8}T\d{9}Z-community-ttl\.evidence\.json$'
    })
    if ($unexpected.Count -gt 0) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "file_unexpected:path=$($unexpected[0].FullName)"
        )
    }
    $evidenceFiles = @($files | Where-Object {
        $_.Name -cmatch '^\d{8}T\d{9}Z-community-ttl\.evidence\.json$'
    })
    if ($evidenceFiles.Count -eq 0) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "missing"
        )
    }

    $candidates = @($evidenceFiles | ForEach-Object {
        $path = $_.FullName
        try {
            $rawEvidence = Get-Content -LiteralPath $path -Raw
            Assert-CommunityTtlJsonNoDuplicateProperties `
                -Json $rawEvidence `
                -FailureCode (
                    "community_ttl_historical_evidence_duplicate_property"
                )
            $evidence = $rawEvidence |
                ConvertFrom-Json -DateKind String
        } catch {
            throw (
                "release_android_play_firestore_community_ttl_historical_evidence_" +
                "invalid_json:path=$path"
            )
        }
        $capturedAt = [DateTimeOffset]::MinValue
        if (-not [DateTimeOffset]::TryParse(
            [string](Get-PlayCommunityTtlAuditProperty `
                $evidence "capturedAtUtc"),
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal,
            [ref]$capturedAt
        )) {
            throw (
                "release_android_play_firestore_community_ttl_historical_evidence_" +
                "capture_invalid:path=$path"
            )
        }
        [PSCustomObject]@{
            CapturedAt = $capturedAt.ToUniversalTime()
            Evidence = $evidence
            Path = $path
        }
    })
    $latest = @($candidates | Sort-Object CapturedAt -Descending)
    if ($latest.Count -gt 1 -and
        $latest[0].CapturedAt -eq $latest[1].CapturedAt) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "latest_ambiguous"
        )
    }

    $headCommit = (& git -C $root rev-parse HEAD 2>&1 |
        Out-String).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $headCommit -notmatch '^[0-9a-f]{40}$') {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "head_commit_unavailable"
        )
    }
    try {
        $headWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
            -RepositoryRoot $root `
            -Commit $headCommit
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "head_writer_contract_failed:$($_.Exception.Message)"
        )
    }
    try {
        $validated = Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $latest[0].Evidence `
            -RepositoryRoot $root `
            -ExpectedWriterContract $headWriterContract `
            -NowUtc $NowUtc
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "failed:$($_.Exception.Message)"
        )
    }
    try {
        $backendWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
            -RepositoryRoot $root `
            -Commit $AuthoritativeBackendCommit
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "backend_commit_failed:$($_.Exception.Message)"
        )
    }
    $recordedWriterContract = Get-PlayCommunityTtlAuditProperty `
        $latest[0].Evidence "writerContract"
    $recordedSourceCommit = [string](
        Get-PlayCommunityTtlAuditProperty `
            $recordedWriterContract "sourceCommit"
    )
    if ($recordedSourceCommit -notmatch '^[0-9a-f]{40}$') {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "source_commit_invalid"
        )
    }
    try {
        $sourceWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
            -RepositoryRoot $root `
            -Commit $recordedSourceCommit
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "source_commit_failed:$($_.Exception.Message)"
        )
    }
    if ([string]$sourceWriterContract.sha256 -cne
        [string]$validated.WriterContractSha256) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "source_writer_contract_hash_mismatch"
        )
    }
    & git -C $root merge-base --is-ancestor `
        $sourceWriterContract.sourceCommit `
        $backendWriterContract.sourceCommit 2>&1 | Out-Null
    $ancestorExitCode = $LASTEXITCODE
    if ($ancestorExitCode -ne 0) {
        $failure = if ($ancestorExitCode -eq 1) {
            "source_commit_not_backend_ancestor"
        } else {
            "source_commit_ancestry_check_failed"
        }
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            $failure
        )
    }
    if ([string]$backendWriterContract.sha256 -cne
        [string]$validated.WriterContractSha256) {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "backend_writer_contract_hash_mismatch"
        )
    }
    $attestation = Get-PlayCommunityTtlAuditProperty `
        $latest[0].Evidence "cloudAttestation"
    try {
        $remoteEntries = @(if ($null -ne $CloudAttestationReader) {
            & $CloudAttestationReader $attestation
        } else {
            Read-CommunityTtlCloudAttestationLive `
                -Attestation $attestation `
                -GcloudPath $GcloudPath
        })
        if ($remoteEntries.Count -ne 1) {
            throw "community_ttl_cloud_attestation_readback_count_invalid"
        }
        $remoteAttestation = Assert-CommunityTtlCloudAttestationReadBack `
            -Evidence $latest[0].Evidence `
            -Entries $remoteEntries
    } catch {
        throw (
            "release_android_play_firestore_community_ttl_historical_evidence_" +
            "cloud_attestation_failed:$($_.Exception.Message)"
        )
    }
    $relativePath = $latest[0].Path.Substring($root.Length).TrimStart(
        [char[]]"\/"
    ).Replace('\', '/')
    return [PSCustomObject]@{
        Path = $latest[0].Path
        RelativePath = $relativePath
        EvidenceSha256 = (Get-FileHash `
            -Algorithm SHA256 `
            -LiteralPath $latest[0].Path).Hash.ToLowerInvariant()
        CapturedAtUtc = $validated.CapturedAtUtc
        AgeSeconds = $validated.AgeSeconds
        MaxAgeSeconds = $validated.MaxAgeSeconds
        WriterContractSha256 = $validated.WriterContractSha256
        SourceCommit = $sourceWriterContract.sourceCommit
        AuthoritativeBackendCommit = $backendWriterContract.sourceCommit
        AuthoritativeBackendWriterContractSha256 = $backendWriterContract.sha256
        CollectionCount = $validated.CollectionCount
        CloudAttestationNonce = $remoteAttestation.Nonce
        EvidenceCoreSha256 = $remoteAttestation.EvidenceCoreSha256
    }
}

function Resolve-PlayBundletoolPath {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Value)

    $candidate = $Value.Trim()
    if (-not $candidate) {
        throw "release_android_play_bundletool_path_missing"
    }
    $resolved = [IO.Path]::GetFullPath($candidate)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "release_android_play_bundletool_not_found: path=$resolved"
    }
    if ([IO.Path]::GetExtension($resolved) -cne ".jar") {
        throw "release_android_play_bundletool_must_be_jar: path=$resolved"
    }
    return $resolved
}

function Invoke-PlayBundletool {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$JavaPath,
        [Parameter(Mandatory = $true)][string]$JarPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureCode
    )

    $output = (& $JavaPath -jar $JarPath @Arguments 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureCode`: $output"
    }
    return $output
}

function Get-PlayBundletoolScalar {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$JavaPath,
        [Parameter(Mandatory = $true)][string]$JarPath,
        [Parameter(Mandatory = $true)][string]$BundlePath,
        [Parameter(Mandatory = $true)][string]$XPath,
        [Parameter(Mandatory = $true)][string]$FailureCode
    )

    $output = Invoke-PlayBundletool `
        -JavaPath $JavaPath `
        -JarPath $JarPath `
        -Arguments @("dump", "manifest", "--bundle=$BundlePath", "--xpath=$XPath") `
        -FailureCode $FailureCode
    $lines = @($output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($lines.Count -ne 1) {
        throw "$FailureCode`: unexpected_output"
    }
    return $lines[0].Trim().Trim('"').Trim("'")
}

function Get-PlayBundleIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$JavaPath,
        [Parameter(Mandatory = $true)][string]$JarPath,
        [Parameter(Mandatory = $true)][string]$BundlePath
    )

    $applicationId = Get-PlayBundletoolScalar `
        -JavaPath $JavaPath -JarPath $JarPath -BundlePath $BundlePath `
        -XPath "/manifest/@package" `
        -FailureCode "release_android_play_application_id_unreadable"
    $versionCodeText = Get-PlayBundletoolScalar `
        -JavaPath $JavaPath -JarPath $JarPath -BundlePath $BundlePath `
        -XPath "/manifest/@android:versionCode" `
        -FailureCode "release_android_play_version_code_unreadable"
    $versionName = Get-PlayBundletoolScalar `
        -JavaPath $JavaPath -JarPath $JarPath -BundlePath $BundlePath `
        -XPath "/manifest/@android:versionName" `
        -FailureCode "release_android_play_version_name_unreadable"

    $versionCode = 0
    if (-not [int]::TryParse($versionCodeText, [ref]$versionCode) -or $versionCode -le 0) {
        throw "release_android_play_version_code_invalid: value=$versionCodeText"
    }
    if ($applicationId -cne $expectedApplicationId) {
        throw "release_android_play_application_id_mismatch: expected=$expectedApplicationId actual=$applicationId"
    }
    if ($versionName -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$') {
        throw "release_android_play_version_name_invalid: value=$versionName"
    }

    return [PSCustomObject]@{
        ApplicationId = $applicationId
        VersionCode = $versionCode
        VersionName = $versionName
    }
}

function Get-PlayGradleDeclaredIdentity {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$AndroidDirectory)

    Push-Location $AndroidDirectory
    try {
        $output = (& .\gradlew.bat -q printPlayReleaseIdentity 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "release_android_play_gradle_identity_failed: $output"
        }
    } finally {
        Pop-Location
    }
    $prefix = "METEO_PLAY_RELEASE_IDENTITY:"
    $matches = @(
        $output -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_.StartsWith($prefix, [StringComparison]::Ordinal) }
    )
    if ($matches.Count -ne 1) {
        throw "release_android_play_gradle_identity_unreadable"
    }
    try {
        $identity = $matches[0].Substring($prefix.Length) | ConvertFrom-Json
    } catch {
        throw "release_android_play_gradle_identity_invalid"
    }
    $versionCode = 0
    if (
        [string]$identity.ApplicationId -cne $expectedApplicationId -or
        -not [int]::TryParse([string]$identity.VersionCode, [ref]$versionCode) -or
        $versionCode -le 0 -or
        [string]$identity.VersionName -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$'
    ) {
        throw "release_android_play_gradle_identity_invalid"
    }
    return [PSCustomObject]@{
        ApplicationId = [string]$identity.ApplicationId
        VersionCode = $versionCode
        VersionName = [string]$identity.VersionName
    }
}

function Invoke-PlaySignedArchiveVerifier {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$JavaPath,
        [Parameter(Mandatory = $true)][string]$VerifierClassDirectory,
        [Parameter(Mandatory = $true)][string]$BundlePath
    )

    $verificationOutput = (
        & $JavaPath -cp $VerifierClassDirectory VerifySignedArchive $BundlePath 2>&1 |
            Out-String
    ).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "release_android_play_signature_verification_failed: $verificationOutput"
    }
    $lines = @(
        $verificationOutput -split "`r?`n" |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    if ($lines.Count -ne 1 -or $lines[0] -notmatch '^[0-9a-f]{64}$') {
        throw "release_android_play_signature_verifier_output_invalid"
    }
    return $lines[0]
}

function Assert-PlayBundleRuntimeBindings {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$BundlePath,
        [Parameter(Mandatory = $true)][string]$ExpectedApiBase,
        [Parameter(Mandatory = $true)][string]$ExpectedCommunityApiBase
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($BundlePath)
    try {
        $webEntries = @(
            $archive.Entries |
                Where-Object { $_.FullName -like "base/assets/public/assets/main-*.js" }
        )
        if ($webEntries.Count -ne 1) {
            throw "release_android_play_webview_entry_invalid: matches=$($webEntries.Count)"
        }
        $reader = [IO.StreamReader]::new($webEntries[0].Open())
        try { $bundleSource = $reader.ReadToEnd() }
        finally { $reader.Dispose() }
        if (-not $bundleSource.Contains($ExpectedApiBase)) {
            throw "release_android_play_api_missing_from_webview"
        }
        if (-not $bundleSource.Contains($ExpectedCommunityApiBase)) {
            throw "release_android_play_community_api_missing_from_webview"
        }

        $dexEntries = @(
            $archive.Entries |
                Where-Object { $_.FullName -like "base/dex/classes*.dex" }
        )
        if ($dexEntries.Count -lt 1) {
            throw "release_android_play_native_dex_missing"
        }
        $nativeApiFound = $false
        foreach ($dexEntry in $dexEntries) {
            $stream = $dexEntry.Open()
            $memory = [IO.MemoryStream]::new()
            try {
                $stream.CopyTo($memory)
                $text = [Text.Encoding]::UTF8.GetString($memory.ToArray())
                if ($text.Contains($ExpectedApiBase)) {
                    $nativeApiFound = $true
                    break
                }
            }
            finally {
                $memory.Dispose()
                $stream.Dispose()
            }
        }
        if (-not $nativeApiFound) {
            throw "release_android_play_api_missing_from_native_worker"
        }
    }
    finally {
        $archive.Dispose()
    }

    return [PSCustomObject]@{
        ApiBase = $ExpectedApiBase
        CommunityApiBase = $ExpectedCommunityApiBase
        NativeWorker = "verified"
        WebView = "verified"
    }
}

function Read-AndroidReleaseHistory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Directory,
        [switch]$RequireCertificate
    )

    $records = @()
    foreach ($releaseRecord in (Get-ChildItem -LiteralPath $Directory -Filter "*.release.json" -File)) {
        try {
            $record = Get-Content -LiteralPath $releaseRecord.FullName -Raw | ConvertFrom-Json
            $certificate = [string]$record.CertificateSha256
            if ($RequireCertificate -and -not $certificate.Trim()) {
                throw "missing_certificate"
            }
            $records += [PSCustomObject]@{
                CertificateSha256 = $certificate
                Path = $releaseRecord.FullName
                VersionCode = $record.VersionCode
                VersionName = [string]$record.VersionName
            }
        } catch {
            throw "release_android_history_record_invalid: path=$($releaseRecord.FullName)"
        }
    }
    return @($records)
}

Assert-PlayPowerShell7Capabilities
& node $versionParityGuardScript
if ($LASTEXITCODE -ne 0) { throw "release_android_version_parity_invalid" }
if (-not (Test-Path -LiteralPath $notificationIconGuardScript -PathType Leaf)) {
    throw "release_android_play_notification_icon_guard_missing"
}
& $notificationIconGuardScript -CheckOnly
# Fail before reserving a Play version when the local map key is unavailable.
# The second check after reservation still verifies the actual build process.
& node (Join-Path $frontendRoot "scripts\carto-basemap-guard.mjs") --mode android
if ($LASTEXITCODE -ne 0) { throw "release_android_carto_basemap_config_invalid" }
Import-Module $releasePreflightModule -Force
Import-Module $playSecurityModule -Force
Import-Module $nativeConfigurationModule -Force
$nativeConfigurationState = Get-PlayNativeConfiguration -SourcePath $nativeConfigurationSource
Import-Module $firestoreCommunityTtlEvidenceModule -Force
Import-Module $firestoreCommunityTtlAuditModule -Force
$normalizedApiBase = Get-NormalizedReleaseApiBase -Value $ApiBase -ServiceName "meteofriul-api"
$normalizedCommunityApiBase = Get-NormalizedCommunityApiBase -Value $CommunityApiBase
$releaseGitState = Assert-ReleaseGitState -RepositoryRoot $workspaceRoot
$ledgerGitState = Assert-PlayReleaseLedgerGitImmutability `
    -RepositoryRoot $workspaceRoot `
    -LedgerDirectory $playReleaseHistoryDirectory
$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -ExpectedImageDigest $ExpectedImageDigest `
    -BackendEvidencePath $BackendEvidencePath `
    -GcloudPath $GcloudPath
$firestoreTtlState = Assert-FirestorePushTtlGate `
    -AuditScriptPath $firestoreTtlAuditScript `
    -ExpectedReleaseApiTag (Get-ReleaseApiTag -ApiBase $normalizedApiBase -ServiceName "meteofriul-api") `
    -GcloudExecutable $GcloudPath
$firestoreCommunityTtlState = Assert-FirestoreCommunityTtlGate `
    -AuditScriptPath $firestoreCommunityTtlAuditScript `
    -GcloudExecutable $GcloudPath
$communityEphemeralSafetyState = Assert-CommunityEphemeralSafetyGate `
    -ApiBase $normalizedCommunityApiBase `
    -ExpectedCatalogSha256 $expectedCommunityLocationCatalogSha256
$firestoreCommunityTtlEvidenceGitState = `
    Assert-FirestoreCommunityTtlEvidenceGitImmutability `
        -RepositoryRoot $workspaceRoot `
        -EvidenceDirectory $firestoreCommunityTtlEvidenceDirectory
$firestoreCommunityTtlHistoricalState = `
    Assert-FirestoreCommunityTtlHistoricalEvidenceGate `
        -RepositoryRoot $workspaceRoot `
        -EvidenceDirectory $firestoreCommunityTtlEvidenceDirectory `
        -AuthoritativeBackendCommit $releaseApiState.BackendCommit `
        -GcloudPath $GcloudPath
$resolvedBundletool = Resolve-PlayBundletoolPath -Value $BundletoolPath
$bundletoolTrust = Assert-PlayBundletoolTrust `
    -Path $resolvedBundletool `
    -ExpectedSha256 $ExpectedBundletoolSha256
$firebaseIdentity = Assert-PlayGoogleServicesConfiguration `
    -Path $googleServicesPath `
    -ExpectedProjectId $expectedFirebaseProjectId `
    -ExpectedProjectNumber $expectedFirebaseProjectNumber `
    -ExpectedApplicationId $expectedApplicationId `
    -ExpectedFirebaseAppId $expectedFirebaseAppId
$playLedger = Read-PlayReleaseLedger -Directory $playReleaseHistoryDirectory
$normalizedExpectedUploadCertificateSha256 = ""
if (-not [string]::IsNullOrWhiteSpace($ExpectedUploadCertificateSha256)) {
    $normalizedExpectedUploadCertificateSha256 = ConvertTo-PlaySha256 `
        -Value $ExpectedUploadCertificateSha256 `
        -FailureCode "release_android_play_expected_certificate_invalid"
}
if (
    $null -eq $playLedger.LatestAcceptedEvidence -and
    -not $normalizedExpectedUploadCertificateSha256
) {
    throw "release_android_play_upload_trust_anchor_required"
}

if (-not (Test-Path -LiteralPath $playKeystoreProperties -PathType Leaf)) {
    throw "release_android_play_signing_not_configured: path=$playKeystoreProperties"
}
if (-not (Test-Path -LiteralPath $javaHome -PathType Container)) {
    throw "Android Studio JBR 21 was not found."
}
if (-not (Test-Path -LiteralPath $androidSdk -PathType Container)) {
    throw "Android SDK was not found."
}
if (
    -not $androidPublic.StartsWith(
        $workspaceRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
) {
    throw "Android asset target escaped the workspace."
}
if (-not (Test-Path -LiteralPath $androidPublic -PathType Container)) {
    throw "Android public asset target is missing."
}
if (-not (Test-Path -LiteralPath $playReleaseHistoryDirectory -PathType Container)) {
    throw "release_android_history_directory_missing: path=$playReleaseHistoryDirectory"
}
if (-not (Test-Path -LiteralPath $privateReleaseHistoryDirectory -PathType Container)) {
    throw "release_android_history_directory_missing: path=$privateReleaseHistoryDirectory"
}
if (-not (Test-Path -LiteralPath $signedArchiveVerifierSource -PathType Leaf)) {
    throw "release_android_play_signature_verifier_source_missing"
}
if (-not (Test-Path -LiteralPath $playReleaseArchiveDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $playReleaseArchiveDirectory | Out-Null
}

$java = Join-Path $javaHome "bin\java.exe"
$javac = Join-Path $javaHome "bin\javac.exe"
foreach ($tool in @($java, $javac)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) {
        throw "release_android_play_java_tool_missing: path=$tool"
    }
}
$bundletoolVersion = Invoke-PlayBundletool `
    -JavaPath $java -JarPath $resolvedBundletool -Arguments @("version") `
    -FailureCode "release_android_play_bundletool_invalid"
$bundletoolSha256 = $bundletoolTrust.Sha256

$temporaryLayout = New-PlayAabTemporaryLayout -TemporaryBasePath $env:TEMP
$buildDirectory = $temporaryLayout.WebAssets
$verifierClassDirectory = $temporaryLayout.VerifierClasses
& $javac -d $verifierClassDirectory $signedArchiveVerifierSource
if ($LASTEXITCODE -ne 0) {
    throw "release_android_play_signature_verifier_compile_failed"
}

$hadWebApiBase = Test-Path Env:VITE_API_BASE
$previousWebApiBase = $env:VITE_API_BASE
$hadAndroidApiBase = Test-Path Env:VITE_ANDROID_API_BASE
$previousAndroidApiBase = $env:VITE_ANDROID_API_BASE
$hadCommunityApiBase = Test-Path Env:VITE_COMMUNITY_API_BASE
$previousCommunityApiBase = $env:VITE_COMMUNITY_API_BASE
$previousJavaHome = $env:JAVA_HOME
$previousAndroidHome = $env:ANDROID_HOME
$previousAndroidSdkRoot = $env:ANDROID_SDK_ROOT
$hadPlayGuardMarker = Test-Path Env:METEO_PLAY_RELEASE_GUARD_MARKER
$previousPlayGuardMarker = $env:METEO_PLAY_RELEASE_GUARD_MARKER
$gradleGuardMarker = (
    [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
)
$declaredIdentity = $null
$reservationPath = $null
$archivePaths = $null
$globalVersionHistory = @(
    Read-AndroidReleaseHistory -Directory $privateReleaseHistoryDirectory
)
$globalVersionHistory += @($playLedger.AllVersions)

try {
    Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue
    $env:VITE_ANDROID_API_BASE = $normalizedApiBase
    $env:VITE_COMMUNITY_API_BASE = $normalizedCommunityApiBase
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidSdk
    $env:ANDROID_SDK_ROOT = $androidSdk
    $env:METEO_PLAY_RELEASE_GUARD_MARKER = $gradleGuardMarker

    $declaredIdentity = Get-PlayGradleDeclaredIdentity -AndroidDirectory $androidRoot
    Assert-PlayCandidateVersion `
        -CandidateVersionCode $declaredIdentity.VersionCode `
        -CandidateVersionName $declaredIdentity.VersionName `
        -LatestConsoleVersionCode $ExpectedLatestPlayVersionCode `
        -ExistingVersions $globalVersionHistory | Out-Null
    Assert-AndroidReleaseVersionHistory `
        -CandidateVersionCode $declaredIdentity.VersionCode `
        -CandidateVersionName $declaredIdentity.VersionName `
        -ExistingReleases $globalVersionHistory | Out-Null

    $reservationPath = Join-Path $playReleaseHistoryDirectory (
        "meteofriul-$($declaredIdentity.VersionCode)-" +
        "$($declaredIdentity.VersionName).reservation.json"
    )
    $reservationPayload = [ordered]@{
        SchemaVersion = 1
        CreatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        Kind = "play-version-reservation"
        Status = "reserved"
        ApplicationId = $declaredIdentity.ApplicationId
        VersionCode = $declaredIdentity.VersionCode
        VersionName = $declaredIdentity.VersionName
        ConsoleObservation = [ordered]@{
            LatestVersionCode = $ExpectedLatestPlayVersionCode
            Source = "operator-confirmed-play-console"
        }
        ApiBase = $normalizedApiBase
        CommunityApiBase = $normalizedCommunityApiBase
        BackendCommit = $releaseApiState.BackendCommit
        CloudRunRevision = $releaseApiState.Revision
        FrontendCommit = $releaseGitState.Commit
    }
    Write-NewPlayJsonFile -Path $reservationPath -Payload $reservationPayload | Out-Null
    $archivePaths = Get-PlayReleaseArchivePaths `
        -WorkspaceRoot $workspaceRoot `
        -VersionCode $declaredIdentity.VersionCode `
        -VersionName $declaredIdentity.VersionName

    Push-Location $frontendRoot
    try {
        # Generate Capacitor's ignored plugin registry without copying a stale
        # frontend/dist into Android. The tracked Gradle wiring is committed
        # and must remain stable. The approved native config is copied separately.
        if (-not (Test-Path -LiteralPath $androidPublic -PathType Container)) {
            New-Item -ItemType Directory -Path $androidPublic -Force | Out-Null
        }
        $settingsHashBefore = (Get-FileHash -LiteralPath $capacitorSettingsPath -Algorithm SHA256).Hash
        $buildHashBefore = (Get-FileHash -LiteralPath $capacitorBuildPath -Algorithm SHA256).Hash
        & npx cap update android
        if ($LASTEXITCODE -ne 0) { throw "Capacitor Android plugin scaffold failed." }
        $settingsHashAfter = (Get-FileHash -LiteralPath $capacitorSettingsPath -Algorithm SHA256).Hash
        $buildHashAfter = (Get-FileHash -LiteralPath $capacitorBuildPath -Algorithm SHA256).Hash
        if ($settingsHashBefore -cne $settingsHashAfter -or $buildHashBefore -cne $buildHashAfter) {
            throw "Capacitor update changed tracked Gradle integration; inspect before building."
        }

        Copy-PlayNativeConfiguration `
            -SourcePath $nativeConfigurationSource `
            -AssetsDirectory $nativeAssetsDirectory `
            -ExpectedSha256 $nativeConfigurationState.Sha256
        $nativePluginsSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (
            Join-Path $nativeAssetsDirectory "capacitor.plugins.json"
        )).Hash.ToLowerInvariant()

        & node scripts/carto-basemap-guard.mjs --mode android
        if ($LASTEXITCODE -ne 0) { throw "release_android_carto_basemap_config_invalid" }
        & npx vite build --mode android --configLoader native --outDir $buildDirectory --emptyOutDir
        if ($LASTEXITCODE -ne 0) { throw "Android Play application build failed." }
        & node $guardScript --target android --build-dir $buildDirectory --expected $normalizedApiBase
        if ($LASTEXITCODE -ne 0) { throw "Android Play runtime API verification failed." }
        & node scripts/carto-basemap-guard.mjs --mode android --build-dir $buildDirectory
        if ($LASTEXITCODE -ne 0) { throw "release_android_carto_basemap_bundle_invalid" }
    }
    finally {
        Pop-Location
    }

    Write-Output "Verified Android Play asset source: $buildDirectory"
    Write-Output "Verified Android Play asset target: $androidPublic"
    & robocopy $buildDirectory $androidPublic /MIR /NFL /NDL /NJH /NJS /NP
    $robocopyCode = $LASTEXITCODE
    if ($robocopyCode -gt 7) {
        throw "Android Play asset synchronization failed with code $robocopyCode."
    }

    Push-Location $androidRoot
    try {
        & .\gradlew.bat bundleRelease `
            "-PMETEO_API_BASE=$normalizedApiBase" `
            "-PMETEO_PLAY_RELEASE_GUARD_MARKER=$gradleGuardMarker" `
            "-PMETEO_PLAY_RELEASE_EXPECTED_APPLICATION_ID=$expectedApplicationId" `
            "-PMETEO_PLAY_RELEASE_EXPECTED_FIREBASE_APP_ID=$expectedFirebaseAppId" `
            "-PMETEO_PLAY_RELEASE_EXPECTED_FIREBASE_PROJECT=$expectedFirebaseProjectId" `
            "-PMETEO_PLAY_RELEASE_EXPECTED_FIREBASE_PROJECT_NUMBER=$expectedFirebaseProjectNumber"
        if ($LASTEXITCODE -ne 0) { throw "Android Play Gradle bundle failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($hadWebApiBase) { $env:VITE_API_BASE = $previousWebApiBase }
    else { Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue }
    if ($hadAndroidApiBase) { $env:VITE_ANDROID_API_BASE = $previousAndroidApiBase }
    else { Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue }
    if ($hadCommunityApiBase) { $env:VITE_COMMUNITY_API_BASE = $previousCommunityApiBase }
    else { Remove-Item Env:VITE_COMMUNITY_API_BASE -ErrorAction SilentlyContinue }
    $env:JAVA_HOME = $previousJavaHome
    $env:ANDROID_HOME = $previousAndroidHome
    $env:ANDROID_SDK_ROOT = $previousAndroidSdkRoot
    if ($hadPlayGuardMarker) { $env:METEO_PLAY_RELEASE_GUARD_MARKER = $previousPlayGuardMarker }
    else { Remove-Item Env:METEO_PLAY_RELEASE_GUARD_MARKER -ErrorAction SilentlyContinue }
}

$aab = Join-Path $androidRoot "app\build\outputs\bundle\release\app-release.aab"
$mapping = Join-Path $androidRoot "app\build\outputs\mapping\release\mapping.txt"
if (-not (Test-Path -LiteralPath $aab -PathType Leaf)) {
    throw "release_android_play_aab_not_generated"
}

Invoke-PlayBundletool `
    -JavaPath $java -JarPath $resolvedBundletool `
    -Arguments @("validate", "--bundle=$aab") `
    -FailureCode "release_android_play_bundle_invalid" | Out-Null
$cordovaResourceDump = Invoke-PlayBundletool `
    -JavaPath $java -JarPath $resolvedBundletool `
    -Arguments @("dump", "resources", "--bundle=$aab", "--resource=xml/config", "--values") `
    -FailureCode "release_android_cordova_config_dump_failed"
$nativeConfigurationArtifacts = Assert-PlayNativeConfigurationBundle `
    -BundlePath $aab `
    -ExpectedConfigSha256 $nativeConfigurationState.Sha256 `
    -ExpectedPluginsSha256 $nativePluginsSha256 `
    -CordovaResourceDump $cordovaResourceDump
$identity = Get-PlayBundleIdentity -JavaPath $java -JarPath $resolvedBundletool -BundlePath $aab
$certificateSha256 = Invoke-PlaySignedArchiveVerifier `
    -JavaPath $java `
    -VerifierClassDirectory $verifierClassDirectory `
    -BundlePath $aab
Assert-PlayBundleRuntimeBindings `
    -BundlePath $aab `
    -ExpectedApiBase $normalizedApiBase `
    -ExpectedCommunityApiBase $normalizedCommunityApiBase | Out-Null
$r8Artifacts = Assert-PlayR8BundleArtifacts `
    -BundlePath $aab `
    -MappingPath $mapping
if (
    $identity.ApplicationId -cne $declaredIdentity.ApplicationId -or
    $identity.VersionCode -ne $declaredIdentity.VersionCode -or
    $identity.VersionName -cne $declaredIdentity.VersionName
) {
    throw "release_android_play_packaged_identity_changed_after_reservation"
}
$certificateTrust = Resolve-PlayUploadCertificateTrust `
    -CandidateCertificateSha256 $certificateSha256 `
    -ExplicitExpectedCertificateSha256 $normalizedExpectedUploadCertificateSha256 `
    -Ledger $playLedger

$releaseAab = $archivePaths.Aab
$releaseMapping = $archivePaths.Mapping
$releaseManifest = Join-Path $playReleaseHistoryDirectory (
    "meteofriul-$($identity.VersionCode)-$($identity.VersionName).release.json"
)
if (Test-Path -LiteralPath $releaseAab) {
    throw "release_android_artifact_path_exists: path=$releaseAab"
}
if (Test-Path -LiteralPath $releaseMapping) {
    throw "release_android_mapping_path_exists: path=$releaseMapping"
}
if (Test-Path -LiteralPath $releaseManifest) {
    throw "release_android_manifest_path_exists: path=$releaseManifest"
}

$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -ExpectedImageDigest $ExpectedImageDigest `
    -BackendEvidencePath $BackendEvidencePath `
    -GcloudPath $GcloudPath
$finalGitState = Assert-PlayReleaseWorkspaceUnchanged `
    -RepositoryRoot $workspaceRoot `
    -ExpectedCommit $releaseGitState.Commit `
    -AllowedUntrackedPaths @($reservationPath)
$finalCommunityEphemeralSafetyState = Assert-CommunityEphemeralSafetyGate `
    -ApiBase $normalizedCommunityApiBase `
    -ExpectedCatalogSha256 $expectedCommunityLocationCatalogSha256

$aabSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $aab).Hash.ToLowerInvariant()
Copy-NewPlayArtifact -Source $aab -Destination $releaseAab | Out-Null
$releaseAabSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseAab).Hash.ToLowerInvariant()
if ($releaseAabSha256 -cne $aabSha256) {
    throw "release_android_artifact_copy_verification_failed: path=$releaseAab"
}
Copy-NewPlayArtifact -Source $mapping -Destination $releaseMapping | Out-Null
$releaseMappingSha256 = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $releaseMapping
).Hash.ToLowerInvariant()
if ($releaseMappingSha256 -cne $r8Artifacts.MappingSha256) {
    throw "release_android_mapping_copy_verification_failed: path=$releaseMapping"
}

$manifestPayload = [ordered]@{
    SchemaVersion = 3
    CreatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    Target = "android-play"
    Status = "built-not-uploaded"
    ApplicationId = $identity.ApplicationId
    VersionCode = $identity.VersionCode
    VersionName = $identity.VersionName
    ReservationFile = [IO.Path]::GetFileName($reservationPath)
    ConsoleObservation = [ordered]@{
        LatestVersionCode = $ExpectedLatestPlayVersionCode
        Source = "operator-confirmed-play-console"
    }
    ApiBase = $normalizedApiBase
    CommunityApiBase = $normalizedCommunityApiBase
    ApiTag = $releaseApiState.ApiTag
    BackendCommit = $releaseApiState.BackendCommit
    CloudRunRevision = $releaseApiState.Revision
    CloudRunImageDigest = $releaseApiState.ImageDigest
    CommunitySafetyModel = "structured-national-v2"
    CommunitySafetyCapturedAtUtc = `
        $finalCommunityEphemeralSafetyState.capturedAtUtc
    CommunitySafetyEndpoint = $finalCommunityEphemeralSafetyState.endpoint
    CommunitySafetyInputMode = `
        $finalCommunityEphemeralSafetyState.observed.inputMode
    CommunitySafetyLocationPrecision = `
        $finalCommunityEphemeralSafetyState.observed.locationPrecision
    CommunitySafetyLocationCount = `
        $finalCommunityEphemeralSafetyState.observed.locationCount
    CommunityLocationCatalogSha256 = `
        $finalCommunityEphemeralSafetyState.observed.locationCatalogSha256
    CommunityPublicContentTtlSeconds = `
        $finalCommunityEphemeralSafetyState.observed.publicContentTtlSeconds
    CommunityPublicIdentity = `
        $finalCommunityEphemeralSafetyState.observed.publicIdentity
    CommunityReportTypeIds = @(
        $finalCommunityEphemeralSafetyState.observed.reportTypeIds
    )
    CommunityFlagReasonIds = @(
        $finalCommunityEphemeralSafetyState.observed.flagReasonIds
    )
    CommunityPublicReportFields = @(
        $finalCommunityEphemeralSafetyState.observed.publicReportFields
    )
    CommunityPublicGroupFields = @(
        $finalCommunityEphemeralSafetyState.observed.publicGroupFields
    )
    FrontendCommit = $finalGitState.Commit
    LedgerRecordCount = $ledgerGitState.RecordCount
    AabFile = [IO.Path]::GetFileName($releaseAab)
    AabSha256 = $releaseAabSha256
    NativeConfiguration = $nativeConfigurationArtifacts
    R8Verification = "external-and-embedded-mapping-match"
    MappingFile = [IO.Path]::GetFileName($releaseMapping)
    MappingSha256 = $releaseMappingSha256
    BundleMappingEntry = $r8Artifacts.BundleMappingEntry
    NativeLibraryCount = $r8Artifacts.NativeLibraryCount
    NativeSymbolEntryCount = $r8Artifacts.NativeSymbolEntryCount
    NativeSymbolsStatus = $r8Artifacts.NativeSymbolsStatus
    CertificateSha256 = $certificateSha256
    UploadCertificateSha256 = $certificateSha256
    SigningCertificateRole = "play-upload"
    BundletoolVersion = $bundletoolVersion
    BundletoolSha256 = $bundletoolSha256
    SignatureVerifier = "scripts/java/VerifySignedArchive.java"
    SignatureVerification = "all-payload-entries-single-signer"
    UploadCertificateTrustSource = $certificateTrust.Source
    FirebaseProjectId = $firebaseIdentity.ProjectId
    FirebaseProjectNumber = $firebaseIdentity.ProjectNumber
    FirebaseAppId = $firebaseIdentity.FirebaseAppId
    FirestoreCommunityTtlFreshCapturedAtUtc = `
        $firestoreCommunityTtlState.capturedAtUtc
    FirestoreCommunityTtlEvidenceFile = `
        $firestoreCommunityTtlHistoricalState.RelativePath
    FirestoreCommunityTtlEvidenceSha256 = `
        $firestoreCommunityTtlHistoricalState.EvidenceSha256
    FirestoreCommunityTtlEvidenceCapturedAtUtc = `
        $firestoreCommunityTtlHistoricalState.CapturedAtUtc
    FirestoreCommunityTtlWriterContractSha256 = `
        $firestoreCommunityTtlHistoricalState.WriterContractSha256
    FirestoreCommunityTtlEvidenceSourceCommit = `
        $firestoreCommunityTtlHistoricalState.SourceCommit
    FirestoreCommunityTtlAuthoritativeBackendCommit = `
        $firestoreCommunityTtlHistoricalState.AuthoritativeBackendCommit
    FirestoreCommunityTtlAuthoritativeBackendWriterContractSha256 = `
        $firestoreCommunityTtlHistoricalState.AuthoritativeBackendWriterContractSha256
    FirestoreCommunityTtlCloudAttestationNonce = `
        $firestoreCommunityTtlHistoricalState.CloudAttestationNonce
    FirestoreCommunityTtlEvidenceCoreSha256 = `
        $firestoreCommunityTtlHistoricalState.EvidenceCoreSha256
    AppSigningCertificateSha256 = $null
    AppCheckPlayRegistration = "pending-play-console"
}
Write-NewPlayJsonFile -Path $releaseManifest -Payload $manifestPayload | Out-Null
$writtenManifest = Get-Content -LiteralPath $releaseManifest -Raw |
    ConvertFrom-Json -DateKind String
if (
    $writtenManifest.NativeConfiguration.ConfigSha256 -cne $nativeConfigurationState.Sha256 -or
    $writtenManifest.NativeConfiguration.PluginsSha256 -cne $nativePluginsSha256 -or
    $writtenManifest.NativeConfiguration.CordovaBundleEntry -cne $nativeConfigurationArtifacts.CordovaBundleEntry -or
    $writtenManifest.AabSha256 -cne $releaseAabSha256 -or
    $writtenManifest.R8Verification -cne
        "external-and-embedded-mapping-match" -or
    $writtenManifest.MappingSha256 -cne $releaseMappingSha256 -or
    $writtenManifest.BundleMappingEntry -cne
        $r8Artifacts.BundleMappingEntry -or
    [int]$writtenManifest.NativeLibraryCount -ne
        $r8Artifacts.NativeLibraryCount -or
    [int]$writtenManifest.NativeSymbolEntryCount -ne
        $r8Artifacts.NativeSymbolEntryCount -or
    $writtenManifest.NativeSymbolsStatus -cne
        $r8Artifacts.NativeSymbolsStatus -or
    $writtenManifest.UploadCertificateSha256 -cne $certificateSha256 -or
    $writtenManifest.CloudRunRevision -cne $releaseApiState.Revision -or
    $writtenManifest.FrontendCommit -cne $finalGitState.Commit -or
    $writtenManifest.CommunitySafetyModel -cne "structured-national-v2" -or
    $writtenManifest.CommunitySafetyCapturedAtUtc -cne
        $finalCommunityEphemeralSafetyState.capturedAtUtc -or
    $writtenManifest.CommunitySafetyEndpoint -cne
        $finalCommunityEphemeralSafetyState.endpoint -or
    $writtenManifest.CommunitySafetyInputMode -cne "closed-phenomena" -or
    $writtenManifest.CommunitySafetyLocationPrecision -cne
        "canonical-municipality" -or
    [int]$writtenManifest.CommunitySafetyLocationCount -ne 7894 -or
    $writtenManifest.CommunityLocationCatalogSha256 -cne
        $expectedCommunityLocationCatalogSha256 -or
    [int]$writtenManifest.CommunityPublicContentTtlSeconds -ne 3600 -or
    $writtenManifest.CommunityPublicIdentity -cne
        "ephemeral-pseudonymous-source-key" -or
    (@($writtenManifest.CommunityReportTypeIds) -join "`n") -cne
        (@($finalCommunityEphemeralSafetyState.observed.reportTypeIds) -join
            "`n") -or
    (@($writtenManifest.CommunityFlagReasonIds) -join "`n") -cne
        (@($finalCommunityEphemeralSafetyState.observed.flagReasonIds) -join
            "`n") -or
    (@($writtenManifest.CommunityPublicReportFields) -join "`n") -cne
        (@($finalCommunityEphemeralSafetyState.observed.publicReportFields) -join
            "`n") -or
    (@($writtenManifest.CommunityPublicGroupFields) -join "`n") -cne
        (@($finalCommunityEphemeralSafetyState.observed.publicGroupFields) -join
            "`n") -or
    $writtenManifest.FirestoreCommunityTtlEvidenceSha256 -cne
        $firestoreCommunityTtlHistoricalState.EvidenceSha256 -or
    $writtenManifest.FirestoreCommunityTtlWriterContractSha256 -cne
        $firestoreCommunityTtlHistoricalState.WriterContractSha256 -or
    $writtenManifest.FirestoreCommunityTtlAuthoritativeBackendCommit -cne
        $releaseApiState.BackendCommit -or
    $writtenManifest.FirestoreCommunityTtlCloudAttestationNonce -cne
        $firestoreCommunityTtlHistoricalState.CloudAttestationNonce -or
    $writtenManifest.FirestoreCommunityTtlEvidenceCoreSha256 -cne
        $firestoreCommunityTtlHistoricalState.EvidenceCoreSha256 -or
    [int]$writtenManifest.VersionCode -ne $identity.VersionCode
) {
    throw "release_android_manifest_verification_failed: path=$releaseManifest"
}
Assert-PlayReleaseWorkspaceUnchanged `
    -RepositoryRoot $workspaceRoot `
    -ExpectedCommit $releaseGitState.Commit `
    -AllowedUntrackedPaths @($reservationPath, $releaseManifest) | Out-Null

if (Test-Path -LiteralPath $temporaryLayout.Root -PathType Container) {
    Remove-Item -LiteralPath $temporaryLayout.Root -Recurse -Force
}

[PSCustomObject]@{
    Aab = $releaseAab
    AabSha256 = $releaseAabSha256
    ApiBase = $normalizedApiBase
    ApiTag = $releaseApiState.ApiTag
    BackendCommit = $releaseApiState.BackendCommit
    BundletoolVersion = $bundletoolVersion
    CloudRunImageDigest = $releaseApiState.ImageDigest
    CloudRunRevision = $releaseApiState.Revision
    FrontendCommit = $finalGitState.Commit
    Health = $releaseApiState.Health
    Manifest = $releaseManifest
    Mapping = $releaseMapping
    MappingSha256 = $releaseMappingSha256
    NativeSymbolsStatus = $r8Artifacts.NativeSymbolsStatus
    Reservation = $reservationPath
    NextStep = (
        "Commit and push reservation + manifest, require green CI, then upload " +
        "this exact archived AAB. Record acceptance or abandonment append-only."
    )
    UploadCertificateSha256 = $certificateSha256
    UploadCertificateTrustSource = $certificateTrust.Source
    VersionCode = $identity.VersionCode
    VersionName = $identity.VersionName
} | Format-List
