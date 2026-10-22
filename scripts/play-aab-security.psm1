Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:Sha256Pattern = '^[0-9a-f]{64}$'
$script:VersionNamePattern = '^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$'

function ConvertTo-PlaySha256 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [string]$FailureCode = "release_android_play_sha256_invalid"
    )

    $normalized = ($Value.Trim() -replace ':', '').ToLowerInvariant()
    if ($normalized -notmatch $script:Sha256Pattern) {
        throw $FailureCode
    }
    return $normalized
}

function Assert-PlayBundletoolTrust {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "release_android_play_bundletool_not_found: path=$resolved"
    }
    if ([IO.Path]::GetExtension($resolved) -cne ".jar") {
        throw "release_android_play_bundletool_must_be_jar: path=$resolved"
    }
    $expected = ConvertTo-PlaySha256 `
        -Value $ExpectedSha256 `
        -FailureCode "release_android_play_bundletool_expected_sha256_invalid"
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolved).Hash.ToLowerInvariant()
    if ($actual -cne $expected) {
        throw (
            "release_android_play_bundletool_sha256_mismatch: " +
            "expected=$expected actual=$actual path=$resolved"
        )
    }
    return [PSCustomObject]@{ Path = $resolved; Sha256 = $actual }
}

function Assert-PlayGoogleServicesConfiguration {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string]$ExpectedProjectId = "meteo-friul",
        [string]$ExpectedProjectNumber = "49007668366",
        [string]$ExpectedApplicationId = "com.meteofriul.app",
        [string]$ExpectedFirebaseAppId = "1:49007668366:android:725bf6f8b339177a852ddf"
    )

    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        throw "release_android_play_google_services_missing: path=$resolved"
    }
    try {
        $payload = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json
    } catch {
        throw "release_android_play_google_services_invalid: path=$resolved"
    }

    if ([string]$payload.project_info.project_id -cne $ExpectedProjectId) {
        throw "release_android_play_firebase_project_mismatch"
    }
    if ([string]$payload.project_info.project_number -cne $ExpectedProjectNumber) {
        throw "release_android_play_firebase_project_number_mismatch"
    }
    $matches = @(
        $payload.client | Where-Object {
            [string]$_.client_info.android_client_info.package_name -ceq $ExpectedApplicationId
        }
    )
    if ($matches.Count -ne 1) {
        throw "release_android_play_firebase_package_mismatch"
    }
    if ([string]$matches[0].client_info.mobilesdk_app_id -cne $ExpectedFirebaseAppId) {
        throw "release_android_play_firebase_app_id_mismatch"
    }
    return [PSCustomObject]@{
        ApplicationId = $ExpectedApplicationId
        FirebaseAppId = $ExpectedFirebaseAppId
        Path = $resolved
        ProjectId = $ExpectedProjectId
        ProjectNumber = $ExpectedProjectNumber
    }
}

function Write-NewPlayJsonFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Payload
    )

    $resolved = [IO.Path]::GetFullPath($Path)
    $parent = Split-Path -Parent $resolved
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "release_android_play_ledger_directory_missing: path=$parent"
    }
    $json = $Payload | ConvertTo-Json -Depth 8
    $encoding = [Text.UTF8Encoding]::new($false)
    try {
        $stream = [IO.File]::Open(
            $resolved,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )
        try {
            $writer = [IO.StreamWriter]::new($stream, $encoding)
            try { $writer.Write($json) }
            finally { $writer.Dispose() }
        } finally {
            $stream.Dispose()
        }
    } catch [IO.IOException] {
        throw "release_android_play_ledger_path_exists: path=$resolved"
    }
    return $resolved
}

