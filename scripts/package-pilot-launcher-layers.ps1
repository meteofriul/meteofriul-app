[CmdletBinding()]
param([switch]$CheckOnly, [switch]$TestOrange)

if ($TestOrange) {
    & (Join-Path $PSScriptRoot 'package-pilot-test-orange.ps1') -CheckOnly:$CheckOnly
    return
}

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Drawing

$repo = Split-Path -Parent $PSScriptRoot
$package = Join-Path $repo 'android/launcher-assets/pilot-092026-launcher-r4'
$foregroundReference = Join-Path $package 'reference/logo1-transparent-20260918.png'
$compositeReference = Join-Path $package 'reference/logo2-composite-20260918.png'
$pilotRuntime = Join-Path $repo 'frontend/android/app/src/localPilot/res'
$officialRuntime = Join-Path $repo 'frontend/android/app/src/main/res'
$webRuntime = Join-Path $repo 'frontend/public'
$inventoryPath = Join-Path $package 'inventario.csv'
$expectedForegroundReferenceHash = '441CA1BA9390FE0BEAFDC84A9395E6DFFE5012C04B5130E0DDE9448A1382E959'
$expectedForegroundReferenceBytes = 661163
$expectedCompositeReferenceHash = 'DD8EB0A97FF8EC28CED3B579F9EF84010B45D3BDE329A344828F5ED3AE6AE270'
$expectedCompositeReferenceBytes = 1146529
$expectedInventoryHash = 'CF3C8EFE8AA8A539EF08A0E09101E0750C1EF6767F795F8727A9D1027DE53AB8'
$expectedOutputHashes = @{
    'source\foreground-original-pixels.png' = 'E039B3D746FA2CFAC009EA54FC7F8AD4827CEA53A1AEE3F425C3B4ADC10E5AF6'
    'source\monochrome-cloud-tower-mask.png' = '0E083E728F4435B1BC4E9479A51BEA933644BB040116427362923D8BDB26CB3F'
    'source\static-original-tile.png' = '23191B93F10EF81DDA460B580FBBD8C459ACCA5D3ADC9013C070289E8F49538A'
    'android\res\drawable\pilot_launcher_background.xml' = '05163207D81F1D81CC21E7CB979929F9073CDF6627A174E227D704CCCE87FC36'
    'android\res\drawable-nodpi\splash_logo.png' = '9F2C98CA4303E68FCCFCC571E97001728569EACFB81C80FEEF14E0C5672CF5FB'
    'android\res\mipmap-mdpi\ic_launcher_foreground.png' = 'C07DB2365160E8F46C30C4F3676A3B3C0B787E39A67051E721D8AFBA2C461A91'
    'android\res\mipmap-hdpi\ic_launcher_foreground.png' = '250AC3CB11383E91D52F37C252AD68AA32DF112E1B7F82D09414B8030CE9D3DA'
    'android\res\mipmap-xhdpi\ic_launcher_foreground.png' = 'F3FC6E9E1D628E4F8715E6535000AA70561027AD4D7348446E914C6369B20A7A'
    'android\res\mipmap-xxhdpi\ic_launcher_foreground.png' = '808766F412A8E1343F6DC0376C484216B01AF2255073BFD7146F0FE3587AE13A'
    'android\res\mipmap-xxxhdpi\ic_launcher_foreground.png' = '1F284A51AE6C2D8C3F2CF692C4644205F6C5D6F07844C4EE57DF4D54B31B1E0E'
    'android\res\mipmap-mdpi\ic_launcher_monochrome.png' = '482AEDCE1D762CD66C4E61416E425059E43F7DAE9A14D13F5A3365F86A18716A'
    'android\res\mipmap-hdpi\ic_launcher_monochrome.png' = '577BFBE05E2C45A9A9B4EBDDB6B7149145F7AA01C7489BFE2DB2AB947F7AB48D'
    'android\res\mipmap-xhdpi\ic_launcher_monochrome.png' = '146CFCB9D98B2F2BCB16AFDC1B14A6EB97BC51EF87A7127155E67F627BBF6D6E'
    'android\res\mipmap-xxhdpi\ic_launcher_monochrome.png' = '3DF66A046970F0428D4F32FD009F46C4EBBA0E40BB6324F9187677D5BD942AED'
    'android\res\mipmap-xxxhdpi\ic_launcher_monochrome.png' = '5B96CEA4C756C114626F3956474055A015941D012DC7229735313E8CA2E98883'
    'webview\public\brand\pilot-r4\meteo-eventi-friul-mark-192.png' = '870F372671267AF414944CEB486EA38F7A51FB9D5BD45DA87002C04D203CAAD8'
}

