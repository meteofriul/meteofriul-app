[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [Parameter(Mandatory = $true)]
    [switch]$RecordLiveEvidence,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{40}$')]
    [string]$SourceCommit,
    [string]$GcloudPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($PSVersionTable.PSVersion.Major -lt 7 -or
    -not (Get-Command ConvertFrom-Json).Parameters.ContainsKey("DateKind")) {
    throw "community_ttl_historical_evidence_powershell_7_required"
}

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$evidenceDirectory = [IO.Path]::GetFullPath(
    (Join-Path $workspaceRoot "release-history\firestore-community-ttl")
)
$auditScript = Join-Path $PSScriptRoot "audit-firestore-community-ttl.ps1"
$evidenceModule = Join-Path $PSScriptRoot "firestore-community-ttl-evidence.psm1"

if (-not $RecordLiveEvidence) {
    throw "community_ttl_historical_evidence_explicit_confirmation_required"
}
if (-not (Test-Path -LiteralPath $auditScript -PathType Leaf)) {
    throw "community_ttl_historical_evidence_audit_script_missing"
}
if (-not (Test-Path -LiteralPath $evidenceModule -PathType Leaf)) {
    throw "community_ttl_historical_evidence_module_missing"
}
if (-not (Test-Path -LiteralPath $evidenceDirectory -PathType Container)) {
    throw "community_ttl_historical_evidence_directory_missing"
}

$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
$resolvedParent = [IO.Path]::GetFullPath((Split-Path -Parent $resolvedOutput))
if ($resolvedParent -cne $evidenceDirectory) {
    throw "community_ttl_historical_evidence_output_outside_ledger"
}
$outputName = [IO.Path]::GetFileName($resolvedOutput)
if ($outputName -cnotmatch '^\d{8}T\d{9}Z-community-ttl\.evidence\.json$') {
    throw "community_ttl_historical_evidence_output_name_invalid"
}
if (Test-Path -LiteralPath $resolvedOutput) {
    throw "community_ttl_historical_evidence_output_exists"
}

Import-Module $evidenceModule -Force

function Resolve-RecorderGcloudExecutable {
    if (-not [string]::IsNullOrWhiteSpace($GcloudPath)) {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) {
            throw "community_ttl_historical_evidence_gcloud_not_found"
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
        throw "community_ttl_historical_evidence_gcloud_not_found"
    }
    return $fallback
}

function Resolve-RecorderGcloudPythonEntrypoint {
    param([Parameter(Mandatory = $true)][string]$Executable)

    $resolvedExecutable = [IO.Path]::GetFullPath($Executable)
    $commandDirectory = [IO.Path]::GetFullPath(
        (Split-Path -Parent $resolvedExecutable)
    )
    $candidateRoots = @(
        $commandDirectory,
        [IO.Path]::GetFullPath((Join-Path $commandDirectory ".."))
    ) | Select-Object -Unique
    foreach ($sdkRoot in $candidateRoots) {
        $bundledPython = Join-Path $sdkRoot "platform\bundledpython\python.exe"
        $gcloudPython = Join-Path $sdkRoot "lib\gcloud.py"
        if ((Test-Path -LiteralPath $bundledPython -PathType Leaf) -and
            (Test-Path -LiteralPath $gcloudPython -PathType Leaf)) {
            return [PSCustomObject]@{
                SdkRoot = $sdkRoot
                Python = $bundledPython
                Gcloud = $gcloudPython
            }
        }
    }
    throw "community_ttl_gcloud_native_entrypoint_missing"
}

function Invoke-RecorderGcloudCapture {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [ValidateRange(1, 600)][int]$TimeoutSeconds = 120
    )

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $resolvedExecutable = [IO.Path]::GetFullPath($Executable)
    if ([IO.Path]::GetExtension($resolvedExecutable) -ieq ".cmd") {
        $entrypoint = Resolve-RecorderGcloudPythonEntrypoint `
            -Executable $resolvedExecutable
        $startInfo.FileName = $entrypoint.Python
        $null = $startInfo.ArgumentList.Add("-S")
        $null = $startInfo.ArgumentList.Add($entrypoint.Gcloud)
        $null = $startInfo.Environment.Remove("PYTHONHOME")
        $startInfo.Environment["CLOUDSDK_ROOT_DIR"] = $entrypoint.SdkRoot
        $startInfo.Environment["PYTHONIOENCODING"] = "utf-8"
    } else {
        $startInfo.FileName = $resolvedExecutable
    }
    foreach ($argument in $Arguments) {
        $null = $startInfo.ArgumentList.Add($argument)
    }
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $utf8 = [Text.UTF8Encoding]::new($false)
    $startInfo.StandardOutputEncoding = $utf8
    $startInfo.StandardErrorEncoding = $utf8

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw "community_ttl_gcloud_process_start_failed"
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw "community_ttl_gcloud_process_timeout"
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult().Trim()
        $stderr = $stderrTask.GetAwaiter().GetResult().Trim()
        return [PSCustomObject]@{
            ExitCode = $process.ExitCode
            Output = (@($stdout, $stderr) | Where-Object { $_ }) -join `
                [Environment]::NewLine
        }
    } finally {
        $process.Dispose()
    }
}

