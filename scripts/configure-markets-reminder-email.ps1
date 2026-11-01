param(
    [string]$SmtpHost = 'smtps.aruba.it',
    [string]$FromAddress = 'info@meteofriul.it',
    [string]$Username = 'info@meteofriul.it',
    [switch]$Configure
)
$ErrorActionPreference = 'Stop'
$workspacePath = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$emailDirectory = Join-Path $workspacePath '.dev-logs/markets/email'
if (-not $Configure) {
    Write-Output 'Anteprima: -Configure chiede la password in questa console, la protegge per questo utente Windows, verifica il solo accesso SMTP e registra il promemoria locale delle 09:00. Nessuna password in chat. Richiede PC acceso e sessione attiva.'
    exit 0
}
if ($SmtpHost -notmatch '^[A-Za-z0-9.-]+$' -or $FromAddress -match '[\r\n]' -or $Username -match '[\r\n]') { throw 'Parametri SMTP non validi.' }
if (Test-Path -LiteralPath (Join-Path $emailDirectory 'credential.xml')) { throw 'Credenziale già presente: preservata. Verificare la configurazione esistente prima di sostituirla.' }
$securePassword = Read-Host 'Password della casella mittente (non viene mostrata)' -AsSecureString
if ($securePassword.Length -eq 0) { throw 'Password non inserita: nessuna configurazione.' }
$credential = New-Object Management.Automation.PSCredential($Username, $securePassword)
$pythonPath = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python313/python.exe'
$keys = @('MARKETS_REMINDER_SMTP_HOST','MARKETS_REMINDER_SMTP_USERNAME','MARKETS_REMINDER_SMTP_PASSWORD','MARKETS_REMINDER_SMTP_FROM')
$previous = @{}
foreach ($key in $keys) { $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    $env:MARKETS_REMINDER_SMTP_HOST = $SmtpHost
    $env:MARKETS_REMINDER_SMTP_USERNAME = $Username
    $env:MARKETS_REMINDER_SMTP_PASSWORD = $credential.GetNetworkCredential().Password
    $env:MARKETS_REMINDER_SMTP_FROM = $FromAddress
    Push-Location -LiteralPath (Join-Path $workspacePath 'backend')
    try { & $pythonPath -m app.markets.email_reminder --check-connection; $connectionCode = $LASTEXITCODE } finally { Pop-Location }
} finally {
    foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
}
if ($connectionCode -ne 0) { throw 'Accesso SMTP non riuscito: nessun file o task creato. Puoi riprovare la configurazione.' }
New-Item -ItemType Directory -Path $emailDirectory -Force | Out-Null
$credential | Export-Clixml -LiteralPath (Join-Path $emailDirectory 'credential.xml')
[pscustomobject]@{host=$SmtpHost;from=$FromAddress;port=465;tls='implicit'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $emailDirectory 'smtp.json') -Encoding UTF8
$securePassword = $null
$credential = $null
& (Join-Path $PSScriptRoot 'install-markets-reminder-task.ps1') -Install
Write-Output 'Accesso SMTP verificato; nessuna email di prova inviata. Il destinatario si modifica nel pannello Mercati.'