$expectedFiles = @(
    'source\foreground-original-pixels.png',
    'source\monochrome-cloud-tower-mask.png',
    'source\static-original-tile.png',
    'android\res\drawable\pilot_launcher_background.xml',
    'android\res\drawable-nodpi\splash_logo.png',
    'android\res\mipmap-mdpi\ic_launcher_foreground.png',
    'android\res\mipmap-hdpi\ic_launcher_foreground.png',
    'android\res\mipmap-xhdpi\ic_launcher_foreground.png',
    'android\res\mipmap-xxhdpi\ic_launcher_foreground.png',
    'android\res\mipmap-xxxhdpi\ic_launcher_foreground.png',
    'android\res\mipmap-mdpi\ic_launcher_monochrome.png',
    'android\res\mipmap-hdpi\ic_launcher_monochrome.png',
    'android\res\mipmap-xhdpi\ic_launcher_monochrome.png',
    'android\res\mipmap-xxhdpi\ic_launcher_monochrome.png',
    'android\res\mipmap-xxxhdpi\ic_launcher_monochrome.png',
    'webview\public\brand\pilot-r4\meteo-eventi-friul-mark-192.png'
)
$densities = @(
    [pscustomobject]@{ Name = 'mdpi'; Size = 108; Side = 69; OffsetX = 19; OffsetY = 20 },
    [pscustomobject]@{ Name = 'hdpi'; Size = 162; Side = 104; OffsetX = 29; OffsetY = 30 },
    [pscustomobject]@{ Name = 'xhdpi'; Size = 216; Side = 138; OffsetX = 39; OffsetY = 40 },
    [pscustomobject]@{ Name = 'xxhdpi'; Size = 324; Side = 207; OffsetX = 58; OffsetY = 60 },
    [pscustomobject]@{ Name = 'xxxhdpi'; Size = 432; Side = 276; OffsetX = 78; OffsetY = 80 }
)

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Resolve-ContainedPath([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|[\\/])\.\.([\\/]|$)') {
        throw 'Unsafe asset path'
    }
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $resolved = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $resolved.StartsWith($rootPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Asset escaped its allowed root'
    }
    return $resolved
}

foreach ($referenceSpec in @(
    @($foregroundReference, $expectedForegroundReferenceBytes, $expectedForegroundReferenceHash),
    @($compositeReference, $expectedCompositeReferenceBytes, $expectedCompositeReferenceHash)
)) {
    if (-not (Test-Path -LiteralPath $referenceSpec[0] -PathType Leaf)) {
        throw 'A user-supplied pilot launcher reference is missing.'
    }
    if ((Get-Item -LiteralPath $referenceSpec[0]).Length -ne $referenceSpec[1] -or
        (Get-Sha256 $referenceSpec[0]) -cne $referenceSpec[2]) {
        throw 'A user-supplied pilot launcher reference changed.'
    }
    $referenceBitmap = [Drawing.Bitmap]::new($referenceSpec[0])
    try {
        if ($referenceBitmap.Width -ne 1254 -or $referenceBitmap.Height -ne 1254) {
            throw 'Unexpected pilot launcher reference dimensions.'
        }
    } finally { $referenceBitmap.Dispose() }
}

