[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$LedgerDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $RepositoryRoot) {
    $RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $LedgerDirectory) {
    $LedgerDirectory = Join-Path $RepositoryRoot "release-history\android-play"
}

Import-Module (Join-Path $PSScriptRoot "play-aab-security.psm1") -Force
$result = Assert-PlayReleaseLedgerGitImmutability `
    -RepositoryRoot $RepositoryRoot `
    -LedgerDirectory $LedgerDirectory

[PSCustomObject]@{
    HistoricalRecordCount = $result.HistoricalRecordCount
    Ledger = [IO.Path]::GetFullPath($LedgerDirectory)
    RecordCount = $result.RecordCount
    Status = "PASS"
} | ConvertTo-Json -Compress