function Copy-NewPlayArtifact {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $resolvedSource = [IO.Path]::GetFullPath($Source)
    $resolvedDestination = [IO.Path]::GetFullPath($Destination)
    if (-not (Test-Path -LiteralPath $resolvedSource -PathType Leaf)) {
        throw "release_android_play_artifact_source_missing: path=$resolvedSource"
    }
    $parent = Split-Path -Parent $resolvedDestination
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "release_android_play_archive_directory_missing: path=$parent"
    }
    if (Test-Path -LiteralPath $resolvedDestination) {
        throw "release_android_artifact_path_exists: path=$resolvedDestination"
    }
    $outputCreated = $false
    try {
        $input = [IO.File]::Open(
            $resolvedSource,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::Read
        )
        try {
            $output = [IO.File]::Open(
                $resolvedDestination,
                [IO.FileMode]::CreateNew,
                [IO.FileAccess]::Write,
                [IO.FileShare]::None
            )
            $outputCreated = $true
            try {
                $input.CopyTo($output)
                $output.Flush($true)
            } finally {
                $output.Dispose()
            }
        } finally {
            $input.Dispose()
        }
    } catch [IO.IOException] {
        if ($outputCreated) {
            try { [IO.File]::Delete($resolvedDestination) } catch { }
            throw "release_android_artifact_copy_failed: path=$resolvedDestination"
        }
        if (Test-Path -LiteralPath $resolvedDestination -PathType Leaf) {
            throw "release_android_artifact_path_exists: path=$resolvedDestination"
        }
        throw
    }
    return $resolvedDestination
}

