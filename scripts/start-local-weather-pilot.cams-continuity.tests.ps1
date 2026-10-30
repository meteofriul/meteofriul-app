$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Load only pure verification functions: no launcher lifecycle or real network.
$tokens = $null
$parseErrors = $null
$launcherAst = [Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $PSScriptRoot "start-local-weather-pilot.ps1"), [ref]$tokens, [ref]$parseErrors
)
if ($parseErrors.Count) { throw "Launcher does not parse" }
foreach ($name in @(
  "Convert-CanonicalUtcSecond", "Convert-CanonicalRunIdToUtcSecond",
  "Get-ResponseSha256", "Test-CamsFamilyReleaseDescriptor", "Test-CamsFamilyLatestPayload",
  "Test-CamsFamilyReleaseResponse", "Test-WeatherManifestResponse", "Test-CamsContinuityResponse",
  "Test-CamsFamilyArtifacts"
)) {
  $definition = $launcherAst.Find({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
  }, $true)
  if ($null -eq $definition) { throw "Missing verifier $name" }
  $body = $definition.Extent.Text
  if ($name -eq "Test-CamsFamilyArtifacts") {
    # Test-only clock injection leaves the production UTC clock unchanged.
    $clock = '$now = [datetimeoffset]::UtcNow'
    if (-not $body.Contains($clock)) { throw "Expected production clock not found" }
    $body = $body.Replace($clock, '$now = $script:fixtureNow')
  }
  Invoke-Expression $body
}

$script:assertions = 0
function Assert-Result {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw "FAIL: $Message" }
  $script:assertions += 1
  Write-Output "PASS: $Message"
}
function New-Response {
  param($Document)
  return [pscustomobject]@{ StatusCode = 200; Content = ($Document | ConvertTo-Json -Depth 12 -Compress) }
}
function Copy-Document { param($Document) return ($Document | ConvertTo-Json -Depth 12 -Compress | ConvertFrom-Json) }

$ExpectedCatalogVersion = "test-catalog-v1"
$ExpectedCatalogSha256 = "a" * 64
$ExpectedMunicipalityCount = 1
$catalog = [ordered]@{ municipality_count = 1; sha256 = $ExpectedCatalogSha256; version = $ExpectedCatalogVersion }
$runId = "20261029T000000Z"
$run = [datetimeoffset]::Parse("2026-10-29T00:00:00Z")
$script:fixtureNow = $run.AddHours(31)
$base = "https://fixture.invalid"
$script:responses = @{}
$script:requests = [System.Collections.Generic.List[string]]::new()
function Invoke-WebRequest {
  param([string]$Uri, [switch]$UseBasicParsing, [int]$TimeoutSec)
  $script:requests.Add($Uri)
  if (-not $script:responses.ContainsKey($Uri)) { throw "Fixture HTTP 404" }
  return $script:responses[$Uri]
}
$components = [ordered]@{}
foreach ($role in @("core", "pollen")) {
  $provider = if ($role -eq "core") { "cams_europe" } else { "cams_europe_pollen" }
  $policy = if ($role -eq "core") { "cams_current_v1" } else { "cams_pollen_current_v1" }
  $manifest = [ordered]@{
    schema_version = 1; kind = "meteofriul.weather.run_manifest"; provider = $provider
    source_run_id = $runId; catalog = $catalog; objects = @{ "030129" = @{} }
    run_at = "2026-10-29T00:00:00Z"; valid_from = "2026-10-29T00:00:00Z"; valid_to = "2026-11-02T00:00:00Z"
    freshness = @{
      policy_id = $policy; required_future_hours = 0; current_sample_max_lag_minutes = 60
      fresh_until = "2026-10-30T00:00:00Z"; usable_until = "2026-10-30T06:00:00Z"
    }
  }
  $response = New-Response $manifest
  $key = "weather/v1/$provider/runs/$runId/manifest.json"
  $script:responses["$base/$key"] = $response
  $components[$role] = @{
    provider = $provider; source_run_id = $runId; manifest_key = $key
    manifest_json_bytes = [System.Text.Encoding]::UTF8.GetByteCount($response.Content)
    manifest_sha256 = Get-ResponseSha256 $response
  }
}
$release = [ordered]@{
  schema_version = 1; kind = "meteofriul.weather.cams_family_release"; family = "cams"
  source_run_id = $runId; catalog = $catalog; published_at = "2026-10-29T10:00:00Z"
  validation_sha256 = "b" * 64; components = $components
}
$releaseResponse = New-Response $release
$script:responses["$base/weather/v1/families/cams/runs/$runId/release.json"] = $releaseResponse
$latest = Copy-Document ([ordered]@{
  schema_version = 1; kind = "meteofriul.weather.cams_family_latest"; family = "cams"
  catalog = $catalog; disabled_run_ids = @(); previous = $null; revision = 1
  published_at = "2026-10-29T10:00:00Z"
  latest = @{
    source_run_id = $runId; release_path = "runs/$runId/release.json"
    release_json_bytes = [System.Text.Encoding]::UTF8.GetByteCount($releaseResponse.Content)
    release_sha256 = Get-ResponseSha256 $releaseResponse
  }
})
# Independent fixture spells out the issued policy, including its exact UTC dates.
$grant = [ordered]@{
  catalog = $catalog; current_sample_max_lag_minutes = 60; fresh_until = "2026-10-30T00:00:00Z"
  issued_at = "2026-10-29T10:00:00Z"; kind = "meteofriul.weather.cams_continuity"
  policy_id = "cams_continuity_36h_v1"; release_json_bytes = $latest.latest.release_json_bytes
  release_sha256 = $latest.latest.release_sha256; run_at = "2026-10-29T00:00:00Z"
  schema_version = 1; source_run_id = $runId; usable_until = "2026-10-30T12:00:00Z"
}
$grantResponse = New-Response $grant
$grantUrl = "$base/weather/v1/families/cams/runs/$runId/continuity.json"
$script:responses[$grantUrl] = $grantResponse

