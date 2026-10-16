param(
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$approvedRoot = Join-Path $repoRoot "android\launcher-assets\approved-082026"
$inventoryPath = Join-Path $approvedRoot "inventario-approvati.csv"
$webShortcutRoot = Join-Path $repoRoot "android\launcher-assets\approved-web-shortcut-082026-r2"
$webShortcutInventoryPath = Join-Path $webShortcutRoot "inventario-sha256.csv"
$masterPath = Join-Path $repoRoot "android\launcher-assets\source\launcher-082026-master.png"

$expectedInventoryHash = "7A8101C2B5C6862611B98A69197805BC4DCC071294A94A03839645E6750A3888"
$expectedWebShortcutInventoryHash = "6A26B33AD997EDB1F70076661661F10C85C99FD8A302DB73D913E262C72CA4C9"
$expectedMasterHash = "7D9D72D20D2661F614EC024BB0C3A1DCFE6E1A6AC8D38ABA00069FE84D768E7F"
$expectedArtifactCount = 41
$expectedWebShortcutArtifactCount = 2

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)

    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Assert-FileHash {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ExpectedHash,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label mancante: $Path"
    }

    $actualHash = Get-Sha256 -Path $Path
    if ($actualHash -ne $ExpectedHash.ToUpperInvariant()) {
        throw "$Label non conforme. Atteso $ExpectedHash, trovato $actualHash ($Path)"
    }
}

function Resolve-SafeChildPath {
    param(
        [Parameter(Mandatory)][string]$Root,
        [Parameter(Mandatory)][string]$RelativePath
    )

    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "Percorso assoluto non ammesso nell'inventario: $RelativePath"
    }

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $childFull = [System.IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    if (-not $childFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Percorso fuori dal pacchetto approvato: $RelativePath"
    }

    return $childFull
}

Assert-FileHash -Path $inventoryPath -ExpectedHash $expectedInventoryHash -Label "Inventario approvato"
Assert-FileHash -Path $masterPath -ExpectedHash $expectedMasterHash -Label "Master launcher-082026"

$records = @(Import-Csv -LiteralPath $inventoryPath)
if ($records.Count -ne $expectedArtifactCount) {
    throw "Inventario non conforme: attesi $expectedArtifactCount asset, trovati $($records.Count)."
}

$inventoryPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($record in $records) {
    $relativePath = ([string]$record.File).Replace('/', '\')
    if ([string]::IsNullOrWhiteSpace($relativePath) -or
        [string]::IsNullOrWhiteSpace([string]$record.Bytes) -or
        [string]::IsNullOrWhiteSpace([string]$record.SHA256)) {
        throw "Riga incompleta nell'inventario approvato."
    }
    if (-not $inventoryPaths.Add($relativePath)) {
        throw "Percorso duplicato nell'inventario: $relativePath"
    }

    $sourcePath = Resolve-SafeChildPath -Root $approvedRoot -RelativePath $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Asset approvato mancante: $relativePath"
    }
    $actualBytes = (Get-Item -LiteralPath $sourcePath).Length
    if ($actualBytes -ne [long]$record.Bytes) {
        throw "Dimensione non conforme per $relativePath. Attesi $($record.Bytes) byte, trovati $actualBytes."
    }
    Assert-FileHash -Path $sourcePath -ExpectedHash ([string]$record.SHA256) -Label "Asset approvato"
}

