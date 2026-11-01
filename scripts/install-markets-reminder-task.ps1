param([switch]$Install)
$ErrorActionPreference = 'Stop'
$workspacePath = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$scriptPath = Join-Path $PSScriptRoot 'send-markets-reminder-local.ps1'
$taskName = 'MeteoFriul-MarketsReminder-Local'
$shellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $scriptPath + '"'
if (-not $Install) { Write-Output 'Anteprima: verifica promemoria alle 09:00 e all’accesso Windows. Una email per periodo mensile ancora da rivedere; solo PC acceso e sessione attiva.'; exit 0 }
$emailDirectory = Join-Path $workspacePath '.dev-logs/markets/email'
foreach ($name in @('smtp.json','credential.xml')) {
    if (-not (Test-Path -LiteralPath (Join-Path $emailDirectory $name))) { throw 'Configurare e verificare prima la casella SMTP.' }
}
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Count -ne 1 -or $existing.Actions[0].Execute -ne $shellPath -or $existing.Actions[0].Arguments -ne $arguments)) { throw 'Nome task già occupato da un altro comando: nessuna modifica.' }
$identityName = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $shellPath -Argument $arguments -WorkingDirectory $workspacePath
$triggers = @((New-ScheduledTaskTrigger -Daily -At '09:00'), (New-ScheduledTaskTrigger -AtLogOn -User $identityName))
$principal = New-ScheduledTaskPrincipal -UserId $identityName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Description 'Promemoria email per la revisione periodica delle fonti Mercati; destinatario gestito dal pannello.'
$registered = Register-ScheduledTask -TaskName $taskName -InputObject $task -Force
[pscustomobject]@{taskName=$registered.TaskName;configuredAt=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $emailDirectory 'task.json') -Encoding UTF8
Write-Output 'Promemoria email locale registrato alle 09:00. Richiede PC acceso e sessione Windows attiva.'
