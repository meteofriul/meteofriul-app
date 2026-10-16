[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Drawing

$repo = Split-Path -Parent $PSScriptRoot
$package = Join-Path $repo 'android/launcher-assets/pilot-092026-launcher-r4'
$foregroundReference = Join-Path $package 'reference/logo1-transparent-20260918.png'
$compositeReference = Join-Path $package 'reference/logo2-composite-20260918.png'
$inventoryPath = Join-Path $package 'inventario.csv'
$foregroundMaster = Join-Path $package 'source/foreground-original-pixels.png'
$monochromeMaster = Join-Path $package 'source/monochrome-cloud-tower-mask.png'
$staticMaster = Join-Path $package 'source/static-original-tile.png'
$splash = Join-Path $package 'android/res/drawable-nodpi/splash_logo.png'
$webMark = Join-Path $package 'webview/public/brand/pilot-r4/meteo-eventi-friul-mark-192.png'
$runtime = Join-Path $repo 'frontend/android/app/src/localPilot/res'
$officialRuntime = Join-Path $repo 'frontend/android/app/src/main/res'
$webRuntime = Join-Path $repo 'frontend/public'
$r3Package = Join-Path $repo 'android/launcher-assets/pilot-092026-launcher-r3'
$preservedPackage = Join-Path $repo 'android/launcher-assets/pilot-092026-text'
$expectedForegroundReferenceHash = '441CA1BA9390FE0BEAFDC84A9395E6DFFE5012C04B5130E0DDE9448A1382E959'
$expectedCompositeReferenceHash = 'DD8EB0A97FF8EC28CED3B579F9EF84010B45D3BDE329A344828F5ED3AE6AE270'
$expectedInventoryHash = 'CF3C8EFE8AA8A539EF08A0E09101E0750C1EF6767F795F8727A9D1027DE53AB8'

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

if ((Get-Sha256 $foregroundReference) -cne $expectedForegroundReferenceHash -or
    (Get-Sha256 $compositeReference) -cne $expectedCompositeReferenceHash) {
    throw 'The user-supplied launcher references changed.'
}
if ($expectedInventoryHash -and (Get-Sha256 $inventoryPath) -cne $expectedInventoryHash) {
    throw 'The launcher-r4 inventory changed.'
}
$inventory = @(Import-Csv -LiteralPath $inventoryPath)
if ($inventory.Count -ne 16) { throw 'Expected 16 launcher-r4 inventory records.' }
foreach ($record in $inventory) {
    $path = Resolve-ContainedPath $package ([string]$record.File)
    if ((Get-Item -LiteralPath $path).Length -ne [long]$record.Bytes -or
        (Get-Sha256 $path) -cne ([string]$record.SHA256).ToUpperInvariant()) {
        throw "Launcher-r4 asset differs from pinned inventory: $($record.File)"
    }
}

if (-not ('PilotLauncherR4Reference' -as [type])) {
    Add-Type -ReferencedAssemblies System.Drawing.Common,System.Drawing.Primitives,System.Private.Windows.GdiPlus,System.Private.Windows.Core,System.Collections -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;

public static class PilotLauncherR4Reference {
    private static void Require(bool condition, string message) {
        if (!condition) throw new Exception(message);
    }

    public static void VerifyMasters(string foregroundReferencePath,
        string compositeReferencePath, string foregroundPath, string monochromePath) {
        using (var reference = new Bitmap(foregroundReferencePath))
        using (var composite = new Bitmap(compositeReferencePath))
        using (var foreground = new Bitmap(foregroundPath))
        using (var monochrome = new Bitmap(monochromePath)) {
            Require(reference.Width == 1254 && reference.Height == 1254,
                "Unexpected transparent reference dimensions");
            Require(composite.Width == 1254 && composite.Height == 1254,
                "Unexpected composite reference dimensions");
            Require(foreground.Width == 1254 && foreground.Height == 1254 &&
                monochrome.Width == 1254 && monochrome.Height == 1254,
                "Unexpected launcher-r4 master dimensions");
            int subject = 0, white = 0;
            for (int y = 0; y < reference.Height; y++) for (int x = 0; x < reference.Width; x++) {
                Color source = reference.GetPixel(x, y);
                Color actual = foreground.GetPixel(x, y);
                if (source.A > 0) {
                    bool neutralWhite = source.R >= 200 && source.G >= 200 && source.B >= 200;
                    Color expectedColor = neutralWhite
                        ? source
                        : Color.FromArgb(source.A,
                            (int)Math.Round(source.R * 0.83),
                            (int)Math.Round(source.G * (46.0 / 56.0)),
                            (int)Math.Round(source.B * (103.0 / 124.0)));
                    Require(expectedColor.ToArgb() == actual.ToArgb(),
                        "Foreground differs from the logo2-matched darker transform");
                } else {
                    Require(actual.A == 0, "Foreground introduced an opaque pixel");
                }
                Color mono = monochrome.GetPixel(x, y);
                bool expectedMono = source.A > 0 && source.R >= 200 && source.G >= 200 && source.B >= 200;
                if (source.A > 0) subject++;
                if (expectedMono) {
                    white++;
                    Require(mono.A == source.A && mono.R == 255 && mono.G == 255 && mono.B == 255,
                        "Monochrome mask changed alpha or color");
                } else {
                    Require(mono.A == 0, "Monochrome mask contains a non-white source pixel");
                }
            }
            Require(subject > 500000 && white > 50000, "Launcher subject extraction is unexpectedly empty");
            Require(reference.GetPixel(0, 0).A == 0 && reference.GetPixel(1253, 1253).A == 0,
                "Transparent reference corners must remain clear");
            Require(composite.GetPixel(0, 0).R < 24 && composite.GetPixel(0, 0).G < 24 &&
                composite.GetPixel(0, 0).B < 24, "Composite reference no longer has its documented black matte");
        }
    }

    public static void VerifyScaled(string masterPath, string targetPath,
        int size, int side, int offsetX, int offsetY) {
        using (var master = new Bitmap(masterPath))
        using (var target = new Bitmap(targetPath))
        using (var expected = new Bitmap(size, size, PixelFormat.Format32bppArgb)) {
            Require(target.Width == size && target.Height == size, "Unexpected scaled launcher dimensions");
            using (var graphics = Graphics.FromImage(expected)) {
                graphics.Clear(Color.Transparent);
                graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
                graphics.DrawImage(master, offsetX, offsetY, side, side);
            }
            int minX = size, minY = size, maxX = -1, maxY = -1;
            double center = (size - 1) / 2.0;
            double safeRadius = size * 33.0 / 108.0;
            for (int y = 0; y < size; y++) for (int x = 0; x < size; x++) {
                Color expectedPixel = expected.GetPixel(x, y);
                Color actualPixel = target.GetPixel(x, y);
                Require(expectedPixel.ToArgb() == actualPixel.ToArgb(),
                    "Scaled launcher differs from canonical master");
                if (actualPixel.A == 0) continue;
                minX = Math.Min(minX, x); minY = Math.Min(minY, y);
                maxX = Math.Max(maxX, x); maxY = Math.Max(maxY, y);
                if (actualPixel.A >= 8 && actualPixel.R >= 200 &&
                    actualPixel.G >= 200 && actualPixel.B >= 200) {
                    double dx = x - center, dy = y - center;
                    Require(dx * dx + dy * dy <= (safeRadius + 0.75) * (safeRadius + 0.75),
                        "Launcher subject escaped the 66dp adaptive safe circle");
                }
            }
            Require(minX >= offsetX && minY >= offsetY &&
                maxX < offsetX + side && maxY < offsetY + side,
                "Launcher subject escaped its adaptive safe square");
        }
    }

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
            queue.Enqueue(x); queue.Enqueue((height - 1) * width + x);
        }
        for (int y = 0; y < height; y++) {
            queue.Enqueue(y * width); queue.Enqueue(y * width + width - 1);
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
        while (queue.Count > 0) {
            int i = queue.Dequeue();
            if (keep[i] || exterior[i]) continue;
            keep[i] = true;
            int x = i % width, y = i / width;
            if (x > 0) queue.Enqueue(i - 1);
            if (x + 1 < width) queue.Enqueue(i + 1);
            if (y > 0) queue.Enqueue(i - width);
            if (y + 1 < height) queue.Enqueue(i + width);
        }
        var tile = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
            if (!keep[y * width + x]) continue;
            Color source = input.GetPixel(x, y);
            tile.SetPixel(x, y, Color.FromArgb(255, source.R, source.G, source.B));
        }
        return tile;
    }

    private static Bitmap ResizeStaticTile(Bitmap source, int size) {
        var target = new Bitmap(size, size, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(target)) {
            graphics.Clear(Color.Transparent);
            graphics.CompositingMode = CompositingMode.SourceCopy;
            graphics.CompositingQuality = CompositingQuality.HighQuality;
            graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
            graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;
            graphics.SmoothingMode = SmoothingMode.HighQuality;
            graphics.DrawImage(source, 0, 0, size, size);
        }
        return target;
    }

    private static void RequirePixelsEqual(Bitmap expected, Bitmap actual, string label) {
        Require(actual.Width == expected.Width && actual.Height == expected.Height,
            "Unexpected " + label + " dimensions");
        for (int y = 0; y < expected.Height; y++) for (int x = 0; x < expected.Width; x++)
            Require(expected.GetPixel(x, y).ToArgb() == actual.GetPixel(x, y).ToArgb(),
                label + " differs from the canonical logo2 composition");
    }

    public static void VerifyStaticMaster(string sourcePath, string staticPath) {
        using (var source = new Bitmap(sourcePath))
        using (var expected = CreateStaticTile(source))
        using (var actual = new Bitmap(staticPath)) {
            RequirePixelsEqual(expected, actual, "static master");
            Require(actual.GetPixel(0, 0).A == 0 &&
                actual.GetPixel(actual.Width - 1, 0).A == 0 &&
                actual.GetPixel(0, actual.Height - 1).A == 0 &&
                actual.GetPixel(actual.Width - 1, actual.Height - 1).A == 0 &&
                actual.GetPixel(actual.Width / 2, 0).A == 255 &&
                actual.GetPixel(0, actual.Height / 2).A == 255 &&
                actual.GetPixel(actual.Width - 1, actual.Height / 2).A == 255 &&
                actual.GetPixel(actual.Width / 2, actual.Height - 1).A == 255 &&
                actual.GetPixel(actual.Width / 2, actual.Height / 2).A == 255,
                "Unexpected logo2 static master alpha geometry");
        }
    }

    public static void VerifyBrandRasters(string staticPath,
        string webPath, string splashPath) {
        using (var staticTile = new Bitmap(staticPath))
        using (var expectedWeb = ResizeStaticTile(staticTile, 192))
        using (var actualWeb = new Bitmap(webPath)) {
            RequirePixelsEqual(expectedWeb, actualWeb, "pilot-r4 WebView mark");
            Require(actualWeb.GetPixel(0, 0).A == 0 &&
                actualWeb.GetPixel(191, 0).A == 0 &&
                actualWeb.GetPixel(0, 191).A == 0 &&
                actualWeb.GetPixel(191, 191).A == 0 &&
                actualWeb.GetPixel(96, 0).A >= 230 &&
                actualWeb.GetPixel(0, 96).A >= 230 &&
                actualWeb.GetPixel(191, 96).A >= 230 &&
                actualWeb.GetPixel(96, 191).A >= 230 &&
                actualWeb.GetPixel(96, 96).A == 255,
                "Unexpected pilot-r4 WebView mark alpha geometry");
            using (var expectedSplashMark = ResizeStaticTile(staticTile, 338))
            using (var expectedSplash = new Bitmap(512, 512, PixelFormat.Format32bppArgb))
            using (var actualSplash = new Bitmap(splashPath)) {
                using (var graphics = Graphics.FromImage(expectedSplash)) {
                    graphics.Clear(Color.Transparent);
                    graphics.CompositingMode = CompositingMode.SourceCopy;
                    graphics.DrawImageUnscaled(expectedSplashMark, 87, 87);
                }
                RequirePixelsEqual(expectedSplash, actualSplash, "pilot-r4 splash");
                Require(actualSplash.GetPixel(87, 87).A == 0 &&
                    actualSplash.GetPixel(424, 87).A == 0 &&
                    actualSplash.GetPixel(87, 424).A == 0 &&
                    actualSplash.GetPixel(424, 424).A == 0 &&
                    actualSplash.GetPixel(256, 87).A >= 230 &&
                    actualSplash.GetPixel(87, 256).A >= 230 &&
                    actualSplash.GetPixel(424, 256).A >= 230 &&
                    actualSplash.GetPixel(256, 424).A >= 230 &&
                    actualSplash.GetPixel(86, 256).A == 0 &&
                    actualSplash.GetPixel(425, 256).A == 0 &&
                    actualSplash.GetPixel(256, 256).A == 255,
                    "Unexpected 338px pilot-r4 splash placement");
            }
        }
    }

    public static void VerifyLegacyLauncher(string staticPath,
        string launcherPath, int size) {
        using (var staticTile = new Bitmap(staticPath))
        using (var expected = ResizeStaticTile(staticTile, size))
        using (var actual = new Bitmap(launcherPath)) {
            RequirePixelsEqual(expected, actual, "official legacy launcher");
        }
    }
}
'@
}

