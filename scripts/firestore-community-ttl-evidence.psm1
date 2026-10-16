Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "firestore-community-ttl-audit.psm1") -Force

$script:HistoricalEvidenceSchema = "firestore-community-ttl-historical-evidence-v2"
$script:HistoricalEvidenceKind = "historical-live-writer-samples"
$script:CloudAttestationSchema = "firestore-community-ttl-cloud-attestation-v1"
$script:CloudAttestationEventSchema = (
    "firestore-community-ttl-cloud-attestation-event-v1"
)
$script:CloudAttestationLogId = "meteofriul-community-ttl-evidence"
$script:CloudAttestationLogName = (
    "projects/meteo-friul/logs/meteofriul-community-ttl-evidence"
)
$script:EvidenceCoreCanonicalization = "v1:powershell-json-depth-12-compress-utf8"
$script:AuditSchema = "firestore-community-ttl-audit-v2"
$script:ExpectedAccount = "meteofriul@gmail.com"
$script:ExpectedProjectId = "meteo-friul"
$script:ExpectedProjectNumber = "49007668366"
$script:ExpectedDatabaseName = "projects/meteo-friul/databases/(default)"
$script:ExpectedDatabaseType = "FIRESTORE_NATIVE"
$script:HistoricalEvidenceMaxAgeSeconds = 30 * 24 * 60 * 60
$script:RecordingDelayMaxSeconds = 15 * 60
$script:FutureClockSkewSeconds = 5 * 60
$script:WriterContractCanonicalization = (
    "v1:utf8-path-lf+decimal-byte-length-lf+raw-bytes+lf"
)
$script:WriterContractFiles = @(
    "backend/app/repositories/community.py",
    "backend/app/services/community.py",
    "backend/app/services/community_moderation_digest.py",
    "backend/tools/moderate_community_reports.py",
    "backend/tools/smoke_community_moderation_live.py",
    "backend/tools/seed_community_ttl_evidence_live.py",
    "scripts/audit-firestore-community-ttl.ps1",
    "scripts/firestore-community-ttl-audit.psm1",
    "scripts/record-firestore-community-ttl-evidence.ps1",
    "scripts/firestore-community-ttl-evidence.psm1"
)

$script:EvidenceRootProperties = @(
    "schemaVersion", "evidenceKind", "sourceMode", "capturedAtUtc",
    "recordedAtUtc", "auditSchemaVersion", "ready", "identityReady",
    "policyReady", "documentReady", "sampleCoverageComplete",
    "blockingCount", "identity", "policies", "collections",
    "writerContract", "cloudAttestation"
)
$script:EvidenceCoreProperties = @(
    $script:EvidenceRootProperties | Where-Object { $_ -cne "cloudAttestation" }
)
$script:IdentityProperties = @(
    "activeAccount", "activeAccountCount", "configuredAccount",
    "configuredProject", "projectId", "projectNumber", "projectState",
    "databaseName", "databaseType"
)
$script:PolicyProperties = @(
    "collectionGroup", "field", "state", "expirationOffset"
)
$script:CollectionProperties = @(
    "collectionGroup", "expiryField", "baselineField",
    "contractualMinimumHorizonSeconds", "contractualMaximumHorizonSeconds",
    "documentCount", "validHorizonSampleCount", "recentHorizonSampleCount",
    "missingExpiryCount", "wrongExpiryTypeCount", "invalidExpiryCount",
    "missingBaselineCount", "wrongBaselineTypeCount", "invalidBaselineCount",
    "futureBaselineCount", "expiredDocumentCount", "expiredBeyondGraceCount",
    "belowMinimumHorizonCount", "aboveMaximumHorizonCount",
    "minimumObservedHorizonSeconds", "maximumObservedHorizonSeconds"
)
$script:WriterContractProperties = @(
    "algorithm", "canonicalization", "sha256", "files", "sourceCommit"
)
$script:CloudAttestationProperties = @(
    "schemaVersion", "logName", "nonce", "evidenceCoreCanonicalization",
    "evidenceCoreSha256", "sourceCommit", "recordedAtUtc",
    "logEntryTimestampUtc"
)
$script:CloudAttestationEventProperties = @(
    "schemaVersion", "projectId", "databaseName", "nonce",
    "evidenceCoreCanonicalization", "evidenceCoreSha256", "sourceCommit",
    "recordedAtUtc"
)

function Get-CommunityTtlEvidenceProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Assert-CommunityTtlExactProperties {
    param(
        [object]$InputObject,
        [string[]]$Expected,
        [string]$FailureCode
    )
    if ($null -eq $InputObject) { throw $FailureCode }
    $actual = @($InputObject.PSObject.Properties.Name)
    if ($actual.Count -ne $Expected.Count) { throw $FailureCode }
    $actualSorted = @($actual | Sort-Object -CaseSensitive)
    $expectedSorted = @($Expected | Sort-Object -CaseSensitive)
    if ((@($actualSorted) -join "`n") -cne (@($expectedSorted) -join "`n")) {
        throw $FailureCode
    }
}

function Assert-CommunityTtlJsonString {
    param([object]$Value, [string]$FailureCode)
    if ($Value -isnot [string]) { throw $FailureCode }
}

function Assert-CommunityTtlJsonBoolean {
    param([object]$Value, [string]$FailureCode)
    if ($Value -isnot [bool]) { throw $FailureCode }
}

function Assert-CommunityTtlJsonArray {
    param([object]$Value, [string]$FailureCode)
    if ($Value -isnot [Array]) { throw $FailureCode }
}

function Assert-CommunityTtlJsonNoDuplicateProperties {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Json,
        [string]$FailureCode = "community_ttl_json_duplicate_property"
    )
    $document = $null
    try {
        $document = [Text.Json.JsonDocument]::Parse($Json)
        $stack = [Collections.Generic.Stack[Text.Json.JsonElement]]::new()
        $stack.Push($document.RootElement)
        while ($stack.Count -gt 0) {
            $element = $stack.Pop()
            if ($element.ValueKind -eq [Text.Json.JsonValueKind]::Object) {
                $names = [Collections.Generic.HashSet[string]]::new(
                    [StringComparer]::Ordinal
                )
                foreach ($property in $element.EnumerateObject()) {
                    if (-not $names.Add($property.Name)) { throw $FailureCode }
                    $stack.Push($property.Value)
                }
            } elseif ($element.ValueKind -eq [Text.Json.JsonValueKind]::Array) {
                foreach ($item in $element.EnumerateArray()) {
                    $stack.Push($item)
                }
            }
        }
    } catch {
        if ($_.Exception.Message -ceq $FailureCode) { throw }
        throw $FailureCode
    } finally {
        if ($null -ne $document) { $document.Dispose() }
    }
}