if (-not $CheckOnly) {
    if (-not ('PilotLauncherR4Assets' -as [type])) {
        Add-Type -ReferencedAssemblies System.Drawing.Common,System.Drawing.Primitives,System.Private.Windows.GdiPlus,System.Private.Windows.Core,System.Collections -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;

public static class PilotLauncherR4Assets {

    private static bool IsExteriorCanvas(Color p) {
        int maximum = Math.Max(p.R, Math.Max(p.G, p.B));
        int minimum = Math.Min(p.R, Math.Min(p.G, p.B));
        return maximum <= 24 && maximum - minimum <= 12;
    }

    private static Bitmap CreateStaticTile(Bitmap input) {
        int width = input.Width, height = input.Height;
        var exterior = new bool[width * height];
        var visited = new bool[width * height];
        var queue = new Queue<int>();
        for (int x = 0; x < width; x++) {
            queue.Enqueue(x);
            queue.Enqueue((height - 1) * width + x);
        }
        for (int y = 0; y < height; y++) {
            queue.Enqueue(y * width);
            queue.Enqueue(y * width + width - 1);
        }
        while (queue.Count > 0) {
            int i = queue.Dequeue();
            if (visited[i]) continue;
            visited[i] = true;
            int x = i % width, y = i / width;
            if (!IsExteriorCanvas(input.GetPixel(x, y))) continue;
            exterior[i] = true;
            if (x > 0) queue.Enqueue(i - 1);
            if (x + 1 < width) queue.Enqueue(i + 1);
            if (y > 0) queue.Enqueue(i - width);
            if (y + 1 < height) queue.Enqueue(i + width);
        }

        var keep = new bool[width * height];
        queue.Clear();
        queue.Enqueue((height / 2) * width + width / 2);
        int keptCount = 0;
        while (queue.Count > 0) {
            int i = queue.Dequeue();
            if (keep[i] || exterior[i]) continue;
            keep[i] = true;
            keptCount++;
            int x = i % width, y = i / width;
            if (x > 0) queue.Enqueue(i - 1);
            if (x + 1 < width) queue.Enqueue(i + 1);
            if (y > 0) queue.Enqueue(i - width);
            if (y + 1 < height) queue.Enqueue(i + width);
        }
        if (keptCount == 0)
            throw new Exception("The original static tile was not found");

        var tile = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
            if (!keep[y * width + x]) continue;
            Color source = input.GetPixel(x, y);
            tile.SetPixel(x, y,
                Color.FromArgb(255, source.R, source.G, source.B));
        }
        return tile;
    }

    public static void ExtractStaticTile(string sourcePath, string targetPath) {
        using (var source = new Bitmap(sourcePath))
        using (var tile = CreateStaticTile(source)) {
            if (source.Width != 1254 || source.Height != 1254)
                throw new Exception("Unexpected pilot launcher reference dimensions");
            tile.Save(targetPath, ImageFormat.Png);
        }
    }

    private static Bitmap ResizeStaticTile(Bitmap source, int size) {
        var target = new Bitmap(size, size, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(target)) {
            graphics.Clear(Color.Transparent);
            graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
            graphics.CompositingQuality = System.Drawing.Drawing2D.CompositingQuality.HighQuality;
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
            graphics.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
            graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
            graphics.DrawImage(source, 0, 0, size, size);
        }
        return target;
    }

    public static void ComposeBrandRasters(string staticTilePath,
        string webTarget, string splashTarget) {
        using (var staticTile = new Bitmap(staticTilePath))
        using (var web = ResizeStaticTile(staticTile, 192)) {
            web.Save(webTarget, ImageFormat.Png);
            using (var splashMark = ResizeStaticTile(staticTile, 338))
            using (var splash = new Bitmap(512, 512, PixelFormat.Format32bppArgb)) {
                using (var graphics = Graphics.FromImage(splash)) {
                    graphics.Clear(Color.Transparent);
                    graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
                    graphics.DrawImageUnscaled(splashMark, 87, 87);
                }
                splash.Save(splashTarget, ImageFormat.Png);
            }
        }
    }

    public static void ComposeLegacyLauncher(string staticTilePath,
        string targetPath, int size) {
        using (var staticTile = new Bitmap(staticTilePath))
        using (var launcher = ResizeStaticTile(staticTile, size)) {
            launcher.Save(targetPath, ImageFormat.Png);
        }
    }

    public static void Extract(string source, string foregroundTarget,
        string monochromeTarget) {
        using (var input = new Bitmap(source))
        using (var foreground = new Bitmap(input.Width, input.Height,
            PixelFormat.Format32bppArgb))
        using (var monochrome = new Bitmap(input.Width, input.Height,
            PixelFormat.Format32bppArgb)) {
            if (input.Width != 1254 || input.Height != 1254)
                throw new Exception("Unexpected pilot launcher reference dimensions");
            int kept = 0, neutralWhiteCount = 0;
            for (int y = 0; y < input.Height; y++) for (int x = 0; x < input.Width; x++) {
                Color p = input.GetPixel(x, y);
                if (p.A == 0) continue;
                bool neutralWhite = p.R >= 200 && p.G >= 200 && p.B >= 200;
                Color colored = neutralWhite
                    ? p
                    : Color.FromArgb(p.A,
                        (int)Math.Round(p.R * 0.83),
                        (int)Math.Round(p.G * (46.0 / 56.0)),
                        (int)Math.Round(p.B * (103.0 / 124.0)));
                foreground.SetPixel(x, y, colored);
                kept++;
                if (neutralWhite) {
                    monochrome.SetPixel(x, y, Color.FromArgb(p.A, 255, 255, 255));
                    neutralWhiteCount++;
                }
            }
            if (kept == 0 || neutralWhiteCount == 0)
                throw new Exception("The transparent launcher reference has no usable subject pixels");
            foreground.Save(foregroundTarget, ImageFormat.Png);
            monochrome.Save(monochromeTarget, ImageFormat.Png);
        }
    }
}
'@
    }
    $foregroundMasterPath = Join-Path $package 'source/foreground-original-pixels.png'
    $monochromeMasterPath = Join-Path $package 'source/monochrome-cloud-tower-mask.png'
    $staticMasterPath = Join-Path $package 'source/static-original-tile.png'
    $splashPath = Join-Path $package 'android/res/drawable-nodpi/splash_logo.png'
    $webMarkPath = Join-Path $package 'webview/public/brand/pilot-r4/meteo-eventi-friul-mark-192.png'
    New-Item -ItemType Directory -Force (Split-Path -Parent $foregroundMasterPath) | Out-Null
    New-Item -ItemType Directory -Force (Split-Path -Parent $splashPath) | Out-Null
    New-Item -ItemType Directory -Force (Split-Path -Parent $webMarkPath) | Out-Null
    [PilotLauncherR4Assets]::Extract($foregroundReference, $foregroundMasterPath, $monochromeMasterPath)
    [PilotLauncherR4Assets]::ExtractStaticTile($compositeReference, $staticMasterPath)
    [PilotLauncherR4Assets]::ComposeBrandRasters($staticMasterPath, $webMarkPath, $splashPath)
    $foregroundMaster = [Drawing.Bitmap]::new($foregroundMasterPath)
    $monochromeMaster = [Drawing.Bitmap]::new($monochromeMasterPath)
    try {
        foreach ($density in $densities) {
            foreach ($variant in @(
                [pscustomobject]@{ Name = 'ic_launcher_foreground.png'; Master = $foregroundMaster },
                [pscustomobject]@{ Name = 'ic_launcher_monochrome.png'; Master = $monochromeMaster }
            )) {
                $destination = Join-Path $package "android/res/mipmap-$($density.Name)/$($variant.Name)"
                New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
                $bitmap = [Drawing.Bitmap]::new($density.Size, $density.Size,
                    [Drawing.Imaging.PixelFormat]::Format32bppArgb)
                $graphics = [Drawing.Graphics]::FromImage($bitmap)
                try {
                    $graphics.Clear([Drawing.Color]::Transparent)
                    $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                    $graphics.DrawImage($variant.Master, $density.OffsetX, $density.OffsetY,
                        $density.Side, $density.Side)
                    $bitmap.Save($destination, [Drawing.Imaging.ImageFormat]::Png)
                } finally { $graphics.Dispose(); $bitmap.Dispose() }
            }
        }
    } finally { $foregroundMaster.Dispose(); $monochromeMaster.Dispose() }
    $records = $expectedFiles | ForEach-Object {
        $assetPath = Resolve-ContainedPath $package $_
        [pscustomobject]@{
            File = $_
            Bytes = (Get-Item -LiteralPath $assetPath).Length
            SHA256 = Get-Sha256 $assetPath
        }
    }
    $csv = $records | ConvertTo-Csv -NoTypeInformation
    [IO.File]::WriteAllText(
        $inventoryPath,
        (($csv -join "`n") + "`n"),
        [Text.UTF8Encoding]::new($false)
    )
}