function Get-PlayLedgerProperty {
    param($InputObject, [string]$Name)
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function ConvertTo-PlayEvidenceTimestamp {
    param($Value, [string]$Path)

    if ($Value -is [datetimeoffset]) {
        return ([datetimeoffset]$Value).ToUniversalTime()
    }
    if ($Value -is [datetime]) {
        $dateTime = [datetime]$Value
        if ($dateTime.Kind -eq [DateTimeKind]::Unspecified) {
            throw "release_android_play_evidence_timestamp_invalid: path=$Path"
        }
        return ([datetimeoffset]$dateTime).ToUniversalTime()
    }
    $parsed = [datetimeoffset]::MinValue
    if (-not [datetimeoffset]::TryParse(
        [string]$Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$parsed
    )) {
        throw "release_android_play_evidence_timestamp_invalid: path=$Path"
    }
    return $parsed.ToUniversalTime()
}

function ConvertTo-PlayVersionRecord {
    param(
        [Parameter(Mandatory = $true)]$Record,
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Kind
    )

    $versionCode = 0
    $versionCodeText = [string](Get-PlayLedgerProperty $Record "VersionCode")
    $versionName = ([string](Get-PlayLedgerProperty $Record "VersionName")).Trim()
    if (
        -not [int]::TryParse($versionCodeText, [ref]$versionCode) -or
        $versionCode -le 0 -or
        $versionName -notmatch $script:VersionNamePattern
    ) {
        throw "release_android_play_ledger_version_invalid: path=$Path"
    }
    return [PSCustomObject]@{
        Kind = $Kind
        Path = $Path
        VersionCode = $versionCode
        VersionName = $versionName
    }
}

function Read-PlayReleaseLedger {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Directory)

    $resolved = [IO.Path]::GetFullPath($Directory)
    if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
        throw "release_android_play_ledger_directory_missing: path=$resolved"
    }

    $reservations = @()
    $releases = @()
    $evidence = @()
    foreach ($path in (Get-ChildItem -LiteralPath $resolved -File | Sort-Object Name)) {
        if ($path.Name -eq "README.md") { continue }
        if ($path.Name -notmatch '\.(reservation|release|evidence)\.json$') {
            throw "release_android_play_ledger_file_unexpected: path=$($path.FullName)"
        }
        try {
            $record = Get-Content -LiteralPath $path.FullName -Raw | ConvertFrom-Json
        } catch {
            throw "release_android_play_ledger_record_invalid: path=$($path.FullName)"
        }
        if ($path.Name.EndsWith(".reservation.json", [StringComparison]::Ordinal)) {
            if (
                [string](Get-PlayLedgerProperty $record "Kind") -cne "play-version-reservation" -or
                [string](Get-PlayLedgerProperty $record "Status") -cne "reserved"
            ) {
                throw "release_android_play_reservation_invalid: path=$($path.FullName)"
            }
            $version = ConvertTo-PlayVersionRecord `
                -Record $record -Path $path.FullName -Kind "reservation"
            $reservations += [PSCustomObject]@{
                Path = $version.Path
                Record = $record
                VersionCode = $version.VersionCode
                VersionName = $version.VersionName
            }
            continue
        }
        if ($path.Name.EndsWith(".release.json", [StringComparison]::Ordinal)) {
            if (
                [string](Get-PlayLedgerProperty $record "Target") -cne "android-play" -or
                [string](Get-PlayLedgerProperty $record "Status") -cne "built-not-uploaded"
            ) {
                throw "release_android_play_manifest_invalid: path=$($path.FullName)"
            }
            $version = ConvertTo-PlayVersionRecord `
                -Record $record -Path $path.FullName -Kind "release"
            $certificate = ConvertTo-PlaySha256 `
                -Value ([string](Get-PlayLedgerProperty $record "UploadCertificateSha256")) `
                -FailureCode "release_android_play_manifest_certificate_invalid: path=$($path.FullName)"
            $aabSha256 = ConvertTo-PlaySha256 `
                -Value ([string](Get-PlayLedgerProperty $record "AabSha256")) `
                -FailureCode "release_android_play_manifest_aab_sha256_invalid: path=$($path.FullName)"
            $schemaVersion = 0
            $schemaVersionValue = Get-PlayLedgerProperty $record "SchemaVersion"
            if (
                $null -ne $schemaVersionValue -and
                (-not [int]::TryParse([string]$schemaVersionValue, [ref]$schemaVersion) -or
                    $schemaVersion -lt 1)
            ) {
                throw "release_android_play_manifest_schema_invalid: path=$($path.FullName)"
            }
            $mappingSha256 = $null
            if ($schemaVersion -ge 3) {
                $mappingSha256Value = [string](
                    Get-PlayLedgerProperty $record "MappingSha256"
                )
                if (-not $mappingSha256Value.Trim()) {
                    throw (
                        "release_android_play_manifest_mapping_sha256_invalid: " +
                        "path=$($path.FullName)"
                    )
                }
                $mappingSha256 = ConvertTo-PlaySha256 `
                    -Value $mappingSha256Value `
                    -FailureCode "release_android_play_manifest_mapping_sha256_invalid: path=$($path.FullName)"
                $expectedMappingFile =
                    "meteofriul-$($version.VersionCode)-$($version.VersionName).mapping.txt"
                $nativeLibraryCount = -1
                $nativeSymbolEntryCount = -1
                $nativeSymbolsStatus = [string](
                    Get-PlayLedgerProperty $record "NativeSymbolsStatus"
                )
                if (
                    [string](Get-PlayLedgerProperty $record "R8Verification") -cne
                        "external-and-embedded-mapping-match" -or
                    [string](Get-PlayLedgerProperty $record "MappingFile") -cne
                        $expectedMappingFile -or
                    [string](Get-PlayLedgerProperty $record "BundleMappingEntry") -cne
                        "BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map" -or
                    -not [int]::TryParse(
                        [string](Get-PlayLedgerProperty $record "NativeLibraryCount"),
                        [ref]$nativeLibraryCount
                    ) -or
                    $nativeLibraryCount -lt 0 -or
                    -not [int]::TryParse(
                        [string](Get-PlayLedgerProperty $record "NativeSymbolEntryCount"),
                        [ref]$nativeSymbolEntryCount
                    ) -or
                    $nativeSymbolEntryCount -lt 0 -or
                    $nativeSymbolsStatus -notin @(
                        "embedded",
                        "unavailable-transitive-native-libraries",
                        "not-applicable"
                    )
                ) {
                    throw "release_android_play_manifest_r8_invalid: path=$($path.FullName)"
                }
            }
            $releases += [PSCustomObject]@{
                AabSha256 = $aabSha256
                MappingSha256 = $mappingSha256
                Path = $version.Path
                Record = $record
                SchemaVersion = $schemaVersion
                UploadCertificateSha256 = $certificate
                VersionCode = $version.VersionCode
                VersionName = $version.VersionName
            }
            continue
        }
        $event = [string](Get-PlayLedgerProperty $record "Event")
        if ($event -notin @("play-accepted", "abandoned", "upload-key-rotation")) {
            throw "release_android_play_evidence_event_invalid: path=$($path.FullName)"
        }
        $createdAt = ConvertTo-PlayEvidenceTimestamp `
            -Value (Get-PlayLedgerProperty $record "CreatedAtUtc") `
            -Path $path.FullName
        $evidence += [PSCustomObject]@{
            CreatedAt = $createdAt
            Event = $event
            Path = $path.FullName
            Record = $record
        }
    }

    $allVersions = @()
    foreach ($group in @($reservations + $releases | Group-Object VersionCode)) {
        $names = @($group.Group.VersionName | Sort-Object -Unique)
        if ($names.Count -ne 1) {
            throw "release_android_play_version_identity_conflict: versionCode=$($group.Name)"
        }
        $allVersions += [PSCustomObject]@{
            Path = ($group.Group.Path -join ";")
            VersionCode = [int]$group.Name
            VersionName = $names[0]
        }
    }

    foreach ($release in $releases) {
        $matchingReservation = @(
            $reservations | Where-Object {
                $_.VersionCode -eq $release.VersionCode -and
                $_.VersionName -ceq $release.VersionName
            }
        )
        if ($matchingReservation.Count -ne 1) {
            throw "release_android_play_manifest_reservation_missing: path=$($release.Path)"
        }
    }

    foreach ($item in $evidence) {
        $record = $item.Record
        if ($item.Event -in @("play-accepted", "abandoned")) {
            $version = 0
            if (-not [int]::TryParse(
                [string](Get-PlayLedgerProperty $record "VersionCode"),
                [ref]$version
            )) {
                throw "release_android_play_evidence_version_invalid: path=$($item.Path)"
            }
            $known = @($allVersions | Where-Object VersionCode -eq $version)
            if ($known.Count -ne 1) {
                throw "release_android_play_evidence_unknown_version: path=$($item.Path)"
            }
            if ($item.Event -eq "play-accepted") {
                $release = @($releases | Where-Object VersionCode -eq $version)
                if ($release.Count -ne 1) {
                    throw "release_android_play_acceptance_without_bundle: path=$($item.Path)"
                }
                $certificate = ConvertTo-PlaySha256 `
                    -Value ([string](Get-PlayLedgerProperty $record "UploadCertificateSha256")) `
                    -FailureCode "release_android_play_acceptance_certificate_invalid: path=$($item.Path)"
                $aabHash = ConvertTo-PlaySha256 `
                    -Value ([string](Get-PlayLedgerProperty $record "AabSha256")) `
                    -FailureCode "release_android_play_acceptance_aab_invalid: path=$($item.Path)"
                if (
                    $certificate -cne $release[0].UploadCertificateSha256 -or
                    $aabHash -cne $release[0].AabSha256
                ) {
                    throw "release_android_play_acceptance_manifest_mismatch: path=$($item.Path)"
                }
                $consoleVersion = 0
                if (
                    -not [int]::TryParse(
                        [string](Get-PlayLedgerProperty $record "LatestConsoleVersionCode"),
                        [ref]$consoleVersion
                    ) -or
                    $consoleVersion -lt $version -or
                    -not ([string](Get-PlayLedgerProperty $record "EvidenceReference")).Trim()
                ) {
                    throw "release_android_play_acceptance_evidence_invalid: path=$($item.Path)"
                }
                $item | Add-Member NoteProperty UploadCertificateSha256 $certificate
                $item | Add-Member NoteProperty VersionCode $version
            } elseif (-not ([string](Get-PlayLedgerProperty $record "Reason")).Trim()) {
                throw "release_android_play_abandoned_evidence_invalid: path=$($item.Path)"
            }
        }
        if ($item.Event -eq "upload-key-rotation") {
            $previous = ConvertTo-PlaySha256 `
                -Value ([string](Get-PlayLedgerProperty $record "PreviousUploadCertificateSha256")) `
                -FailureCode "release_android_play_rotation_previous_invalid: path=$($item.Path)"
            $next = ConvertTo-PlaySha256 `
                -Value ([string](Get-PlayLedgerProperty $record "NewUploadCertificateSha256")) `
                -FailureCode "release_android_play_rotation_new_invalid: path=$($item.Path)"
            if ($previous -ceq $next -or -not ([string](Get-PlayLedgerProperty $record "EvidenceReference")).Trim()) {
                throw "release_android_play_rotation_invalid: path=$($item.Path)"
            }
            $item | Add-Member NoteProperty PreviousUploadCertificateSha256 $previous
            $item | Add-Member NoteProperty NewUploadCertificateSha256 $next
        }
    }


    foreach ($terminalGroup in @(
        $evidence |
            Where-Object Event -in @("play-accepted", "abandoned") |
            Group-Object { [int](Get-PlayLedgerProperty $_.Record "VersionCode") }
    )) {
        if ($terminalGroup.Count -ne 1) {
            throw "release_android_play_terminal_evidence_conflict: versionCode=$($terminalGroup.Name)"
        }
    }

    # A validated built manifest or abandonment permits another build with the
    # same display name and a strictly greater version code. Play acceptance
    # does not reserve a display name forever. An unresolved reservation still
    # blocks it. Derive this only from the validated ledger, never a CLI bypass.
    # Keep RetryableVersionName for both existing candidate guards; every code
    # remains in AllVersions and can never be reused.
    foreach ($version in $allVersions) {
        $abandoned = @($evidence | Where-Object {
            $_.Event -ceq "abandoned" -and
            [int](Get-PlayLedgerProperty $_.Record "VersionCode") -eq $version.VersionCode
        })
        $built = @($releases | Where-Object VersionCode -eq $version.VersionCode)
        $version | Add-Member NoteProperty RetryableVersionName (
            $abandoned.Count -eq 1 -or $built.Count -eq 1
        )
    }
    # Multiple completed builds may share a name; two unresolved reservations may not.
    $duplicateName = @($allVersions | Where-Object { -not $_.RetryableVersionName } |
        Group-Object { $_.VersionName.ToLowerInvariant() } |
        Where-Object Count -gt 1 | Select-Object -First 1)
    if ($duplicateName.Count -gt 0) {
        throw "release_android_play_version_name_conflict: versionName=$($duplicateName[0].Name)"
    }

    $latestAccepted = @(
        $evidence | Where-Object Event -eq "play-accepted" |
            Sort-Object VersionCode, CreatedAt -Descending | Select-Object -First 1
    )
    $maxReserved = if ($allVersions.Count -gt 0) {
        [int](($allVersions.VersionCode | Measure-Object -Maximum).Maximum)
    } else { 0 }
    return [PSCustomObject]@{
        AllVersions = @($allVersions)
        Evidence = @($evidence)
        LatestAcceptedEvidence = if ($latestAccepted.Count) { $latestAccepted[0] } else { $null }
        MaxReservedVersionCode = $maxReserved
        Releases = @($releases)
        Reservations = @($reservations)
        Rotations = @($evidence | Where-Object Event -eq "upload-key-rotation")
    }
}