function Get-CommunityTtlJsonCount {
    param([object]$Value, [string]$FailureCode)
    if ($Value -isnot [int] -and $Value -isnot [long]) {
        throw $FailureCode
    }
    $count = [long]$Value
    if ($count -lt 0 -or $count -gt [int]::MaxValue) {
        throw $FailureCode
    }
    return [int]$count
}

function Get-CommunityTtlJsonFiniteNumber {
    param([object]$Value, [string]$FailureCode)
    if ($Value -isnot [int] -and
        $Value -isnot [long] -and
        $Value -isnot [double]) {
        throw $FailureCode
    }
    $number = [double]$Value
    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        throw $FailureCode
    }
    return $number
}

function Get-CommunityTtlSha256Hex {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    return [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData($Bytes)
    ).ToLowerInvariant()
}

function Get-CommunityTtlEvidenceCoreObject {
    param([Parameter(Mandatory = $true)][object]$Evidence)
    $core = [ordered]@{}
    foreach ($name in $script:EvidenceCoreProperties) {
        $core[$name] = Get-CommunityTtlEvidenceProperty $Evidence $name
    }
    return [PSCustomObject]$core
}

function Get-CommunityTtlEvidenceCoreSha256 {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Evidence)
    $json = Get-CommunityTtlEvidenceCoreObject $Evidence |
        ConvertTo-Json -Depth 12 -Compress
    return Get-CommunityTtlSha256Hex `
        -Bytes ([Text.UTF8Encoding]::new($false).GetBytes($json))
}

function ConvertTo-CommunityTtlEvidenceTimestamp {
    param([object]$Value, [string]$FailureCode)
    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }
    if ($Value -is [DateTime]) {
        $dateTime = [DateTime]$Value
        if ($dateTime.Kind -eq [DateTimeKind]::Unspecified) {
            throw $FailureCode
        }
        return ([DateTimeOffset]$dateTime).ToUniversalTime()
    }
    $parsed = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse(
        [string]$Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$parsed
    )) {
        throw $FailureCode
    }
    return $parsed.ToUniversalTime()
}

function Get-CommunityTtlWriterContract {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$RepositoryRoot)

    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char[]]"\/")
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "community_ttl_writer_contract_root_missing"
    }

    $stream = [IO.MemoryStream]::new()
    try {
        $encoding = [Text.UTF8Encoding]::new($false)
        foreach ($relativePath in $script:WriterContractFiles) {
            $nativeRelativePath = $relativePath.Replace(
                '/', [IO.Path]::DirectorySeparatorChar
            )
            $sourcePath = [IO.Path]::GetFullPath(
                (Join-Path $root $nativeRelativePath)
            )
            if (-not $sourcePath.StartsWith(
                $root + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "community_ttl_writer_contract_path_outside_repository"
            }
            if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                throw (
                    "community_ttl_writer_contract_source_missing: " +
                    "path=$relativePath"
                )
            }
            $content = [IO.File]::ReadAllBytes($sourcePath)
            $header = $encoding.GetBytes(
                "$relativePath`n$($content.LongLength)`n"
            )
            $stream.Write($header, 0, $header.Length)
            $stream.Write($content, 0, $content.Length)
            $stream.WriteByte([byte]10)
        }
        $digest = [Convert]::ToHexString(
            [Security.Cryptography.SHA256]::HashData($stream.ToArray())
        ).ToLowerInvariant()
    } finally {
        $stream.Dispose()
    }

    return [PSCustomObject]@{
        algorithm = "sha256"
        canonicalization = $script:WriterContractCanonicalization
        sha256 = $digest
        files = @($script:WriterContractFiles)
    }
}

function Get-CommunityTtlGitBlobBytes {
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$ObjectExpression,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "git"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    foreach ($argument in @(
        "-C", $RepositoryRoot, "cat-file", "blob", $ObjectExpression
    )) {
        $null = $startInfo.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $output = [IO.MemoryStream]::new()
    try {
        if (-not $process.Start()) {
            throw (
                "community_ttl_writer_contract_git_blob_failed: " +
                "path=$RelativePath"
            )
        }
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.StandardOutput.BaseStream.CopyTo($output)
        $process.WaitForExit()
        $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
        if ($process.ExitCode -ne 0) {
            throw (
                "community_ttl_writer_contract_git_blob_failed: " +
                "path=$RelativePath error=$stderr"
            )
        }
        return ,$output.ToArray()
    } finally {
        $output.Dispose()
        $process.Dispose()
    }
}

function Get-CommunityTtlWriterContractFromGitCommit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$Commit
    )

    $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char[]]"\/")
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw "community_ttl_writer_contract_root_missing"
    }
    $normalizedCommit = $Commit.Trim().ToLowerInvariant()
    if ($normalizedCommit -notmatch '^[0-9a-f]{40}$') {
        throw "community_ttl_writer_contract_commit_invalid"
    }
    $resolvedCommit = (& git -C $root rev-parse --verify `
        "${normalizedCommit}^{commit}" 2>&1 | Out-String).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or
        $resolvedCommit -notmatch '^[0-9a-f]{40}$' -or
        $resolvedCommit -cne $normalizedCommit) {
        throw "community_ttl_writer_contract_commit_unavailable"
    }

    $stream = [IO.MemoryStream]::new()
    try {
        $encoding = [Text.UTF8Encoding]::new($false)
        foreach ($relativePath in $script:WriterContractFiles) {
            $content = Get-CommunityTtlGitBlobBytes `
                -RepositoryRoot $root `
                -ObjectExpression "${resolvedCommit}:$relativePath" `
                -RelativePath $relativePath
            $header = $encoding.GetBytes(
                "$relativePath`n$($content.LongLength)`n"
            )
            $stream.Write($header, 0, $header.Length)
            $stream.Write($content, 0, $content.Length)
            $stream.WriteByte([byte]10)
        }
        $digest = [Convert]::ToHexString(
            [Security.Cryptography.SHA256]::HashData($stream.ToArray())
        ).ToLowerInvariant()
    } finally {
        $stream.Dispose()
    }

    return [PSCustomObject]@{
        algorithm = "sha256"
        canonicalization = $script:WriterContractCanonicalization
        sha256 = $digest
        files = @($script:WriterContractFiles)
        sourceCommit = $resolvedCommit
    }
}

function Assert-CommunityTtlEvidenceIdentity {
    param([object]$Identity)
    Assert-CommunityTtlExactProperties `
        -InputObject $Identity `
        -Expected $script:IdentityProperties `
        -FailureCode "community_ttl_historical_evidence_identity_schema_invalid"
    $failureCode = "community_ttl_historical_evidence_identity_schema_invalid"
    foreach ($name in @(
        "activeAccount", "configuredAccount", "configuredProject", "projectId",
        "projectNumber", "projectState", "databaseName", "databaseType"
    )) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $Identity $name) `
            -FailureCode $failureCode
    }
    $activeAccountCount = Get-CommunityTtlJsonCount `
        -Value (Get-CommunityTtlEvidenceProperty $Identity "activeAccountCount") `
        -FailureCode $failureCode
    if (
        [string](Get-CommunityTtlEvidenceProperty $Identity "activeAccount") -cne
            $script:ExpectedAccount -or
        $activeAccountCount -ne 1 -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "configuredAccount") -cne
            $script:ExpectedAccount -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "configuredProject") -cne
            $script:ExpectedProjectId -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "projectId") -cne
            $script:ExpectedProjectId -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "projectNumber") -cne
            $script:ExpectedProjectNumber -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "projectState") -cne
            "ACTIVE" -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "databaseName") -cne
            $script:ExpectedDatabaseName -or
        [string](Get-CommunityTtlEvidenceProperty $Identity "databaseType") -cne
            $script:ExpectedDatabaseType
    ) {
        throw "community_ttl_historical_evidence_identity_mismatch"
    }
}

function Assert-CommunityTtlEvidencePolicies {
    param([object[]]$Policies)
    $contracts = @(Get-CommunityTtlAuditContract)
    if ($Policies.Count -ne $contracts.Count) {
        throw "community_ttl_historical_evidence_policy_coverage_invalid"
    }
    foreach ($policy in $Policies) {
        Assert-CommunityTtlExactProperties `
            -InputObject $policy `
            -Expected $script:PolicyProperties `
            -FailureCode (
                "community_ttl_historical_evidence_policy_schema_invalid"
            )
        foreach ($name in $script:PolicyProperties) {
            Assert-CommunityTtlJsonString `
                -Value (Get-CommunityTtlEvidenceProperty $policy $name) `
                -FailureCode (
                    "community_ttl_historical_evidence_policy_schema_invalid"
                )
        }
    }
    foreach ($contract in $contracts) {
        $matches = @($Policies | Where-Object {
            [string](Get-CommunityTtlEvidenceProperty $_ "collectionGroup") -ceq
                [string]$contract.collectionGroup
        })
        if ($matches.Count -ne 1 -or
            [string](Get-CommunityTtlEvidenceProperty $matches[0] "field") -cne
                [string]$contract.field -or
            [string](Get-CommunityTtlEvidenceProperty $matches[0] "state") -cne
                "ACTIVE" -or
            [string](Get-CommunityTtlEvidenceProperty $matches[0] "expirationOffset") -cne
                "0s") {
            throw "community_ttl_historical_evidence_policy_coverage_invalid"
        }
    }
}