[PilotLauncherR4Reference]::VerifyMasters(
    $foregroundReference,
    $compositeReference,
    $foregroundMaster,
    $monochromeMaster
)
[PilotLauncherR4Reference]::VerifyStaticMaster($compositeReference, $staticMaster)
foreach ($density in @(
    @('mdpi', 108, 69, 19, 20), @('hdpi', 162, 104, 29, 30),
    @('xhdpi', 216, 138, 39, 40), @('xxhdpi', 324, 207, 58, 60),
    @('xxxhdpi', 432, 276, 78, 80)
)) {
    foreach ($name in @('ic_launcher_foreground.png', 'ic_launcher_monochrome.png')) {
        $master = if ($name -eq 'ic_launcher_foreground.png') { $foregroundMaster } else { $monochromeMaster }
        [PilotLauncherR4Reference]::VerifyScaled(
            $master,
            (Join-Path $package "android/res/mipmap-$($density[0])/$name"),
            $density[1], $density[2], $density[3], $density[4]
        )
    }
}
[PilotLauncherR4Reference]::VerifyBrandRasters($staticMaster, $webMark, $splash)
foreach ($density in @(
    @('mdpi', 48), @('hdpi', 72), @('xhdpi', 96),
    @('xxhdpi', 144), @('xxxhdpi', 192)
)) {
    foreach ($name in @('ic_launcher.png', 'ic_launcher_round.png')) {
        [PilotLauncherR4Reference]::VerifyLegacyLauncher(
            $staticMaster,
            (Join-Path $officialRuntime "mipmap-$($density[0])/$name"),
            $density[1]
        )
    }
}