Assert-Result (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent) "valid bound grant permits cloud startup at run+31h"
Assert-Result ($script:requests.Contains($grantUrl)) "extended startup reads the exact family grant"
foreach ($hour in @(0, 30, 36)) {
  Assert-Result (Test-CamsContinuityResponse $grantResponse $releaseResponse $latest -Now $run.AddHours($hour)) "valid grant accepts boundary run+$hour h"
}
foreach ($instant in @($run.AddSeconds(-1), $run.AddHours(36).AddSeconds(1))) {
  Assert-Result (-not (Test-CamsContinuityResponse $grantResponse $releaseResponse $latest -Now $instant)) "grant rejects future or expired family"
}
foreach ($change in @(
  @{ field = "release_sha256"; value = ("c" * 64) },
  @{ field = "release_json_bytes"; value = ($latest.latest.release_json_bytes + 1) },
  @{ field = "source_run_id"; value = "20261028T000000Z" },
  @{ field = "issued_at"; value = "2026-10-29T10:00:01Z" },
  @{ field = "run_at"; value = "2026-10-29T01:00:00Z" },
  @{ field = "fresh_until"; value = "2026-10-30T01:00:00Z" },
  @{ field = "usable_until"; value = "2026-10-30T13:00:00Z" },
  @{ field = "kind"; value = "other" },
  @{ field = "policy_id"; value = "cams_continuity_48h_v1" },
  @{ field = "current_sample_max_lag_minutes"; value = 120 },
  @{ field = "schema_version"; value = "1" }
)) {
  $altered = Copy-Document $grant
  $altered.($change.field) = $change.value
  Assert-Result (-not (Test-CamsContinuityResponse (New-Response $altered) $releaseResponse $latest -Now $script:fixtureNow)) "grant rejects changed $($change.field)"
}
$altered = Copy-Document $grant
$altered.catalog.sha256 = "d" * 64
Assert-Result (-not (Test-CamsContinuityResponse (New-Response $altered) $releaseResponse $latest -Now $script:fixtureNow)) "grant rejects another catalog"
$altered = Copy-Document $grant
$altered | Add-Member -NotePropertyName extra -NotePropertyValue $true
Assert-Result (-not (Test-CamsContinuityResponse (New-Response $altered) $releaseResponse $latest -Now $script:fixtureNow)) "grant rejects extra fields"
foreach ($content in @(($grantResponse.Content + " "), ($grantResponse.Content + (" " * 4096)), '{"schema_version":1,"schema_version":1}')) {
  $badResponse = [pscustomobject]@{ StatusCode = 200; Content = $content }
  Assert-Result (-not (Test-CamsContinuityResponse $badResponse $releaseResponse $latest -Now $script:fixtureNow)) "noncanonical, oversized or duplicate-key grant is rejected"
}
$revoked = Copy-Document $latest
$revoked.disabled_run_ids = @($runId)
$script:requests.Clear()
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $revoked -RequireCurrent)) "revoked family cannot use a valid continuity grant"
Assert-Result ($script:requests.Count -eq 0) "revocation is checked before reading family artifacts"
$corruptRelease = [pscustomobject]@{ StatusCode = 200; Content = $releaseResponse.Content + " " }
Assert-Result (-not (Test-CamsContinuityResponse $grantResponse $corruptRelease $latest -Now $script:fixtureNow)) "grant cannot authorize tampered release bytes"

$script:responses.Remove($grantUrl)
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent)) "missing grant fails closed beyond 30h"
$script:responses[$grantUrl] = [pscustomobject]@{ StatusCode = 503; Content = $grantResponse.Content }
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent)) "HTTP error cannot authorize continuity"
$script:responses[$grantUrl] = [pscustomobject]@{ StatusCode = 200; Content = $grantResponse.Content.Replace("cams_continuity_36h_v1", "cams_continuity_48h_v1") }
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent)) "invalid grant fails closed through the artifact verifier"
$script:responses.Remove($grantUrl)
Assert-Result (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest) "offline artifact validation does not request continuity"
$script:fixtureNow = $run.AddHours(30)
$script:requests.Clear()
Assert-Result (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent) "legacy 30h contract still works without a grant"
Assert-Result (-not $script:requests.Contains($grantUrl)) "legacy window does not depend on the optional grant"
$script:responses[$grantUrl] = $grantResponse
$script:fixtureNow = $run.AddHours(36).AddSeconds(1)
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent)) "expired 36h grant cannot start the cloud pilot"
$script:fixtureNow = $run.AddHours(31)
$coreUrl = "$base/$($components.core.manifest_key)"
$script:responses[$coreUrl] = [pscustomobject]@{ StatusCode = 200; Content = $script:responses[$coreUrl].Content + " " }
Assert-Result (-not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $latest -RequireCurrent)) "continuity does not bypass component manifest integrity"
Write-Output "PASS: $script:assertions CAMS continuity assertions; no services started or network used"