function Assert-CommunityTtlEvidenceCollections {
    param([object[]]$Collections)
    $contracts = @(Get-CommunityTtlAuditContract)
    if ($Collections.Count -ne $contracts.Count) {
        throw "community_ttl_historical_evidence_sample_coverage_invalid"
    }
    foreach ($collection in $Collections) {
        Assert-CommunityTtlExactProperties `
            -InputObject $collection `
            -Expected $script:CollectionProperties `
            -FailureCode (
                "community_ttl_historical_evidence_collection_schema_invalid"
            )
        foreach ($name in @("collectionGroup", "expiryField", "baselineField")) {
            Assert-CommunityTtlJsonString `
                -Value (Get-CommunityTtlEvidenceProperty $collection $name) `
                -FailureCode (
                    "community_ttl_historical_evidence_collection_schema_invalid"
                )
        }
    }
    foreach ($contract in $contracts) {
        $matches = @($Collections | Where-Object {
            [string](Get-CommunityTtlEvidenceProperty $_ "collectionGroup") -ceq
                [string]$contract.collectionGroup
        })
        if ($matches.Count -ne 1) {
            throw "community_ttl_historical_evidence_sample_coverage_invalid"
        }
        $row = $matches[0]
        $failureCode = "community_ttl_historical_evidence_sample_coverage_invalid"
        $documentCount = Get-CommunityTtlJsonCount `
            -Value (Get-CommunityTtlEvidenceProperty $row "documentCount") `
            -FailureCode $failureCode
        $validSampleCount = Get-CommunityTtlJsonCount `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "validHorizonSampleCount") `
            -FailureCode $failureCode
        $recentSampleCount = Get-CommunityTtlJsonCount `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "recentHorizonSampleCount") `
            -FailureCode $failureCode
        $contractualMinimum = Get-CommunityTtlJsonFiniteNumber `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "contractualMinimumHorizonSeconds") `
            -FailureCode $failureCode
        $contractualMaximum = Get-CommunityTtlJsonFiniteNumber `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "contractualMaximumHorizonSeconds") `
            -FailureCode $failureCode
        $minimumObserved = Get-CommunityTtlJsonFiniteNumber `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "minimumObservedHorizonSeconds") `
            -FailureCode $failureCode
        $maximumObserved = Get-CommunityTtlJsonFiniteNumber `
            -Value (Get-CommunityTtlEvidenceProperty `
                $row "maximumObservedHorizonSeconds") `
            -FailureCode $failureCode
        if (
            [string](Get-CommunityTtlEvidenceProperty $row "expiryField") -cne
                [string]$contract.field -or
            [string](Get-CommunityTtlEvidenceProperty $row "baselineField") -cne
                [string]$contract.baselineField -or
            $contractualMinimum -ne [double]$contract.minimumHorizonSeconds -or
            $contractualMaximum -ne [double]$contract.maximumHorizonSeconds -or
            $documentCount -lt 1 -or
            $validSampleCount -lt 1 -or
            $validSampleCount -gt $documentCount -or
            $recentSampleCount -lt 1 -or
            $recentSampleCount -gt $validSampleCount -or
            $minimumObserved -le 0 -or
            $maximumObserved -lt $minimumObserved -or
            ([double]$contract.minimumHorizonSeconds -gt 0 -and
                $minimumObserved -lt (
                    [double]$contract.minimumHorizonSeconds - 5.0
                )) -or
            $maximumObserved -gt (
                [double]$contract.maximumHorizonSeconds + 5.0
            )
        ) {
            throw "community_ttl_historical_evidence_sample_coverage_invalid"
        }
        foreach ($countName in @(
            "expiredDocumentCount",
            "missingExpiryCount",
            "wrongExpiryTypeCount",
            "invalidExpiryCount",
            "missingBaselineCount",
            "wrongBaselineTypeCount",
            "invalidBaselineCount",
            "futureBaselineCount",
            "expiredBeyondGraceCount",
            "belowMinimumHorizonCount",
            "aboveMaximumHorizonCount"
        )) {
            $count = Get-CommunityTtlJsonCount `
                -Value (Get-CommunityTtlEvidenceProperty $row $countName) `
                -FailureCode $failureCode
            if ($countName -cne "expiredDocumentCount" -and $count -ne 0) {
                throw "community_ttl_historical_evidence_sample_coverage_invalid"
            }
        }
    }
}

function New-FirestoreCommunityTtlHistoricalEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Audit,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [string]$SourceCommit = "",
        [DateTimeOffset]$RecordedAtUtc = [DateTimeOffset]::UtcNow
    )

    foreach ($name in @("schemaVersion", "sourceMode", "capturedAtUtc")) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $Audit $name) `
            -FailureCode "community_ttl_historical_evidence_audit_schema_invalid"
    }
    foreach ($name in @(
        "ready", "identityReady", "policyReady", "documentReady",
        "sampleCoverageComplete"
    )) {
        Assert-CommunityTtlJsonBoolean `
            -Value (Get-CommunityTtlEvidenceProperty $Audit $name) `
            -FailureCode "community_ttl_historical_evidence_audit_schema_invalid"
    }
    $auditBlockingCount = Get-CommunityTtlJsonCount `
        -Value (Get-CommunityTtlEvidenceProperty $Audit "blockingCount") `
        -FailureCode "community_ttl_historical_evidence_audit_schema_invalid"
    if ([string](Get-CommunityTtlEvidenceProperty $Audit "schemaVersion") -cne
            $script:AuditSchema -or
        [string](Get-CommunityTtlEvidenceProperty $Audit "sourceMode") -cne
            "live-read-only") {
        throw "community_ttl_historical_evidence_live_audit_required"
    }
    if ((Get-CommunityTtlEvidenceProperty $Audit "ready") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Audit "identityReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Audit "policyReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Audit "documentReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Audit "sampleCoverageComplete") -ne $true -or
        $auditBlockingCount -ne 0) {
        throw "community_ttl_historical_evidence_audit_not_ready"
    }

    $capturedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $Audit "capturedAtUtc") `
        -FailureCode "community_ttl_historical_evidence_capture_invalid"
    $recordedAt = $RecordedAtUtc.ToUniversalTime()
    $recordingDelay = ($recordedAt - $capturedAt).TotalSeconds
    if ($recordingDelay -lt (-1 * $script:FutureClockSkewSeconds) -or
        $recordingDelay -gt $script:RecordingDelayMaxSeconds) {
        throw "community_ttl_historical_evidence_recording_delay_invalid"
    }

    $identity = Get-CommunityTtlEvidenceProperty $Audit "identity"
    $rawPolicies = Get-CommunityTtlEvidenceProperty $Audit "policies"
    $rawCollections = Get-CommunityTtlEvidenceProperty $Audit "collections"
    Assert-CommunityTtlJsonArray `
        -Value $rawPolicies `
        -FailureCode "community_ttl_historical_evidence_audit_schema_invalid"
    Assert-CommunityTtlJsonArray `
        -Value $rawCollections `
        -FailureCode "community_ttl_historical_evidence_audit_schema_invalid"
    $policies = @($rawPolicies)
    $collections = @($rawCollections)
    Assert-CommunityTtlEvidenceIdentity $identity
    Assert-CommunityTtlEvidencePolicies $policies
    Assert-CommunityTtlEvidenceCollections $collections
    $writerContract = $null
    if (-not [string]::IsNullOrWhiteSpace($SourceCommit)) {
        $root = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd([char[]]"\/")
        # Compare the actual worktree bytes. Git status can deliberately hide a
        # changed file through assume-unchanged or skip-worktree and is not a
        # provenance check.
        $worktreeWriterContract = Get-CommunityTtlWriterContract `
            -RepositoryRoot $root
        $committedWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
            -RepositoryRoot $root `
            -Commit $SourceCommit
        if ([string]$committedWriterContract.sha256 -cne
            [string]$worktreeWriterContract.sha256) {
            throw (
                "community_ttl_historical_evidence_source_commit_" +
                "writer_contract_mismatch"
            )
        }
        $writerContract = $committedWriterContract
    } else {
        $writerContract = Get-CommunityTtlWriterContract `
            -RepositoryRoot $RepositoryRoot
    }
    $sanitizedIdentity = [PSCustomObject][ordered]@{
        activeAccount = [string](
            Get-CommunityTtlEvidenceProperty $identity "activeAccount"
        )
        activeAccountCount = [int](
            Get-CommunityTtlEvidenceProperty $identity "activeAccountCount"
        )
        configuredAccount = [string](
            Get-CommunityTtlEvidenceProperty $identity "configuredAccount"
        )
        configuredProject = [string](
            Get-CommunityTtlEvidenceProperty $identity "configuredProject"
        )
        projectId = [string](Get-CommunityTtlEvidenceProperty $identity "projectId")
        projectNumber = [string](
            Get-CommunityTtlEvidenceProperty $identity "projectNumber"
        )
        projectState = [string](
            Get-CommunityTtlEvidenceProperty $identity "projectState"
        )
        databaseName = [string](
            Get-CommunityTtlEvidenceProperty $identity "databaseName"
        )
        databaseType = [string](
            Get-CommunityTtlEvidenceProperty $identity "databaseType"
        )
    }
    $sanitizedPolicies = @($policies | ForEach-Object {
        [PSCustomObject][ordered]@{
            collectionGroup = [string](
                Get-CommunityTtlEvidenceProperty $_ "collectionGroup"
            )
            field = [string](Get-CommunityTtlEvidenceProperty $_ "field")
            state = [string](Get-CommunityTtlEvidenceProperty $_ "state")
            expirationOffset = [string](
                Get-CommunityTtlEvidenceProperty $_ "expirationOffset"
            )
        }
    })
    $collectionCountFields = @(
        "documentCount",
        "validHorizonSampleCount",
        "recentHorizonSampleCount",
        "missingExpiryCount",
        "wrongExpiryTypeCount",
        "invalidExpiryCount",
        "missingBaselineCount",
        "wrongBaselineTypeCount",
        "invalidBaselineCount",
        "futureBaselineCount",
        "expiredDocumentCount",
        "expiredBeyondGraceCount",
        "belowMinimumHorizonCount",
        "aboveMaximumHorizonCount"
    )
    $sanitizedCollections = @($collections | ForEach-Object {
        $inputRow = $_
        $row = [ordered]@{
            collectionGroup = [string](
                Get-CommunityTtlEvidenceProperty $inputRow "collectionGroup"
            )
            expiryField = [string](
                Get-CommunityTtlEvidenceProperty $inputRow "expiryField"
            )
            baselineField = [string](
                Get-CommunityTtlEvidenceProperty $inputRow "baselineField"
            )
            contractualMinimumHorizonSeconds = [double](
                Get-CommunityTtlEvidenceProperty `
                    $inputRow "contractualMinimumHorizonSeconds"
            )
            contractualMaximumHorizonSeconds = [double](
                Get-CommunityTtlEvidenceProperty `
                    $inputRow "contractualMaximumHorizonSeconds"
            )
        }
        foreach ($fieldName in $collectionCountFields) {
            $row[$fieldName] = [int](
                Get-CommunityTtlEvidenceProperty $inputRow $fieldName
            )
        }
        $row.minimumObservedHorizonSeconds = [double](
            Get-CommunityTtlEvidenceProperty `
                $inputRow "minimumObservedHorizonSeconds"
        )
        $row.maximumObservedHorizonSeconds = [double](
            Get-CommunityTtlEvidenceProperty `
                $inputRow "maximumObservedHorizonSeconds"
        )
        [PSCustomObject]$row
    })

    return [PSCustomObject][ordered]@{
        schemaVersion = $script:HistoricalEvidenceSchema
        evidenceKind = $script:HistoricalEvidenceKind
        sourceMode = "live-read-only"
        capturedAtUtc = $capturedAt.ToString("o")
        recordedAtUtc = $recordedAt.ToString("o")
        auditSchemaVersion = $script:AuditSchema
        ready = $true
        identityReady = $true
        policyReady = $true
        documentReady = $true
        sampleCoverageComplete = $true
        blockingCount = 0
        identity = $sanitizedIdentity
        policies = $sanitizedPolicies
        collections = $sanitizedCollections
        writerContract = $writerContract
    }
}

function New-CommunityTtlCloudAttestationEvent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$EvidenceCore,
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[0-9a-f]{64}$')]
        [string]$Nonce
    )
    $hasAttestation = $null -ne $EvidenceCore.PSObject.Properties[
        "cloudAttestation"
    ]
    Assert-CommunityTtlExactProperties `
        -InputObject $EvidenceCore `
        -Expected $(if ($hasAttestation) {
            $script:EvidenceRootProperties
        } else {
            $script:EvidenceCoreProperties
        }) `
        -FailureCode "community_ttl_cloud_attestation_core_schema_invalid"
    $core = Get-CommunityTtlEvidenceCoreObject $EvidenceCore
    $writerContract = Get-CommunityTtlEvidenceProperty `
        $core "writerContract"
    Assert-CommunityTtlExactProperties `
        -InputObject $writerContract `
        -Expected $script:WriterContractProperties `
        -FailureCode "community_ttl_cloud_attestation_writer_schema_invalid"
    $sourceCommit = [string](Get-CommunityTtlEvidenceProperty `
        $writerContract "sourceCommit")
    if ($sourceCommit -notmatch '^[0-9a-f]{40}$') {
        throw "community_ttl_cloud_attestation_source_commit_invalid"
    }
    return [PSCustomObject][ordered]@{
        schemaVersion = $script:CloudAttestationEventSchema
        projectId = $script:ExpectedProjectId
        databaseName = $script:ExpectedDatabaseName
        nonce = $Nonce.ToLowerInvariant()
        evidenceCoreCanonicalization = $script:EvidenceCoreCanonicalization
        evidenceCoreSha256 = Get-CommunityTtlEvidenceCoreSha256 $core
        sourceCommit = $sourceCommit
        recordedAtUtc = [string](Get-CommunityTtlEvidenceProperty `
            $core "recordedAtUtc")
    }
}

