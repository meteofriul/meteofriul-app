param(
  [int]$ApiPort = 8002,
  [int]$FrontendPort = 5173,
  [switch]$EventSourcePreview,
  [string]$EventSourceStatePath = "",
  [switch]$CheckOnly,
  [switch]$Stop,
  [switch]$Restart,
  [switch]$Open
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $Root ".dev-logs"
$ApiLog = Join-Path $LogDir "ui3-api.log"
$FrontendLog = Join-Path $LogDir "ui3-frontend.log"
$ApiPidFile = Join-Path $LogDir "ui3-api.pid"
$FrontendPidFile = Join-Path $LogDir "ui3-frontend.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Get-LanIPv4Address {
  $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
      $_.IPAddress -notlike "127.*" -and
      $_.IPAddress -notlike "169.254.*" -and
      $_.PrefixOrigin -ne "WellKnown"
    } |
    Sort-Object -Property InterfaceMetric, PrefixLength |
    Select-Object -First 1 -ExpandProperty IPAddress

  if ($ip) {
    return $ip
  }

  return "127.0.0.1"
}

function Quote-CmdArgument {
  param([string]$Value)
  return '"' + $Value.Replace('"', '\"') + '"'
}

function Test-PortListening {
  param([int]$Port)

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if ($connections) {
    return $true
  }

  $netstat = netstat -ano | Select-String -Pattern "127\.0\.0\.1:$Port\s+.*LISTENING|0\.0\.0\.0:$Port\s+.*LISTENING|\[::1\]:$Port\s+.*LISTENING"
  return [bool]$netstat
}

function Test-HttpOk {
  param([string]$Url)

  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
    return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Wait-HttpOk {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 30
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpOk $Url) {
      return $true
    }

    Start-Sleep -Milliseconds 500
  }

  return (Test-HttpOk $Url)
}

function Get-PidFromFile {
  param([string]$PidFile)

  if (-not (Test-Path -LiteralPath $PidFile)) {
    return $null
  }

  $pidValue = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  $processId = 0
  if (-not [int]::TryParse($pidValue, [ref]$processId)) {
    return $null
  }

  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($process) {
    return $processId
  }

  Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
  return $null
}

function Get-ListenerPid {
  param([int]$Port)

  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($connection) {
    return [int]$connection.OwningProcess
  }

  return $null
}

function Stop-ProcessTree {
  param([int]$ProcessId)

  $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
  foreach ($child in $children) {
    Stop-ProcessTree -ProcessId ([int]$child.ProcessId)
  }

  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-DevProcess {
  param(
    [string]$Name,
    [string]$PidFile,
    [int]$Port
  )

  $candidates = @()
  $pidFromFile = Get-PidFromFile $PidFile
  if ($pidFromFile) {
    $candidates += $pidFromFile
  }

  $listenerPid = Get-ListenerPid $Port
  if ($listenerPid) {
    $candidates += $listenerPid
  }

  $candidates = $candidates | Sort-Object -Unique
  foreach ($processId in $candidates) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
      Write-Host "stopping $Name pid $processId..."
      Stop-ProcessTree -ProcessId $processId
    }
  }

  Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Start-DetachedDevProcess {
  param(
    [string]$Name,
    [string]$WorkingDirectory,
    [string]$FileName,
    [string]$Arguments,
    [string]$LogPath,
    [string]$PidFile,
    [hashtable]$Environment = @{}
  )

  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value "`n[$(Get-Date -Format s)] starting $Name"

  $quotedFileName = Quote-CmdArgument $FileName
  $quotedLogPath = Quote-CmdArgument $LogPath
  $command = "$quotedFileName $Arguments >> $quotedLogPath 2>&1"

  $processInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $processInfo.FileName = "cmd.exe"
  $processInfo.Arguments = '/d /s /c "' + $command + '"'
  $processInfo.WorkingDirectory = $WorkingDirectory
  $processInfo.UseShellExecute = $false
  $processInfo.CreateNoWindow = $true
  $processEnvironment = $processInfo.Environment
  if ($null -eq $processEnvironment) {
    $processEnvironment = $processInfo.EnvironmentVariables
  }
  if ($null -eq $processEnvironment) {
    throw "Impossibile preparare le variabili d'ambiente per $Name"
  }
  foreach ($entry in $Environment.GetEnumerator()) {
    $processEnvironment[[string]$entry.Key] = [string]$entry.Value
  }

  $process = [System.Diagnostics.Process]::Start($processInfo)
  Set-Content -LiteralPath $PidFile -Encoding ASCII -Value $process.Id
  Write-Host "started $Name pid $($process.Id)"
}

function Assert-Path {
  param(
    [string]$Label,
    [string]$Path
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    throw "$Label non trovato: $Path"
  }
}