function Assert-PlayCandidateVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][int]$CandidateVersionCode,
        [Parameter(Mandatory = $true)][string]$CandidateVersionName,
        [Parameter(Mandatory = $true)][ValidateRange(0, 2100000000)][int]$LatestConsoleVersionCode,
        [object[]]$ExistingVersions = @()
    )

    $name = $CandidateVersionName.Trim()
    if ($CandidateVersionCode -le 0 -or $name -notmatch $script:VersionNamePattern) {
        throw "release_android_play_candidate_version_invalid"
    }
    foreach ($existing in @($ExistingVersions)) {
        $retryableName = Get-PlayLedgerProperty $existing "RetryableVersionName"
        $canRetryName = $retryableName -is [bool] -and $retryableName -eq $true
        if (
            [int]$existing.VersionCode -eq $CandidateVersionCode -or
            ([string]$existing.VersionName -ieq $name -and -not $canRetryName)
        ) {
            throw "release_android_play_candidate_version_reserved"
        }
    }
    $historyMaximum = if (@($ExistingVersions).Count -gt 0) {
        [int]((@($ExistingVersions).VersionCode | Measure-Object -Maximum).Maximum)
    } else { 0 }
    $minimumExclusive = [Math]::Max($historyMaximum, $LatestConsoleVersionCode)
    if ($CandidateVersionCode -le $minimumExclusive) {
        throw (
            "release_android_play_version_not_incremented: " +
            "candidate=$CandidateVersionCode requiredAbove=$minimumExclusive"
        )
    }
    return [PSCustomObject]@{
        CandidateVersionCode = $CandidateVersionCode
        CandidateVersionName = $name
        LatestConsoleVersionCode = $LatestConsoleVersionCode
        MaximumReservedVersionCode = $historyMaximum
        RequiredAboveVersionCode = $minimumExclusive
    }
}