$packageFiles = @(Get-ChildItem -LiteralPath $approvedRoot -Recurse -File)
if ($packageFiles.Count -ne ($expectedArtifactCount + 1)) {
    throw "Pacchetto non conforme: attesi l'inventario e $expectedArtifactCount asset, trovati $($packageFiles.Count) file."
}
foreach ($packageFile in $packageFiles) {
    $approvedPrefix = [System.IO.Path]::GetFullPath($approvedRoot).TrimEnd('\') + '\'
    $packagePath = [System.IO.Path]::GetFullPath($packageFile.FullName)
    if (-not $packagePath.StartsWith($approvedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Asset fuori dal pacchetto approvato: $packagePath"
    }
    $relativePath = $packagePath.Substring($approvedPrefix.Length).Replace('/', '\')
    if ($relativePath.Equals("inventario-approvati.csv", [System.StringComparison]::OrdinalIgnoreCase)) {
        continue
    }
    if (-not $inventoryPaths.Contains($relativePath)) {
        throw "File non inventariato nel pacchetto approvato: $relativePath"
    }
}

Assert-FileHash `
    -Path $webShortcutInventoryPath `
    -ExpectedHash $expectedWebShortcutInventoryHash `
    -Label "Inventario supplemento web r2"

$webShortcutRecords = @(Import-Csv -LiteralPath $webShortcutInventoryPath)
if ($webShortcutRecords.Count -ne $expectedWebShortcutArtifactCount) {
    throw "Supplemento web r2 non conforme: attesi $expectedWebShortcutArtifactCount asset, trovati $($webShortcutRecords.Count)."
}

$webShortcutInventoryPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($record in $webShortcutRecords) {
    $relativePath = ([string]$record.File).Replace('/', '\')
    if ([string]::IsNullOrWhiteSpace($relativePath) -or
        [string]::IsNullOrWhiteSpace([string]$record.Bytes) -or
        [string]::IsNullOrWhiteSpace([string]$record.SHA256)) {
        throw "Riga incompleta nell'inventario del supplemento web r2."
    }
    if (-not $relativePath.StartsWith("web-app\public\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Destinazione non ammessa nel supplemento web r2: $relativePath"
    }
    if (-not $webShortcutInventoryPaths.Add($relativePath)) {
        throw "Percorso duplicato nel supplemento web r2: $relativePath"
    }

    $sourcePath = Resolve-SafeChildPath -Root $webShortcutRoot -RelativePath $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Asset supplemento web r2 mancante: $relativePath"
    }
    $actualBytes = (Get-Item -LiteralPath $sourcePath).Length
    if ($actualBytes -ne [long]$record.Bytes) {
        throw "Dimensione non conforme per $relativePath. Attesi $($record.Bytes) byte, trovati $actualBytes."
    }
    Assert-FileHash -Path $sourcePath -ExpectedHash ([string]$record.SHA256) -Label "Asset supplemento web r2"
}

$webShortcutPackageFiles = @(Get-ChildItem -LiteralPath $webShortcutRoot -Recurse -File)
if ($webShortcutPackageFiles.Count -ne ($expectedWebShortcutArtifactCount + 1)) {
    throw "Supplemento web r2 non conforme: attesi l'inventario e $expectedWebShortcutArtifactCount asset, trovati $($webShortcutPackageFiles.Count) file."
}
foreach ($packageFile in $webShortcutPackageFiles) {
    $packagePrefix = [System.IO.Path]::GetFullPath($webShortcutRoot).TrimEnd('\') + '\'
    $packagePath = [System.IO.Path]::GetFullPath($packageFile.FullName)
    if (-not $packagePath.StartsWith($packagePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Asset fuori dal supplemento web r2: $packagePath"
    }
    $relativePath = $packagePath.Substring($packagePrefix.Length).Replace('/', '\')
    if ($relativePath.Equals("inventario-sha256.csv", [System.StringComparison]::OrdinalIgnoreCase)) {
        continue
    }
    if (-not $webShortcutInventoryPaths.Contains($relativePath)) {
        throw "File non inventariato nel supplemento web r2: $relativePath"
    }
}

Write-Output "Pacchetto launcher-082026 verificato: $expectedArtifactCount asset approvati."
Write-Output "Supplemento web 082026-r2 verificato: $expectedWebShortcutArtifactCount asset approvati."
Write-Output "Archivio 082026 verificato soltanto: nessuna icona con scritte viene copiata nel runtime Web o Android."
Write-Output "Launcher Android ufficiale gestito dal pacchetto launcher-r4; PWA gestita da package-web-pwa-icons.ps1."
Write-Output "L'asset Google Play resta esterno alla build e non viene copiato nel runtime."
