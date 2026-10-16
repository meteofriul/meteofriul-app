$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-Contract {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw "FAIL: $Message" }
  Write-Output "PASS: $Message"
}

$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$launcherPath = Join-Path $PSScriptRoot "start-local-weather-pilot.ps1"
$tokens = $null
$parseErrors = $null
$launcherAst = [Management.Automation.Language.Parser]::ParseFile(
  $launcherPath,
  [ref]$tokens,
  [ref]$parseErrors
)
Assert-Contract ($parseErrors.Count -eq 0) "launcher PowerShell parses cleanly"

$parameterNames = @(
  $launcherAst.ParamBlock.Parameters | ForEach-Object { $_.Name.VariablePath.UserPath }
)
Assert-Contract ($parameterNames -contains "WeatherCloud") "launcher exposes explicit -WeatherCloud opt-in"

$main = $launcherAst.Find({
  param($node)
  $node -is [Management.Automation.Language.FunctionDefinitionAst] -and `
    $node.Name -ceq "Invoke-LauncherMain"
}, $true)
Assert-Contract ($null -ne $main) "launcher main function is present"
$mainText = $main.Extent.Text
Assert-Contract (
  $mainText.Contains('if (-not $WeatherCloud -and -not $NationalOnly -and -not $NationalCloud) {') -and `
  $mainText.Contains('Assert-ExistingFile -Label "Payload ICON ufficiale"') -and `
  $mainText.Contains('$ArtifactMetadata = Get-SelectedArtifactMetadata')
) "offline mode retains strict local artifact validation"
Assert-Contract (
  $mainText.Contains('if ($WeatherCloud) {') -and `
  $mainText.Contains('writer e data plane locali non vengono avviati') -and `
  $mainText.Contains('Write-OptionalDataPlaneStatus')
) "cloud mode skips the local writer and data-plane lifecycle"
Assert-Contract (
  $mainText.Contains('VITE_LOCAL_WEATHER_PROXY_TARGET = if ($WeatherCloud -or $NationalCloud)') -and `
  $mainText.Contains('$CloudWeatherPilotBaseUrl') -and `
  $mainText.Contains('"http://127.0.0.1:8781"')
) "frontend proxy selects cloud explicitly while preserving offline default"
Assert-Contract (
  $mainText.Contains('METEO_PILOT_WEATHER_CLOUD = "0"') -and `
  $mainText.Contains('VITE_LOCAL_WEATHER_PILOT_NOW = ""')
) "browser child sanitizes inherited Android-cloud and deterministic-clock flags"
Assert-Contract (
  $mainText.Contains('METEOFRIUL_OPEN_METEO_ENABLED = "0"')
) "pilot backend starts with the authoritative Open-Meteo kill switch disabled"
Assert-Contract (
  $mainText.Contains('Test-CurrentReadOnlyWeatherContract -BaseUrl $CloudWeatherPilotBaseUrl') -and `
  $mainText.Contains('Reader meteo cloud non disponibile, non corrente o non conforme')
) "cloud CheckOnly directly validates the current read-only remote contract"
Assert-Contract (
  $mainText.Contains('foreach ($service in @($Services[2], $Services[3], $Services[1], $Services[0]))')
) "Stop remains mode-independent and considers every owned service"

$launcherText = Get-Content -Raw -LiteralPath $launcherPath
Assert-Contract (
  $parameterNames -contains "StableFrontend" -and `
  $launcherText.Contains('METEO_PILOT_STABLE_FRONTEND = if ($StableFrontend)') -and `
  $launcherText.Contains('-stable-no-hmr-v1') -and `
  $launcherText.Contains('stable-local-weather-pilot.mjs') -and `
  $launcherText.Contains('"--service-identity", "dev:local-pilot"') -and `
  $launcherText.Contains('Remove-VerifiedPilotCleanupPaths -Metadata $stopRecord') -and `
  $launcherText.Contains('$frontendEnvironment["NODE_ENV"] = "development"') -and `
  $launcherText.Contains('$StableFrontend -or $WeatherCloud -or $NationalCloud') -and `
  $launcherText.Contains('content="stable-static-v1"')
) "launcher exposes a profile-bound static browser pilot without HMR"
Assert-Contract (
  $parameterNames -contains "CommunityPilot" -and `
  $launcherText.Contains('$CommunityPilot -and $WeatherCloud') -and `
  $launcherText.Contains('METEO_PILOT_COMMUNITY_LOCAL = if ($CommunityPilot)') -and `
  $launcherText.Contains('meteofriul.community.local-pilot.v1') -and `
  $launcherText.Contains('community-geography.sqlite3')
) "community remains an explicit isolated local opt-in with a verified catalog"
Assert-Contract (
  $parameterNames -contains "RestartCommunity" -and `
  $launcherText.Contains('try { Stop-OwnedService -Service $Community }') -and `
  $launcherText.Contains('finally { $Community.LaunchProfile = $requestedCommunityProfile }') -and `
  $launcherText.Contains('$payload.storage -eq "sqlite"')
) "community uses durable local storage and restarts only its owned process"
Assert-Contract (
  $parameterNames -contains "NationalOnly" -and `
  $mainText.Contains('Test-NationalPilotReady -BaseUrl "http://127.0.0.1:8782"') -and `
  $launcherText.Contains('NationalOnly richiede dati nazionali locali e orologio reale.')
) "national-only mode requires a verified local bundle and a real clock"
Assert-Contract (
  $parameterNames -contains "NationalCloud" -and $parameterNames -contains "CommunityCloudStore" -and `
  $launcherText.Contains('CommunityCloudStore e stato ritirato: usa il servizio Community ufficiale meteo-friul.') -and `
  $launcherText.Contains('METEO_PILOT_NATIONAL_CLOUD = if ($NationalCloud)') -and `
  $mainText.Contains('Test-NationalPilotReady -BaseUrl $CloudNationalPilotBaseUrl -TimeoutSec 30')
) "retired cloud-store preview is rejected while national cloud reads stay official"
Assert-Contract (
  $launcherText.Contains('weather_provider_policy.open_meteo_enabled')
) "pilot readiness rejects a backend that reports Open-Meteo enabled"
Assert-Contract (
  $launcherText.Contains('https://meteofriul-weather-49007668366.europe-west1.run.app') -and `
  $launcherText.Contains('https://meteofriul-national-weather-49007668366.europe-west1.run.app') -and `
  -not $launcherText.Contains('https://pilot-weather-335641913741.europe-west1.run.app') -and `
  -not $launcherText.Contains('https://pilot-national-weather-335641913741.europe-west1.run.app')
) "cloud mode is pinned to the current official read-only origins"
Assert-Contract (
  $launcherText.Contains('weather-cloud-v1') -and `
  $launcherText.Contains('weather-offline-v1') -and `
  $launcherText.Contains('launch_profile')
) "ownership records distinguish cloud and offline frontend profiles"
Assert-Contract (
  $launcherText.Contains('Test-CurrentReadOnlyWeatherContract') -and `
  $launcherText.Contains('-UseBasicParsing -TimeoutSec 30')
) "cloud readiness uses a bounded read-only contract check with cold-start allowance"

$camsArtifactCheck = $launcherAst.Find({
  param($node)
  $node -is [Management.Automation.Language.FunctionDefinitionAst] -and `
    $node.Name -ceq "Test-CamsFamilyArtifacts"
}, $true)
Assert-Contract ($null -ne $camsArtifactCheck) "shared CAMS artifact verifier is present"
$camsArtifactCheckText = $camsArtifactCheck.Extent.Text
Assert-Contract (
  $camsArtifactCheckText.Contains('Test-CamsFamilyReleaseResponse') -and `
  $camsArtifactCheckText.Contains('$core.manifest_key') -and `
  $camsArtifactCheckText.Contains('$pollen.manifest_key') -and `
  $camsArtifactCheckText.Contains('-Provider "cams_europe"') -and `
  $camsArtifactCheckText.Contains('-Provider "cams_europe_pollen"')
) "shared CAMS verifier checks the hashed family release and both component manifests"