function Resolve-PlayUploadCertificateTrust {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$CandidateCertificateSha256,
        [string]$ExplicitExpectedCertificateSha256 = "",
        [Parameter(Mandatory = $true)]$Ledger
    )

    $candidate = ConvertTo-PlaySha256 `
        -Value $CandidateCertificateSha256 `
        -FailureCode "release_android_play_candidate_certificate_invalid"
    $explicit = ""
    if (-not [string]::IsNullOrWhiteSpace($ExplicitExpectedCertificateSha256)) {
        $explicit = ConvertTo-PlaySha256 `
            -Value $ExplicitExpectedCertificateSha256 `
            -FailureCode "release_android_play_expected_certificate_invalid"
        if ($candidate -cne $explicit) {
            throw "release_android_play_explicit_certificate_mismatch"
        }
    }

    $accepted = $Ledger.LatestAcceptedEvidence
    if ($null -eq $accepted) {
        if (-not $explicit) {
            throw "release_android_play_upload_trust_anchor_required"
        }
        return [PSCustomObject]@{
            CertificateSha256 = $candidate
            Source = "explicit-first-upload-anchor"
        }
    }

    $effective = [string]$accepted.UploadCertificateSha256
    if ($candidate -ceq $effective) {
        return [PSCustomObject]@{
            CertificateSha256 = $candidate
            Source = "latest-play-accepted"
        }
    }
    $visited = @{}
    foreach ($rotation in @($Ledger.Rotations | Sort-Object CreatedAt)) {
        if (
            $rotation.CreatedAt -gt $accepted.CreatedAt -and
            $rotation.PreviousUploadCertificateSha256 -ceq $effective -and
            -not $visited.ContainsKey($rotation.Path)
        ) {
            $visited[$rotation.Path] = $true
            $effective = $rotation.NewUploadCertificateSha256
        }
    }
    if ($candidate -cne $effective) {
        throw "release_android_play_upload_certificate_untrusted"
    }
    return [PSCustomObject]@{
        CertificateSha256 = $candidate
        Source = "append-only-rotation-evidence"
    }
}

