Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NativeBytesSha256 {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)).ToLowerInvariant()
}

function Assert-NativeConfigurationBytes {
    param([byte[]]$Bytes)
    try {
        $config = [Text.UTF8Encoding]::new($false, $true).GetString($Bytes) |
            ConvertFrom-Json -AsHashtable -Depth 64 -NoEnumerate
    } catch { throw "release_android_native_config_invalid_json" }
    if ($config -isnot [System.Collections.IDictionary] -or
        $config['appId'] -cne 'com.meteofriul.app' -or $config['webDir'] -cne 'dist') {
        throw "release_android_native_config_identity_invalid"
    }
    $server = $config['server']
    $android = $config['android']
    $plugins = $config['plugins']
    if ($server -isnot [System.Collections.IDictionary] -or
        $server.Contains('url') -or $server['hostname'] -cne 'localhost' -or
        $server['androidScheme'] -cne 'https' -or
        $android -isnot [System.Collections.IDictionary] -or
        $android['webContentsDebuggingEnabled'] -isnot [bool] -or
        $android['webContentsDebuggingEnabled'] -or
        $android['allowMixedContent'] -isnot [bool] -or $android['allowMixedContent']) {
        throw "release_android_native_config_runtime_invalid"
    }
    if ($android.Contains('buildOptions') -or
        ($config['ios'] -is [System.Collections.IDictionary] -and ($config['ios']).Contains('buildOptions'))) {
        # Capacitor strips buildOptions before packaging. Refuse to copy signing data.
        throw "release_android_native_config_build_options_forbidden"
    }
    if ($plugins -isnot [System.Collections.IDictionary] -or
        $plugins['SystemBars'] -isnot [System.Collections.IDictionary] -or
        $plugins['SystemBars']['style'] -cne 'DARK' -or
        $plugins['SystemBars']['insetsHandling'] -cne 'disable') {
        throw "release_android_native_config_system_bars_invalid"
    }
}

function Get-PlayNativeConfiguration {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$SourcePath)
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
        throw "release_android_native_config_source_missing"
    }
    $bytes = [IO.File]::ReadAllBytes($SourcePath)
    Assert-NativeConfigurationBytes -Bytes $bytes
    return [PSCustomObject]@{ Sha256 = Get-NativeBytesSha256 $bytes }
}

function Copy-PlayNativeConfiguration {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SourcePath,
        [Parameter(Mandatory)][string]$AssetsDirectory,
        [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedSha256
    )
    $state = Get-PlayNativeConfiguration -SourcePath $SourcePath
    if ($state.Sha256 -cne $ExpectedSha256) {
        throw "release_android_native_config_source_changed"
    }
    $destination = Join-Path $AssetsDirectory 'capacitor.config.json'
    [IO.Directory]::CreateDirectory($AssetsDirectory) | Out-Null
    [IO.File]::Copy($SourcePath, $destination, $true)
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedSha256) {
        throw "release_android_native_config_copy_mismatch"
    }
}

function Read-NativeBundleEntry {
    param($Archive, [string]$Name, [string]$FailureCode)
    $entries = @($Archive.Entries | Where-Object FullName -CEQ $Name)
    if ($entries.Count -ne 1 -or $entries[0].Length -le 0 -or $entries[0].Length -gt 1048576) {
        throw $FailureCode
    }
    $stream = $entries[0].Open()
    $buffer = [IO.MemoryStream]::new()
    try {
        $stream.CopyTo($buffer)
        return ,$buffer.ToArray()
    } finally { $stream.Dispose(); $buffer.Dispose() }
}

function Assert-PlayNativeConfigurationBundle {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$BundlePath,
        [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedConfigSha256,
        [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedPluginsSha256,
        [Parameter(Mandatory)][AllowEmptyString()][string]$CordovaResourceDump
    )
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($BundlePath)
    try {
        $configBytes = Read-NativeBundleEntry $archive 'base/assets/capacitor.config.json' `
            'release_android_native_config_bundle_entry_invalid'
        Assert-NativeConfigurationBytes -Bytes $configBytes
        $configHash = Get-NativeBytesSha256 $configBytes
        if ($configHash -cne $ExpectedConfigSha256) {
            throw "release_android_native_config_bundle_mismatch"
        }
        $pluginBytes = Read-NativeBundleEntry $archive 'base/assets/capacitor.plugins.json' `
            'release_android_native_plugins_bundle_entry_invalid'
        try {
            $registry = [Text.Encoding]::UTF8.GetString($pluginBytes) |
                ConvertFrom-Json -AsHashtable -NoEnumerate
        } catch { throw "release_android_native_plugins_invalid_json" }
        if ($registry -isnot [array] -or $registry.Count -eq 0) {
            throw "release_android_native_plugins_invalid_registry"
        }
        foreach ($plugin in $registry) {
            if ($plugin -isnot [System.Collections.IDictionary] -or
                [string]::IsNullOrWhiteSpace($plugin['pkg']) -or
                [string]::IsNullOrWhiteSpace($plugin['classpath'])) {
                throw "release_android_native_plugins_invalid_registry"
            }
        }
        $pluginsHash = Get-NativeBytesSha256 $pluginBytes
        if ($pluginsHash -cne $ExpectedPluginsSha256) {
            throw "release_android_native_plugins_bundle_mismatch"
        }

        # The dump is restricted by bundletool to com.meteofriul.app:xml/config.
        # Require both the resource name used by Cordova and its actual default file;
        # a similarly named ZIP entry alone cannot prove getIdentifier() will work.
        $resourceNames = [regex]::Matches($CordovaResourceDump, '(?m)^0x[0-9a-fA-F]+ - xml/config\r?$')
        $files = [regex]::Matches($CordovaResourceDump, '(?m)^\s*\(default\) - \[FILE\] (res/[^\s]+)\r?$')
        if ($resourceNames.Count -ne 1 -or $files.Count -ne 1 -or
            $files[0].Groups[1].Value.Contains('..')) {
            throw "release_android_cordova_config_resource_missing"
        }
        $cordovaEntry = 'base/' + $files[0].Groups[1].Value
        $null = Read-NativeBundleEntry $archive $cordovaEntry `
            'release_android_cordova_config_bundle_entry_invalid'
        return [PSCustomObject]@{
            Verification = 'native-config-hashes-and-cordova-resource'
            ConfigSha256 = $configHash
            PluginsSha256 = $pluginsHash
            CordovaResource = 'com.meteofriul.app:xml/config'
            CordovaBundleEntry = $cordovaEntry
        }
    } finally { $archive.Dispose() }
}

Export-ModuleMember -Function Get-PlayNativeConfiguration, Copy-PlayNativeConfiguration, Assert-PlayNativeConfigurationBundle
