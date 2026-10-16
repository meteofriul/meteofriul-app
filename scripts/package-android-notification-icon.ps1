[CmdletBinding()]
param([switch]$CheckOnly)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$repo = Split-Path -Parent $PSScriptRoot
$package = Join-Path $repo 'android/launcher-assets/notification-092026-r3'
$inventoryPath = Join-Path $package 'inventario.csv'
$masterRelative = 'source\notification-cloud-tower-mask-r3.png'
$masterPath = Join-Path $package $masterRelative
$manifestPath = Join-Path $repo 'frontend/android/app/src/main/AndroidManifest.xml'
$runtimeRoots = @(
    (Join-Path $repo 'frontend/android/app/src/main/res'),
    (Join-Path $repo 'frontend/android/app/src/localPilot/res')
)
$expectedMasterHash = 'E64D61BCA0782041E80B19722346C934E41CCB64FEA9411B76B58824E5FE2BB3'
$expectedInventoryHash = 'DC30BC4C3C75A724FAA13299BF68143DC3A4D7B1833232BDB1D5F2F8E18F3623'
$specs = @{
    'drawable-mdpi' = [pscustomobject]@{ Canvas = 24; Width = 22; Height = 18 }
    'drawable-hdpi' = [pscustomobject]@{ Canvas = 36; Width = 32; Height = 26 }
    'drawable-xhdpi' = [pscustomobject]@{ Canvas = 48; Width = 42; Height = 34 }
    'drawable-xxhdpi' = [pscustomobject]@{ Canvas = 72; Width = 62; Height = 50 }
    'drawable-xxxhdpi' = [pscustomobject]@{ Canvas = 96; Width = 82; Height = 66 }
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Resolve-ContainedPath([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw 'notification_icon_unsafe_path'
    }
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $resolved = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $resolved.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'notification_icon_path_escape'
    }
    return $resolved
}

function Assert-AssetGeometry([string]$Path, [object]$Spec) {
    $bitmap = [Drawing.Bitmap]::new($Path)
    try {
        if ($bitmap.Width -ne $Spec.Canvas -or $bitmap.Height -ne $Spec.Canvas) {
            throw "notification_icon_canvas_mismatch: $Path"
        }
        $minX = $bitmap.Width
        $minY = $bitmap.Height
        $maxX = -1
        $maxY = -1
        for ($y = 0; $y -lt $bitmap.Height; $y += 1) {
            for ($x = 0; $x -lt $bitmap.Width; $x += 1) {
                $pixel = $bitmap.GetPixel($x, $y)
                if ($pixel.A -eq 0) { continue }
                if ($pixel.R -ne 255 -or $pixel.G -ne 255 -or $pixel.B -ne 255) {
                    throw "notification_icon_not_monochrome_white: $Path"
                }
                $minX = [Math]::Min($minX, $x)
                $minY = [Math]::Min($minY, $y)
                $maxX = [Math]::Max($maxX, $x)
                $maxY = [Math]::Max($maxY, $y)
            }
        }
        if ($maxX -lt 0 -or $maxY -lt 0) {
            throw "notification_icon_empty: $Path"
        }
        $visibleWidth = $maxX - $minX + 1
        $visibleHeight = $maxY - $minY + 1
        if ($visibleWidth -ne $Spec.Width -or $visibleHeight -ne $Spec.Height) {
            throw "notification_icon_visible_bounds_mismatch: $Path"
        }
        if ([Math]::Abs(($minX + $maxX) - ($Spec.Canvas - 1)) -gt 1 -or
            [Math]::Abs(($minY + $maxY) - ($Spec.Canvas - 1)) -gt 1) {
            throw "notification_icon_not_centered: $Path"
        }
    } finally {
        $bitmap.Dispose()
    }
}

if ((Get-Sha256 $masterPath) -cne $expectedMasterHash) {
    throw 'notification_icon_master_changed'
}
if ((Get-Sha256 $inventoryPath) -cne $expectedInventoryHash) {
    throw 'notification_icon_inventory_changed'
}

$records = @(Import-Csv -LiteralPath $inventoryPath)
if ($records.Count -ne $specs.Count) {
    throw 'notification_icon_inventory_count_mismatch'
}
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($record in $records) {
    $relative = ([string]$record.File).Replace('/', '\')
    if (-not $seen.Add($relative)) {
        throw "notification_icon_duplicate_inventory_path: $relative"
    }
    if ($relative -cnotmatch '^android\\res\\(drawable-(?:mdpi|hdpi|xhdpi|xxhdpi|xxxhdpi))\\ic_stat_meteofriul\.png$') {
        throw "notification_icon_unexpected_path: $relative"
    }
    $density = $Matches[1]
    if (-not $specs.ContainsKey($density)) {
        throw "notification_icon_unexpected_density: $density"
    }
    $source = Resolve-ContainedPath $package $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "notification_icon_asset_missing: $relative"
    }
    if ((Get-Item -LiteralPath $source).Length -ne [long]$record.Bytes) {
        throw "notification_icon_byte_count_mismatch: $relative"
    }
    $hash = Get-Sha256 $source
    if ($hash -cne ([string]$record.SHA256).ToUpperInvariant()) {
        throw "notification_icon_hash_mismatch: $relative"
    }
    Assert-AssetGeometry $source $specs[$density]

    $runtimeRelative = $relative.Substring('android\res\'.Length)
    foreach ($runtimeRoot in $runtimeRoots) {
        $destination = Resolve-ContainedPath $runtimeRoot $runtimeRelative
        $matches = (Test-Path -LiteralPath $destination -PathType Leaf) -and
            ((Get-Sha256 $destination) -ceq $hash)
        if (-not $CheckOnly -and -not $matches) {
            New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
            Copy-Item -LiteralPath $source -Destination $destination -Force
        }
        if (-not (Test-Path -LiteralPath $destination -PathType Leaf) -or
            (Get-Sha256 $destination) -cne $hash) {
            throw "notification_icon_runtime_mismatch: $destination"
        }
    }
}

$allowedPackageFiles = @('README.md', 'inventario.csv', $masterRelative) + @($records.File)
$packagePrefix = [IO.Path]::GetFullPath($package).TrimEnd('\') + '\'
$actualPackageFiles = @(Get-ChildItem -LiteralPath $package -Recurse -File | ForEach-Object {
    ([IO.Path]::GetFullPath($_.FullName)).Substring($packagePrefix.Length).Replace('/', '\')
})
if ($actualPackageFiles.Count -ne $allowedPackageFiles.Count) {
    throw 'notification_icon_unexpected_package_file_count'
}
foreach ($relative in $actualPackageFiles) {
    if ($relative -cnotin $allowedPackageFiles) {
        throw "notification_icon_uninventoried_file: $relative"
    }
}

$manifest = [IO.File]::ReadAllText($manifestPath)
if (-not $manifest.Contains('android:resource="@drawable/ic_stat_meteofriul"')) {
    throw 'notification_icon_manifest_binding_missing'
}

$mode = if ($CheckOnly) { 'verificate' } else { 'sincronizzate' }
Write-Output "PASS: 5 icone notifica r3 $mode per build pilota e ufficiale."
