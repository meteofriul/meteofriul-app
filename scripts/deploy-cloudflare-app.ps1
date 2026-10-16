[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBase,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedRevision,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBackendCommit,

    [string]$ExpectedImageDigest,

    [string]$BackendEvidencePath,

    [string]$ProjectName = "meteofriul-app-bcee09e",

    [string]$Branch = "main",

    [string]$GcloudPath,

    [switch]$BuildOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$expectedAccountId = "b74cf20dd75712b35313b69c191c97d5"
$expectedEmail = "meteofriul@gmail.com"
$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$frontendRoot = Join-Path $workspaceRoot "frontend"
$guardScript = Join-Path $frontendRoot "scripts\runtime-api-binding.mjs"
$versionParityGuardScript = Join-Path $frontendRoot "scripts\assert-version-parity.mjs"
$cartoGuardScript = Join-Path $frontendRoot "scripts\carto-basemap-guard.mjs"
$serviceWorkerGuard = Join-Path $frontendRoot "scripts\assert-web-push-service-worker.mjs"
$releasePreflightModule = Join-Path $PSScriptRoot "release-api-preflight.psm1"
Import-Module $releasePreflightModule -Force

function Get-NormalizedReleaseApiBase([string]$Value) {
    $candidate = $Value.Trim()
    $uri = $null
    if (-not [Uri]::TryCreate($candidate, [UriKind]::Absolute, [ref]$uri)) {
        throw "ApiBase must be an absolute HTTPS URL."
    }
    if (
        $uri.Scheme -ne "https" -or
        $uri.UserInfo -or
        $uri.Port -ne 443 -or
        $uri.Query -or
        $uri.Fragment -or
        $uri.AbsolutePath.TrimEnd('/') -ne "/api" -or
        $uri.DnsSafeHost -notmatch '^[a-z0-9-]+---[a-z0-9-]+-[a-z0-9]+\.a\.run\.app$'
    ) {
        throw "ApiBase must be the tagged Cloud Run HTTPS endpoint ending in /api."
    }
    return "https://$($uri.DnsSafeHost)/api"
}

function Get-LocalViteEnvironmentValue([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $pattern = '^\s*' + [Regex]::Escape($Name) + '\s*=\s*(.*)\s*$'
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -notmatch $pattern) { continue }
        $value = $Matches[1].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($value) { return $value }
    }
    return $null
}

function Resolve-TerritoryCartoApiKey {
    $processValue = [Environment]::GetEnvironmentVariable("VITE_TERRITORY_CARTO_API_KEY")
    if ($processValue -and $processValue.Trim()) { return $processValue.Trim() }

    $candidateFiles = @(
        (Join-Path $frontendRoot ".env.cloudflare.local"),
        (Join-Path $frontendRoot ".env.android.local"),
        (Join-Path $frontendRoot ".env.local-pilot.local")
    )
    foreach ($candidateFile in $candidateFiles) {
        $value = Get-LocalViteEnvironmentValue `
            -Path $candidateFile `
            -Name "VITE_TERRITORY_CARTO_API_KEY"
        if ($value) { return $value }
    }
    throw "VITE_TERRITORY_CARTO_API_KEY is required for the Cloudflare release."
}

$normalizedApiBase = Get-NormalizedReleaseApiBase $ApiBase
& node $versionParityGuardScript
if ($LASTEXITCODE -ne 0) { throw "Frontend and Android versions do not match." }
$shortCommit = (& git -C $workspaceRoot rev-parse --short=7 HEAD).Trim()
if (-not $shortCommit) {
    throw "Unable to resolve the current Git commit."
}

$releaseGitState = $null
if (-not $BuildOnly) {
    $releaseGitState = Assert-ReleaseGitState -RepositoryRoot $workspaceRoot
}

$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -ExpectedImageDigest $ExpectedImageDigest `
    -BackendEvidencePath $BackendEvidencePath `
    -GcloudPath $GcloudPath
$territoryCartoApiKey = Resolve-TerritoryCartoApiKey

