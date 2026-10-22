[CmdletBinding()]
param([string]$ArchivedBundlePath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'play-native-configuration.psm1') -Force
Add-Type -AssemblyName System.IO.Compression
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'frontend/capacitor.config.json'
$sourceBytes = [IO.File]::ReadAllBytes($source)
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$pluginsBytes = [Text.Encoding]::UTF8.GetBytes('[{"pkg":"@capacitor/app","classpath":"com.capacitorjs.plugins.app.AppPlugin"}]')
$pluginsHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($pluginsBytes)).ToLowerInvariant()
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('meteo-native-config-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($tempRoot) | Out-Null
$count = 0
function Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:count++
}
function Reject([scriptblock]$Action, [string]$Code) {
    try { & $Action | Out-Null } catch {
        if ($_.Exception.Message.Contains($Code)) { $script:count++; return }
        throw "Expected $Code; received $($_.Exception.Message)"
    }
    throw "Expected rejection: $Code"
}
function Zip-Entry([string]$Name, [byte[]]$Bytes) { return @{ Name=$Name; Bytes=$Bytes } }
function Fixture([object[]]$Entries) {
    $path = Join-Path $tempRoot ([guid]::NewGuid().ToString('N') + '.zip')
    $zip = [IO.Compression.ZipFile]::Open($path, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($item in $Entries) {
            $stream = $zip.CreateEntry($item.Name).Open()
            try { $stream.Write($item.Bytes, 0, $item.Bytes.Length) } finally { $stream.Dispose() }
        }
    } finally { $zip.Dispose() }
    return $path
}
$cordovaBytes = [Text.Encoding]::UTF8.GetBytes('compiled-resource-fixture')
$cordovaDump = "0x7f110002 - xml/config`n`t(default) - [FILE] res/xml/config.xml"
$configEntry = Zip-Entry 'base/assets/capacitor.config.json' $sourceBytes
$pluginEntry = Zip-Entry 'base/assets/capacitor.plugins.json' $pluginsBytes
$cordovaEntry = Zip-Entry 'base/res/xml/config.xml' $cordovaBytes
function Verify([string]$Path, [string]$Dump=$cordovaDump) {
    Assert-PlayNativeConfigurationBundle -BundlePath $Path -ExpectedConfigSha256 $sourceHash `
        -ExpectedPluginsSha256 $pluginsHash -CordovaResourceDump $Dump
}
try {
    $state = Get-PlayNativeConfiguration -SourcePath $source
    Check ($state.Sha256 -ceq $sourceHash) 'Approved source hash changed'
    $assets = Join-Path $tempRoot 'assets'
    [IO.Directory]::CreateDirectory((Join-Path $assets 'public')) | Out-Null
    [IO.File]::WriteAllText((Join-Path $assets 'public/index.html'), 'preserve-web')
    [IO.File]::WriteAllText((Join-Path $assets 'capacitor.config.json'), 'stale-config')
    Copy-PlayNativeConfiguration -SourcePath $source -AssetsDirectory $assets -ExpectedSha256 $sourceHash
    Check ((Get-FileHash (Join-Path $assets 'capacitor.config.json')).Hash.ToLowerInvariant() -ceq $sourceHash) 'Copy did not replace stale configuration'
    Check ([IO.File]::ReadAllText((Join-Path $assets 'public/index.html')) -ceq 'preserve-web') 'Configuration copy changed Web assets'
    Reject { Copy-PlayNativeConfiguration -SourcePath $source -AssetsDirectory $assets -ExpectedSha256 ('0' * 64) } 'source_changed'
    Reject { Get-PlayNativeConfiguration -SourcePath (Join-Path $tempRoot 'absent.json') } 'source_missing'
    foreach ($case in @(
        @{Text='{'; Code='invalid_json'},
        @{Text='[]'; Code='identity_invalid'},
        @{Text='{}'; Code='identity_invalid'}
    )) {
        $badSource = Join-Path $tempRoot 'invalid.json'
        [IO.File]::WriteAllText($badSource, $case.Text)
        Reject { Get-PlayNativeConfiguration -SourcePath $badSource } $case.Code
    }
    foreach ($case in @(
        @{Edit={param($c) $c.appId='com.meteofriul.app.localpilot'}; Code='identity_invalid'},
        @{Edit={param($c) $c.server.url='http://localhost:5174'}; Code='runtime_invalid'},
        @{Edit={param($c) $c.android.webContentsDebuggingEnabled=$true}; Code='runtime_invalid'},
        @{Edit={param($c) $c.android.webContentsDebuggingEnabled='false'}; Code='runtime_invalid'},
        @{Edit={param($c) $c.android.allowMixedContent=$true}; Code='runtime_invalid'},
        @{Edit={param($c) $c.Remove('android')}; Code='runtime_invalid'},
        @{Edit={param($c) $c.android.buildOptions=@{}}; Code='build_options_forbidden'},
        @{Edit={param($c) $c.ios=@{buildOptions=@{}}}; Code='build_options_forbidden'},
        @{Edit={param($c) $c.plugins.SystemBars.insetsHandling='css'}; Code='system_bars_invalid'},
        @{Edit={param($c) $c.plugins.Remove('SystemBars')}; Code='system_bars_invalid'}
    )) {
        $candidate = [Text.Encoding]::UTF8.GetString($sourceBytes) | ConvertFrom-Json -AsHashtable
        & $case.Edit $candidate | Out-Null
        [IO.File]::WriteAllText($badSource, ($candidate | ConvertTo-Json -Depth 20))
        Reject { Get-PlayNativeConfiguration -SourcePath $badSource } $case.Code
    }
    $valid = Fixture @($configEntry,$pluginEntry,$cordovaEntry)
    $result = Verify $valid
    Check ($result.ConfigSha256 -ceq $sourceHash -and $result.PluginsSha256 -ceq $pluginsHash) 'Packaged hashes not recorded'
    Check ($result.CordovaBundleEntry -ceq 'base/res/xml/config.xml') 'Cordova resource path not recorded'
    Reject { Verify (Fixture @($pluginEntry,$cordovaEntry)) } 'config_bundle_entry_invalid'
    Reject { Verify (Fixture @($configEntry,$configEntry,$pluginEntry,$cordovaEntry)) } 'config_bundle_entry_invalid'
    Reject { Verify (Fixture @((Zip-Entry 'base/assets/capacitor.config.json' ([byte[]]@())),$pluginEntry,$cordovaEntry)) } 'config_bundle_entry_invalid'
    Reject { Verify (Fixture @((Zip-Entry 'base/assets/capacitor.config.json' ([Text.Encoding]::UTF8.GetBytes('{'))),$pluginEntry,$cordovaEntry)) } 'config_invalid_json'
    $changedConfig = [Text.Encoding]::UTF8.GetBytes(([Text.Encoding]::UTF8.GetString($sourceBytes) -replace 'Meteo Friûl','Changed'))
    Reject { Verify (Fixture @((Zip-Entry 'base/assets/capacitor.config.json' $changedConfig),$pluginEntry,$cordovaEntry)) } 'config_bundle_mismatch'
    Reject { Verify (Fixture @($configEntry,$cordovaEntry)) } 'plugins_bundle_entry_invalid'
    Reject { Verify (Fixture @($configEntry,$pluginEntry,$pluginEntry,$cordovaEntry)) } 'plugins_bundle_entry_invalid'
    Reject { Verify (Fixture @($configEntry,(Zip-Entry 'base/assets/capacitor.plugins.json' ([Text.Encoding]::UTF8.GetBytes('[]'))),$cordovaEntry)) } 'plugins_invalid_registry'
    $changedPlugins = [Text.Encoding]::UTF8.GetBytes('[{"pkg":"other","classpath":"Other"}]')
    Reject { Verify (Fixture @($configEntry,(Zip-Entry 'base/assets/capacitor.plugins.json' $changedPlugins),$cordovaEntry)) } 'plugins_bundle_mismatch'
    Reject { Verify $valid '' } 'cordova_config_resource_missing'
    Reject { Verify $valid ($cordovaDump -replace 'xml/config','xml/other') } 'cordova_config_resource_missing'
    Reject { Verify (Fixture @($configEntry,$pluginEntry)) } 'cordova_config_bundle_entry_invalid'
    $renamed = Fixture @($configEntry,$pluginEntry,(Zip-Entry 'base/res/q.xml' $cordovaBytes))
    $renamedResult = Verify $renamed ($cordovaDump -replace 'res/xml/config.xml','res/q.xml')
    Check ($renamedResult.CordovaBundleEntry -ceq 'base/res/q.xml') 'Physical file rename must retain semantic resource identity'

    # Bind the guard to the actual builder order, before a reservation / artifact acceptance.
    $builder = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'build-play-aab.ps1'))
    Check ($builder.IndexOf('$nativeConfigurationState = Get-PlayNativeConfiguration') -lt $builder.IndexOf('Write-NewPlayJsonFile -Path $reservationPath')) 'Native source preflight must precede reservation'
    Check ($builder.IndexOf('Copy-PlayNativeConfiguration') -gt $builder.IndexOf('& npx cap update android') -and $builder.IndexOf('Copy-PlayNativeConfiguration') -lt $builder.IndexOf('& .\gradlew.bat bundleRelease')) 'Configuration copy must follow update and precede Gradle'
    Check ($builder.IndexOf('$nativeConfigurationArtifacts = Assert-PlayNativeConfigurationBundle') -lt $builder.IndexOf('Copy-NewPlayArtifact -Source $aab')) 'Native bundle guard must precede archival'
    Check ($builder.Contains('--resource=com.meteofriul.app:xml/config')) 'Resource dump must be scoped to the application resource'
    Check ($builder.Contains('NativeConfiguration = $nativeConfigurationArtifacts')) 'Manifest must retain native verification'
    $keepPath = Join-Path $root 'frontend/android/app/src/main/res/raw/com_meteofriul_native_config_keep.xml'
    [xml]$keep = [IO.File]::ReadAllText($keepPath)
    Check ($keep.resources.GetAttribute('keep','http://schemas.android.com/tools') -ceq '@xml/config') 'Keep rule must preserve only the dynamic Cordova config resource'

    $archivedStatus = 'NOT_REQUESTED'
    if ($ArchivedBundlePath) {
        $before = (Get-FileHash -LiteralPath $ArchivedBundlePath -Algorithm SHA256).Hash
        Reject { Verify $ArchivedBundlePath '' } 'config_bundle_entry_invalid'
        Check ((Get-FileHash -LiteralPath $ArchivedBundlePath -Algorithm SHA256).Hash -ceq $before) 'Archived AAB changed during read-only regression'
        $archivedStatus = 'REJECTED_MISSING_NATIVE_CONFIG'
    }
    Check ((Get-FileHash -LiteralPath $source).Hash.ToLowerInvariant() -ceq $sourceHash) 'Approved source was modified'
    [PSCustomObject]@{Status='PASS'; Assertions=$count; ArchivedBundle=$archivedStatus; AndroidBuild='NOT_RUN'; VersionReserved=$false} | ConvertTo-Json -Compress
} finally {
    $resolved = [IO.Path]::GetFullPath($tempRoot)
    $allowed = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolved) -notmatch '^meteo-native-config-[0-9a-f]{32}$') { throw 'Unexpected temporary cleanup target' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
