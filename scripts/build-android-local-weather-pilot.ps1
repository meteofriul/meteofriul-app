[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBase,
    [string]$WeatherTestNow,
    [switch]$Minified,
    [switch]$WeatherCloud,
    [switch]$CommunityPilot,
    [switch]$EventsLocal
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ($WeatherCloud -and $WeatherTestNow) { throw "La pilota cloud richiede l'orario reale, senza WeatherTestNow." }
if ($EventsLocal -and (-not $CommunityPilot -or $WeatherCloud)) { throw "EventsLocal richiede CommunityPilot locale." }

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$frontendRoot = Join-Path $workspaceRoot "frontend"
$androidRoot = Join-Path $frontendRoot "android"
$localAssetsRoot = [IO.Path]::GetFullPath(
    (Join-Path $androidRoot "app\src\localPilot\assets")
)
$localPublicRoot = Join-Path $localAssetsRoot "public"
$mainAssetsRoot = [IO.Path]::GetFullPath(
    (Join-Path $androidRoot "app\src\main\assets")
)
$mainPublicRoot = Join-Path $mainAssetsRoot "public"
$guardScript = Join-Path $frontendRoot "scripts\android-local-pilot-guard.mjs"
$capacitorSettingsPath = Join-Path $androidRoot "capacitor.settings.gradle"
$capacitorBuildPath = Join-Path $androidRoot "app\capacitor.build.gradle"
$javaHome = "C:\Program Files\Android\Android Studio\jbr"
$androidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"

function Get-NormalizedTaggedApiBase([string]$Value) {
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

$normalizedApiBase = Get-NormalizedTaggedApiBase $ApiBase
$normalizedWeatherTestNow = ([string]$WeatherTestNow).Trim()
if ($normalizedWeatherTestNow) {
    $parsedWeatherTestNow = [datetimeoffset]::MinValue
    $parsedOk = [datetimeoffset]::TryParseExact(
        $normalizedWeatherTestNow,
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal,
        [ref]$parsedWeatherTestNow
    )
    if (-not $parsedOk -or $parsedWeatherTestNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'") -cne $normalizedWeatherTestNow) {
        throw "WeatherTestNow must use canonical UTC seconds, for example 2026-09-04T05:00:00Z."
    }
}
$workspacePrefix = $workspaceRoot + [IO.Path]::DirectorySeparatorChar
if (-not $localAssetsRoot.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Android local-pilot asset target escaped the workspace."
}
if (-not (Test-Path -LiteralPath $guardScript -PathType Leaf)) {
    throw "Android local-pilot guard is missing."
}
if (-not (Test-Path -LiteralPath $javaHome -PathType Container)) {
    throw "Android Studio JBR 21 was not found."
}
if (-not (Test-Path -LiteralPath $androidSdk -PathType Container)) {
    throw "Android SDK was not found."
}

# Refuse a pilot APK whose launcher diverges from the user-approved image.
# Read-only check: never regenerate assets as a side effect of a build.
& (Join-Path $PSScriptRoot 'package-pilot-launcher-layers.ps1') -CheckOnly

$buildDirectory = [IO.Path]::GetFullPath((Join-Path $env:TEMP (
    "meteofriul-android-local-pilot-" + [Guid]::NewGuid().ToString("N")
)))
$temporaryPrefix = [IO.Path]::GetFullPath($env:TEMP).TrimEnd(
    [IO.Path]::DirectorySeparatorChar
) + [IO.Path]::DirectorySeparatorChar
if (-not $buildDirectory.StartsWith($temporaryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Android local-pilot temporary build directory escaped the OS temporary directory."
}
New-Item -ItemType Directory -Path $buildDirectory | Out-Null

$guardMarker = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
$managedEnvironment = @(
    "VITE_API_BASE",
    "VITE_ANDROID_API_BASE",
    "VITE_LOCAL_WEATHER_PILOT",
    "VITE_LOCAL_WEATHER_PILOT_NOW",
    "VITE_LOCAL_WEATHER_NATIONAL_ENABLED",
    "VITE_LOCAL_WEATHER_NATIONAL_API_BASE",
    "ORG_GRADLE_PROJECT_METEO_LOCAL_PILOT_MINIFIED",
    "METEO_PILOT_WEATHER_CLOUD",
    "METEO_PILOT_COMMUNITY_LOCAL",
    "METEO_PILOT_EVENTS_LOCAL",
    "VITE_LOCAL_COMMUNITY_PILOT_ENABLED",
    "VITE_LOCAL_COMMUNITY_PILOT_API_BASE",
    "METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER",
    "METEO_PLAY_RELEASE_GUARD_MARKER",
    "JAVA_HOME",
    "ANDROID_HOME",
    "ANDROID_SDK_ROOT"
)
$previousEnvironment = @{}
foreach ($name in $managedEnvironment) {
    $existing = Get-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    $previousEnvironment[$name] = if ($null -eq $existing) { $null } else { $existing.Value }
}

try {
    Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue
    Remove-Item Env:VITE_LOCAL_WEATHER_PILOT -ErrorAction SilentlyContinue
    Remove-Item Env:VITE_LOCAL_WEATHER_NATIONAL_ENABLED -ErrorAction SilentlyContinue
    Remove-Item Env:VITE_LOCAL_WEATHER_NATIONAL_API_BASE -ErrorAction SilentlyContinue
    Remove-Item Env:METEO_PLAY_RELEASE_GUARD_MARKER -ErrorAction SilentlyContinue
    $env:VITE_ANDROID_API_BASE = $normalizedApiBase
    $env:ORG_GRADLE_PROJECT_METEO_LOCAL_PILOT_MINIFIED = if ($Minified) { "true" } else { "false" }
    $env:METEO_PILOT_WEATHER_CLOUD = if ($WeatherCloud) { "1" } else { "0" }
    $env:METEO_PILOT_COMMUNITY_LOCAL = if ($CommunityPilot) { "1" } else { "0" }
    $env:METEO_PILOT_EVENTS_LOCAL = if ($EventsLocal) { "1" } else { "0" }
    Remove-Item Env:VITE_LOCAL_COMMUNITY_PILOT_ENABLED -ErrorAction SilentlyContinue
    Remove-Item Env:VITE_LOCAL_COMMUNITY_PILOT_API_BASE -ErrorAction SilentlyContinue
    if ($normalizedWeatherTestNow) {
        $env:VITE_LOCAL_WEATHER_PILOT_NOW = $normalizedWeatherTestNow
    } else {
        Remove-Item Env:VITE_LOCAL_WEATHER_PILOT_NOW -ErrorAction SilentlyContinue
    }
    $env:METEO_ANDROID_LOCAL_PILOT_GUARD_MARKER = $guardMarker
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidSdk
    $env:ANDROID_SDK_ROOT = $androidSdk

    Push-Location $frontendRoot
    try {
        # Prepare only Capacitor's ignored plugin scaffold. The two generated
        # Gradle files are tracked and must remain byte-for-byte identical.
        # Capacitor 8 update falls back to `copy android` when this ignored
        # directory is absent. Create only its plugin scaffold, not Web assets:
        # a clean clone has no ordinary dist, and pilot assets must stay localPilot.
        if (-not (Test-Path -LiteralPath $mainPublicRoot -PathType Container)) {
            New-Item -ItemType Directory -Path $mainPublicRoot -Force | Out-Null
        }
        $settingsHashBefore = (Get-FileHash -LiteralPath $capacitorSettingsPath -Algorithm SHA256).Hash
        $buildHashBefore = (Get-FileHash -LiteralPath $capacitorBuildPath -Algorithm SHA256).Hash
        & npx cap update android
        if ($LASTEXITCODE -ne 0) { throw "Capacitor Android plugin scaffold failed." }
        $settingsHashAfter = (Get-FileHash -LiteralPath $capacitorSettingsPath -Algorithm SHA256).Hash
        $buildHashAfter = (Get-FileHash -LiteralPath $capacitorBuildPath -Algorithm SHA256).Hash
        if ($settingsHashBefore -cne $settingsHashAfter -or $buildHashBefore -cne $buildHashAfter) {
            throw "Capacitor update changed tracked Gradle integration; inspect before building."
        }

        & npx vite build `
            --mode android-local-pilot `
            --configLoader native `
            --outDir $buildDirectory `
            --emptyOutDir
        if ($LASTEXITCODE -ne 0) { throw "Android local-pilot Web build failed." }

        & node $guardScript `
            --build-dir $buildDirectory `
            --expected $normalizedApiBase `
            --frontend-root $frontendRoot `
            --marker $guardMarker
        if ($LASTEXITCODE -ne 0) { throw "Android local-pilot Web guard failed." }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $localPublicRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $localPublicRoot | Out-Null
    }
    & robocopy $buildDirectory $localPublicRoot /MIR /NFL /NDL /NJH /NJS /NP
    $robocopyCode = $LASTEXITCODE
    if ($robocopyCode -gt 7) {
        throw "Android local-pilot asset synchronization failed with code $robocopyCode."
    }

    Push-Location $androidRoot
    try {
        & .\gradlew.bat assembleLocalPilot `
            "-PMETEO_API_BASE=$normalizedApiBase" `
            "-PMETEO_ANDROID_LOCAL_PILOT_GUARD_MARKER=$guardMarker"
        if ($LASTEXITCODE -ne 0) { throw "Android local-pilot Gradle build failed." }
    }
    finally {
        Pop-Location
    }
}
finally {
    foreach ($name in $managedEnvironment) {
        $previous = $previousEnvironment[$name]
        if ($null -eq $previous) {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item -LiteralPath "Env:$name" -Value $previous
        }
    }
    if (
        (Test-Path -LiteralPath $buildDirectory) -and
        $buildDirectory.StartsWith($temporaryPrefix, [StringComparison]::OrdinalIgnoreCase)
    ) {
        Remove-Item -LiteralPath $buildDirectory -Recurse -Force
    }
}

$apk = Join-Path $androidRoot "app\build\outputs\apk\localPilot\app-localPilot.apk"
if (-not (Test-Path -LiteralPath $apk -PathType Leaf)) {
    throw "Android local-pilot APK was not generated."
}

$buildTools = Get-ChildItem -LiteralPath (Join-Path $androidSdk "build-tools") -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1
if (-not $buildTools) { throw "Android build-tools were not found." }
$aapt = Join-Path $buildTools.FullName "aapt.exe"
$badging = (& $aapt dump badging $apk)
$packageLine = $badging | Select-Object -First 1
if ($packageLine -notmatch "package: name='com\.meteofriul\.app\.localpilot'") {
    throw "Android local-pilot package identity is not isolated."
}
$apkDebuggable = [bool]($badging | Select-String -SimpleMatch "application-debuggable")
if ($apkDebuggable -eq $Minified.IsPresent) {
    throw "Android local-pilot APK debug mode differs from the requested optimization mode."
}
if ($Minified) {
    foreach ($artifactName in @('mapping.txt', 'configuration.txt', 'resources.txt')) {
        $artifactPath = Join-Path $androidRoot "app/build/outputs/mapping/localPilot/$artifactName"
        if (-not (Test-Path -LiteralPath $artifactPath) -or (Get-Item -LiteralPath $artifactPath).Length -eq 0) {
            throw "Minified TEST artifact is missing: $artifactName"
        }
    }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($apk)
try {
    $configEntry = $archive.GetEntry("assets/capacitor.config.json")
    if ($null -eq $configEntry) { throw "Packaged local-pilot Capacitor config is missing." }
    $reader = [IO.StreamReader]::new($configEntry.Open())
    try { $packagedConfig = $reader.ReadToEnd() | ConvertFrom-Json }
    finally { $reader.Dispose() }
    if (
        $packagedConfig.appId -cne "com.meteofriul.app.localpilot" -or
        $packagedConfig.loggingBehavior -cne "none" -or
        $packagedConfig.server.hostname -cne "localhost" -or
        $packagedConfig.server.androidScheme -cne "https" -or
        $packagedConfig.android.allowMixedContent -ne $true -or
        $packagedConfig.android.webContentsDebuggingEnabled -ne $true
    ) {
        throw "Packaged local-pilot Capacitor config is invalid."
    }
}
finally {
    $archive.Dispose()
}

$apkSha256 = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash.ToLowerInvariant()
[PSCustomObject]@{
    ApiBase = $normalizedApiBase
    Apk = $apk
    ApkSha256 = $apkSha256
    Minified = $Minified.IsPresent
    Debuggable = $apkDebuggable
    ApplicationId = "com.meteofriul.app.localpilot"
    EventsApiBase = if ($EventsLocal) { "http://127.0.0.1:8784/api (catalogo candidato locale, adb reverse tcp:8784 tcp:8784)" } else { "https://meteofriul-events-49007668366.europe-west1.run.app/api" }
    LocalWeatherApiBase = if ($WeatherCloud) { "https://meteofriul-weather-49007668366.europe-west1.run.app" } else { "http://127.0.0.1:8781" }
    NationalWeatherApiBase = if ($WeatherCloud) { "https://meteofriul-national-weather-49007668366.europe-west1.run.app" } else { "http://127.0.0.1:8782" }
    CommunityApiBase = if ($CommunityPilot) { if ($WeatherCloud) { "https://meteofriul-community-49007668366.europe-west1.run.app/api (servizio ufficiale; le scritture richiedono App Check)" } else { "http://127.0.0.1:8783/api (SQLite locale, adb reverse tcp:8783 tcp:8783)" } } else { $null }
    WeatherTestNow = if ($normalizedWeatherTestNow) { $normalizedWeatherTestNow } else { $null }
    NextStep = if ($WeatherCloud) {
        "Installa solo il package localpilot; il meteo usa HTTPS senza adb reverse."
    } elseif ($EventsLocal) {
        "Per la TEST usa adb reverse delle porte 8781, 8782, 8783 e 8784. Installa solo il package localpilot dopo autorizzazione."
    } elseif ($CommunityPilot) {
        "Collega il telefono, esegui adb reverse tcp:8781 tcp:8781, adb reverse tcp:8782 tcp:8782 e adb reverse tcp:8783 tcp:8783, poi installa questo APK."
    } else {
        "Collega il telefono, esegui adb reverse tcp:8781 tcp:8781 e adb reverse tcp:8782 tcp:8782, poi installa questo APK."
    }
    Published = $false
} | Format-List