if (-not (Test-Path -LiteralPath $inventoryPath -PathType Leaf)) {
    throw 'Pilot launcher-r4 inventory is missing.'
}
if ($expectedInventoryHash -and (Get-Sha256 $inventoryPath) -cne $expectedInventoryHash) {
    throw 'Pilot launcher-r4 inventory changed.'
}
$inventory = @(Import-Csv -LiteralPath $inventoryPath)
if ($inventory.Count -ne $expectedFiles.Count) {
    throw "Expected $($expectedFiles.Count) launcher-r4 assets."
}
if (@($inventory.File | Sort-Object -Unique).Count -ne $expectedFiles.Count) {
    throw 'Duplicate launcher-r4 inventory paths.'
}
$copies = @()
foreach ($record in $inventory) {
    $relative = ([string]$record.File).Replace('/', '\')
    if ($relative -cnotin $expectedFiles) { throw "Unexpected launcher-r4 asset: $relative" }
    $path = Resolve-ContainedPath $package $relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing launcher-r4 asset: $relative" }
    if ((Get-Item -LiteralPath $path).Length -ne [long]$record.Bytes) { throw "Byte count mismatch: $relative" }
    $actualHash = Get-Sha256 $path
    if ($actualHash -cne ([string]$record.SHA256).ToUpperInvariant()) { throw "Inventory hash mismatch: $relative" }
    if ($expectedOutputHashes.Count -gt 0 -and
        (-not $expectedOutputHashes.ContainsKey($relative) -or $actualHash -cne $expectedOutputHashes[$relative])) {
        throw "Pinned hash mismatch: $relative"
    }
    if ($relative.StartsWith('android\res\', [StringComparison]::Ordinal)) {
        foreach ($runtime in @($pilotRuntime, $officialRuntime)) {
            $copies += [pscustomobject]@{
                Source = $path
                Destination = Resolve-ContainedPath $runtime $relative.Substring(12)
                Hash = $actualHash
            }
        }
    } elseif ($relative.StartsWith('webview\public\', [StringComparison]::Ordinal)) {
        $copies += [pscustomobject]@{
            Source = $path
            Destination = Resolve-ContainedPath $webRuntime $relative.Substring(15)
            Hash = $actualHash
        }
    }
}

$allowedPackageFiles = @('README.md', 'inventario.csv',
    'reference\logo1-transparent-20260918.png',
    'reference\logo2-composite-20260918.png') + $expectedFiles
$packagePrefix = [IO.Path]::GetFullPath($package).TrimEnd('\') + '\'
$actualPackageFiles = @(Get-ChildItem -LiteralPath $package -Recurse -File | ForEach-Object {
    ([IO.Path]::GetFullPath($_.FullName)).Substring($packagePrefix.Length).Replace('/', '\')
})
if ($actualPackageFiles.Count -ne $allowedPackageFiles.Count) { throw 'Unexpected launcher-r4 package file count.' }
foreach ($relative in $actualPackageFiles) {
    if ($relative -cnotin $allowedPackageFiles) { throw "Uninventoried launcher-r4 file: $relative" }
}

foreach ($copy in $copies) {
    $destinationMatches = (Test-Path -LiteralPath $copy.Destination -PathType Leaf) -and
        ((Get-Sha256 $copy.Destination) -ceq $copy.Hash)
    if (-not $CheckOnly -and -not $destinationMatches) {
        New-Item -ItemType Directory -Force (Split-Path -Parent $copy.Destination) | Out-Null
        Copy-Item -LiteralPath $copy.Source -Destination $copy.Destination -Force
    }
    if ((Get-Sha256 $copy.Destination) -cne $copy.Hash) {
        throw "Runtime launcher-r4 mismatch: $($copy.Destination)"
    }
}

$legacyDensities = @(
    [pscustomobject]@{ Name = 'mdpi'; Size = 48 },
    [pscustomobject]@{ Name = 'hdpi'; Size = 72 },
    [pscustomobject]@{ Name = 'xhdpi'; Size = 96 },
    [pscustomobject]@{ Name = 'xxhdpi'; Size = 144 },
    [pscustomobject]@{ Name = 'xxxhdpi'; Size = 192 }
)
if (-not $CheckOnly) {
    foreach ($density in $legacyDensities) {
        foreach ($name in @('ic_launcher.png', 'ic_launcher_round.png')) {
            $destination = Resolve-ContainedPath `
                $officialRuntime "mipmap-$($density.Name)\$name"
            New-Item -ItemType Directory -Force `
                (Split-Path -Parent $destination) | Out-Null
            [PilotLauncherR4Assets]::ComposeLegacyLauncher(
                (Join-Path $package 'source/static-original-tile.png'),
                $destination,
                $density.Size
            )
        }
    }
}
& (Join-Path $PSScriptRoot 'test-pilot-launcher-reference.ps1')
Write-Output 'PASS: 16 launcher-r4 assets verified; pilot and official launchers, native splash and Home/Settings mark synchronized from the darker references; notification r3 verified separately; PWA, Play and beta assets preserved.'
