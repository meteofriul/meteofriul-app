param([switch]$Preview, [switch]$Force, [string[]]$MarketId = @())
$ErrorActionPreference = 'Stop'
$workspacePath = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$backendPath = Join-Path $workspacePath 'backend'
$pythonPath = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'
$archivePath = Join-Path $workspacePath '.dev-logs/markets/archive.sqlite3'
$reportDirectory = Join-Path $workspacePath '.dev-logs/markets/refresh'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Python 3.13 non disponibile.' }
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw 'Archivio Mercati locale non disponibile; nessuna inizializzazione automatica.' }
if ($env:K_SERVICE -or $env:CLOUD_RUN_JOB) { throw 'Questo launcher è riservato all’archivio locale.' }
$created = New-Item -ItemType Directory -Path $reportDirectory -Force
$reportPath = Join-Path $reportDirectory ('refresh-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '.json')
$arguments = @('-m', 'app.markets.refresh_job', '--report', $reportPath)
if (-not $Preview) { $arguments += '--apply' }
if ($Force) { $arguments += '--force' }
foreach ($identifier in $MarketId) { $arguments += @('--market-id', $identifier) }
$previousStorage = $env:MARKETS_STORAGE
$previousPath = $env:MARKETS_SQLITE_PATH
try {
    $env:MARKETS_STORAGE = 'sqlite'
    $env:MARKETS_SQLITE_PATH = $archivePath
    Push-Location -LiteralPath $backendPath
    try { & $pythonPath @arguments; $resultCode = $LASTEXITCODE } finally { Pop-Location }
} finally {
    $env:MARKETS_STORAGE = $previousStorage
    $env:MARKETS_SQLITE_PATH = $previousPath
}
Write-Output ('Rapporto: ' + $reportPath)
exit $resultCode
