Set-StrictMode -Version Latest

function Get-CutoverProperty {
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

function Get-CutoverRequiredString {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ErrorCode
    )

    $value = [string](Get-CutoverProperty -InputObject $InputObject -Name $Name)
    $value = $value.Trim()
    if (-not $value) {
        throw $ErrorCode
    }
    return $value
}

function Get-CutoverRequiredNonNegativeInteger {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$ErrorCode
    )

    $value = Get-CutoverProperty -InputObject $InputObject -Name $Name
    $text = ([string]$value).Trim()
    if ($null -eq $value -or $text -notmatch '^[0-9]+$') {
        throw "$ErrorCode`: name=$Name"
    }
    try {
        return [Convert]::ToInt32($text, [Globalization.CultureInfo]::InvariantCulture)
    } catch {
        throw "$ErrorCode`: name=$Name"
    }
}

function ConvertTo-CutoverFingerprint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$ErrorCode
    )

    $normalized = $Value.Trim().Replace(":", "").ToUpperInvariant()
    if ($normalized -notmatch '^[0-9A-F]{64}$') {
        throw $ErrorCode
    }
    return $normalized
}

function ConvertTo-CutoverDurationSeconds {
    param([object]$Value)

    $text = ([string]$Value).Trim()
    if (-not $text) {
        return 3600
    }
    if ($text -notmatch '^(?<seconds>[0-9]+)(?:\.(?<fraction>[0-9]{1,9}))?s$') {
        throw "cutover_app_check_token_ttl_invalid"
    }
    $seconds = [double]$Matches.seconds
    if ($Matches.ContainsKey("fraction") -and $Matches["fraction"]) {
        $seconds += [double]("0." + $Matches["fraction"])
    }
    if ($seconds -lt 1800 -or $seconds -gt 604800) {
        throw "cutover_app_check_token_ttl_out_of_range"
    }
    return [int][Math]::Ceiling($seconds)
}

function ConvertTo-CutoverEnvTable {
    param(
        [object]$Target,
        [Parameter(Mandatory = $true)]
        [string]$TargetName
    )

    $raw = Get-CutoverProperty -InputObject $Target -Name "env"
    if ($null -eq $raw) {
        throw "cutover_cloud_env_missing: target=$TargetName"
    }

    $table = @{}
    foreach ($property in $raw.PSObject.Properties) {
        if ($table.ContainsKey($property.Name)) {
            throw "cutover_cloud_env_duplicate: target=$TargetName name=$($property.Name)"
        }
        $table[$property.Name] = ([string]$property.Value).Trim()
    }
    return $table
}

function Assert-CutoverExactEnv {
    param(
        [hashtable]$Environment,
        [string]$Name,
        [string]$Expected,
        [string]$TargetName
    )

    if (-not $Environment.ContainsKey($Name)) {
        throw "cutover_cloud_env_required: target=$TargetName name=$Name"
    }
    if ([string]$Environment[$Name] -cne $Expected) {
        throw "cutover_cloud_env_mismatch: target=$TargetName name=$Name expected=$Expected actual=$($Environment[$Name])"
    }
}

function ConvertTo-CutoverAppVersionList {
    param(
        [object[]]$Values,
        [Parameter(Mandatory = $true)]
        [string]$ErrorCode
    )

    $versions = [Collections.Generic.List[string]]::new()
    $seen = [Collections.Generic.HashSet[string]]::new(
        [StringComparer]::Ordinal
    )
    foreach ($value in @($Values)) {
        foreach ($part in ([string]$value -split ",")) {
            $normalized = $part.Trim().ToLowerInvariant()
            if (-not $normalized -or
                $normalized -notmatch '^[a-z0-9][a-z0-9._+-]{0,63}$') {
                throw "$ErrorCode`: invalid=$part"
            }
            if (-not $seen.Add($normalized)) {
                throw "$ErrorCode`: duplicate=$normalized"
            }
            $versions.Add($normalized)
        }
    }
    if ($versions.Count -eq 0) {
        throw "$ErrorCode`: missing"
    }
    return @($versions.ToArray() | Sort-Object)
}

function Assert-CutoverAppVersionsEnv {
    param(
        [hashtable]$Environment,
        [string]$Name,
        [string[]]$Expected,
        [string]$TargetName
    )

    if (-not $Environment.ContainsKey($Name)) {
        throw "cutover_cloud_env_required: target=$TargetName name=$Name"
    }
    $actualRaw = [string]$Environment[$Name]
    $actual = @(ConvertTo-CutoverAppVersionList `
        -Values @($actualRaw) `
        -ErrorCode "cutover_cloud_env_invalid: target=$TargetName name=$Name")
    if (($actual -join "`n") -cne (@($Expected) -join "`n")) {
        throw (
            "cutover_cloud_env_mismatch: target=$TargetName name=$Name " +
            "expected=$(@($Expected) -join ',') actual=$actualRaw"
        )
    }
}

function Assert-CutoverEmptyEnv {
    param(
        [hashtable]$Environment,
        [string]$Name,
        [string]$TargetName
    )

    if ($Environment.ContainsKey($Name) -and [string]$Environment[$Name]) {
        throw "cutover_cloud_legacy_allowlist_not_empty: target=$TargetName name=$Name"
    }
}

function Assert-CutoverCloudTarget {
    param(
        [object]$Target,
        [string]$ExpectedName,
        [string]$TargetKind,
        [string]$ExpectedDigest
    )

    $actualName = Get-CutoverRequiredString -InputObject $Target -Name "name" -ErrorCode "cutover_cloud_target_name_missing"
    if ($actualName -cne $ExpectedName) {
        throw "cutover_cloud_target_name_mismatch: expected=$ExpectedName actual=$actualName"
    }
    $actualKind = Get-CutoverRequiredString -InputObject $Target -Name "kind" -ErrorCode "cutover_cloud_target_kind_missing"
    if ($actualKind -cne $TargetKind) {
        throw "cutover_cloud_target_kind_mismatch: target=$ExpectedName expected=$TargetKind actual=$actualKind"
    }
    $digest = Get-CutoverRequiredString -InputObject $Target -Name "imageDigest" -ErrorCode "cutover_cloud_image_digest_missing"
    if ($digest -notmatch '^.+@sha256:[0-9a-f]{64}$') {
        throw "cutover_cloud_image_digest_invalid: target=$ExpectedName"
    }
    if ($digest -cne $ExpectedDigest) {
        throw "cutover_cloud_image_digest_mismatch: target=$ExpectedName"
    }
    $ready = Get-CutoverProperty -InputObject $Target -Name "ready"
    if ($ready -ne $true) {
        throw "cutover_cloud_target_not_ready: target=$ExpectedName"
    }
}