function Get-PlayReleaseArchivePaths {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
        [Parameter(Mandatory = $true)][int]$VersionCode,
        [Parameter(Mandatory = $true)][string]$VersionName
    )

    if ($VersionName -notmatch $script:VersionNamePattern -or $VersionCode -le 0) {
        throw "release_android_play_archive_identity_invalid"
    }
    $directory = [IO.Path]::GetFullPath(
        (Join-Path $WorkspaceRoot "release-artifacts\android-play")
    )
    $aab = Join-Path $directory "meteofriul-$VersionCode-$VersionName.aab"
    $mapping = Join-Path $directory "meteofriul-$VersionCode-$VersionName.mapping.txt"
    return [PSCustomObject]@{
        Aab = $aab
        Directory = $directory
        Mapping = $mapping
    }
}

function Assert-PlayR8BundleArtifacts {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$BundlePath,
        [Parameter(Mandatory = $true)][string]$MappingPath
    )

    $resolvedBundle = [IO.Path]::GetFullPath($BundlePath)
    $resolvedMapping = [IO.Path]::GetFullPath($MappingPath)
    if (-not (Test-Path -LiteralPath $resolvedBundle -PathType Leaf)) {
        throw "release_android_play_r8_bundle_missing: path=$resolvedBundle"
    }
    if (-not (Test-Path -LiteralPath $resolvedMapping -PathType Leaf)) {
        throw "release_android_play_r8_mapping_missing: path=$resolvedMapping"
    }
    if ((Get-Item -LiteralPath $resolvedMapping).Length -le 0) {
        throw "release_android_play_r8_mapping_empty: path=$resolvedMapping"
    }

    $mappingSha256 = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedMapping
    ).Hash.ToLowerInvariant()
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($resolvedBundle)
    try {
        $mappingEntryPath =
            "BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map"
        $mappingEntries = @(
            $archive.Entries | Where-Object FullName -CEQ $mappingEntryPath
        )
        if ($mappingEntries.Count -ne 1) {
            throw (
                "release_android_play_r8_bundle_mapping_invalid: " +
                "count=$($mappingEntries.Count) entry=$mappingEntryPath"
            )
        }
        if ($mappingEntries[0].Length -le 0) {
            throw "release_android_play_r8_bundle_mapping_empty"
        }

        $sha256 = [Security.Cryptography.SHA256]::Create()
        $mappingStream = $mappingEntries[0].Open()
        try {
            $bundleMappingSha256 = [Convert]::ToHexString(
                $sha256.ComputeHash($mappingStream)
            ).ToLowerInvariant()
        } finally {
            $mappingStream.Dispose()
            $sha256.Dispose()
        }
        if ($bundleMappingSha256 -cne $mappingSha256) {
            throw (
                "release_android_play_r8_mapping_bundle_mismatch: " +
                "external=$mappingSha256 embedded=$bundleMappingSha256"
            )
        }

        $nativeLibraries = @(
            $archive.Entries | Where-Object {
                $_.FullName -match '^base/lib/[^/]+/[^/]+\.so$'
            }
        )
        $nativeSymbolEntries = @(
            $archive.Entries | Where-Object {
                $_.FullName.StartsWith(
                    "BUNDLE-METADATA/com.android.tools.build.debugsymbols/",
                    [StringComparison]::Ordinal
                ) -and $_.Length -gt 0
            }
        )
        $nativeSymbolsStatus = if ($nativeSymbolEntries.Count -gt 0) {
            "embedded"
        } elseif ($nativeLibraries.Count -gt 0) {
            "unavailable-transitive-native-libraries"
        } else {
            "not-applicable"
        }

        return [PSCustomObject]@{
            BundleMappingEntry = $mappingEntryPath
            MappingSha256 = $mappingSha256
            NativeLibraryCount = $nativeLibraries.Count
            NativeSymbolEntryCount = $nativeSymbolEntries.Count
            NativeSymbolsStatus = $nativeSymbolsStatus
        }
    } finally {
        $archive.Dispose()
    }
}