$cloudContract = $launcherAst.Find({
  param($node)
  $node -is [Management.Automation.Language.FunctionDefinitionAst] -and `
    $node.Name -ceq "Test-CurrentReadOnlyWeatherContract"
}, $true)
Assert-Contract (
  $null -ne $cloudContract -and `
  $cloudContract.Extent.Text.Contains('Test-CamsFamilyArtifacts') -and `
  $cloudContract.Extent.Text.Contains('-TimeoutSec 30 -RequireCurrent')
) "cloud preflight requires current hash-validated CAMS release and manifests"

$atomicContract = $launcherAst.Find({
  param($node)
  $node -is [Management.Automation.Language.FunctionDefinitionAst] -and `
    $node.Name -ceq "Test-AtomicWeatherContract"
}, $true)
Assert-Contract (
  $null -ne $atomicContract -and `
  $atomicContract.Extent.Text.Contains('Test-CamsFamilyArtifacts')
) "offline and cloud preflights share the same CAMS artifact verifier"

$package = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "frontend\package.json") | ConvertFrom-Json
Assert-Contract (
  [string]$package.scripts.'dev:local-pilot' -match '--mode local-pilot(?:\s|$)' -and `
  [string]$package.scripts.'dev:local-pilot:cloud' -match '--mode local-pilot-cloud(?:\s|$)'
) "Vite process command lines distinguish offline and cloud browser pilots"