function Assert-CommunityTtlCloudAttestationEvent {
    param(
        [Parameter(Mandatory = $true)][object]$Event,
        [Parameter(Mandatory = $true)][object]$EvidenceCore,
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[0-9a-f]{64}$')]
        [string]$ExpectedNonce
    )
    Assert-CommunityTtlExactProperties `
        -InputObject $Event `
        -Expected $script:CloudAttestationEventProperties `
        -FailureCode "community_ttl_cloud_attestation_event_schema_invalid"
    foreach ($name in $script:CloudAttestationEventProperties) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $Event $name) `
            -FailureCode "community_ttl_cloud_attestation_event_schema_invalid"
    }
    $expected = New-CommunityTtlCloudAttestationEvent `
        -EvidenceCore $EvidenceCore `
        -Nonce $ExpectedNonce
    foreach ($name in $script:CloudAttestationEventProperties) {
        if ([string](Get-CommunityTtlEvidenceProperty $Event $name) -cne
            [string](Get-CommunityTtlEvidenceProperty $expected $name)) {
            throw "community_ttl_cloud_attestation_event_mismatch:$name"
        }
    }
    return $expected
}

function Complete-FirestoreCommunityTtlHistoricalEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$EvidenceCore,
        [Parameter(Mandatory = $true)][object]$CloudLogEntry,
        [Parameter(Mandatory = $true)]
        [ValidatePattern('^[0-9a-f]{64}$')]
        [string]$ExpectedNonce
    )
    Assert-CommunityTtlJsonString `
        -Value (Get-CommunityTtlEvidenceProperty $CloudLogEntry "logName") `
        -FailureCode "community_ttl_cloud_attestation_log_name_invalid"
    Assert-CommunityTtlJsonString `
        -Value (Get-CommunityTtlEvidenceProperty $CloudLogEntry "timestamp") `
        -FailureCode "community_ttl_cloud_attestation_timestamp_invalid"
    $event = Get-CommunityTtlEvidenceProperty $CloudLogEntry "jsonPayload"
    $null = Assert-CommunityTtlCloudAttestationEvent `
        -Event $event `
        -EvidenceCore $EvidenceCore `
        -ExpectedNonce $ExpectedNonce
    $logName = [string](Get-CommunityTtlEvidenceProperty `
        $CloudLogEntry "logName")
    if ($logName -cne $script:CloudAttestationLogName) {
        throw "community_ttl_cloud_attestation_log_name_invalid"
    }
    $logTimestamp = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $CloudLogEntry "timestamp") `
        -FailureCode "community_ttl_cloud_attestation_timestamp_invalid"
    $recordedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $event "recordedAtUtc") `
        -FailureCode "community_ttl_cloud_attestation_recorded_at_invalid"
    if ([Math]::Abs(($logTimestamp - $recordedAt).TotalSeconds) -gt
        $script:RecordingDelayMaxSeconds) {
        throw "community_ttl_cloud_attestation_timestamp_mismatch"
    }
    $result = [ordered]@{}
    foreach ($name in $script:EvidenceCoreProperties) {
        $result[$name] = Get-CommunityTtlEvidenceProperty $EvidenceCore $name
    }
    $result.cloudAttestation = [PSCustomObject][ordered]@{
        schemaVersion = $script:CloudAttestationSchema
        logName = $logName
        nonce = [string](Get-CommunityTtlEvidenceProperty $event "nonce")
        evidenceCoreCanonicalization = $script:EvidenceCoreCanonicalization
        evidenceCoreSha256 = [string](Get-CommunityTtlEvidenceProperty `
            $event "evidenceCoreSha256")
        sourceCommit = [string](Get-CommunityTtlEvidenceProperty `
            $event "sourceCommit")
        recordedAtUtc = $recordedAt.ToString("o")
        logEntryTimestampUtc = $logTimestamp.ToString("o")
    }
    return [PSCustomObject]$result
}