$buildDirectory = Join-Path $env:TEMP (
    "meteofriul-cloudflare-$shortCommit-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Path $buildDirectory | Out-Null

$hadWebApiBase = Test-Path Env:VITE_API_BASE
$previousWebApiBase = $env:VITE_API_BASE
$hadAndroidApiBase = Test-Path Env:VITE_ANDROID_API_BASE
$previousAndroidApiBase = $env:VITE_ANDROID_API_BASE
$hadTerritoryCartoApiKey = Test-Path Env:VITE_TERRITORY_CARTO_API_KEY
$previousTerritoryCartoApiKey = $env:VITE_TERRITORY_CARTO_API_KEY

try {
    $env:VITE_API_BASE = $normalizedApiBase
    $env:VITE_TERRITORY_CARTO_API_KEY = $territoryCartoApiKey
    Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue

    Push-Location $frontendRoot
    try {
        & node $cartoGuardScript --mode cloudflare
        if ($LASTEXITCODE -ne 0) { throw "Cloudflare CARTO basemap configuration is invalid." }

        & npx vite build --mode cloudflare --configLoader native --outDir $buildDirectory --emptyOutDir
        if ($LASTEXITCODE -ne 0) { throw "Cloudflare application build failed." }

        & npx vite build --mode cloudflare --config vite.sw.config.js --configLoader native --outDir $buildDirectory
        if ($LASTEXITCODE -ne 0) { throw "Cloudflare service worker build failed." }

        & node $serviceWorkerGuard $buildDirectory
        if ($LASTEXITCODE -ne 0) { throw "Service worker verification failed." }

        & node $guardScript --target cloudflare --build-dir $buildDirectory --expected $normalizedApiBase
        if ($LASTEXITCODE -ne 0) { throw "Runtime API verification failed." }

        & node $cartoGuardScript --mode cloudflare --build-dir $buildDirectory
        if ($LASTEXITCODE -ne 0) { throw "Cloudflare CARTO basemap bundle verification failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($hadWebApiBase) { $env:VITE_API_BASE = $previousWebApiBase }
    else { Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue }
    if ($hadAndroidApiBase) { $env:VITE_ANDROID_API_BASE = $previousAndroidApiBase }
    else { Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue }
    if ($hadTerritoryCartoApiKey) { $env:VITE_TERRITORY_CARTO_API_KEY = $previousTerritoryCartoApiKey }
    else { Remove-Item Env:VITE_TERRITORY_CARTO_API_KEY -ErrorAction SilentlyContinue }
}

if ($BuildOnly) {
    $releaseApiState = Invoke-ReleaseApiPreflight `
        -ApiBase $normalizedApiBase `
        -ExpectedRevision $ExpectedRevision `
        -ExpectedBackendCommit $ExpectedBackendCommit `
        -ExpectedImageDigest $ExpectedImageDigest `
        -BackendEvidencePath $BackendEvidencePath `
        -GcloudPath $GcloudPath
    [PSCustomObject]@{
        ApiBase = $releaseApiState.ApiBase
        ApiTag = $releaseApiState.ApiTag
        BackendCommit = $releaseApiState.BackendCommit
        BackendCommitBinding = $releaseApiState.BackendCommitBinding
        BackendEvidencePath = $releaseApiState.BackendEvidencePath
        BuildDirectory = $buildDirectory
        CartoBasemap = "verified"
        CloudRunImageDigest = $releaseApiState.ImageDigest
        CloudRunRevision = $releaseApiState.Revision
        FrontendCommit = (& git -C $workspaceRoot rev-parse HEAD).Trim()
        Health = $releaseApiState.Health
        Mode = "build-only"
    } | Format-List
    exit 0
}

$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -ExpectedImageDigest $ExpectedImageDigest `
    -BackendEvidencePath $BackendEvidencePath `
    -GcloudPath $GcloudPath

$whoAmI = (& npx wrangler whoami 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) {
    throw "Wrangler authentication check failed."
}
if (-not $whoAmI.Contains($expectedAccountId) -or -not $whoAmI.Contains($expectedEmail)) {
    throw "Wrangler is not authenticated with the Meteo Friul account."
}

& npx wrangler pages deploy $buildDirectory `
    --project-name $ProjectName `
    --branch $Branch `
    --commit-hash (& git -C $workspaceRoot rev-parse HEAD).Trim() `
    --commit-message "Verified release $shortCommit"
if ($LASTEXITCODE -ne 0) {
    throw "Cloudflare Pages deployment failed."
}

$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -ExpectedImageDigest $ExpectedImageDigest `
    -BackendEvidencePath $BackendEvidencePath `
    -GcloudPath $GcloudPath

[PSCustomObject]@{
    ApiBase = $releaseApiState.ApiBase
    ApiTag = $releaseApiState.ApiTag
    BackendCommit = $releaseApiState.BackendCommit
    BackendCommitBinding = $releaseApiState.BackendCommitBinding
    BackendEvidencePath = $releaseApiState.BackendEvidencePath
    BuildDirectory = $buildDirectory
    CartoBasemap = "verified"
    CloudRunImageDigest = $releaseApiState.ImageDigest
    CloudRunRevision = $releaseApiState.Revision
    FrontendCommit = $releaseGitState.Commit
    Health = $releaseApiState.Health
    Mode = "deployed"
    ProjectName = $ProjectName
} | Format-List