function New-PlayAabTemporaryLayout {
    [CmdletBinding()]
    param([string]$TemporaryBasePath = [IO.Path]::GetTempPath())

    $base = [IO.Path]::GetFullPath($TemporaryBasePath)
    if (-not (Test-Path -LiteralPath $base -PathType Container)) {
        throw "release_android_play_temporary_base_missing: path=$base"
    }
    $root = Join-Path $base (
        "meteofriul-play-aab-" + [Guid]::NewGuid().ToString("N")
    )
    $webAssets = Join-Path $root "web-assets"
    $verifierClasses = Join-Path $root "signed-archive-verifier"
    New-Item -ItemType Directory -Path $webAssets | Out-Null
    New-Item -ItemType Directory -Path $verifierClasses | Out-Null
    return [PSCustomObject]@{
        Root = $root
        VerifierClasses = $verifierClasses
        WebAssets = $webAssets
    }
}

function Assert-PlayReleaseLedgerGitImmutability {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$LedgerDirectory
    )

    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char[]]"\/")
    $ledger = [IO.Path]::GetFullPath($LedgerDirectory).TrimEnd([char[]]"\/")
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "release_android_play_git_root_missing: path=$root"
    }
    if (-not (Test-Path -LiteralPath $ledger -PathType Container)) {
        throw "release_android_history_directory_missing: path=$ledger"
    }
    if (-not $ledger.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "release_android_play_ledger_outside_repository"
    }

    $topLevel = (& git -C $root rev-parse --show-toplevel 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $topLevel) {
        throw "release_android_play_git_root_mismatch: expected=$root actual=$topLevel"
    }
    # On Windows, .NET can return an 8.3 path while Git returns the equivalent
    # long path. Asking Git for the prefix proves filesystem identity without
    # weakening the requirement that RepositoryRoot itself is the top level.
    $topLevelPrefix = (& git -C $root rev-parse --show-prefix 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $topLevelPrefix) {
        throw "release_android_play_git_root_mismatch: expected=$root actual=$topLevel"
    }
    $ledgerRelative = $ledger.Substring($root.Length).TrimStart([char[]]"\/").Replace('\', '/')

    $dirty = (& git -C $root status --porcelain -- $ledgerRelative 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "release_android_play_ledger_git_status_failed"
    }
    if ($dirty) {
        throw "release_android_play_ledger_worktree_not_clean"
    }

    $trackedPaths = @(
        & git -C $root ls-files -- "$ledgerRelative/*.json" 2>&1 |
            ForEach-Object { ([string]$_).Trim().Replace('\', '/') } |
            Where-Object { $_ }
    )
    if ($LASTEXITCODE -ne 0) {
        throw "release_android_play_ledger_git_list_failed"
    }
    $historicalPaths = @(
        & git -C $root log --name-only --pretty=format: -- $ledgerRelative 2>&1 |
            ForEach-Object { ([string]$_).Trim().Replace('\', '/') } |
            Where-Object { $_ -match '\.json$' }
    )
    if ($LASTEXITCODE -ne 0) {
        throw "release_android_play_ledger_git_history_failed"
    }
    $filesystemPaths = @(
        Get-ChildItem -LiteralPath $ledger -Filter '*.json' -File -Recurse |
            ForEach-Object {
                $_.FullName.Substring($root.Length).TrimStart([char[]]"\/").Replace('\', '/')
            }
    )

    $tracked = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($path in $trackedPaths) { $null = $tracked.Add($path) }
    $historical = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($path in $historicalPaths) { $null = $historical.Add($path) }
    $filesystem = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($path in $filesystemPaths) { $null = $filesystem.Add($path) }

    foreach ($path in $historical) {
        if (-not $tracked.Contains($path)) {
            throw "release_android_play_ledger_record_deleted_or_renamed: path=$path"
        }
    }
    foreach ($path in $filesystem) {
        if (-not $tracked.Contains($path)) {
            throw "release_android_play_ledger_record_untracked: path=$path"
        }
    }
    foreach ($path in $tracked) {
        if (-not $filesystem.Contains($path)) {
            throw "release_android_play_ledger_record_missing: path=$path"
        }
        $addCommits = @(
            & git -C $root log --format=%H --diff-filter=A -- $path 2>&1 |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object { $_ }
        )
        if ($LASTEXITCODE -ne 0) {
            throw "release_android_play_ledger_git_history_failed: path=$path"
        }
        if ($addCommits.Count -ne 1) {
            throw "release_android_play_ledger_record_add_history_invalid: path=$path count=$($addCommits.Count)"
        }
        $mutations = @(
            & git -C $root log --format=%H --diff-filter=MRCD -- $path 2>&1 |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object { $_ }
        )
        if ($LASTEXITCODE -ne 0) {
            throw "release_android_play_ledger_git_history_failed: path=$path"
        }
        if ($mutations.Count -ne 0) {
            throw "release_android_play_ledger_record_was_modified: path=$path"
        }
    }

    return [PSCustomObject]@{
        HistoricalRecordCount = $historical.Count
        RecordCount = $tracked.Count
    }
}

function Test-PlayReleaseProducingTaskName {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$TaskName)

    $name = $TaskName.Trim().ToLowerInvariant()
    if (-not $name.Contains("release")) { return $false }
    return [bool]($name -match '(assemble|bundle|sign|package|finalize|publish)')
}

function Assert-PlayReleaseWorkspaceUnchanged {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$ExpectedCommit,
        [string[]]$AllowedUntrackedPaths = @()
    )

    $head = (& git -C $RepositoryRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -cne $ExpectedCommit) {
        throw "release_git_head_changed_during_build: before=$ExpectedCommit after=$head"
    }
    & git -C $RepositoryRoot diff --quiet
    if ($LASTEXITCODE -ne 0) { throw "release_git_tracked_files_changed_during_build" }
    & git -C $RepositoryRoot diff --cached --quiet
    if ($LASTEXITCODE -ne 0) { throw "release_git_index_changed_during_build" }

    $allowed = @{}
    foreach ($path in $AllowedUntrackedPaths) {
        $relative = [IO.Path]::GetRelativePath($RepositoryRoot, [IO.Path]::GetFullPath($path))
        $allowed[($relative -replace '\\', '/')] = $true
    }
    $untracked = @(& git -C $RepositoryRoot ls-files --others --exclude-standard)
    foreach ($path in $untracked) {
        if (-not $allowed.ContainsKey([string]$path)) {
            throw "release_git_unexpected_untracked_file: path=$path"
        }
    }
    return [PSCustomObject]@{ Commit = $head; UntrackedCount = $untracked.Count }
}

Export-ModuleMember -Function @(
    "Assert-PlayBundletoolTrust",
    "Assert-PlayCandidateVersion",
    "Assert-PlayGoogleServicesConfiguration",
    "Assert-PlayR8BundleArtifacts",
    "Assert-PlayReleaseLedgerGitImmutability",
    "Assert-PlayReleaseWorkspaceUnchanged",
    "ConvertTo-PlaySha256",
    "Copy-NewPlayArtifact",
    "Get-PlayReleaseArchivePaths",
    "New-PlayAabTemporaryLayout",
    "Read-PlayReleaseLedger",
    "Resolve-PlayUploadCertificateTrust",
    "Test-PlayReleaseProducingTaskName",
    "Write-NewPlayJsonFile"
)