function Assert-CutoverDebugTokenPagination {
    param([object]$Pages)

    $pageList = @($Pages)
    if ($pageList.Count -lt 1) {
        throw "cutover_debug_token_pages_missing"
    }

    $expectedRequestToken = ""
    $seenRequestTokens = [Collections.Generic.HashSet[string]]::new(
        [StringComparer]::Ordinal
    )
    $totalTokens = 0
    for ($index = 0; $index -lt $pageList.Count; $index += 1) {
        $page = $pageList[$index]
        $requestToken = [string](Get-CutoverProperty -InputObject $page -Name "requestPageToken")
        $nextToken = [string](Get-CutoverProperty -InputObject $page -Name "nextPageToken")
        if ($requestToken -cne $expectedRequestToken) {
            throw "cutover_debug_token_pagination_gap: page=$index"
        }
        if (-not $seenRequestTokens.Add($requestToken)) {
            throw "cutover_debug_token_pagination_cycle: page=$index"
        }
        $rawTokens = Get-CutoverProperty -InputObject $page -Name "debugTokens"
        $tokens = @()
        if ($null -ne $rawTokens) {
            $tokens = @($rawTokens)
        }
        $totalTokens += $tokens.Count
        if ($index -lt ($pageList.Count - 1) -and -not $nextToken) {
            throw "cutover_debug_token_pagination_truncated: page=$index"
        }
        $expectedRequestToken = $nextToken
    }

    if ($expectedRequestToken) {
        throw "cutover_debug_token_pagination_incomplete"
    }
    if ($totalTokens -ne 0) {
        throw "cutover_debug_tokens_present: count=$totalTokens"
    }
    return $totalTokens
}

function ConvertTo-CutoverUtcTimestamp {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Value,
        [Parameter(Mandatory = $true)]
        [string]$ErrorCode
    )

    if ($null -eq $Value) {
        throw $ErrorCode
    }
    if ($Value -is [datetimeoffset]) {
        return ([datetimeoffset]$Value).ToUniversalTime()
    }
    if ($Value -is [datetime]) {
        $dateTimeValue = [datetime]$Value
        if ($dateTimeValue.Kind -eq [DateTimeKind]::Unspecified) {
            $dateTimeValue = [DateTime]::SpecifyKind(
                $dateTimeValue,
                [DateTimeKind]::Utc
            )
        }
        return ([datetimeoffset]$dateTimeValue).ToUniversalTime()
    }

    $timestampText = [string]$Value
    if ([string]::IsNullOrWhiteSpace($timestampText)) {
        throw $ErrorCode
    }
    try {
        return [datetimeoffset]::Parse(
            $timestampText,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        ).ToUniversalTime()
    } catch {
        throw $ErrorCode
    }
}