function Assert-CommunityTtlCloudAttestation {
    param(
        [Parameter(Mandatory = $true)][object]$Evidence,
        [Parameter(Mandatory = $true)][object]$Attestation
    )
    Assert-CommunityTtlExactProperties `
        -InputObject $Attestation `
        -Expected $script:CloudAttestationProperties `
        -FailureCode "community_ttl_cloud_attestation_schema_invalid"
    foreach ($name in $script:CloudAttestationProperties) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $Attestation $name) `
            -FailureCode "community_ttl_cloud_attestation_schema_invalid"
    }
    $nonce = [string](Get-CommunityTtlEvidenceProperty $Attestation "nonce")
    $sourceCommit = [string](Get-CommunityTtlEvidenceProperty `
        $Attestation "sourceCommit")
    $coreSha = [string](Get-CommunityTtlEvidenceProperty `
        $Attestation "evidenceCoreSha256")
    if ([string](Get-CommunityTtlEvidenceProperty `
            $Attestation "schemaVersion") -cne $script:CloudAttestationSchema -or
        [string](Get-CommunityTtlEvidenceProperty `
            $Attestation "logName") -cne $script:CloudAttestationLogName -or
        $nonce -notmatch '^[0-9a-f]{64}$' -or
        [string](Get-CommunityTtlEvidenceProperty `
            $Attestation "evidenceCoreCanonicalization") -cne
                $script:EvidenceCoreCanonicalization -or
        $coreSha -notmatch '^[0-9a-f]{64}$' -or
        $coreSha -cne (Get-CommunityTtlEvidenceCoreSha256 $Evidence) -or
        $sourceCommit -notmatch '^[0-9a-f]{40}$') {
        throw "community_ttl_cloud_attestation_invalid"
    }
    $writerSourceCommit = [string](Get-CommunityTtlEvidenceProperty `
        (Get-CommunityTtlEvidenceProperty $Evidence "writerContract") `
        "sourceCommit")
    if ($sourceCommit -cne $writerSourceCommit) {
        throw "community_ttl_cloud_attestation_source_commit_mismatch"
    }
    $recordedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $Evidence "recordedAtUtc") `
        -FailureCode "community_ttl_cloud_attestation_recorded_at_invalid"
    $attestedRecordedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $Attestation "recordedAtUtc") `
        -FailureCode "community_ttl_cloud_attestation_recorded_at_invalid"
    $logTimestamp = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty `
            $Attestation "logEntryTimestampUtc") `
        -FailureCode "community_ttl_cloud_attestation_timestamp_invalid"
    if ($attestedRecordedAt -ne $recordedAt -or
        [Math]::Abs(($logTimestamp - $recordedAt).TotalSeconds) -gt
            $script:RecordingDelayMaxSeconds) {
        throw "community_ttl_cloud_attestation_timestamp_mismatch"
    }
}

function Resolve-CommunityTtlEvidenceGcloud {
    param([string]$GcloudPath = "")
    if (-not [string]::IsNullOrWhiteSpace($GcloudPath)) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) {
            throw "community_ttl_cloud_attestation_gcloud_not_found"
        }
        return (Resolve-Path -LiteralPath $GcloudPath).Path
    }
    foreach ($commandName in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    $fallback = Join-Path $env:LOCALAPPDATA (
        "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    )
    if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) {
        throw "community_ttl_cloud_attestation_gcloud_not_found"
    }
    return $fallback
}

function Read-CommunityTtlCloudAttestationLive {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Attestation,
        [string]$GcloudPath = ""
    )
    Assert-CommunityTtlExactProperties `
        -InputObject $Attestation `
        -Expected $script:CloudAttestationProperties `
        -FailureCode "community_ttl_cloud_attestation_schema_invalid"
    $gcloud = Resolve-CommunityTtlEvidenceGcloud -GcloudPath $GcloudPath
    $nonce = [string](Get-CommunityTtlEvidenceProperty $Attestation "nonce")
    $coreHash = [string](Get-CommunityTtlEvidenceProperty `
        $Attestation "evidenceCoreSha256")
    if ($nonce -notmatch '^[0-9a-f]{64}$' -or
        $coreHash -notmatch '^[0-9a-f]{64}$') {
        throw "community_ttl_cloud_attestation_invalid"
    }
    $filter = (
        'logName="' + $script:CloudAttestationLogName + '" AND ' +
        'jsonPayload.schemaVersion="' +
            $script:CloudAttestationEventSchema + '" AND ' +
        'jsonPayload.nonce="' + $nonce + '" AND ' +
        'jsonPayload.evidenceCoreSha256="' + $coreHash + '"'
    )
    $output = & $gcloud logging read $filter `
        "--project=$($script:ExpectedProjectId)" `
        "--account=$($script:ExpectedAccount)" `
        "--freshness=31d" `
        "--limit=2" `
        "--order=desc" `
        "--format=json" `
        --quiet --verbosity=error 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "community_ttl_cloud_attestation_readback_failed"
    }
    try {
        $rawOutput = [string]($output -join [Environment]::NewLine)
        Assert-CommunityTtlJsonNoDuplicateProperties `
            -Json $rawOutput `
            -FailureCode "community_ttl_cloud_attestation_readback_invalid_json"
        return @(($rawOutput |
            ConvertFrom-Json -DateKind String))
    } catch {
        throw "community_ttl_cloud_attestation_readback_invalid_json"
    }
}

