[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBase,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedRevision,

    [Parameter(Mandatory = $true)]
    [string]$ExpectedBackendCommit,

    [string]$GcloudPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$frontendRoot = Join-Path $workspaceRoot "frontend"
$androidRoot = Join-Path $frontendRoot "android"
$androidPublic = [IO.Path]::GetFullPath(
    (Join-Path $androidRoot "app\src\main\assets\public")
)
$guardScript = Join-Path $frontendRoot "scripts\runtime-api-binding.mjs"
$releasePreflightModule = Join-Path $PSScriptRoot "release-api-preflight.psm1"
$releaseHistoryDirectory = Join-Path $workspaceRoot "release-history\android-private-test"
$keystoreProperties = Join-Path $androidRoot "keystore.properties"
$javaHome = "C:\Program Files\Android\Android Studio\jbr"
$androidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"

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

Import-Module $releasePreflightModule -Force
$normalizedApiBase = Get-NormalizedReleaseApiBase $ApiBase
$releaseGitState = Assert-ReleaseGitState -RepositoryRoot $workspaceRoot
$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -GcloudPath $GcloudPath
if (-not (Test-Path -LiteralPath $keystoreProperties -PathType Leaf)) {
    throw "Private-test signing is not configured."
}
if (-not (Test-Path -LiteralPath $javaHome -PathType Container)) {
    throw "Android Studio JBR 21 was not found."
}
if (-not (Test-Path -LiteralPath $androidSdk -PathType Container)) {
    throw "Android SDK was not found."
}
if (
    -not $androidPublic.StartsWith(
        $workspaceRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
) {
    throw "Android asset target escaped the workspace."
}
if (-not (Test-Path -LiteralPath $androidPublic -PathType Container)) {
    throw "Android public asset target is missing."
}
if (-not (Test-Path -LiteralPath $releaseHistoryDirectory -PathType Container)) {
    throw "release_android_history_directory_missing: path=$releaseHistoryDirectory"
}

$buildDirectory = Join-Path $env:TEMP (
    "meteofriul-private-test-" + [Guid]::NewGuid().ToString("N")
)
New-Item -ItemType Directory -Path $buildDirectory | Out-Null

$hadWebApiBase = Test-Path Env:VITE_API_BASE
$previousWebApiBase = $env:VITE_API_BASE
$hadAndroidApiBase = Test-Path Env:VITE_ANDROID_API_BASE
$previousAndroidApiBase = $env:VITE_ANDROID_API_BASE
$previousJavaHome = $env:JAVA_HOME
$previousAndroidHome = $env:ANDROID_HOME
$previousAndroidSdkRoot = $env:ANDROID_SDK_ROOT

try {
    Remove-Item Env:VITE_API_BASE -ErrorAction SilentlyContinue
    $env:VITE_ANDROID_API_BASE = $normalizedApiBase
    $env:JAVA_HOME = $javaHome
    $env:ANDROID_HOME = $androidSdk
    $env:ANDROID_SDK_ROOT = $androidSdk

    Push-Location $frontendRoot
    try {
        & npx vite build --mode android --configLoader native --outDir $buildDirectory --emptyOutDir
        if ($LASTEXITCODE -ne 0) { throw "Android application build failed." }
        & node $guardScript --target android --build-dir $buildDirectory --expected $normalizedApiBase
        if ($LASTEXITCODE -ne 0) { throw "Android runtime API verification failed." }
    }
    finally {
        Pop-Location
    }

    Write-Output "Verified Android asset source: $buildDirectory"
    Write-Output "Verified Android asset target: $androidPublic"
    & robocopy $buildDirectory $androidPublic /MIR /NFL /NDL /NJH /NJS /NP
    $robocopyCode = $LASTEXITCODE
    if ($robocopyCode -gt 7) {
        throw "Android asset synchronization failed with code $robocopyCode."
    }

    Push-Location $androidRoot
    try {
        & .\gradlew.bat assemblePrivateTest "-PMETEO_API_BASE=$normalizedApiBase"
        if ($LASTEXITCODE -ne 0) { throw "Private-test Gradle build failed." }
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
    $env:JAVA_HOME = $previousJavaHome
    $env:ANDROID_HOME = $previousAndroidHome
    $env:ANDROID_SDK_ROOT = $previousAndroidSdkRoot
}

$apk = Join-Path $androidRoot "app\build\outputs\apk\privateTest\app-privateTest.apk"
if (-not (Test-Path -LiteralPath $apk -PathType Leaf)) {
    throw "Private-test APK was not generated."
}

$buildTools = Get-ChildItem -LiteralPath (Join-Path $androidSdk "build-tools") -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1
if (-not $buildTools) { throw "Android build-tools were not found." }
$aapt = Join-Path $buildTools.FullName "aapt.exe"
$apksigner = Join-Path $buildTools.FullName "apksigner.bat"
$badging = (& $aapt dump badging $apk | Select-Object -First 1)
if ($badging -notmatch "package: name='com\.meteofriul\.app' versionCode='(\d+)' versionName='([^']+)'" ) {
    throw "Unable to verify private-test package metadata."
}
$versionCode = [int]$Matches[1]
$versionName = $Matches[2]
$certificateLine = (& $apksigner verify --print-certs $apk |
    Select-String "certificate SHA-256 digest:" |
    Select-Object -First 1).Line
if (-not $certificateLine) { throw "Unable to verify private-test signature." }
$certificateSha256 = ($certificateLine -replace '^.*digest:\s*', '').Trim()

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($apk)
try {
    $entry = $archive.Entries |
        Where-Object { $_.FullName -like "assets/public/assets/main-*.js" } |
        Select-Object -First 1
    if (-not $entry) { throw "Android entry bundle is missing from the APK." }
    $reader = [IO.StreamReader]::new($entry.Open())
    try { $bundleSource = $reader.ReadToEnd() }
    finally { $reader.Dispose() }
    if (-not $bundleSource.Contains($normalizedApiBase)) {
        throw "Verified API base is missing from the packaged Android bundle."
    }

    $nativeApiFound = $false
    foreach ($dexEntry in ($archive.Entries | Where-Object { $_.Name -like "classes*.dex" })) {
        $stream = $dexEntry.Open()
        $memory = [IO.MemoryStream]::new()
        try {
            $stream.CopyTo($memory)
            $text = [Text.Encoding]::UTF8.GetString($memory.ToArray())
            if ($text.Contains($normalizedApiBase)) { $nativeApiFound = $true; break }
        }
        finally {
            $memory.Dispose()
            $stream.Dispose()
        }
    }
    if (-not $nativeApiFound) {
        throw "Verified API base is missing from the native background worker."
    }
}
finally {
    $archive.Dispose()
}

$releaseDirectory = Split-Path -Parent $apk
$existingReleases = @()
foreach ($releaseRecord in (Get-ChildItem -LiteralPath $releaseHistoryDirectory -Filter "*.release.json" -File)) {
    try {
        $record = Get-Content -LiteralPath $releaseRecord.FullName -Raw | ConvertFrom-Json
        $existingReleases += [PSCustomObject]@{
            CertificateSha256 = [string]$record.CertificateSha256
            Path = $releaseRecord.FullName
            VersionCode = $record.VersionCode
            VersionName = [string]$record.VersionName
        }
    } catch {
        throw "release_android_history_record_invalid: path=$($releaseRecord.FullName)"
    }
}
foreach ($existingApk in (Get-ChildItem -LiteralPath $releaseDirectory -Filter "meteofriul-*.apk" -File)) {
    $existingBadging = (& $aapt dump badging $existingApk.FullName | Select-Object -First 1)
    if ($existingBadging -notmatch "package: name='com\.meteofriul\.app' versionCode='(\d+)' versionName='([^']+)'" ) {
        throw "release_android_existing_artifact_invalid: path=$($existingApk.FullName)"
    }
    $existingVersionCode = [int]$Matches[1]
    $existingVersionName = $Matches[2]
    $existingCertificateLine = (& $apksigner verify --print-certs $existingApk.FullName |
        Select-String "certificate SHA-256 digest:" |
        Select-Object -First 1).Line
    if (-not $existingCertificateLine) {
        throw "release_android_existing_artifact_invalid: path=$($existingApk.FullName)"
    }
    $existingCertificateSha256 = ($existingCertificateLine -replace '^.*digest:\s*', '').Trim()
    $existingReleases += [PSCustomObject]@{
        CertificateSha256 = $existingCertificateSha256
        Path = $existingApk.FullName
        VersionCode = $existingVersionCode
        VersionName = $existingVersionName
    }
}

Assert-AndroidReleaseVersionHistory `
    -CandidateVersionCode $versionCode `
    -CandidateVersionName $versionName `
    -ExistingReleases $existingReleases | Out-Null
Assert-AndroidReleaseSigningHistory `
    -CandidateCertificateSha256 $certificateSha256 `
    -ExistingReleases $existingReleases | Out-Null

$releaseApk = Join-Path $releaseDirectory "meteofriul-$versionName.apk"
$releaseManifest = Join-Path $releaseHistoryDirectory "meteofriul-$versionName.release.json"
if (Test-Path -LiteralPath $releaseApk) {
    throw "release_android_artifact_path_exists: path=$releaseApk"
}
if (Test-Path -LiteralPath $releaseManifest) {
    throw "release_android_manifest_path_exists: path=$releaseManifest"
}

$releaseApiState = Invoke-ReleaseApiPreflight `
    -ApiBase $normalizedApiBase `
    -ExpectedRevision $ExpectedRevision `
    -ExpectedBackendCommit $ExpectedBackendCommit `
    -GcloudPath $GcloudPath
$finalGitState = Assert-ReleaseGitState -RepositoryRoot $workspaceRoot
if ($finalGitState.Commit -cne $releaseGitState.Commit) {
    throw "release_git_head_changed_during_build: before=$($releaseGitState.Commit) after=$($finalGitState.Commit)"
}

$apkSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $apk).Hash
Copy-Item -LiteralPath $apk -Destination $releaseApk
$releaseApkSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseApk).Hash
if ($releaseApkSha256 -cne $apkSha256) {
    throw "release_android_artifact_copy_verification_failed: path=$releaseApk"
}

$manifestPayload = [ordered]@{
    SchemaVersion = 1
    CreatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    Target = "android-private-test"
    ApiBase = $normalizedApiBase
    ApiTag = $releaseApiState.ApiTag
    BackendCommit = $releaseApiState.BackendCommit
    CloudRunRevision = $releaseApiState.Revision
    CloudRunImageDigest = $releaseApiState.ImageDigest
    FrontendCommit = $finalGitState.Commit
    ApkFile = [IO.Path]::GetFileName($releaseApk)
    ApkSha256 = $releaseApkSha256
    CertificateSha256 = $certificateSha256
    VersionCode = $versionCode
    VersionName = $versionName
    Status = "built"
}
$manifestPayload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $releaseManifest -Encoding utf8
$writtenManifest = Get-Content -LiteralPath $releaseManifest -Raw | ConvertFrom-Json
if (
    $writtenManifest.ApkSha256 -cne $releaseApkSha256 -or
    $writtenManifest.CloudRunRevision -cne $releaseApiState.Revision -or
    $writtenManifest.FrontendCommit -cne $finalGitState.Commit
) {
    throw "release_android_manifest_verification_failed: path=$releaseManifest"
}

[PSCustomObject]@{
    ApiTag = $releaseApiState.ApiTag
    Apk = $releaseApk
    ApiBase = $normalizedApiBase
    BackendCommit = $releaseApiState.BackendCommit
    CertificateSha256 = $certificateSha256
    CloudRunImageDigest = $releaseApiState.ImageDigest
    CloudRunRevision = $releaseApiState.Revision
    FrontendCommit = $finalGitState.Commit
    Health = $releaseApiState.Health
    ApkSha256 = $releaseApkSha256
    Manifest = $releaseManifest
    NextStep = "Commit and push the release manifest before Firebase distribution."
    VersionCode = $versionCode
    VersionName = $versionName
} | Format-List
