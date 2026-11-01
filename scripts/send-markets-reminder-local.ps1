param([switch]$CheckConnection)
$ErrorActionPreference = 'Stop'
$workspacePath = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$pythonPath = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'
$archivePath = Join-Path $workspacePath '.dev-logs/markets/archive.sqlite3'
$emailDirectory = Join-Path $workspacePath '.dev-logs/markets/email'
if ($env:K_SERVICE -or $env:CLOUD_RUN_JOB) { throw 'Launcher email riservato al PC locale.' }
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf)) { throw 'Archivio Mercati mancante.' }
$settingsPath = Join-Path $emailDirectory 'smtp.json'
$credentialPath = Join-Path $emailDirectory 'credential.xml'
if (-not (Test-Path -LiteralPath $settingsPath) -or -not (Test-Path -LiteralPath $credentialPath)) { throw 'Collegamento della casella email ancora da configurare.' }
$settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
$credential = Import-Clixml -LiteralPath $credentialPath
if ($credential -isnot [Management.Automation.PSCredential]) { throw 'Credenziale SMTP locale non valida.' }
$keys = @('MARKETS_STORAGE','MARKETS_SQLITE_PATH','MARKETS_REMINDER_SMTP_HOST','MARKETS_REMINDER_SMTP_USERNAME','MARKETS_REMINDER_SMTP_PASSWORD','MARKETS_REMINDER_SMTP_FROM')
$previous = @{}
foreach ($key in $keys) { $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    $env:MARKETS_STORAGE = 'sqlite'
    $env:MARKETS_SQLITE_PATH = $archivePath
    $env:MARKETS_REMINDER_SMTP_HOST = $settings.host
    $env:MARKETS_REMINDER_SMTP_FROM = $settings.from
    $env:MARKETS_REMINDER_SMTP_USERNAME = $credential.UserName
    $env:MARKETS_REMINDER_SMTP_PASSWORD = $credential.GetNetworkCredential().Password
    $arguments = @('-m','app.markets.email_reminder')
    if ($CheckConnection) { $arguments += '--check-connection' }
    Push-Location -LiteralPath (Join-Path $workspacePath 'backend')
    try { & $pythonPath @arguments; $resultCode = $LASTEXITCODE } finally { Pop-Location }
} finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
    $credential = $null
}
exit $resultCode
