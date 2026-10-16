[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot
$package = Join-Path $repo 'android/launcher-assets/pilot-test-orange-v1'
$reference = Join-Path $repo 'android/launcher-assets/pilot-092026-launcher-r4'
$runtime = Join-Path $repo 'frontend/android/app/src/localPilot/res'
$web = Join-Path $repo 'frontend/public'
$inventoryPath = Join-Path $package 'inventory.json'
$expectedInventoryHash = '966E01CD89AF238480C785577FDC387A086F1E620454EAF9D7DC504DFC141042'
if ((Get-FileHash (Join-Path $reference 'inventario.csv') -Algorithm SHA256).Hash -cne 'CF3C8EFE8AA8A539EF08A0E09101E0750C1EF6767F795F8727A9D1027DE53AB8') {
    throw 'Approved foreground inventory changed'
}
# Immutable raster layers are reused, without redrawing the approved logo.
# Only localPilot native resources and its versioned Web mark are destinations.
$targets = @()
foreach ($density in @('mdpi','hdpi','xhdpi','xxhdpi','xxxhdpi')) {
    foreach ($name in @('ic_launcher_foreground.png','ic_launcher_monochrome.png')) {
        $relative = "android/res/mipmap-$density/$name"
        $source = Join-Path $reference $relative
        $record = Import-Csv (Join-Path $reference 'inventario.csv') | Where-Object { $_.File.Replace('\','/') -ceq $relative }
        if (-not $record -or (Get-FileHash $source -Algorithm SHA256).Hash -cne $record.SHA256) { throw 'Approved layer changed' }
        if (-not $CheckOnly) {
            New-Item -ItemType Directory -Force (Split-Path -Parent (Join-Path $package $relative)) | Out-Null
            Copy-Item -LiteralPath $source -Destination (Join-Path $package $relative)
        }
        $targets += $relative
    }
}
$xml = '<?xml version="1.0" encoding="utf-8"?>'
$generated = @{
    'android/res/drawable/pilot_launcher_background.xml' = $xml + @'

<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#F4B536" android:pathData="M0,0H108V108H0Z" />
</vector>
'@
    'android/res/values/colors.xml' = $xml + "`n<resources><color name=`"splash_background`">#F4B536</color></resources>`n"
    'android/res/values-night/colors.xml' = $xml + "`n<resources><color name=`"splash_background`">#F4B536</color></resources>`n"
}
foreach ($qualifier in @('v26','v33')) {
    $mono = if ($qualifier -eq 'v33') { '  <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />' } else { '' }
    foreach ($name in @('ic_launcher.xml','ic_launcher_round.xml')) {
        $generated["android/res/mipmap-anydpi-$qualifier/$name"] = $xml + @"

<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@drawable/pilot_launcher_background" />
  <foreground android:drawable="@mipmap/ic_launcher_foreground" />
$mono
</adaptive-icon>
"@
    }
}
$foreground = Join-Path $reference 'android/res/mipmap-xxxhdpi/ic_launcher_foreground.png'
$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($foreground))
$generated['web/brand/pilot-test-orange-v1/mark.svg'] = @"
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="192" height="192" viewBox="0 0 192 192"><rect width="192" height="192" rx="38" fill="#F4B536"/><image width="192" height="192" xlink:href="data:image/png;base64,$base64"/></svg>
"@
foreach ($relative in $generated.Keys) {
    if (-not $CheckOnly) {
        $target = Join-Path $package $relative
        New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
        [IO.File]::WriteAllText($target, $generated[$relative], [Text.UTF8Encoding]::new($false))
    }
    $targets += $relative
}
$splash = 'android/res/drawable-nodpi/splash_logo.png'
if (-not $CheckOnly) {
    New-Item -ItemType Directory -Force (Split-Path -Parent (Join-Path $package $splash)) | Out-Null
    Copy-Item -LiteralPath $foreground -Destination (Join-Path $package $splash)
}
$targets += $splash
$records = @($targets | Sort-Object | ForEach-Object {
    $file = Join-Path $package $_
    [ordered]@{path=$_; bytes=(Get-Item -LiteralPath $file).Length; sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash}
})
if (-not $CheckOnly) {
    $inventoryJson = ($records | ConvertTo-Json -Depth 3).Replace("`r`n", "`n")
    [IO.File]::WriteAllText($inventoryPath, $inventoryJson, [Text.UTF8Encoding]::new($false))
}
if ((Get-FileHash $inventoryPath -Algorithm SHA256).Hash -cne $expectedInventoryHash) {
    throw 'Orange TEST inventory must match the pinned version'
}
$inventory = @(Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json)
if ($inventory.Count -ne $records.Count) { throw 'Unexpected orange TEST asset count' }
foreach ($record in $records) {
    $pinned = @($inventory | Where-Object path -CEQ $record.path)
    if ($pinned.Count -ne 1 -or $pinned[0].sha256 -cne $record.sha256 -or $pinned[0].bytes -ne $record.bytes) { throw 'Orange TEST asset differs from inventory' }
    $destination = if ($record.path.StartsWith('android/res/')) { Join-Path $runtime $record.path.Substring(12) } else { Join-Path $web $record.path.Substring(4) }
    if (-not $CheckOnly) {
        New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
        Copy-Item -LiteralPath (Join-Path $package $record.path) -Destination $destination
    }
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -cne $record.sha256) { throw 'Orange TEST runtime asset differs from inventory' }
}
Write-Output "PASS: $($records.Count) orange TEST assets; adaptive colour/monochrome/background, splash and versioned Home/Settings mark. Official/beta/PWA/notification and legacy launcher resources are not targets."