$gcloud = Resolve-RecorderGcloudExecutable
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) (
    "meteofriul-community-ttl-record-" + [Guid]::NewGuid().ToString("N")
)
$auditPath = Join-Path $temporaryRoot "fresh-live-audit.json"
New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
try {
    $auditArguments = @{
        OutputPath = $auditPath
        Account = "meteofriul@gmail.com"
        ProjectId = "meteo-friul"
        DatabaseId = "(default)"
    }
    if (-not [string]::IsNullOrWhiteSpace($GcloudPath)) {
        $auditArguments.GcloudPath = $GcloudPath
    }

    $auditError = $null
    try {
        & $auditScript @auditArguments | Out-Null
    } catch {
        $auditError = $_.Exception.Message
    }
    if (-not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
        throw "community_ttl_historical_evidence_audit_output_missing"
    }
    try {
        $audit = Get-Content -LiteralPath $auditPath -Raw |
            ConvertFrom-Json -DateKind String
    } catch {
        throw "community_ttl_historical_evidence_audit_output_invalid"
    }
    if ([string]$audit.sourceMode -cne "live-read-only") {
        throw "community_ttl_historical_evidence_fixture_rejected"
    }
    if ($null -ne $auditError) {
        throw "community_ttl_historical_evidence_live_audit_failed:$auditError"
    }

    $recordedAt = [DateTimeOffset]::UtcNow
    $evidenceCore = New-FirestoreCommunityTtlHistoricalEvidence `
        -Audit $audit `
        -RepositoryRoot $workspaceRoot `
        -SourceCommit $SourceCommit `
        -RecordedAtUtc $recordedAt
    $nonceBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    $nonce = [Convert]::ToHexString($nonceBytes).ToLowerInvariant()
    $attestationEvent = New-CommunityTtlCloudAttestationEvent `
        -EvidenceCore $evidenceCore `
        -Nonce $nonce
    $payload = $attestationEvent | ConvertTo-Json -Depth 5 -Compress
    $writeResult = Invoke-RecorderGcloudCapture `
        -Executable $gcloud `
        -Arguments @(
            "logging", "write", "meteofriul-community-ttl-evidence",
            $payload, "--payload-type=json", "--severity=NOTICE",
            "--project=meteo-friul", "--account=meteofriul@gmail.com",
            "--quiet", "--verbosity=error"
        )
    if ($writeResult.ExitCode -ne 0) {
        throw (
            "community_ttl_cloud_attestation_write_failed:" +
            $writeResult.Output
        )
    }

    $readProbe = [PSCustomObject][ordered]@{
        schemaVersion = "firestore-community-ttl-cloud-attestation-v1"
        logName = (
            "projects/meteo-friul/logs/" +
            "meteofriul-community-ttl-evidence"
        )
        nonce = $nonce
        evidenceCoreCanonicalization = (
            "v1:powershell-json-depth-12-compress-utf8"
        )
        evidenceCoreSha256 = [string]$attestationEvent.evidenceCoreSha256
        sourceCommit = [string]$attestationEvent.sourceCommit
        recordedAtUtc = [string]$attestationEvent.recordedAtUtc
        logEntryTimestampUtc = [string]$attestationEvent.recordedAtUtc
    }
    $remoteEntries = @()
    for ($attempt = 1; $attempt -le 12; $attempt += 1) {
        $remoteEntries = @(Read-CommunityTtlCloudAttestationLive `
            -Attestation $readProbe `
            -GcloudPath $gcloud)
        if ($remoteEntries.Count -eq 1) { break }
        if ($attempt -lt 12) { Start-Sleep -Seconds 2 }
    }
    if ($remoteEntries.Count -ne 1) {
        throw "community_ttl_cloud_attestation_readback_count_invalid"
    }
    $evidence = Complete-FirestoreCommunityTtlHistoricalEvidence `
        -EvidenceCore $evidenceCore `
        -CloudLogEntry $remoteEntries[0] `
        -ExpectedNonce $nonce
    $json = $evidence | ConvertTo-Json -Depth 10
    $encoding = [Text.UTF8Encoding]::new($false)
    try {
        $stream = [IO.File]::Open(
            $resolvedOutput,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )
        try {
            $writer = [IO.StreamWriter]::new($stream, $encoding)
            try { $writer.Write("$json$([Environment]::NewLine)") }
            finally { $writer.Dispose() }
        } finally {
            $stream.Dispose()
        }
    } catch [IO.IOException] {
        throw "community_ttl_historical_evidence_output_exists"
    }

    try {
        $rawWritten = Get-Content -LiteralPath $resolvedOutput -Raw
        Assert-CommunityTtlJsonNoDuplicateProperties `
            -Json $rawWritten `
            -FailureCode "community_ttl_historical_evidence_duplicate_property"
        $written = $rawWritten |
            ConvertFrom-Json -DateKind String
        $sourceWriterContract = Get-CommunityTtlWriterContractFromGitCommit `
            -RepositoryRoot $workspaceRoot `
            -Commit $SourceCommit
        $validated = Assert-FirestoreCommunityTtlHistoricalEvidence `
            -Evidence $written `
            -RepositoryRoot $workspaceRoot `
            -ExpectedWriterContract $sourceWriterContract `
            -NowUtc $recordedAt
    } catch {
        if (Test-Path -LiteralPath $resolvedOutput -PathType Leaf) {
            Remove-Item -LiteralPath $resolvedOutput -Force
        }
        throw
    }

    [PSCustomObject]@{
        Path = $resolvedOutput
        CapturedAtUtc = $validated.CapturedAtUtc
        WriterContractSha256 = $validated.WriterContractSha256
        NextStep = (
            "Review the aggregate-only record, run contract tests, then add and " +
            "commit it as a new immutable file. Never edit an existing record."
        )
    } | Format-List
} finally {
    $resolvedTemporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolvedTemporaryRoot.StartsWith(
        $resolvedSystemTemp,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        throw "community_ttl_historical_evidence_unsafe_cleanup_target"
    }
    if (Test-Path -LiteralPath $resolvedTemporaryRoot -PathType Container) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