$viteGuard = Get-Content -Raw -LiteralPath (
  Join-Path $repoRoot "frontend\scripts\local-weather-pilot-config.mjs"
)
Assert-Contract (
  $viteGuard.Contains('BROWSER_CLOUD_WEATHER_PILOT_MODE = "local-pilot-cloud"') -and `
  $viteGuard.Contains('["local-pilot", BROWSER_CLOUD_WEATHER_PILOT_MODE].includes(mode)') -and `
  -not $viteGuard.Contains('__national-weather-api')
) "Vite guard recognizes the cloud browser mode without exposing an ordinary weather proxy"

$viteConfig = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "frontend\vite.config.js")
Assert-Contract (
  $viteConfig.Contains('const pilotEnvMode = resolveBrowserPilotEnvMode(mode);') -and `
  $viteConfig.Contains('loadEnv(pilotEnvMode, rootDir, "VITE_")') -and `
  $viteConfig.Contains('...sharedPilotClientDefines') -and `
  $viteConfig.IndexOf('...sharedPilotClientDefines') -lt $viteConfig.IndexOf('...pilot.define')
) "cloud browser mode loads shared local-pilot VITE settings with guarded values taking precedence"

# Execute only the parameter/guard prefix: no launcher lifecycle or network.
$guardEnd = $launcherText.IndexOf('$RepoRoot =')
$guardOnly = [scriptblock]::Create($launcherText.Substring(0, $guardEnd))
foreach ($arguments in @(
  @{ CommunityCloudStore = $true },
  @{ NationalCloud = $true; NationalOnly = $true },
  @{ NationalCloud = $true; WeatherCloud = $true },
  @{ NationalCloud = $true; WeatherTestNow = "2026-09-04T05:00:00Z" },
  @{ CommunityPilot = $true; CommunityCloudStore = $true; WeatherTestNow = "2026-09-04T05:00:00Z" }
)) {
  $rejected = $false
  try { & $guardOnly @arguments } catch { $rejected = $true }
  Assert-Contract $rejected "unsafe cloud-preview flag combination rejected before lifecycle work"
}
Write-Output "PASS: start-local-weather-pilot cloud/offline contract complete"

# Exercise the clock guard, without launching processes or changing artifacts.
$clockGuard = $launcherAst.Find({ param($node)
  $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq "Assert-IconClockWindow"
}, $true)
Invoke-Expression $clockGuard.Extent.Text
function Get-PilotClockNow { return $script:camsPolicyTestNow }
$ExpectedIconRunAtUtc = "2026-09-04T00:00:00Z"
$ExpectedIconValidToUtc = "2026-09-07T00:00:00Z"
foreach ($hour in @(24, 33, 36, 61)) {
  $script:camsPolicyTestNow = [datetimeoffset]::Parse($ExpectedIconRunAtUtc).AddHours($hour)
  Assert-IconClockWindow
  Assert-Contract $true "pilot accepts unchanged ICON hourly window at run+$hour h"
}
foreach ($instant in @("2026-09-03T23:59:59Z", "2026-09-06T13:00:01Z")) {
  $script:camsPolicyTestNow = [datetimeoffset]::Parse($instant)
  $rejected = $false
  try { Assert-IconClockWindow } catch { $rejected = $true }
  Assert-Contract $rejected "pilot rejects insufficient/future ICON at $instant"
}