function Assert-PlayNotificationCutoverSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Snapshot,

        [Parameter(Mandatory = $true)]
        [ValidateSet("staged", "active")]
        [string]$Phase,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedAccount,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedProjectId,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedProjectNumber,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedFirebaseAppId,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedAndroidPackage,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedPlaySigningSha256,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedEnrollmentGeneration,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedVersionName,

        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 2147483647)]
        [int]$ExpectedVersionCode,

        [string[]]$ExpectedAllowedAppVersions = @(),

        [Parameter(Mandatory = $true)]
        [ValidateRange(1, 500)]
        [int]$ExpectedMaxDevices,

        [datetimeoffset]$NowUtc = [datetimeoffset]::UtcNow,

        [string]$ExpectedRegion = "europe-west1",

        [string]$ExpectedServiceName = "meteofriul-api",

        [string]$ExpectedOfficialJobName = "meteofriul-official-alert-sync",

        [string]$ExpectedLocalJobName = "meteofriul-local-notice"
    )

    if ([int](Get-CutoverProperty -InputObject $Snapshot -Name "schemaVersion") -ne 1) {
        throw "cutover_snapshot_schema_unsupported"
    }
    $capturedAtText = Get-CutoverRequiredString -InputObject $Snapshot -Name "capturedAtUtc" -ErrorCode "cutover_snapshot_capture_time_missing"
    try {
        $capturedAt = [datetimeoffset]::Parse(
            $capturedAtText,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        )
    } catch {
        throw "cutover_snapshot_capture_time_invalid"
    }
    $snapshotAge = $NowUtc.ToUniversalTime() - $capturedAt.ToUniversalTime()
    if ($snapshotAge.TotalSeconds -lt -60 -or $snapshotAge.TotalMinutes -gt 15) {
        throw "cutover_snapshot_not_fresh"
    }
    if ($ExpectedEnrollmentGeneration -notmatch '^[a-z0-9][a-z0-9._-]{0,63}$') {
        throw "cutover_expected_generation_invalid"
    }
    if ($ExpectedVersionName.Trim() -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$') {
        throw "cutover_expected_version_name_invalid"
    }
    if ($Phase -ceq "staged" -and $ExpectedMaxDevices -ne 1) {
        throw "cutover_staged_cap_must_be_one"
    }

    $expectedFingerprint = ConvertTo-CutoverFingerprint `
        -Value $ExpectedPlaySigningSha256 `
        -ErrorCode "cutover_expected_play_signing_sha256_invalid"
    $expectedAppVersion = "$($ExpectedVersionName.Trim())+$ExpectedVersionCode"
    $requestedAllowedAppVersions = @($ExpectedAllowedAppVersions)
    if ($requestedAllowedAppVersions.Count -eq 0) {
        $requestedAllowedAppVersions = @($expectedAppVersion)
    }
    $expectedAllowedAppVersions = @(ConvertTo-CutoverAppVersionList `
        -Values $requestedAllowedAppVersions `
        -ErrorCode "cutover_expected_app_versions_invalid")
    if ($expectedAllowedAppVersions -cnotcontains $expectedAppVersion.ToLowerInvariant()) {
        throw "cutover_expected_current_app_version_missing"
    }

    $identity = Get-CutoverProperty -InputObject $Snapshot -Name "identity"
    $account = Get-CutoverRequiredString -InputObject $identity -Name "activeAccount" -ErrorCode "cutover_active_account_missing"
    $projectId = Get-CutoverRequiredString -InputObject $identity -Name "projectId" -ErrorCode "cutover_project_id_missing"
    $projectNumber = Get-CutoverRequiredString -InputObject $identity -Name "projectNumber" -ErrorCode "cutover_project_number_missing"
    if ($account -cne $ExpectedAccount) {
        throw "cutover_active_account_mismatch: expected=$ExpectedAccount actual=$account"
    }
    if ($projectId -cne $ExpectedProjectId -or $projectNumber -cne $ExpectedProjectNumber) {
        throw "cutover_project_mismatch: expected=$ExpectedProjectId/$ExpectedProjectNumber actual=$projectId/$projectNumber"
    }

    $firebase = Get-CutoverProperty -InputObject $Snapshot -Name "firebase"
    $androidApp = Get-CutoverProperty -InputObject $firebase -Name "androidApp"
    $expectedAndroidAppName = "projects/$ExpectedProjectId/androidApps/$ExpectedFirebaseAppId"
    $androidAppName = Get-CutoverRequiredString -InputObject $androidApp -Name "name" -ErrorCode "cutover_firebase_android_app_name_missing"
    $appId = Get-CutoverRequiredString -InputObject $androidApp -Name "appId" -ErrorCode "cutover_firebase_app_id_missing"
    $packageName = Get-CutoverRequiredString -InputObject $androidApp -Name "packageName" -ErrorCode "cutover_android_package_missing"
    $androidAppState = Get-CutoverRequiredString -InputObject $androidApp -Name "state" -ErrorCode "cutover_firebase_android_app_state_missing"
    if ($androidAppName -cne $expectedAndroidAppName -or
        $appId -cne $ExpectedFirebaseAppId -or
        $packageName -cne $ExpectedAndroidPackage -or
        $androidAppState -cne "ACTIVE") {
        throw "cutover_firebase_android_app_mismatch"
    }
    $shaCertificates = @(Get-CutoverProperty -InputObject $androidApp -Name "shaCertificates")
    $matchingSha = @(
        $shaCertificates | Where-Object {
            [string](Get-CutoverProperty -InputObject $_ -Name "certType") -ceq "SHA_256" -and
            (ConvertTo-CutoverFingerprint `
                -Value ([string](Get-CutoverProperty -InputObject $_ -Name "shaHash")) `
                -ErrorCode "cutover_firebase_sha256_invalid") -ceq $expectedFingerprint
        }
    )
    if ($matchingSha.Count -ne 1) {
        throw "cutover_play_signing_sha256_not_registered_in_firebase"
    }

    $appCheck = Get-CutoverProperty -InputObject $firebase -Name "appCheck"
    $playIntegrity = Get-CutoverProperty -InputObject $appCheck -Name "playIntegrityConfig"
    $expectedConfigName = "projects/$ExpectedProjectNumber/apps/$ExpectedFirebaseAppId/playIntegrityConfig"
    $configName = Get-CutoverRequiredString -InputObject $playIntegrity -Name "name" -ErrorCode "cutover_play_integrity_config_missing"
    if ($configName -cne $expectedConfigName) {
        throw "cutover_play_integrity_config_name_mismatch"
    }
    $appIntegrity = Get-CutoverProperty -InputObject $playIntegrity -Name "appIntegrity"
    $allowUnrecognizedVersion = Get-CutoverProperty `
        -InputObject $appIntegrity `
        -Name "allowUnrecognizedVersion"
    # Firebase uses protobuf JSON and omits scalar fields set to their default.
    # An omitted boolean therefore means false; only an explicit true is unsafe.
    if ($null -ne $allowUnrecognizedVersion -and $allowUnrecognizedVersion -ne $false) {
        throw "cutover_play_integrity_unrecognized_version_allowed"
    }
    $accountDetails = Get-CutoverProperty -InputObject $playIntegrity -Name "accountDetails"
    if ((Get-CutoverProperty -InputObject $accountDetails -Name "requireLicensed") -ne $true) {
        throw "cutover_play_integrity_license_not_required"
    }
    $deviceIntegrity = Get-CutoverProperty -InputObject $playIntegrity -Name "deviceIntegrity"
    $deviceLevel = [string](Get-CutoverProperty -InputObject $deviceIntegrity -Name "minDeviceRecognitionLevel")
    if ($deviceLevel -cne "MEETS_DEVICE_INTEGRITY") {
        throw "cutover_play_integrity_device_level_invalid: actual=$deviceLevel"
    }
    $currentTokenTtlSeconds = ConvertTo-CutoverDurationSeconds `
        -Value (Get-CutoverProperty -InputObject $playIntegrity -Name "tokenTtl")

    Assert-CutoverDebugTokenPagination `
        -Pages (Get-CutoverProperty -InputObject $appCheck -Name "debugTokenPages") | Out-Null

    $evidence = Get-CutoverProperty -InputObject $Snapshot -Name "debugTokenRevocationEvidence"
    if ((Get-CutoverProperty -InputObject $evidence -Name "tracked") -ne $true) {
        throw "cutover_debug_revocation_evidence_not_tracked"
    }
    if ((Get-CutoverProperty -InputObject $evidence -Name "clean") -ne $true) {
        throw "cutover_debug_revocation_evidence_dirty"
    }
    if ([int](Get-CutoverProperty -InputObject $evidence -Name "addCommitCount") -ne 1) {
        throw "cutover_debug_revocation_evidence_not_append_only"
    }
    if ([int](Get-CutoverProperty -InputObject $evidence -Name "mutationCommitCount") -ne 0) {
        throw "cutover_debug_revocation_evidence_was_modified"
    }
    $addCommitTimeText = Get-CutoverRequiredString -InputObject $evidence -Name "addCommitTimeUtc" -ErrorCode "cutover_debug_revocation_evidence_commit_time_missing"
    try {
        $addCommitTime = [datetimeoffset]::Parse(
            $addCommitTimeText,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        )
    } catch {
        throw "cutover_debug_revocation_evidence_commit_time_invalid"
    }
    $record = Get-CutoverProperty -InputObject $evidence -Name "record"
    if ([int](Get-CutoverProperty -InputObject $record -Name "schemaVersion") -ne 1 -or
        [string](Get-CutoverProperty -InputObject $record -Name "event") -cne "firebase-app-check-debug-tokens-revoked") {
        throw "cutover_debug_revocation_evidence_schema_invalid"
    }
    foreach ($pair in @(
        @("projectId", $ExpectedProjectId),
        @("projectNumber", $ExpectedProjectNumber),
        @("firebaseAppId", $ExpectedFirebaseAppId),
        @("androidPackage", $ExpectedAndroidPackage)
    )) {
        if ([string](Get-CutoverProperty -InputObject $record -Name $pair[0]) -cne [string]$pair[1]) {
            throw "cutover_debug_revocation_evidence_identity_mismatch: name=$($pair[0])"
        }
    }
    $evidenceFingerprint = ConvertTo-CutoverFingerprint `
        -Value ([string](Get-CutoverProperty -InputObject $record -Name "playSigningCertificateSha256")) `
        -ErrorCode "cutover_debug_revocation_evidence_sha256_invalid"
    if ($evidenceFingerprint -cne $expectedFingerprint) {
        throw "cutover_debug_revocation_evidence_sha256_mismatch"
    }
    if ((Get-CutoverRequiredNonNegativeInteger `
            -InputObject $record `
            -Name "verifiedDebugTokenCount" `
            -ErrorCode "cutover_debug_revocation_evidence_count_invalid") -ne 0) {
        throw "cutover_debug_revocation_evidence_count_invalid"
    }
    if ([string](Get-CutoverProperty -InputObject $record -Name "verificationMethod") -cne "firebase-app-check-rest-v1-paginated") {
        throw "cutover_debug_revocation_evidence_method_invalid"
    }
    Get-CutoverRequiredString -InputObject $record -Name "playConsoleEvidenceReference" -ErrorCode "cutover_play_console_evidence_reference_missing" | Out-Null
    Get-CutoverRequiredString -InputObject $record -Name "firebaseConsoleEvidenceReference" -ErrorCode "cutover_firebase_console_evidence_reference_missing" | Out-Null
    $revokedAtText = Get-CutoverRequiredString -InputObject $record -Name "revokedAtUtc" -ErrorCode "cutover_debug_revoked_at_missing"
    try {
        $revokedAt = [datetimeoffset]::Parse(
            $revokedAtText,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        )
    } catch {
        throw "cutover_debug_revoked_at_invalid"
    }
    $recordedAtText = Get-CutoverRequiredString -InputObject $record -Name "recordedAtUtc" -ErrorCode "cutover_debug_recorded_at_missing"
    try {
        $recordedAt = [datetimeoffset]::Parse(
            $recordedAtText,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal
        )
    } catch {
        throw "cutover_debug_recorded_at_invalid"
    }
    if ($recordedAt -lt $revokedAt) {
        throw "cutover_debug_recorded_at_invalid"
    }
    if ($recordedAt -gt $NowUtc.ToUniversalTime() -or
        $addCommitTime -lt $recordedAt -or
        $addCommitTime -gt $NowUtc.ToUniversalTime()) {
        throw "cutover_debug_revocation_evidence_timeline_invalid"
    }
    $evidenceTtl = [int](Get-CutoverProperty -InputObject $record -Name "maximumTokenTtlSeconds")
    if ($evidenceTtl -lt 1800 -or $evidenceTtl -gt 604800) {
        throw "cutover_debug_revocation_evidence_ttl_invalid"
    }
    $waitSeconds = [Math]::Max($evidenceTtl, $currentTokenTtlSeconds)
    $eligibleAt = $revokedAt.ToUniversalTime().AddSeconds($waitSeconds)
    if ($NowUtc.ToUniversalTime() -lt $eligibleAt) {
        throw "cutover_debug_token_ttl_not_elapsed: eligible_at=$($eligibleAt.ToString('o'))"
    }

    if ($Phase -ceq "active") {
        $cleanupEvidence = Get-CutoverProperty -InputObject $Snapshot -Name "legacyPushCleanupEvidence"
        if ((Get-CutoverProperty -InputObject $cleanupEvidence -Name "tracked") -ne $true) {
            throw "cutover_legacy_push_cleanup_evidence_not_tracked"
        }
        if ((Get-CutoverProperty -InputObject $cleanupEvidence -Name "clean") -ne $true) {
            throw "cutover_legacy_push_cleanup_evidence_dirty"
        }
        if ([int](Get-CutoverProperty -InputObject $cleanupEvidence -Name "addCommitCount") -ne 1) {
            throw "cutover_legacy_push_cleanup_evidence_not_append_only"
        }
        if ([int](Get-CutoverProperty -InputObject $cleanupEvidence -Name "mutationCommitCount") -ne 0) {
            throw "cutover_legacy_push_cleanup_evidence_was_modified"
        }
        $cleanupCommitTimeText = Get-CutoverRequiredString `
            -InputObject $cleanupEvidence `
            -Name "addCommitTimeUtc" `
            -ErrorCode "cutover_legacy_push_cleanup_evidence_commit_time_missing"
        try {
            $cleanupCommitTime = [datetimeoffset]::Parse(
                $cleanupCommitTimeText,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal
            )
        } catch {
            throw "cutover_legacy_push_cleanup_evidence_commit_time_invalid"
        }

        $cleanupRecord = Get-CutoverProperty -InputObject $cleanupEvidence -Name "record"
        if ([int](Get-CutoverProperty -InputObject $cleanupRecord -Name "schemaVersion") -ne 1 -or
            [string](Get-CutoverProperty -InputObject $cleanupRecord -Name "event") -cne "legacy-push-state-cleanup-verified") {
            throw "cutover_legacy_push_cleanup_evidence_schema_invalid"
        }
        foreach ($pair in @(
            @("projectId", $ExpectedProjectId),
            @("projectNumber", $ExpectedProjectNumber),
            @("firebaseAppId", $ExpectedFirebaseAppId),
            @("androidPackage", $ExpectedAndroidPackage),
            @("currentEnrollmentGeneration", $ExpectedEnrollmentGeneration)
        )) {
            if ([string](Get-CutoverProperty -InputObject $cleanupRecord -Name $pair[0]) -cne [string]$pair[1]) {
                throw "cutover_legacy_push_cleanup_evidence_identity_mismatch: name=$($pair[0])"
            }
        }
        $cleanupAppVersion = (Get-CutoverRequiredString `
            -InputObject $cleanupRecord `
            -Name "currentAppVersion" `
            -ErrorCode "cutover_legacy_push_cleanup_evidence_identity_mismatch: name=currentAppVersion").ToLowerInvariant()
        if ($expectedAllowedAppVersions -cnotcontains $cleanupAppVersion) {
            throw "cutover_legacy_push_cleanup_evidence_identity_mismatch: name=currentAppVersion"
        }
        if ([string](Get-CutoverProperty -InputObject $cleanupRecord -Name "cleanupScope") -cne
            "missing-or-different-enrollment-generation-only") {
            throw "cutover_legacy_push_cleanup_scope_invalid"
        }
        if ([string](Get-CutoverProperty -InputObject $cleanupRecord -Name "verificationMethod") -cne
            "firestore-admin-paginated-read-back") {
            throw "cutover_legacy_push_cleanup_method_invalid"
        }
        Get-CutoverRequiredString `
            -InputObject $cleanupRecord `
            -Name "evidenceReference" `
            -ErrorCode "cutover_legacy_push_cleanup_reference_missing" | Out-Null
        foreach ($countName in @(
            "legacyPushDeviceCountAfterReadBack",
            "orphanOrLegacyTargetOwnerCountAfterReadBack",
            "legacyCapacityDocumentCountAfterReadBack"
        )) {
            if ((Get-CutoverRequiredNonNegativeInteger `
                    -InputObject $cleanupRecord `
                    -Name $countName `
                    -ErrorCode "cutover_legacy_push_cleanup_count_invalid") -ne 0) {
                throw "cutover_legacy_push_cleanup_residue_present: name=$countName"
            }
        }
        $currentDeviceCount = Get-CutoverRequiredNonNegativeInteger `
            -InputObject $cleanupRecord `
            -Name "currentGenerationPushDeviceCountAfterReadBack" `
            -ErrorCode "cutover_legacy_push_cleanup_count_invalid"
        $currentOwnerCount = Get-CutoverRequiredNonNegativeInteger `
            -InputObject $cleanupRecord `
            -Name "currentGenerationTargetOwnerCountAfterReadBack" `
            -ErrorCode "cutover_legacy_push_cleanup_count_invalid"
        $currentCapacityCount = Get-CutoverRequiredNonNegativeInteger `
            -InputObject $cleanupRecord `
            -Name "currentGenerationCapacityDocumentCountAfterReadBack" `
            -ErrorCode "cutover_legacy_push_cleanup_count_invalid"
        $currentCapacityActiveCount = Get-CutoverRequiredNonNegativeInteger `
            -InputObject $cleanupRecord `
            -Name "currentGenerationCapacityActiveCountAfterReadBack" `
            -ErrorCode "cutover_legacy_push_cleanup_count_invalid"
        if ($currentDeviceCount -lt 1 -or $currentDeviceCount -gt $ExpectedMaxDevices -or
            $currentOwnerCount -ne $currentDeviceCount -or
            $currentCapacityCount -ne 1 -or
            $currentCapacityActiveCount -ne $currentDeviceCount -or
            (Get-CutoverProperty -InputObject $cleanupRecord -Name "currentPlayRecordPreserved") -ne $true) {
            throw "cutover_current_play_registration_not_preserved"
        }

        $cleanupTimes = @{}
        foreach ($timeField in @(
            "firstPlayRegistrationVerifiedAtUtc",
            "cleanupCompletedAtUtc",
            "readBackAtUtc",
            "recordedAtUtc"
        )) {
            $timeText = Get-CutoverRequiredString `
                -InputObject $cleanupRecord `
                -Name $timeField `
                -ErrorCode "cutover_legacy_push_cleanup_time_missing: name=$timeField"
            try {
                $cleanupTimes[$timeField] = [datetimeoffset]::Parse(
                    $timeText,
                    [Globalization.CultureInfo]::InvariantCulture,
                    [Globalization.DateTimeStyles]::AssumeUniversal
                ).ToUniversalTime()
            } catch {
                throw "cutover_legacy_push_cleanup_time_invalid: name=$timeField"
            }
        }
        if ($cleanupTimes.firstPlayRegistrationVerifiedAtUtc -gt $cleanupTimes.cleanupCompletedAtUtc -or
            $cleanupTimes.cleanupCompletedAtUtc -gt $cleanupTimes.readBackAtUtc -or
            $cleanupTimes.readBackAtUtc -gt $cleanupTimes.recordedAtUtc -or
            $cleanupTimes.recordedAtUtc -gt $NowUtc.ToUniversalTime() -or
            $cleanupCommitTime.ToUniversalTime() -lt $cleanupTimes.recordedAtUtc -or
            $cleanupCommitTime.ToUniversalTime() -gt $NowUtc.ToUniversalTime()) {
            throw "cutover_legacy_push_cleanup_timeline_invalid"
        }
    }

    $aabEvidence = Get-CutoverProperty -InputObject $Snapshot -Name "aabReleaseManifestEvidence"
    if ((Get-CutoverProperty -InputObject $aabEvidence -Name "tracked") -ne $true) {
        throw "cutover_aab_release_manifest_not_tracked"
    }
    if ((Get-CutoverProperty -InputObject $aabEvidence -Name "clean") -ne $true) {
        throw "cutover_aab_release_manifest_dirty"
    }
    if ([int](Get-CutoverProperty -InputObject $aabEvidence -Name "addCommitCount") -ne 1 -or
        [int](Get-CutoverProperty -InputObject $aabEvidence -Name "mutationCommitCount") -ne 0) {
        throw "cutover_aab_release_manifest_not_append_only"
    }
    $aabCommitTime = ConvertTo-CutoverUtcTimestamp `
        -Value (Get-CutoverProperty `
            -InputObject $aabEvidence `
            -Name "addCommitTimeUtc") `
        -ErrorCode "cutover_aab_release_manifest_commit_time_invalid"
    if ($aabCommitTime -gt $NowUtc.ToUniversalTime()) {
        throw "cutover_aab_release_manifest_timeline_invalid"
    }
    $aabRecord = Get-CutoverProperty -InputObject $aabEvidence -Name "record"
    if ([int](Get-CutoverProperty -InputObject $aabRecord -Name "SchemaVersion") -lt 2 -or
        [string](Get-CutoverProperty -InputObject $aabRecord -Name "Target") -cne "android-play" -or
        [string](Get-CutoverProperty -InputObject $aabRecord -Name "Status") -cne "built-not-uploaded") {
        throw "cutover_aab_release_manifest_schema_invalid"
    }
    if ([string](Get-CutoverProperty -InputObject $aabRecord -Name "ApplicationId") -cne $ExpectedAndroidPackage -or
        [string](Get-CutoverProperty -InputObject $aabRecord -Name "VersionName") -cne $ExpectedVersionName.Trim() -or
        [int](Get-CutoverProperty -InputObject $aabRecord -Name "VersionCode") -ne $ExpectedVersionCode) {
        throw "cutover_aab_release_manifest_identity_mismatch"
    }
    $aabSha256 = ConvertTo-CutoverFingerprint `
        -Value ([string](Get-CutoverProperty -InputObject $aabRecord -Name "AabSha256")) `
        -ErrorCode "cutover_aab_release_manifest_sha256_invalid"
    foreach ($commitName in @("FrontendCommit", "BackendCommit")) {
        $commit = [string](Get-CutoverProperty -InputObject $aabRecord -Name $commitName)
        if ($commit -notmatch '^[0-9a-f]{40}$') {
            throw "cutover_aab_release_manifest_commit_invalid: name=$commitName"
        }
    }
    $expectedApiBase = Get-CutoverRequiredString `
        -InputObject $aabRecord -Name "ApiBase" `
        -ErrorCode "cutover_aab_release_manifest_api_base_missing"
    try {
        $expectedApiUri = [Uri]$expectedApiBase
    } catch {
        throw "cutover_aab_release_manifest_api_base_invalid"
    }
    if (-not $expectedApiUri.IsAbsoluteUri -or
        $expectedApiUri.Scheme -cne "https" -or
        $expectedApiUri.AbsolutePath.TrimEnd('/') -cne "/api" -or
        $expectedApiUri.Query -or $expectedApiUri.Fragment) {
        throw "cutover_aab_release_manifest_api_base_invalid"
    }
    $expectedApiTag = Get-CutoverRequiredString `
        -InputObject $aabRecord -Name "ApiTag" `
        -ErrorCode "cutover_aab_release_manifest_api_tag_missing"
    if ($expectedApiTag -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$' -or
        -not $expectedApiUri.Host.StartsWith("$expectedApiTag---", [StringComparison]::Ordinal)) {
        throw "cutover_aab_release_manifest_api_tag_invalid"
    }
    $expectedRevision = Get-CutoverRequiredString `
        -InputObject $aabRecord -Name "CloudRunRevision" `
        -ErrorCode "cutover_aab_release_manifest_revision_missing"
    $expectedDigest = Get-CutoverRequiredString `
        -InputObject $aabRecord -Name "CloudRunImageDigest" `
        -ErrorCode "cutover_aab_release_manifest_digest_missing"
    if ($expectedDigest -notmatch '^.+@sha256:[0-9a-f]{64}$') {
        throw "cutover_aab_release_manifest_digest_invalid"
    }

    $aabEvidencePath = Get-CutoverRequiredString `
        -InputObject $aabEvidence `
        -Name "path" `
        -ErrorCode "cutover_aab_release_manifest_path_missing"
    $aabManifestSha256 = ConvertTo-CutoverFingerprint `
        -Value ([string](Get-CutoverProperty -InputObject $aabEvidence -Name "fileSha256")) `
        -ErrorCode "cutover_aab_release_manifest_file_sha256_invalid"
    $expectedTagUrl = $expectedApiUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/')
    $runtimeRevision = $expectedRevision
    $runtimeEvidenceRaw = Get-CutoverProperty `
        -InputObject $Snapshot `
        -Name "runtimeRevisionEvidence"
    [object[]]$runtimeEvidenceStates = @()
    if ($null -ne $runtimeEvidenceRaw) {
        [object[]]$runtimeEvidenceStates = @($runtimeEvidenceRaw)
    }
    $runtimeLineage = [Collections.Generic.List[object]]::new()
    $runtimeLineage.Add([PSCustomObject]@{
        evidencePath = [string](Get-CutoverProperty -InputObject $aabEvidence -Name "path")
        imageDigest = $expectedDigest
        recordedAtUtc = $aabCommitTime.ToString("o")
        retargetedAtUtc = $null
        revision = $expectedRevision
        sequence = 0
        source = "aab-manifest"
        tag = $expectedApiTag
        tagUrl = $expectedTagUrl
    })
    $seenRuntimeRevisions = [Collections.Generic.HashSet[string]]::new(
        [StringComparer]::Ordinal
    )
    [void]$seenRuntimeRevisions.Add($expectedRevision)
    $previousRetargetTime = $aabCommitTime
    $previousEvidenceCommitTime = $aabCommitTime
    $previousEvidencePath = ""
    $activePurposeSeen = $false

    for ($runtimeIndex = 0; $runtimeIndex -lt $runtimeEvidenceStates.Count; $runtimeIndex += 1) {
        $runtimeEvidence = $runtimeEvidenceStates[$runtimeIndex]
        $runtimeEvidencePath = Get-CutoverRequiredString `
            -InputObject $runtimeEvidence `
            -Name "path" `
            -ErrorCode "cutover_runtime_revision_evidence_path_missing: index=$runtimeIndex"
        if ($runtimeEvidencePath -notmatch
            '^release-history/play-notification-cutover/evidence/\d{8}T\d{6}Z-runtime-revision-retarget-verified\.json$') {
            throw "cutover_runtime_revision_evidence_path_invalid: index=$runtimeIndex"
        }
        if ((Get-CutoverProperty -InputObject $runtimeEvidence -Name "tracked") -ne $true) {
            throw "cutover_runtime_revision_evidence_not_tracked: index=$runtimeIndex"
        }
        if ((Get-CutoverProperty -InputObject $runtimeEvidence -Name "clean") -ne $true) {
            throw "cutover_runtime_revision_evidence_dirty: index=$runtimeIndex"
        }
        if ([int](Get-CutoverProperty -InputObject $runtimeEvidence -Name "addCommitCount") -ne 1) {
            throw "cutover_runtime_revision_evidence_not_append_only: index=$runtimeIndex"
        }
        if ([int](Get-CutoverProperty -InputObject $runtimeEvidence -Name "mutationCommitCount") -ne 0) {
            throw "cutover_runtime_revision_evidence_was_modified: index=$runtimeIndex"
        }
        $runtimeCommitTime = ConvertTo-CutoverUtcTimestamp `
            -Value (Get-CutoverProperty `
                -InputObject $runtimeEvidence `
                -Name "addCommitTimeUtc") `
            -ErrorCode "cutover_runtime_revision_evidence_commit_time_invalid: index=$runtimeIndex"

        $runtimeRecord = Get-CutoverProperty -InputObject $runtimeEvidence -Name "record"
        if ([int](Get-CutoverProperty -InputObject $runtimeRecord -Name "schemaVersion") -ne 1 -or
            [string](Get-CutoverProperty -InputObject $runtimeRecord -Name "event") -cne
                "android-play-runtime-revision-retarget-verified") {
            throw "cutover_runtime_revision_evidence_schema_invalid: index=$runtimeIndex"
        }
        foreach ($pair in @(
            @("projectId", $ExpectedProjectId),
            @("projectNumber", $ExpectedProjectNumber),
            @("region", $ExpectedRegion),
            @("serviceName", $ExpectedServiceName),
            @("androidPackage", $ExpectedAndroidPackage),
            @("versionName", $ExpectedVersionName.Trim()),
            @("versionCode", [string]$ExpectedVersionCode)
        )) {
            if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name $pair[0]) -cne
                [string]$pair[1]) {
                throw "cutover_runtime_revision_evidence_identity_mismatch: index=$runtimeIndex name=$($pair[0])"
            }
        }
        $runtimeAabSha256 = ConvertTo-CutoverFingerprint `
            -Value ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "aabSha256")) `
            -ErrorCode "cutover_runtime_revision_evidence_aab_sha256_invalid: index=$runtimeIndex"
        if ($runtimeAabSha256 -cne $aabSha256) {
            throw "cutover_runtime_revision_evidence_aab_sha256_mismatch: index=$runtimeIndex"
        }
        if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "aabReleaseManifestPath") -cne
                $aabEvidencePath -or
            (ConvertTo-CutoverFingerprint `
                -Value ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "aabReleaseManifestSha256")) `
                -ErrorCode "cutover_runtime_revision_evidence_manifest_sha256_invalid: index=$runtimeIndex") -cne
                $aabManifestSha256) {
            throw "cutover_runtime_revision_evidence_manifest_binding_mismatch: index=$runtimeIndex"
        }
        if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "previousEvidencePath") -cne
            $previousEvidencePath) {
            throw "cutover_runtime_revision_evidence_previous_path_mismatch: index=$runtimeIndex"
        }
        if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "apiTag") -cne $expectedApiTag -or
            [string](Get-CutoverProperty -InputObject $runtimeRecord -Name "apiBase") -cne $expectedApiBase) {
            throw "cutover_runtime_revision_evidence_api_binding_mismatch: index=$runtimeIndex"
        }
        if ((Get-CutoverProperty -InputObject $runtimeRecord -Name "sameImageDigest") -ne $true) {
            throw "cutover_runtime_revision_evidence_digest_changed: index=$runtimeIndex"
        }
        $configurationPurpose = [string](Get-CutoverProperty `
            -InputObject $runtimeRecord `
            -Name "configurationPurpose")
        if ($configurationPurpose -ceq "play-notification-cutover-active") {
            $activePurposeSeen = $true
        } elseif ($configurationPurpose -ceq "play-notification-cutover-staged") {
            if ($Phase -ceq "active" -and $activePurposeSeen) {
                throw "cutover_runtime_revision_evidence_purpose_invalid: index=$runtimeIndex"
            }
        } else {
            throw "cutover_runtime_revision_evidence_purpose_invalid: index=$runtimeIndex"
        }
        if ($Phase -ceq "staged" -and
            $configurationPurpose -cne "play-notification-cutover-staged") {
            throw "cutover_runtime_revision_evidence_purpose_invalid: index=$runtimeIndex"
        }
        if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "verificationMethod") -cne
            "cloud-run-admin-read-back") {
            throw "cutover_runtime_revision_evidence_method_invalid: index=$runtimeIndex"
        }

        $fromRevision = Get-CutoverRequiredString `
            -InputObject $runtimeRecord -Name "fromRevision" `
            -ErrorCode "cutover_runtime_revision_evidence_from_revision_missing: index=$runtimeIndex"
        $toRevision = Get-CutoverRequiredString `
            -InputObject $runtimeRecord -Name "toRevision" `
            -ErrorCode "cutover_runtime_revision_evidence_to_revision_missing: index=$runtimeIndex"
        if ($fromRevision -cne $runtimeRevision) {
            throw "cutover_runtime_revision_evidence_chain_gap: index=$runtimeIndex expected=$runtimeRevision actual=$fromRevision"
        }
        if ($toRevision -notmatch '^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$' -or
            $toRevision -ceq $fromRevision -or
            -not $seenRuntimeRevisions.Add($toRevision)) {
            throw "cutover_runtime_revision_evidence_chain_cycle: index=$runtimeIndex"
        }

        $fromDigest = Get-CutoverRequiredString `
            -InputObject $runtimeRecord -Name "fromImageDigest" `
            -ErrorCode "cutover_runtime_revision_evidence_digest_missing: index=$runtimeIndex side=from"
        $toDigest = Get-CutoverRequiredString `
            -InputObject $runtimeRecord -Name "toImageDigest" `
            -ErrorCode "cutover_runtime_revision_evidence_digest_missing: index=$runtimeIndex side=to"
        if ($fromDigest -cne $expectedDigest -or $toDigest -cne $expectedDigest) {
            throw "cutover_runtime_revision_evidence_digest_mismatch: index=$runtimeIndex"
        }
        if ([string](Get-CutoverProperty -InputObject $runtimeRecord -Name "fromTag") -cne
                $expectedApiTag -or
            [string](Get-CutoverProperty -InputObject $runtimeRecord -Name "toTag") -cne
                $expectedApiTag) {
            throw "cutover_runtime_revision_evidence_tag_mismatch: index=$runtimeIndex"
        }

        foreach ($urlName in @("fromTagUrl", "toTagUrl")) {
            $tagUrl = Get-CutoverRequiredString `
                -InputObject $runtimeRecord -Name $urlName `
                -ErrorCode "cutover_runtime_revision_evidence_tag_url_missing: index=$runtimeIndex name=$urlName"
            try {
                $tagUri = [Uri]$tagUrl
            } catch {
                throw "cutover_runtime_revision_evidence_tag_url_invalid: index=$runtimeIndex name=$urlName"
            }
            if (-not $tagUri.IsAbsoluteUri -or
                $tagUri.Scheme -cne "https" -or
                $tagUri.Query -or $tagUri.Fragment -or
                $tagUri.AbsolutePath.TrimEnd('/') -ne "" -or
                $tagUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/') -cne $expectedTagUrl) {
                throw "cutover_runtime_revision_evidence_tag_url_mismatch: index=$runtimeIndex name=$urlName"
            }
        }

        $retargetedAt = ConvertTo-CutoverUtcTimestamp `
            -Value (Get-CutoverProperty `
                -InputObject $runtimeRecord `
                -Name "retargetedAtUtc") `
            -ErrorCode "cutover_runtime_revision_evidence_retargeted_at_invalid: index=$runtimeIndex"
        $runtimeRecordedAt = ConvertTo-CutoverUtcTimestamp `
            -Value (Get-CutoverProperty `
                -InputObject $runtimeRecord `
                -Name "recordedAtUtc") `
            -ErrorCode "cutover_runtime_revision_evidence_recorded_at_invalid: index=$runtimeIndex"
        if ($retargetedAt -lt $previousRetargetTime -or
            $runtimeRecordedAt -lt $retargetedAt -or
            $runtimeCommitTime -lt $runtimeRecordedAt -or
            $runtimeCommitTime -lt $previousEvidenceCommitTime -or
            $runtimeCommitTime -gt $NowUtc.ToUniversalTime()) {
            throw "cutover_runtime_revision_evidence_timeline_invalid: index=$runtimeIndex"
        }

        $runtimeRevision = $toRevision
        $previousRetargetTime = $retargetedAt
        $previousEvidenceCommitTime = $runtimeCommitTime
        $previousEvidencePath = $runtimeEvidencePath
        $runtimeLineage.Add([PSCustomObject]@{
            configurationPurpose = $configurationPurpose
            evidencePath = $previousEvidencePath
            imageDigest = $toDigest
            recordedAtUtc = $runtimeRecordedAt.ToString("o")
            retargetedAtUtc = $retargetedAt.ToString("o")
            revision = $toRevision
            sequence = $runtimeIndex + 1
            source = "runtime-revision-retarget-evidence"
            tag = $expectedApiTag
            tagUrl = $expectedTagUrl
        })
    }
    if ($Phase -ceq "active" -and
        $runtimeEvidenceStates.Count -gt 0 -and
        -not $activePurposeSeen) {
        throw "cutover_runtime_revision_evidence_purpose_invalid: active_retarget_missing"
    }

    $cloudRun = Get-CutoverProperty -InputObject $Snapshot -Name "cloudRun"
    $service = Get-CutoverProperty -InputObject $cloudRun -Name "service"
    $officialJob = Get-CutoverProperty -InputObject $cloudRun -Name "officialAlertsJob"
    $localJob = Get-CutoverProperty -InputObject $cloudRun -Name "localNoticesJob"
    Assert-CutoverCloudTarget -Target $service -ExpectedName $ExpectedServiceName -TargetKind "service" -ExpectedDigest $expectedDigest
    Assert-CutoverCloudTarget -Target $officialJob -ExpectedName $ExpectedOfficialJobName -TargetKind "job" -ExpectedDigest $expectedDigest
    Assert-CutoverCloudTarget -Target $localJob -ExpectedName $ExpectedLocalJobName -TargetKind "job" -ExpectedDigest $expectedDigest
    if ([string](Get-CutoverProperty -InputObject $service -Name "revision") -cne $runtimeRevision -or
        [string](Get-CutoverProperty -InputObject $service -Name "trafficRevision") -cne $runtimeRevision) {
        throw "cutover_runtime_revision_lineage_incomplete: expected=$runtimeRevision"
    }
    if ([string](Get-CutoverProperty -InputObject $service -Name "trafficTag") -cne $expectedApiTag) {
        throw "cutover_cloud_tag_revision_mismatch"
    }
    $trafficUrl = Get-CutoverRequiredString `
        -InputObject $service -Name "trafficUrl" `
        -ErrorCode "cutover_cloud_tag_url_missing"
    try {
        $trafficUri = [Uri]$trafficUrl
    } catch {
        throw "cutover_cloud_tag_url_invalid"
    }
    if (-not $trafficUri.IsAbsoluteUri -or
        $trafficUri.Scheme -cne "https" -or
        $trafficUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/') -cne
            $expectedApiUri.GetLeftPart([UriPartial]::Authority).TrimEnd('/')) {
        throw "cutover_cloud_tag_url_mismatch"
    }

    $serviceEnv = ConvertTo-CutoverEnvTable -Target $service -TargetName $ExpectedServiceName
    $officialEnv = ConvertTo-CutoverEnvTable -Target $officialJob -TargetName $ExpectedOfficialJobName
    $localEnv = ConvertTo-CutoverEnvTable -Target $localJob -TargetName $ExpectedLocalJobName
    $targets = @(
        [PSCustomObject]@{ Name = $ExpectedServiceName; Env = $serviceEnv },
        [PSCustomObject]@{ Name = $ExpectedOfficialJobName; Env = $officialEnv },
        [PSCustomObject]@{ Name = $ExpectedLocalJobName; Env = $localEnv }
    )
    foreach ($target in $targets) {
        Assert-CutoverExactEnv -Environment $target.Env -Name "PUSH_PILOT_ENROLLMENT_MODE" -Expected "play_beta" -TargetName $target.Name
        Assert-CutoverExactEnv -Environment $target.Env -Name "LOCAL_NOTICE_ENROLLMENT_MODE" -Expected "play_beta" -TargetName $target.Name
        Assert-CutoverExactEnv -Environment $target.Env -Name "PUSH_ENROLLMENT_GENERATION" -Expected $ExpectedEnrollmentGeneration -TargetName $target.Name
        Assert-CutoverExactEnv -Environment $target.Env -Name "PUSH_APP_CHECK_ANDROID_APP_IDS" -Expected $ExpectedFirebaseAppId -TargetName $target.Name
        Assert-CutoverAppVersionsEnv -Environment $target.Env -Name "PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS" -Expected $expectedAllowedAppVersions -TargetName $target.Name
        Assert-CutoverExactEnv -Environment $target.Env -Name "PUSH_PILOT_MAX_DEVICES" -Expected ([string]$ExpectedMaxDevices) -TargetName $target.Name
        Assert-CutoverEmptyEnv -Environment $target.Env -Name "PUSH_PILOT_ALLOWED_INSTALLATION_HASHES" -TargetName $target.Name
        Assert-CutoverEmptyEnv -Environment $target.Env -Name "LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES" -TargetName $target.Name
    }
    Assert-CutoverExactEnv -Environment $serviceEnv -Name "PUSH_APP_CHECK_MODE" -Expected "enforce" -TargetName $ExpectedServiceName

    $expectedDeliveryMode = if ($Phase -ceq "staged") { "dry_run" } else { "send" }
    Assert-CutoverExactEnv -Environment $serviceEnv -Name "PUSH_OFFICIAL_ALERTS_MODE" -Expected $expectedDeliveryMode -TargetName $ExpectedServiceName
    Assert-CutoverExactEnv -Environment $officialEnv -Name "PUSH_OFFICIAL_ALERTS_MODE" -Expected $expectedDeliveryMode -TargetName $ExpectedOfficialJobName
    Assert-CutoverExactEnv -Environment $localEnv -Name "LOCAL_NOTICE_DELIVERY_MODE" -Expected $expectedDeliveryMode -TargetName $ExpectedLocalJobName
    $requiredValue = if ($Phase -ceq "active") { "true" } else { "false" }
    Assert-CutoverExactEnv -Environment $officialEnv -Name "PUSH_OFFICIAL_ALERTS_REQUIRED" -Expected $requiredValue -TargetName $ExpectedOfficialJobName

    return [PSCustomObject]@{
        Account = $account
        AabSha256 = $aabSha256
        ApiBase = $expectedApiBase
        ApiTag = $expectedApiTag
        AppCheckTokenTtlSeconds = $currentTokenTtlSeconds
        AppVersion = $expectedAppVersion
        AllowedAppVersions = @($expectedAllowedAppVersions)
        DebugTokenCount = 0
        Digest = $expectedDigest
        EligibleSinceUtc = $eligibleAt.ToString("o")
        EnrollmentGeneration = $ExpectedEnrollmentGeneration
        MaxDevices = $ExpectedMaxDevices
        Phase = $Phase
        AabRevision = $expectedRevision
        ApiTagRetarget = if ($runtimeEvidenceStates.Count -gt 0) { "VERIFIED" } else { "NOT_REQUIRED" }
        Revision = $runtimeRevision
        RuntimeRevisionEvidenceCount = $runtimeEvidenceStates.Count
        RuntimeRevisionLineage = $runtimeLineage.ToArray()
        LegacyPushCleanup = if ($Phase -ceq "active") { "VERIFIED" } else { "NOT_YET_REQUIRED" }
        Project = "$projectId/$projectNumber"
        Status = "PASS"
    }
}

Export-ModuleMember -Function @(
    "Assert-PlayNotificationCutoverSnapshot",
    "ConvertTo-CutoverDurationSeconds",
    "ConvertTo-CutoverFingerprint"
)
