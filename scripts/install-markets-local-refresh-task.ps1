param([switch]$Install)
$ErrorActionPreference = 'Stop'
$workspacePath = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$scriptPath = Join-Path $workspacePath 'scripts/refresh-markets-local.ps1'
$taskName = 'MeteoFriul-MarketsRefresh-Local'
$shellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $scriptPath + '"'
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) { throw 'Launcher Mercati mancante.' }
if (-not $Install) {
    Write-Output 'Anteprima: controllo ogni giorno alle 08:20 e all’accesso Windows; fonti mensili, appuntamenti nei prossimi 30 giorni e scadenze settimanali. Solo archivio locale, senza pubblicazione.'
    exit 0
}
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Count -ne 1 -or $existing.Actions[0].Execute -ne $shellPath -or $existing.Actions[0].Arguments -ne $arguments)) {
    throw 'Il nome del task è già usato con un comando diverso: nessuna sovrascrittura.'
}
$identityName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $shellPath -Argument $arguments -WorkingDirectory $workspacePath
$triggers = @((New-ScheduledTaskTrigger -Daily -At '08:20'), (New-ScheduledTaskTrigger -AtLogOn -User $identityName))
$principal = New-ScheduledTaskPrincipal -UserId $identityName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Description 'Ricerca periodica Mercati: aggiornamento documentato dell’archivio locale, revisioni conservate, pubblicazione disattivata.'
$registered = Register-ScheduledTask -TaskName $taskName -InputObject $task -Force
Write-Output ('Task registrato: ' + $registered.TaskName + '. Richiede PC acceso e sessione Windows attiva.')
