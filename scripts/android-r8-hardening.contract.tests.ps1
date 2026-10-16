[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$gradlePath = Join-Path $workspaceRoot 'frontend\android\app\build.gradle'
$proguardPath = Join-Path $workspaceRoot 'frontend\android\app\proguard-rules.pro'
$buildScriptPath = Join-Path $PSScriptRoot 'build-play-aab.ps1'
$securityModulePath = Join-Path $PSScriptRoot 'play-aab-security.psm1'

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

foreach ($path in @(
    $gradlePath,
    $proguardPath,
    $buildScriptPath,
    $securityModulePath
)) {
    Assert-True (Test-Path -LiteralPath $path -PathType Leaf) `
        "Required R8 contract file missing: $path"
}

$gradle = Get-Content -LiteralPath $gradlePath -Raw
$releaseMatch = [regex]::Match(
    $gradle,
    '(?s)\brelease\s*\{(?<body>.*?)\r?\n\s*\}\s*\r?\n\s*privateTest\s*\{'
)
Assert-True $releaseMatch.Success 'Android release build type could not be isolated.'
$releaseBlock = $releaseMatch.Groups['body'].Value
foreach ($required in @(
    'minifyEnabled true',
    'shrinkResources true',
    "getDefaultProguardFile('proguard-android-optimize.txt')",
    "debugSymbolLevel 'SYMBOL_TABLE'"
)) {
    Assert-True ($releaseBlock.Contains($required)) `
        "Android release R8 contract is missing: $required"
}
Assert-True (-not $releaseBlock.Contains('minifyEnabled false')) `
    'Android release unexpectedly disables R8.'
Assert-True (-not $releaseBlock.Contains("getDefaultProguardFile('proguard-android.txt')")) `
    'Android release uses the non-optimizing default ProGuard configuration.'

$privateTestMatch = [regex]::Match(
    $gradle,
    '(?s)\bprivateTest\s*\{(?<body>.*?)\r?\n\s*\}\s*\r?\n\s*localPilot\s*\{'
)
Assert-True (
    $privateTestMatch.Success -and
    $privateTestMatch.Groups['body'].Value.Contains('initWith release')
) 'Private-test APK must inherit the minified release configuration.'

$proguardLines = @(
    Get-Content -LiteralPath $proguardPath |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and -not $_.StartsWith('#') }
)
$proguard = Get-Content -LiteralPath $proguardPath -Raw
Assert-True ('-keepattributes SourceFile,LineNumberTable' -in $proguardLines) `
    'R8 must preserve source and line metadata for de-obfuscated stack traces.'
Assert-True ('-renamesourcefileattribute SourceFile' -in $proguardLines) `
    'R8 source file naming contract is missing.'
foreach ($required in @(
    '-keepclassmembers,allowobfuscation class com.getcapacitor.PluginHandle {',
    'private com.getcapacitor.annotation.CapacitorPlugin pluginAnnotation;',
    'public com.getcapacitor.annotation.CapacitorPlugin getPluginAnnotation();'
)) {
    Assert-True ($proguard.Contains($required)) `
        "Capacitor runtime permission metadata keep contract is missing: $required"
}

$prohibitedRules = @(
    '^-keep(?:,\S+)?\s+(?:class|interface|enum)\s+\*\*',
    '^-keep(?:,\S+)?\s+(?:class|interface|enum)\s+com\.google\.firebase\.\*\*',
    '^-keep(?:,\S+)?\s+(?:class|interface|enum)\s+com\.getcapacitor\.\*\*',
    '^-keep(?:,\S+)?\s+(?:class|interface|enum)\s+androidx\.work\.\*\*',
    '^-dontwarn\s+\*\*'
)
foreach ($line in $proguardLines) {
    foreach ($pattern in $prohibitedRules) {
        Assert-True ($line -notmatch $pattern) `
            "Over-broad R8 rule is forbidden: $line"
    }
}

$buildScript = Get-Content -LiteralPath $buildScriptPath -Raw
$securityModule = Get-Content -LiteralPath $securityModulePath -Raw
foreach ($required in @(
    'Assert-PlayR8BundleArtifacts',
    '$archivePaths.Mapping',
    'MappingSha256',
    'BundleMappingEntry',
    'NativeSymbolsStatus'
)) {
    Assert-True ($buildScript.Contains($required)) `
        "Protected Play build does not enforce R8 artifact evidence: $required"
}
foreach ($required in @(
    'function Assert-PlayR8BundleArtifacts',
    'BUNDLE-METADATA/com.android.tools.build.obfuscation/proguard.map',
    'release_android_play_r8_mapping_bundle_mismatch',
    'meteofriul-$VersionCode-$VersionName.mapping.txt'
)) {
    Assert-True ($securityModule.Contains($required)) `
        "Play security module does not enforce R8 artifact evidence: $required"
}

[PSCustomObject]@{
    Configuration = 'PASS'
    MappingArchive = 'PASS'
    NativeSymbolsInventory = 'PASS'
    OverBroadKeepRules = 'ABSENT'
    CapacitorPermissionMetadata = 'PASS'
    StackTraceMetadata = 'PASS'
} | ConvertTo-Json -Compress
