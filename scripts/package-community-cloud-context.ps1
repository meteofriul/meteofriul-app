param(
  [string]$GeographyPath,
  [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$CommunityRepoRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$CommunityManifest = Get-Content -LiteralPath (Join-Path $CommunityRepoRoot "backend/community-pilot-context.files.json") -Raw | ConvertFrom-Json
if ($CommunityManifest.schema -ne "meteofriul.community-cloud-context.v1" -or $CommunityManifest.project -ne "meteo-friul") {
  throw "Unexpected Community cloud package contract."
}
if ([string]::IsNullOrWhiteSpace($GeographyPath)) {
  $GeographyPath = Join-Path $CommunityRepoRoot ".dev-logs/local-weather-pilot/community-geography.sqlite3"
}
$CommunityGeography = (Resolve-Path -LiteralPath $GeographyPath).Path
if ((Get-FileHash -LiteralPath $CommunityGeography -Algorithm SHA256).Hash.ToLowerInvariant() -ne $CommunityManifest.geographySha256) {
  throw "Community geography SHA-256 mismatch."
}
$CommunitySourcePrefix = $CommunityRepoRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
$CommunityEntries = @()
$CommunityDestinations = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($CommunityPair in $CommunityManifest.files) {
  $CommunitySource = [IO.Path]::GetFullPath((Join-Path $CommunityRepoRoot $CommunityPair[0]))
  $CommunityRelative = [string]$CommunityPair[1]
  if (-not $CommunitySource.StartsWith($CommunitySourcePrefix, [StringComparison]::OrdinalIgnoreCase) -or
      [IO.Path]::IsPathRooted($CommunityRelative) -or $CommunityRelative -match '(^|[\\/])\.\.([\\/]|$)' -or
      -not $CommunityDestinations.Add($CommunityRelative)) {
    throw "Invalid or duplicate Community context path."
  }
  $CommunityItem = Get-Item -LiteralPath $CommunitySource
  if ($CommunityItem.PSIsContainer -or ($CommunityItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "Only explicit regular source files may enter the Community context."
  }
  $CommunityEntries += [pscustomobject]@{ Source = $CommunitySource; Destination = $CommunityRelative }
}
$CommunityEntries += [pscustomobject]@{ Source = $CommunityGeography; Destination = "geography/community-geography.sqlite3" }
if ($VerifyOnly) {
  [pscustomobject]@{ Project = $CommunityManifest.project; Files = $CommunityEntries.Count; GeographySha256 = $CommunityManifest.geographySha256; Verified = $true } | ConvertTo-Json
  return
}
$CommunityTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$CommunityContext = Join-Path $CommunityTempRoot ("meteofriul-community-context-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $CommunityContext | Out-Null
foreach ($CommunityEntry in $CommunityEntries) {
  $CommunityTarget = Join-Path $CommunityContext $CommunityEntry.Destination
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $CommunityTarget) | Out-Null
  Copy-Item -LiteralPath $CommunityEntry.Source -Destination $CommunityTarget
  if ((Get-FileHash -LiteralPath $CommunityEntry.Source -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $CommunityTarget -Algorithm SHA256).Hash) {
    throw "Community context copy hash mismatch."
  }
}
$CommunityActualFiles = @(Get-ChildItem -LiteralPath $CommunityContext -Recurse -File -Force)
if ($CommunityActualFiles.Count -ne $CommunityEntries.Count) { throw "Unexpected Community context file count." }
[pscustomobject]@{
  Project = $CommunityManifest.project
  ContextPath = $CommunityContext
  BuildConfig = Join-Path $CommunityContext "cloudbuild.yaml"
  Files = $CommunityActualFiles.Count
  GeographySha256 = $CommunityManifest.geographySha256
  CloudBuildStarted = $false
} | ConvertTo-Json