$LanIPv4 = Get-LanIPv4Address
$BackendListenHost = "0.0.0.0"
$LocalApiUrl = "http://127.0.0.1:$ApiPort/healthz"
$LanApiUrl = "http://$LanIPv4`:$ApiPort/healthz"
$FrontendApiBase = "/api"
$ApiProxyTarget = "http://127.0.0.1:$ApiPort"
$LocalFrontendUrl = "http://localhost:$FrontendPort/"
$LanFrontendUrl = "http://$LanIPv4`:$FrontendPort/"
$ApiEnvironment = @{}
if ($EventSourcePreview) {
  if (-not $EventSourceStatePath) {
    $EventSourceStatePath = Join-Path $Root "tmp\event-source-automation\local-state.json"
  }
  $EventSourceStatePath = [System.IO.Path]::GetFullPath($EventSourceStatePath)
  if (-not (Test-Path -LiteralPath $EventSourceStatePath)) {
    throw "Stato locale fonti Eventi non trovato: $EventSourceStatePath"
  }
  $ApiEnvironment["EVENT_SOURCE_FEED_MODE"] = "preview"
  $ApiEnvironment["EVENT_SOURCE_LOCAL_STATE_PATH"] = $EventSourceStatePath
}

$ApiPython = Join-Path $ApiDir "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $ApiPython)) {
  $ApiPython = "python"
}

$NpmCmd = Join-Path $env:ProgramFiles "nodejs\npm.cmd"
if (-not (Test-Path -LiteralPath $NpmCmd)) {
  $NpmCommand = Get-Command npm.cmd,npm -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $NpmCommand) {
    throw "npm non trovato. Installa Node.js o aggiungi npm al PATH."
  }

  $NpmCmd = $NpmCommand.Source
}

function Write-Status {
  $apiPid = Get-PidFromFile $ApiPidFile
  $frontendPid = Get-PidFromFile $FrontendPidFile
  if (-not $apiPid) { $apiPid = "-" }
  if (-not $frontendPid) { $frontendPid = "-" }
  $apiPortStatus = if (Test-PortListening $ApiPort) { "port-ok" } else { "port-down" }
  $frontendPortStatus = if (Test-PortListening $FrontendPort) { "port-ok" } else { "port-down" }
  $apiHttpStatus = if (Test-HttpOk $LocalApiUrl) { "http-ok" } else { "http-down" }
  $frontendHttpStatus = if (Test-HttpOk $LocalFrontendUrl) { "http-ok" } else { "http-down" }

  Write-Host "api      $apiPortStatus/$apiHttpStatus pid:$apiPid  local:$LocalApiUrl lan:$LanApiUrl"
  Write-Host "frontend $frontendPortStatus/$frontendHttpStatus pid:$frontendPid  local:$LocalFrontendUrl lan:$LanFrontendUrl"
  Write-Host "api source: $ApiDir"
  Write-Host "frontend source: $FrontendDir"
  Write-Host "frontend api: $FrontendApiBase"
  Write-Host "api proxy: $ApiProxyTarget"
  Write-Host "logs: $LogDir"
}

if ($Stop -or $Restart) {
  Stop-DevProcess -Name "frontend-ui3" -PidFile $FrontendPidFile -Port $FrontendPort
  Stop-DevProcess -Name "api-ui3" -PidFile $ApiPidFile -Port $ApiPort
}

if ($Stop -and -not $Restart) {
  Write-Status
  exit 0
}

if ($CheckOnly) {
  Write-Status
  exit 0
}

Assert-Path -Label "API UI3" -Path $ApiDir
Assert-Path -Label "Frontend UI 3" -Path $FrontendDir

if (Test-HttpOk $LocalApiUrl) {
  Write-Host "ui3 api ok: $LocalApiUrl"
} else {
  Start-DetachedDevProcess `
    -Name "api-ui3" `
    -WorkingDirectory $ApiDir `
    -FileName $ApiPython `
    -Arguments "-m uvicorn app.main:app --host $BackendListenHost --port $ApiPort" `
    -LogPath $ApiLog `
    -PidFile $ApiPidFile `
    -Environment $ApiEnvironment

  if (Wait-HttpOk -Url $LocalApiUrl) {
    Write-Host "ui3 api ready: $LocalApiUrl"
  } else {
    Write-Host "ui3 api not ready yet: see $ApiLog"
  }
}

if (Test-HttpOk $LocalFrontendUrl) {
  Write-Host "frontend ok: $LocalFrontendUrl"
} else {
  Start-DetachedDevProcess `
    -Name "frontend-ui3" `
    -WorkingDirectory $FrontendDir `
    -FileName $NpmCmd `
    -Arguments "run dev -- --host 0.0.0.0 --port $FrontendPort --strictPort" `
    -LogPath $FrontendLog `
    -PidFile $FrontendPidFile `
    -Environment @{
      VITE_API_BASE = $FrontendApiBase
      VITE_API_PROXY_TARGET = $ApiProxyTarget
    }

  if (Wait-HttpOk -Url $LocalFrontendUrl) {
    Write-Host "frontend ready: $LocalFrontendUrl"
  } else {
    Write-Host "frontend not ready yet: see $FrontendLog"
  }
}

Write-Status

if ($Open) {
  $openInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $openInfo.FileName = $LocalFrontendUrl
  $openInfo.UseShellExecute = $true
  [System.Diagnostics.Process]::Start($openInfo) | Out-Null
}