function Assert-CommunityTtlCloudAttestationReadBack {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Evidence,
        [Parameter(Mandatory = $true)][object[]]$Entries
    )
    $attestation = Get-CommunityTtlEvidenceProperty `
        $Evidence "cloudAttestation"
    Assert-CommunityTtlCloudAttestation `
        -Evidence $Evidence `
        -Attestation $attestation
    if ($Entries.Count -ne 1) {
        throw "community_ttl_cloud_attestation_readback_count_invalid"
    }
    $entry = $Entries[0]
    Assert-CommunityTtlJsonString `
        -Value (Get-CommunityTtlEvidenceProperty $entry "logName") `
        -FailureCode (
            "community_ttl_cloud_attestation_readback_log_name_invalid"
        )
    Assert-CommunityTtlJsonString `
        -Value (Get-CommunityTtlEvidenceProperty $entry "timestamp") `
        -FailureCode (
            "community_ttl_cloud_attestation_readback_timestamp_invalid"
        )
    if ([string](Get-CommunityTtlEvidenceProperty $entry "logName") -cne
        $script:CloudAttestationLogName) {
        throw "community_ttl_cloud_attestation_readback_log_name_invalid"
    }
    $event = Get-CommunityTtlEvidenceProperty $entry "jsonPayload"
    $null = Assert-CommunityTtlCloudAttestationEvent `
        -Event $event `
        -EvidenceCore $Evidence `
        -ExpectedNonce ([string](Get-CommunityTtlEvidenceProperty `
            $attestation "nonce"))
    $remoteTimestamp = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $entry "timestamp") `
        -FailureCode "community_ttl_cloud_attestation_readback_timestamp_invalid"
    $recordedTimestamp = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty `
            $attestation "logEntryTimestampUtc") `
        -FailureCode "community_ttl_cloud_attestation_timestamp_invalid"
    if ($remoteTimestamp -ne $recordedTimestamp) {
        throw "community_ttl_cloud_attestation_readback_timestamp_mismatch"
    }
    return [PSCustomObject]@{
        Nonce = [string](Get-CommunityTtlEvidenceProperty $attestation "nonce")
        EvidenceCoreSha256 = [string](Get-CommunityTtlEvidenceProperty `
            $attestation "evidenceCoreSha256")
        LogEntryTimestampUtc = $remoteTimestamp.ToString("o")
    }
}

function Assert-FirestoreCommunityTtlHistoricalEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Evidence,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [object]$ExpectedWriterContract = $null,
        [DateTimeOffset]$NowUtc = [DateTimeOffset]::UtcNow
    )

    Assert-CommunityTtlExactProperties `
        -InputObject $Evidence `
        -Expected $script:EvidenceRootProperties `
        -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    foreach ($name in @(
        "schemaVersion", "evidenceKind", "sourceMode", "capturedAtUtc",
        "recordedAtUtc", "auditSchemaVersion"
    )) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $Evidence $name) `
            -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    }
    foreach ($name in @(
        "ready", "identityReady", "policyReady", "documentReady",
        "sampleCoverageComplete"
    )) {
        Assert-CommunityTtlJsonBoolean `
            -Value (Get-CommunityTtlEvidenceProperty $Evidence $name) `
            -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    }
    $blockingCount = Get-CommunityTtlJsonCount `
        -Value (Get-CommunityTtlEvidenceProperty $Evidence "blockingCount") `
        -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    if ([string](Get-CommunityTtlEvidenceProperty $Evidence "schemaVersion") -cne
            $script:HistoricalEvidenceSchema -or
        [string](Get-CommunityTtlEvidenceProperty $Evidence "evidenceKind") -cne
            $script:HistoricalEvidenceKind -or
        [string](Get-CommunityTtlEvidenceProperty $Evidence "auditSchemaVersion") -cne
            $script:AuditSchema) {
        throw "community_ttl_historical_evidence_schema_invalid"
    }
    if ([string](Get-CommunityTtlEvidenceProperty $Evidence "sourceMode") -cne
            "live-read-only") {
        throw "community_ttl_historical_evidence_fixture_rejected"
    }
    if ((Get-CommunityTtlEvidenceProperty $Evidence "ready") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Evidence "identityReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Evidence "policyReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Evidence "documentReady") -ne $true -or
        (Get-CommunityTtlEvidenceProperty $Evidence "sampleCoverageComplete") -ne $true -or
        $blockingCount -ne 0) {
        throw "community_ttl_historical_evidence_not_ready"
    }

    $capturedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $Evidence "capturedAtUtc") `
        -FailureCode "community_ttl_historical_evidence_capture_invalid"
    $recordedAt = ConvertTo-CommunityTtlEvidenceTimestamp `
        -Value (Get-CommunityTtlEvidenceProperty $Evidence "recordedAtUtc") `
        -FailureCode "community_ttl_historical_evidence_recorded_at_invalid"
    $now = $NowUtc.ToUniversalTime()
    if ($capturedAt -gt $now.AddSeconds($script:FutureClockSkewSeconds) -or
        $recordedAt -gt $now.AddSeconds($script:FutureClockSkewSeconds)) {
        throw "community_ttl_historical_evidence_timestamp_in_future"
    }
    $recordingDelay = ($recordedAt - $capturedAt).TotalSeconds
    if ($recordingDelay -lt (-1 * $script:FutureClockSkewSeconds) -or
        $recordingDelay -gt $script:RecordingDelayMaxSeconds) {
        throw "community_ttl_historical_evidence_recording_delay_invalid"
    }
    $ageSeconds = ($now - $capturedAt).TotalSeconds
    if ($ageSeconds -gt $script:HistoricalEvidenceMaxAgeSeconds) {
        throw "community_ttl_historical_evidence_stale"
    }

    $rawPolicies = Get-CommunityTtlEvidenceProperty $Evidence "policies"
    $rawCollections = Get-CommunityTtlEvidenceProperty $Evidence "collections"
    Assert-CommunityTtlJsonArray `
        -Value $rawPolicies `
        -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    Assert-CommunityTtlJsonArray `
        -Value $rawCollections `
        -FailureCode "community_ttl_historical_evidence_root_schema_invalid"
    Assert-CommunityTtlEvidenceIdentity (
        Get-CommunityTtlEvidenceProperty $Evidence "identity"
    )
    Assert-CommunityTtlEvidencePolicies @($rawPolicies)
    Assert-CommunityTtlEvidenceCollections @($rawCollections)

    $expectedContract = $ExpectedWriterContract
    if ($null -eq $expectedContract) {
        $expectedContract = Get-CommunityTtlWriterContract `
            -RepositoryRoot $RepositoryRoot
    }
    $recordedContract = Get-CommunityTtlEvidenceProperty $Evidence "writerContract"
    Assert-CommunityTtlExactProperties `
        -InputObject $recordedContract `
        -Expected $script:WriterContractProperties `
        -FailureCode (
            "community_ttl_historical_evidence_writer_contract_schema_invalid"
        )
    foreach ($name in @(
        "algorithm", "canonicalization", "sha256", "sourceCommit"
    )) {
        Assert-CommunityTtlJsonString `
            -Value (Get-CommunityTtlEvidenceProperty $recordedContract $name) `
            -FailureCode (
                "community_ttl_historical_evidence_writer_contract_schema_invalid"
            )
    }
    $rawRecordedFiles = Get-CommunityTtlEvidenceProperty $recordedContract "files"
    Assert-CommunityTtlJsonArray `
        -Value $rawRecordedFiles `
        -FailureCode (
            "community_ttl_historical_evidence_writer_contract_schema_invalid"
        )
    $recordedFiles = @($rawRecordedFiles)
    foreach ($recordedFile in $recordedFiles) {
        Assert-CommunityTtlJsonString `
            -Value $recordedFile `
            -FailureCode (
                "community_ttl_historical_evidence_writer_contract_schema_invalid"
            )
    }
    if ([string](Get-CommunityTtlEvidenceProperty $recordedContract "algorithm") -cne
            "sha256" -or
        [string](Get-CommunityTtlEvidenceProperty $recordedContract "canonicalization") -cne
            $script:WriterContractCanonicalization -or
        $recordedFiles.Count -ne $expectedContract.files.Count -or
        (@($recordedFiles) -join "`n") -cne (@($expectedContract.files) -join "`n")) {
        throw "community_ttl_historical_evidence_writer_contract_invalid"
    }
    $recordedSha256 = [string](
        Get-CommunityTtlEvidenceProperty $recordedContract "sha256"
    )
    if ($recordedSha256 -notmatch '^[0-9a-f]{64}$' -or
        $recordedSha256 -cne [string]$expectedContract.sha256) {
        throw "community_ttl_historical_evidence_writer_contract_hash_mismatch"
    }
    $recordedSourceCommit = [string](Get-CommunityTtlEvidenceProperty `
        $recordedContract "sourceCommit")
    if ($recordedSourceCommit -notmatch '^[0-9a-f]{40}$') {
        throw "community_ttl_historical_evidence_source_commit_invalid"
    }
    Assert-CommunityTtlCloudAttestation `
        -Evidence $Evidence `
        -Attestation (Get-CommunityTtlEvidenceProperty `
            $Evidence "cloudAttestation")

    return [PSCustomObject]@{
        CapturedAtUtc = $capturedAt.ToString("o")
        RecordedAtUtc = $recordedAt.ToString("o")
        AgeSeconds = [Math]::Round($ageSeconds, 3)
        MaxAgeSeconds = $script:HistoricalEvidenceMaxAgeSeconds
        WriterContractSha256 = $recordedSha256
        SourceCommit = $recordedSourceCommit
        CloudAttestationNonce = [string](Get-CommunityTtlEvidenceProperty `
            (Get-CommunityTtlEvidenceProperty $Evidence "cloudAttestation") `
            "nonce")
        EvidenceCoreSha256 = [string](Get-CommunityTtlEvidenceProperty `
            (Get-CommunityTtlEvidenceProperty $Evidence "cloudAttestation") `
            "evidenceCoreSha256")
        CollectionCount = @(Get-CommunityTtlAuditContract).Count
    }
}

Export-ModuleMember -Function @(
    "Assert-CommunityTtlJsonNoDuplicateProperties",
    "Assert-CommunityTtlCloudAttestationReadBack",
    "Assert-FirestoreCommunityTtlHistoricalEvidence",
    "Assert-CommunityTtlCloudAttestationEvent",
    "Complete-FirestoreCommunityTtlHistoricalEvidence",
    "Get-CommunityTtlEvidenceCoreSha256",
    "Get-CommunityTtlWriterContract",
    "Get-CommunityTtlWriterContractFromGitCommit",
    "New-CommunityTtlCloudAttestationEvent",
    "New-FirestoreCommunityTtlHistoricalEvidence",
    "Read-CommunityTtlCloudAttestationLive"
)
