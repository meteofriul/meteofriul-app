param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
  param([string]$Message)
  $Failures.Add($Message)
}

$trackedFiles = @(& git -C $Root ls-files)
if ($LASTEXITCODE -ne 0) {
  throw "Unable to read the tracked-file inventory."
}

$trackedNoisePattern = '(^|/)(node_modules|dist|build|__pycache__|\.pytest_cache|\.dev-logs|\.wrangler)(/|$)'
$trackedSecretPattern = '(^|/)\.env($|\.)|(^|/)(google-services\.json|local\.properties)$|\.(jks|keystore)$'

foreach ($relativePath in $trackedFiles) {
  $normalizedPath = $relativePath -replace '\\', '/'

  if ($normalizedPath -match $trackedNoisePattern) {
    Add-Failure "generated file is tracked: $relativePath"
  }

  if ($normalizedPath -match $trackedSecretPattern -and $normalizedPath -notmatch '\.env\.example$') {
    Add-Failure "local configuration or secret is tracked: $relativePath"
  }
}

$activeScopes = @(
  '.github',
  'backend/app',
  'backend/tests',
  'backend_dryrun_staging',
  'frontend/src',
  'scripts',
  'firebase.json'
)

$forbiddenReferences = @(
  'meteo friul 13 - Nuova UI con Figma',
  'meteo friul - ui 3.0.0',
  '.codex/worktrees',
  '.codex\\worktrees',
  'C:\Users\',
  'C:/Users/',
  'F:\proggetto Meteo Friul App\scarica dati fvg',
  'F:/proggetto Meteo Friul App/scarica dati fvg',
  'F:\proggetto Meteo Friul App\documentazione ed installer',
  'F:/proggetto Meteo Friul App/documentazione ed installer'
)

$activeScopePathspecs = @($activeScopes) + @(
  ':(exclude)scripts/test-canonical-workspace-cleanliness.ps1'
)

foreach ($forbiddenReference in $forbiddenReferences) {
  $matches = @(& git -C $Root grep -n -I -F -- $forbiddenReference -- @activeScopePathspecs 2>$null)
  $grepExitCode = $LASTEXITCODE

  if ($grepExitCode -eq 0) {
    foreach ($match in $matches) {
      Add-Failure "obsolete workspace reference: $match"
    }
  } elseif ($grepExitCode -ne 1) {
    throw "Unable to inspect active project paths for '$forbiddenReference'."
  }
}

$snapshotPackPath = Join-Path $Root 'experiments\weather_autonomy\fixtures\local-pilot-snapshot-20260904.zip'
$snapshotHashes = [ordered]@{
  'icon_payload_precipitation_semantics_v3_20260904.json' = '9b9e18bc3613eed505180ce99af8fca723047d1956d817db79985ded4fe1a74e'
  'icon_report_precipitation_semantics_v3_20260904.json' = '6abcbf6fda33621f50dd1f114c6d92de362b119754bdd83954cca9dce6df8186'
  'cams_fvg_authoritative_20260904.json' = '77c9b9181e95797ea7f380a7bd91bc6fdc7133412708a253268de36ab82825f0'
  'cams_fvg_authoritative_report_20260904.json' = '40c28f7df8c1d166ea9673013bcceecd20bf496236f8a2fd6297a07ef1d7a4e3'
}

if (-not [System.IO.File]::Exists($snapshotPackPath)) {
  Add-Failure "bundled offline-pilot snapshot is missing"
} else {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($snapshotPackPath)
  try {
    $seenEntries = @{}
    foreach ($entry in $archive.Entries) {
      if (-not $snapshotHashes.Contains($entry.FullName) -or $entry.Name -cne $entry.FullName) {
        Add-Failure "unexpected bundled snapshot entry: $($entry.FullName)"
        continue
      }
      if ($seenEntries.ContainsKey($entry.FullName)) {
        Add-Failure "duplicate bundled snapshot entry: $($entry.FullName)"
        continue
      }
      $seenEntries[$entry.FullName] = $true
      $stream = $entry.Open()
      $sha256 = [System.Security.Cryptography.SHA256]::Create()
      try {
        $digestBytes = $sha256.ComputeHash($stream)
        $digest = [System.BitConverter]::ToString($digestBytes).Replace('-', '').ToLowerInvariant()
      } finally {
        $sha256.Dispose()
        $stream.Dispose()
      }
      if ($digest -cne $snapshotHashes[$entry.FullName]) {
        Add-Failure "bundled snapshot digest differs: $($entry.FullName)"
      }
    }
    foreach ($expectedEntry in $snapshotHashes.Keys) {
      if (-not $seenEntries.ContainsKey($expectedEntry)) {
        Add-Failure "bundled snapshot entry is missing: $expectedEntry"
      }
    }
  } finally {
    $archive.Dispose()
  }
}

if ($Failures.Count -gt 0) {
  Write-Host "Canonical workspace cleanliness: FAILED" -ForegroundColor Red
  $Failures | ForEach-Object { Write-Host "- $_" }
  exit 1
}

Write-Host "Canonical workspace cleanliness: OK"
Write-Host "Tracked files: $($trackedFiles.Count)"
Write-Host "No generated output, local secrets, or obsolete active workspace references are tracked."
