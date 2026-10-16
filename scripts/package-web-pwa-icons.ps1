param(
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$version = "mf-r5-20260927"
$splashBackground = "#061A2E"
$source = Join-Path $repoRoot "frontend\android\app\src\main\res\drawable-nodpi\splash_logo.png"
$publicRoot = Join-Path $repoRoot "frontend\public"
$brandingRoot = Join-Path $publicRoot "branding"
$any192 = Join-Path $brandingRoot "icon_launcher_any_${version}-192.png"
$any512 = Join-Path $brandingRoot "icon_launcher_any_${version}-512.png"
$maskable192 = Join-Path $brandingRoot "icon_launcher_maskable_${version}-192.png"
$maskable512 = Join-Path $brandingRoot "icon_launcher_maskable_${version}-512.png"
$appleTouch = Join-Path $publicRoot "apple-touch-icon-${version}.png"
$expectedSourceHash = "9F2C98CA4303E68FCCFCC571E97001728569EACFB81C80FEEF14E0C5672CF5FB"

function Require-File {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Asset PWA mancante: $Path"
    }
}

function Invoke-Magick {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & magick @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ImageMagick non ha completato la generazione degli asset PWA."
    }
}

function Require-Geometry {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][int]$Size,
        [Parameter(Mandatory)][string]$Opaque
    )

    Require-File -Path $Path
    $metadata = (& magick identify -format "%w|%h|%[opaque]" $Path).Trim()
    if ($LASTEXITCODE -ne 0 -or $metadata -ne "${Size}|${Size}|${Opaque}") {
        throw "Geometria PWA non conforme per $Path. Atteso ${Size}x${Size}, opaque=${Opaque}; trovato $metadata."
    }
}

Require-File -Path $source
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToUpperInvariant()
if ($sourceHash -ne $expectedSourceHash) {
    throw "Lo splash Android sorgente non coincide con il riferimento approvato launcher-r4."
}

if (-not $CheckOnly) {
    Copy-Item -LiteralPath $source -Destination $any512 -Force
    Invoke-Magick -Arguments @($source, "-resize", "192x192", $any192)
    Invoke-Magick -Arguments @(
        "-size", "512x512", "canvas:${splashBackground}",
        $source, "-compose", "over", "-composite", $maskable512
    )
    Invoke-Magick -Arguments @($maskable512, "-resize", "192x192", $maskable192)
    Invoke-Magick -Arguments @($maskable512, "-resize", "180x180", $appleTouch)
}

Require-Geometry -Path $any192 -Size 192 -Opaque "False"
Require-Geometry -Path $any512 -Size 512 -Opaque "False"
Require-Geometry -Path $maskable192 -Size 192 -Opaque "True"
Require-Geometry -Path $maskable512 -Size 512 -Opaque "True"
Require-Geometry -Path $appleTouch -Size 180 -Opaque "True"

$any512Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $any512).Hash.ToUpperInvariant()
if ($any512Hash -ne $expectedSourceHash) {
    throw "L'icona PWA any 512 non coincide pixel-per-pixel con lo splash Android approvato."
}

$mode = if ($CheckOnly) { "verificati" } else { "generati e verificati" }
Write-Output "Asset PWA ${version} ${mode}: icona scorciatoia e splash allineati al launcher-r4."
