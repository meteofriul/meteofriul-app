[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("play-accepted", "abandoned", "upload-key-rotation")]
    [string]$Event,

    [ValidateRange(1, 2100000000)]
    [int]$VersionCode,

    [ValidateRange(0, 2100000000)]
    [int]$LatestConsoleVersionCode,

    [string]$EvidenceReference,
    [string]$Reason,
    [string]$PreviousUploadCertificateSha256,
    [string]$NewUploadCertificateSha256,

    [string]$LedgerDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$ledgerDirectory = if ([string]::IsNullOrWhiteSpace($LedgerDirectory)) {
    Join-Path $workspaceRoot "release-history\android-play"
} else {
    [IO.Path]::GetFullPath($LedgerDirectory)
}
Import-Module (Join-Path $PSScriptRoot "play-aab-security.psm1") -Force
$ledger = Read-PlayReleaseLedger -Directory $ledgerDirectory
$createdAt = (Get-Date).ToUniversalTime()
$payload = [ordered]@{
    SchemaVersion = 1
    CreatedAtUtc = $createdAt.ToString("o")
    Event = $Event
}

switch ($Event) {
    "play-accepted" {
        if ([string]::IsNullOrWhiteSpace($EvidenceReference)) {
            throw "release_android_play_acceptance_reference_required"
        }
        if (@($ledger.Evidence | Where-Object {
            $_.Event -in @("play-accepted", "abandoned") -and
            [int]$_.Record.VersionCode -eq $VersionCode
        }).Count -gt 0) {
            throw "release_android_play_terminal_evidence_already_exists"
        }
        $release = @($ledger.Releases | Where-Object VersionCode -eq $VersionCode)
        if ($release.Count -ne 1) {
            throw "release_android_play_acceptance_bundle_required: versionCode=$VersionCode"
        }
        if ($LatestConsoleVersionCode -lt $VersionCode) {
            throw "release_android_play_acceptance_console_version_invalid"
        }
        $payload.VersionCode = $VersionCode
        $payload.VersionName = $release[0].VersionName
        $payload.AabSha256 = $release[0].AabSha256
        $payload.UploadCertificateSha256 = $release[0].UploadCertificateSha256
        $payload.LatestConsoleVersionCode = $LatestConsoleVersionCode
        $payload.EvidenceReference = $EvidenceReference.Trim()
    }
    "abandoned" {
        if ([string]::IsNullOrWhiteSpace($Reason)) {
            throw "release_android_play_abandoned_reason_required"
        }
        $known = @($ledger.AllVersions | Where-Object VersionCode -eq $VersionCode)
        if ($known.Count -ne 1) {
            throw "release_android_play_abandoned_version_unknown: versionCode=$VersionCode"
        }
        if (@($ledger.Evidence | Where-Object {
            $_.Event -in @("play-accepted", "abandoned") -and
            [int]$_.Record.VersionCode -eq $VersionCode
        }).Count -gt 0) {
            throw "release_android_play_terminal_evidence_already_exists"
        }
        $payload.VersionCode = $VersionCode
        $payload.VersionName = $known[0].VersionName
        $payload.Reason = $Reason.Trim()
    }
    "upload-key-rotation" {
        if ([string]::IsNullOrWhiteSpace($EvidenceReference)) {
            throw "release_android_play_rotation_reference_required"
        }
        $previous = ConvertTo-PlaySha256 `
            -Value $PreviousUploadCertificateSha256 `
            -FailureCode "release_android_play_rotation_previous_invalid"
        $next = ConvertTo-PlaySha256 `
            -Value $NewUploadCertificateSha256 `
            -FailureCode "release_android_play_rotation_new_invalid"
        if ($previous -ceq $next) {
            throw "release_android_play_rotation_certificate_unchanged"
        }
        if ($null -eq $ledger.LatestAcceptedEvidence) {
            throw "release_android_play_rotation_acceptance_anchor_required"
        }
        $effectiveCertificate = [string]$ledger.LatestAcceptedEvidence.UploadCertificateSha256
        foreach ($rotation in @($ledger.Rotations | Sort-Object CreatedAt)) {
            if (
                $rotation.CreatedAt -gt $ledger.LatestAcceptedEvidence.CreatedAt -and
                $rotation.PreviousUploadCertificateSha256 -ceq $effectiveCertificate
            ) {
                $effectiveCertificate = $rotation.NewUploadCertificateSha256
            }
        }
        if ($previous -cne $effectiveCertificate) {
            throw "release_android_play_rotation_previous_not_current"
        }
        $payload.PreviousUploadCertificateSha256 = $previous
        $payload.NewUploadCertificateSha256 = $next
        $payload.EvidenceReference = $EvidenceReference.Trim()
    }
}

$safeEvent = $Event -replace '[^a-z0-9-]', '-'
$stamp = $createdAt.ToString("yyyyMMddTHHmmssfffZ")
$suffix = [Guid]::NewGuid().ToString("N")
$path = Join-Path $ledgerDirectory "$stamp-$safeEvent-$suffix.evidence.json"
Write-NewPlayJsonFile -Path $path -Payload $payload | Out-Null

[PSCustomObject]@{
    Event = $Event
    Evidence = $path
    NextStep = "Review, commit and push this append-only evidence file. Never edit an existing ledger record."
} | Format-List
