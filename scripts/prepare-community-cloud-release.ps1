param(
  [Parameter(Mandatory = $true)][string]$ExpectedCurrentRevision,
  [Parameter(Mandatory = $true)][string]$ExpectedCurrentImageDigest
)

# Local preparation only. This script has no gcloud, GitHub or deployment calls.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$CommunityReleaseRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$CommunitySourceCommit = (& git -C $CommunityReleaseRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $CommunitySourceCommit -notmatch '^[0-9a-f]{40}$') {
  throw 'Cannot identify the candidate commit.'
}
$CommunityReleaseBranch = (& git -C $CommunityReleaseRoot branch --show-current).Trim()
if ($CommunityReleaseBranch -notlike 'codex/*') { throw 'Prepare on the dedicated codex release branch.' }
& git -C $CommunityReleaseRoot diff --quiet HEAD
if ($LASTEXITCODE -ne 0) { throw 'Commit tracked candidate changes before preparing the release.' }
if ($ExpectedCurrentRevision -notmatch '^meteofriul-community-[a-z0-9-]+$' -or
    $ExpectedCurrentImageDigest -notmatch '^europe-west1-docker.pkg.dev/meteo-friul/meteofriul/community@sha256:[0-9a-f]{64}$') {
  throw 'Supply the verified Community production revision and immutable image digest.'
}
$CommunityRuntimeEnv = Get-Content -LiteralPath (Join-Path $CommunityReleaseRoot 'backend/community-production.env.yaml') -Raw
if ($CommunityRuntimeEnv -notmatch '(?m)^COMMUNITY_V3_WRITES_ENABLED: "0"\s*$') {
  throw 'The initial candidate must keep v3 writes disabled.'
}
# Run the check in a fresh PowerShell process: its successful path can leave
# rg's "no match" exit code behind even after printing the PASS summary.
& (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'test-canonical-workspace-cleanliness.ps1') | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Canonical cleanliness failed.' }

$CommunityPreparedContext = & (Join-Path $PSScriptRoot 'package-community-cloud-context.ps1') | ConvertFrom-Json
# Require every packaged source to be committed, even if unrelated user files
# are untracked. Ignored geography is the sole explicitly pinned exception.
$CommunityAllowlist = Get-Content -LiteralPath (Join-Path $CommunityReleaseRoot 'backend/community-pilot-context.files.json') -Raw | ConvertFrom-Json
foreach ($CommunityPair in $CommunityAllowlist.files) {
  & git -C $CommunityReleaseRoot ls-files --error-unmatch -- $CommunityPair[0] | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Uncommitted package source: $($CommunityPair[0])" }
}
$CommunityShortCommit = $CommunitySourceCommit.Substring(0, 8)
$CommunityStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$CommunityOutput = Join-Path $CommunityReleaseRoot "build/community-cloud/$CommunityShortCommit-$CommunityStamp"
New-Item -ItemType Directory -Path $CommunityOutput | Out-Null
$CommunityArchive = Join-Path $CommunityOutput 'source.tar.gz'
& tar.exe -czf $CommunityArchive -C $CommunityPreparedContext.ContextPath .
if ($LASTEXITCODE -ne 0) { throw 'Cannot archive the allowlisted context.' }
Copy-Item -LiteralPath (Join-Path $CommunityReleaseRoot 'backend/community-production.env.yaml') -Destination (Join-Path $CommunityOutput 'runtime.env.yaml')
$CommunityValidationService = 'meteofriul-community-validation'
$CommunityValidationHost = "$CommunityValidationService-49007668366.europe-west1.run.app"
$CommunityValidationPointer = "compat-validation-$CommunityShortCommit"
$CommunityValidationEnv = $CommunityRuntimeEnv `
  -replace '(?m)^COMMUNITY_POINTER_DOCUMENT: current\r?$', "COMMUNITY_POINTER_DOCUMENT: $CommunityValidationPointer" `
  -replace '(?m)^COMMUNITY_SNAPSHOT_PREFIX: community/v2/snapshots/\r?$', "COMMUNITY_SNAPSHOT_PREFIX: community/v2/validation/$CommunityShortCommit/snapshots/" `
  -replace '(?m)^COMMUNITY_V3_WRITES_ENABLED: "0"\r?$', 'COMMUNITY_V3_WRITES_ENABLED: "1"' `
  -replace '(?m)^COMMUNITY_ALLOWED_HOSTS: .+\r?$', "COMMUNITY_ALLOWED_HOSTS: $CommunityValidationHost"
if ($CommunityValidationEnv -match '(?m)^COMMUNITY_POINTER_DOCUMENT: current\s*$' -or
    $CommunityValidationEnv -notmatch "(?m)^COMMUNITY_POINTER_DOCUMENT: $CommunityValidationPointer\s*$") {
  throw 'Validation must never use the production state pointer.'
}
$CommunityValidationEnv | Set-Content -LiteralPath (Join-Path $CommunityOutput 'validation.env.yaml') -Encoding utf8
$CommunityManifest = [ordered]@{
  Schema = 'meteofriul.community-release-preparation.v1'
  PreparedAtUtc = $CommunityStamp
  SourceCommit = $CommunitySourceCommit
  Branch = $CommunityReleaseBranch
  Project = 'meteo-friul'
  Region = 'europe-west1'
  Service = 'meteofriul-community'
  ExpectedCurrentRevision = $ExpectedCurrentRevision
  ExpectedCurrentImageDigest = $ExpectedCurrentImageDigest
  CandidateImage = "europe-west1-docker.pkg.dev/meteo-friul/meteofriul/community:compat-$CommunityShortCommit"
  ContextPath = $CommunityPreparedContext.ContextPath
  BuildConfig = $CommunityPreparedContext.BuildConfig
  Archive = $CommunityArchive
  ArchiveSha256 = (Get-FileHash -LiteralPath $CommunityArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  RuntimeEnvSha256 = (Get-FileHash -LiteralPath (Join-Path $CommunityOutput 'runtime.env.yaml') -Algorithm SHA256).Hash.ToLowerInvariant()
  Validation = @{
    Service = $CommunityValidationService
    Host = $CommunityValidationHost
    StatePointer = "community_state_v2/$CommunityValidationPointer"
    SnapshotPrefix = "community/v2/validation/$CommunityShortCommit/snapshots/"
    EnvSha256 = (Get-FileHash -LiteralPath (Join-Path $CommunityOutput 'validation.env.yaml') -Algorithm SHA256).Hash.ToLowerInvariant()
    Initialized = $false
    Deployed = $false
  }
  Files = $CommunityPreparedContext.Files
  GeographySha256 = $CommunityPreparedContext.GeographySha256
  DefaultProtocol = 'community-pilot-national-safety-v2'
  V3WritesEnabled = $false
  CloudBuildStarted = $false
  Deployed = $false
  TrafficChanged = $false
}
$CommunityManifestPath = Join-Path $CommunityOutput 'release-manifest.json'
$CommunityManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $CommunityManifestPath -Encoding utf8
[pscustomobject]@{ Manifest = $CommunityManifestPath; Archive = $CommunityArchive; SourceCommit = $CommunitySourceCommit; Deployed = $false } | ConvertTo-Json