$backgroundRelative = 'android\res\drawable\pilot_launcher_background.xml'
$backgroundPath = Resolve-ContainedPath $package $backgroundRelative
$backgroundText = [IO.File]::ReadAllText($backgroundPath)
foreach ($required in @('#1A92F8', '#097CE7', '#0470DB', '#016CD8')) {
    if (-not $backgroundText.Contains($required)) {
        throw "Launcher-r4 background lost a logo2 palette anchor: $required"
    }
}

foreach ($record in $inventory) {
    $relative = ([string]$record.File).Replace('/', '\')
    if ($relative.StartsWith('android\res\', [StringComparison]::Ordinal) ) {
        foreach ($destinationRoot in @($runtime, $officialRuntime)) {
            $destination = Resolve-ContainedPath $destinationRoot $relative.Substring(12)
            $source = Resolve-ContainedPath $package $relative
            if ((Get-Sha256 $source) -cne (Get-Sha256 $destination)) {
                throw "Stale launcher-r4 runtime copy: $destination"
            }
        }
    } elseif ($relative.StartsWith('webview\public\', [StringComparison]::Ordinal)) {
        $destination = Resolve-ContainedPath $webRuntime $relative.Substring(15)
        $source = Resolve-ContainedPath $package $relative
        if ((Get-Sha256 $source) -cne (Get-Sha256 $destination)) {
            throw "Stale launcher-r4 runtime copy: $destination"
        }
    }
}

foreach ($relative in @(
    'mipmap-anydpi-v26\ic_launcher.xml',
    'mipmap-anydpi-v26\ic_launcher_round.xml',
    'mipmap-anydpi-v33\ic_launcher.xml',
    'mipmap-anydpi-v33\ic_launcher_round.xml'
)) {
    $text = [IO.File]::ReadAllText((Resolve-ContainedPath $officialRuntime $relative))
    if (-not $text.Contains('@drawable/pilot_launcher_background')) {
        throw "Official adaptive launcher still uses the legacy background: $relative"
    }
}

# These launcher surfaces are deliberately outside the launcher-r4 scope and
# must stay byte-identical to r3. The notification icon has its own approved
# r3 package and is verified separately below.
foreach ($relative in @(
    'android\res\mipmap-anydpi-v26\ic_launcher.xml',
    'android\res\mipmap-anydpi-v26\ic_launcher_round.xml',
    'android\res\mipmap-anydpi-v33\ic_launcher.xml',
    'android\res\mipmap-anydpi-v33\ic_launcher_round.xml'
)) {
    $baseline = Resolve-ContainedPath $r3Package $relative
    $destination = Resolve-ContainedPath $runtime $relative.Substring(12)
    if ((Get-Sha256 $baseline) -cne (Get-Sha256 $destination)) {
        throw "Preserved launcher-adjacent runtime asset changed: $destination"
    }
}
$r3WebMark = Join-Path $r3Package 'webview/public/brand/pilot-r3/meteo-eventi-friul-mark-192.png'
$runtimeWebMark = Join-Path $repo 'frontend/public/brand/pilot-r3/meteo-eventi-friul-mark-192.png'
if ((Get-Sha256 $r3WebMark) -cne (Get-Sha256 $runtimeWebMark)) {
    throw 'The preserved pilot-r3 WebView mark changed.'
}

$preservedInventory = @(Import-Csv -LiteralPath (Join-Path $preservedPackage 'inventario.csv') | Where-Object {
    $relative = ([string]$_.File).Replace('/', '\')
    $relative -match '^android\\res\\mipmap-(?:mdpi|hdpi|xhdpi|xxhdpi|xxxhdpi)\\ic_launcher(?:_round)?\.png$'
})
if ($preservedInventory.Count -ne 10) { throw 'Expected 10 preserved legacy launcher assets.' }
foreach ($record in $preservedInventory) {
    $relative = ([string]$record.File).Replace('/', '\')
    $source = Resolve-ContainedPath $preservedPackage $relative
    $destination = Resolve-ContainedPath $runtime $relative.Substring(12)
    if ((Get-Sha256 $source) -cne (Get-Sha256 $destination)) {
        throw "Preserved legacy launcher asset changed: $destination"
    }
}

& (Join-Path $PSScriptRoot 'package-android-notification-icon.ps1') -CheckOnly
& (Join-Path $PSScriptRoot 'generate-android-launcher-assets.ps1') -CheckOnly
Write-Output 'PASS: launcher-r4 uses the darker references across pilot and official adaptive/legacy launchers, native splash and Home/Settings mark; notification r3 is synchronized; PWA is packaged independently; Play and beta assets remain unchanged.'
