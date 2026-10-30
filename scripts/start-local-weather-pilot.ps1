param(
  [switch]$CheckOnly,
  [switch]$Open,
  [switch]$Stop,
  [switch]$WeatherCloud,
  [switch]$CommunityPilot,
  [switch]$CommunityCloudStore,
  [switch]$NationalOnly,
  [switch]$NationalCloud,
  [switch]$RestartFrontend,
  [switch]$StableFrontend,
  [switch]$RestartCommunity,
  [string]$NodeDirectory,
  [string]$IconPayload,
  [string]$IconReport,
  [string]$CamsPayload,
  [string]$CamsReport,
  [string]$ObjectDatabase,
  [string]$WeatherTestNow
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$NodeDirectorySpecified = $PSBoundParameters.ContainsKey("NodeDirectory")
if ($NodeDirectorySpecified -and [string]::IsNullOrWhiteSpace($NodeDirectory)) {
  throw "NodeDirectory esplicita non puo essere vuota."
}
if ($CommunityCloudStore) {
  throw "CommunityCloudStore e stato ritirato: usa il servizio Community ufficiale meteo-friul."
}
if ($CommunityPilot -and $WeatherCloud) { throw "CommunityPilot richiede il profilo locale, non WeatherCloud." }
if ($CommunityCloudStore -and -not $CommunityPilot) { throw "CommunityCloudStore richiede CommunityPilot esplicito." }
if ($NationalCloud -and ($WeatherCloud -or $NationalOnly -or $WeatherTestNow)) { throw "NationalCloud richiede il profilo browser locale e orologio reale, senza WeatherCloud o NationalOnly." }
if ($CommunityCloudStore -and $WeatherTestNow) { throw "CommunityCloudStore richiede orologio reale." }
if ($NationalOnly -and ($WeatherCloud -or $WeatherTestNow)) { throw "NationalOnly richiede dati nazionali locali e orologio reale." }
if ($RestartFrontend -and ($CheckOnly -or $Stop)) { throw "RestartFrontend non e compatibile con CheckOnly o Stop." }
if ($StableFrontend -and ($CheckOnly -or $Stop)) { throw "StableFrontend non e compatibile con CheckOnly o Stop." }
if ($RestartCommunity -and (-not $CommunityPilot -or $CheckOnly -or $Stop)) { throw "RestartCommunity richiede CommunityPilot e non e compatibile con CheckOnly o Stop." }

if ($Stop -and ($CheckOnly -or $Open)) {
  throw "-Stop non puo essere combinato con -CheckOnly o -Open."
}
if (-not $Stop -and $WeatherCloud -and -not [string]::IsNullOrWhiteSpace($WeatherTestNow)) {
  throw "-WeatherCloud usa dati correnti e non puo essere combinato con -WeatherTestNow."
}

$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$BackendDir = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "backend"))
$FrontendDir = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "frontend"))
$StableFrontendScript = [System.IO.Path]::GetFullPath((Join-Path $FrontendDir "scripts\stable-local-weather-pilot.mjs"))
$ExperimentDir = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "experiments\weather_autonomy"))
$SnapshotWriterScript = [System.IO.Path]::GetFullPath((Join-Path $ExperimentDir "publish_snapshots_v1.py"))
$DataPlaneScript = [System.IO.Path]::GetFullPath((Join-Path $ExperimentDir "serve_published_contract_v1.py"))
$ArtifactDir = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ".dev-logs\weather-v1"))
$BundledArtifactPack = [System.IO.Path]::GetFullPath((Join-Path $ExperimentDir "fixtures\local-pilot-snapshot-20260904.zip"))
$BundledArtifactHashes = [ordered]@{
  "icon_payload_precipitation_semantics_v3_20260904.json" = "9b9e18bc3613eed505180ce99af8fca723047d1956d817db79985ded4fe1a74e"
  "icon_report_precipitation_semantics_v3_20260904.json" = "6abcbf6fda33621f50dd1f114c6d92de362b119754bdd83954cca9dce6df8186"
  "cams_fvg_authoritative_20260904.json" = "77c9b9181e95797ea7f380a7bd91bc6fdc7133412708a253268de36ab82825f0"
  "cams_fvg_authoritative_report_20260904.json" = "40c28f7df8c1d166ea9673013bcceecd20bf496236f8a2fd6297a07ef1d7a4e3"
}
$BundledArtifactOverrides = @{
  "icon_payload_precipitation_semantics_v3_20260904.json" = $IconPayload
  "icon_report_precipitation_semantics_v3_20260904.json" = $IconReport
  "cams_fvg_authoritative_20260904.json" = $CamsPayload
  "cams_fvg_authoritative_report_20260904.json" = $CamsReport
}
$CloudWeatherPilotBaseUrl = "https://meteofriul-weather-49007668366.europe-west1.run.app"
$CloudNationalPilotBaseUrl = "https://meteofriul-national-weather-49007668366.europe-west1.run.app"
$CommunityModule = if ($CommunityCloudStore) { "app.pilot_community_cloud_loopback" } else { "app.pilot_community" }
$CommunityLaunchProfile = if ($Stop) { $null } elseif ($CommunityCloudStore) { "community-cloud-store-v1" } else { "community-local-v1" }
$FrontendViteMode = if ($WeatherCloud) { "local-pilot-cloud" } else { "local-pilot" }
$FrontendNpmScript = if ($WeatherCloud) { "dev:local-pilot:cloud" } else { "dev:local-pilot" }
$FrontendLaunchProfile = if ($Stop) {
  $null
} elseif ($WeatherCloud) {
  "weather-cloud-v1"
} else {
  "weather-offline-v1"
}
if ($CommunityPilot -and -not $Stop) { $FrontendLaunchProfile += "-$CommunityLaunchProfile" }
if ($NationalOnly -and -not $Stop) { $FrontendLaunchProfile += "-national-v2" }
if ($NationalCloud -and -not $Stop) { $FrontendLaunchProfile += "-national-cloud-v2" }
if ($StableFrontend -and -not $Stop) { $FrontendLaunchProfile += "-stable-no-hmr-v1" }

function Resolve-LauncherPath {
  param(
    [string]$Label,
    [string]$Value,
    [string]$DefaultRelativePath
  )
  $selected = if ([string]::IsNullOrWhiteSpace($Value)) { $DefaultRelativePath } else { $Value }
  try {
    if (-not [System.IO.Path]::IsPathRooted($selected)) {
      $selected = Join-Path $RepoRoot $selected
    }
    return [System.IO.Path]::GetFullPath($selected)
  } catch {
    throw "$Label non contiene un percorso valido: $selected"
  }
}

function Initialize-BundledWeatherArtifacts {
  if ($WeatherCloud -or $NationalOnly -or $NationalCloud) { return }

  $requiredDefaults = @(
    $BundledArtifactHashes.Keys | Where-Object {
      [string]::IsNullOrWhiteSpace([string]$BundledArtifactOverrides[$_]) -and
      -not [System.IO.File]::Exists((Join-Path $ArtifactDir $_))
    }
  )
  if ($requiredDefaults.Count -eq 0) { return }
  if (-not [System.IO.File]::Exists($BundledArtifactPack)) {
    throw "Pacchetto snapshot locale mancante: $BundledArtifactPack"
  }

  New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $archive = [System.IO.Compression.ZipFile]::OpenRead($BundledArtifactPack)
  try {
    $entries = @{}
    foreach ($entry in $archive.Entries) {
      if (-not $BundledArtifactHashes.Contains($entry.FullName) -or $entry.Name -cne $entry.FullName) {
        throw "Il pacchetto snapshot contiene una voce inattesa: $($entry.FullName)"
      }
      if ($entries.ContainsKey($entry.FullName)) {
        throw "Il pacchetto snapshot contiene una voce duplicata: $($entry.FullName)"
      }
      $entries[$entry.FullName] = $entry
    }
    if ($entries.Count -ne $BundledArtifactHashes.Count) {
      throw "Il pacchetto snapshot non contiene l'insieme esatto degli artefatti previsti."
    }

    foreach ($name in $requiredDefaults) {
      if (-not $entries.ContainsKey($name)) {
        throw "Artefatto locale mancante nel pacchetto: $name"
      }
      $target = Join-Path $ArtifactDir $name
      $temporary = Join-Path $ArtifactDir (".bootstrap-$([guid]::NewGuid().ToString('N'))-$name")
      try {
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entries[$name], $temporary, $false)
        $digest = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($digest -cne $BundledArtifactHashes[$name]) {
          throw "SHA-256 non valido per l'artefatto locale: $name"
        }
        [System.IO.File]::Move($temporary, $target)
      } finally {
        if ([System.IO.File]::Exists($temporary)) {
          [System.IO.File]::Delete($temporary)
        }
      }
      Write-Host "Snapshot locale inizializzato: $name"
    }
  } finally {
    $archive.Dispose()
  }
}

Initialize-BundledWeatherArtifacts

$IconPayload = Resolve-LauncherPath `
  -Label "Payload ICON" `
  -Value $IconPayload `
  -DefaultRelativePath ".dev-logs\weather-v1\icon_payload_precipitation_semantics_v3_20260904.json"
$IconReport = Resolve-LauncherPath `
  -Label "Report ICON" `
  -Value $IconReport `
  -DefaultRelativePath ".dev-logs\weather-v1\icon_report_precipitation_semantics_v3_20260904.json"
$CamsPayload = Resolve-LauncherPath `
  -Label "Payload CAMS" `
  -Value $CamsPayload `
  -DefaultRelativePath ".dev-logs\weather-v1\cams_fvg_authoritative_20260904.json"
$CamsReport = Resolve-LauncherPath `
  -Label "Report CAMS" `
  -Value $CamsReport `
  -DefaultRelativePath ".dev-logs\weather-v1\cams_fvg_authoritative_report_20260904.json"
$ObjectDatabase = Resolve-LauncherPath `
  -Label "Object DB" `
  -Value $ObjectDatabase `
  -DefaultRelativePath ".dev-logs\weather-v1\weather-v1-objects-20260905-v6-readonly-split.sqlite3"
$LogDir = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ".dev-logs\local-weather-pilot"))
$PilotTempRoot = if ($env:LOCALAPPDATA) {
  Join-Path $env:LOCALAPPDATA "Temp"
} else {
  [System.IO.Path]::GetTempPath()
}
$StableFrontendBuildRoot = if ($StableFrontend -and -not $Stop) {
  [System.IO.Path]::GetFullPath((Join-Path $PilotTempRoot (
    "meteofriul-local-weather-pilot-$([guid]::NewGuid().ToString('N'))"
  )))
} else {
  $null
}
$IsolatedPilotPython = [System.IO.Path]::GetFullPath((Join-Path $PilotTempRoot "meteofriul-weather-autonomy-20260902\venv\Scripts\python.exe"))
$ExpectedCatalogVersion = "istat-2026-irdat-2006-representative-points-v1"
$ExpectedCatalogSha256 = "d5cb6f9efdf10151caa0508b07ed910488db01dc29de45b293ac9eb05652eca4"
$ExpectedMunicipalityCount = 215
$ExpectedIconRunId = $null
$ExpectedCamsRunId = $null
$ExpectedIconRunAtUtc = $null
$ExpectedCamsRunAtUtc = $null
$ExpectedIconValidToUtc = $null
$ExpectedCamsValidToUtc = $null
$IconFreshUntilUtc = $null
$CamsFreshUntilUtc = $null
$IconUsableUntilUtc = $null
$CamsUsableUntilUtc = $null

function Convert-OptionalPilotClock {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
  $trimmed = $Value.Trim()
  $parsed = [datetimeoffset]::MinValue
  $valid = [datetimeoffset]::TryParseExact(
    $trimmed,
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::AssumeUniversal -bor `
      [System.Globalization.DateTimeStyles]::AdjustToUniversal,
    [ref]$parsed
  )
  if (-not $valid -or $parsed.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'") -cne $trimmed) {
    throw "WeatherTestNow deve usare secondi UTC canonici, per esempio 2026-09-04T21:00:00Z."
  }
  return $trimmed
}

$WeatherTestNow = Convert-OptionalPilotClock -Value $WeatherTestNow

function Get-PilotClockNow {
  if ($WeatherTestNow) { return [datetimeoffset]::ParseExact(
    $WeatherTestNow,
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::AssumeUniversal -bor `
      [System.Globalization.DateTimeStyles]::AdjustToUniversal
  ) }
  return [datetimeoffset]::UtcNow
}

$Services = @(
  [pscustomobject]@{
    Name = "backend"
    Port = 8002
    PidFile = Join-Path $LogDir "backend.pid"
    LogFile = Join-Path $LogDir "backend.log"
    Identity = @("uvicorn", "app.main:app", "127.0.0.1", "8002")
    ListenerExecutableNames = @("python.exe")
    HealthUrl = "http://127.0.0.1:8002/healthz"
  },
  [pscustomobject]@{
    Name = "data-plane"
    Port = 8781
    PidFile = Join-Path $LogDir "data-plane.pid"
    LogFile = Join-Path $LogDir "data-plane.log"
    Identity = @("serve_published_contract_v1.py", "--object-db", $ObjectDatabase, "--port", "8781")
    ExactArguments = [ordered]@{
      "--object-db" = $ObjectDatabase
      "--port" = "8781"
    }
    ListenerExecutableNames = @("python.exe")
    HealthUrl = "http://127.0.0.1:8781/weather/v1/icon2i/latest.json"
  },
  [pscustomobject]@{
    Name = "frontend"
    Port = 5174
    PidFile = Join-Path $LogDir "frontend.pid"
    LogFile = Join-Path $LogDir "frontend.log"
    Identity = @("dev:local-pilot", "5174")
    ExactArguments = if ($Stop) { $null } else { [ordered]@{
      "--mode" = $FrontendViteMode
      "--port" = "5174"
    } }
    LaunchProfile = $FrontendLaunchProfile
    CleanupPaths = if ($StableFrontend -and -not $Stop) { @($StableFrontendBuildRoot) } else { @() }
    ListenerExecutableNames = @("node.exe")
    HealthUrl = "http://127.0.0.1:5174/"
  }
  [pscustomobject]@{
    Name = "community-pilot"
    Port = 8783
    PidFile = Join-Path $LogDir "community-pilot.pid"
    LogFile = Join-Path $LogDir "community-pilot.log"
    Identity = @("app.pilot_community", "127.0.0.1", "8783")
    ExactArguments = if ($Stop) { $null } else { [ordered]@{ "-m" = $CommunityModule; "--host" = "127.0.0.1"; "--port" = "8783" } }
    LaunchProfile = $CommunityLaunchProfile
    ListenerExecutableNames = @("python.exe")
    HealthUrl = "http://127.0.0.1:8783/api/community/health"
  }
)

function Get-LauncherMutexName {
  param([string]$WorkspacePath)
  $normalized = [System.IO.Path]::GetFullPath($WorkspacePath).ToUpperInvariant()
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
    $digest = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
  return "Local\MeteoFriul.LocalWeatherPilot.$($digest.Substring(0, 32))"
}

function Enter-LauncherMutex {
  param([string]$Name)
  $mutex = [System.Threading.Mutex]::new($false, $Name)
  $acquired = $false
  try {
    try {
      $acquired = $mutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
      $acquired = $true
    }
    if (-not $acquired) {
      throw "Un'altra invocazione del launcher locale e gia attiva per questa worktree. Riprova al termine."
    }
    return $mutex
  } catch {
    if (-not $acquired) { $mutex.Dispose() }
    throw
  }
}

function Assert-ExistingFile {
  param([string]$Label, [string]$Path)
  if (-not [System.IO.File]::Exists($Path)) {
    throw "$Label non trovato: $Path"
  }
}

function Resolve-Executable {
  param([string[]]$Candidates)
  foreach ($candidate in $Candidates) {
    if ([System.IO.File]::Exists($candidate)) {
      return [System.IO.Path]::GetFullPath($candidate)
    }
  }
  foreach ($candidate in $Candidates) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) {
      return $command.Source
    }
  }
  throw "Eseguibile non trovato: $($Candidates -join ', ')"
}

function Resolve-PilotNodeToolchain {
  param([string]$Directory, [switch]$ExplicitDirectory)
  if (-not $ExplicitDirectory) {
    # Preserve the existing default; an explicit path never falls back here.
    return [pscustomobject]@{
      Node = Resolve-Executable -Candidates @((Join-Path $env:ProgramFiles "nodejs\node.exe"), "node.exe", "node")
      Npm = Resolve-Executable -Candidates @((Join-Path $env:ProgramFiles "nodejs\npm.cmd"), "npm.cmd", "npm")
      NpmCli = $null
      ChildPath = $null
    }
  }
  if ([string]::IsNullOrWhiteSpace($Directory)) { throw "NodeDirectory esplicita non puo essere vuota." }
  $resolved = Resolve-LauncherPath -Label "NodeDirectory" -Value $Directory
  if (-not [System.IO.Directory]::Exists($resolved)) { throw "NodeDirectory non trovata: $resolved" }
  $nodePath = Join-Path $resolved "node.exe"
  $npmPath = Join-Path $resolved "npm.cmd"
  $npmCliPath = Join-Path $resolved "node_modules\npm\bin\npm-cli.js"
  Assert-ExistingFile -Label "Node esplicito" -Path $nodePath
  Assert-ExistingFile -Label "npm esplicito" -Path $npmPath
  Assert-ExistingFile -Label "CLI npm della toolchain" -Path $npmCliPath
  return [pscustomobject]@{
    Node = $nodePath
    Npm = $npmPath
    NpmCli = $npmCliPath
    ChildPath = $resolved + [System.IO.Path]::PathSeparator + $env:PATH
  }
}

function Assert-PilotNodeVersions {
  param($Toolchain)
  $engines = (Get-Content -Raw -LiteralPath (Join-Path $FrontendDir "package.json") | ConvertFrom-Json).engines
  $nodeVersion = @(& $Toolchain.Node --version)
  if ($LASTEXITCODE -ne 0 -or $nodeVersion.Count -ne 1 -or $nodeVersion[0] -cne "v$($engines.node)") {
    throw "NodeDirectory richiede Node $($engines.node), come frontend/package.json."
  }
  # Use the selected node directly, so version validation cannot use global node.
  $npmVersion = @(& $Toolchain.Node $Toolchain.NpmCli --version)
  if ($LASTEXITCODE -ne 0 -or $npmVersion.Count -ne 1 -or $npmVersion[0] -cne [string]$engines.npm) {
    throw "NodeDirectory richiede npm $($engines.npm), come frontend/package.json."
  }
  Write-Host "Toolchain esplicita verificata: Node $($nodeVersion[0]), npm $($npmVersion[0])."
}

function Assert-PilotNodeListener {
  param($Service, [string]$NodePath)
  foreach ($listener in @(Get-ListenerRecords -Port $Service.Port)) {
    $process = Get-Process -Id ([int]$listener.Pid) -ErrorAction Stop
    if (-not $process.Path -or [System.IO.Path]::GetFullPath([string]$process.Path) -ne $NodePath) {
      throw "Porta $($Service.Port) usa un eseguibile diverso dal Node selezionato; nessun riuso. Per il frontend posseduto usa -RestartFrontend."
    }
  }
}

function Initialize-ProcessTreeInspector {
  if ("MeteoFriulProcessTreeSnapshot" -as [type]) { return }
  $source = @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public sealed class MeteoFriulProcessEntry
{
    public int ProcessId { get; set; }
    public int ParentProcessId { get; set; }
    public string ExecutableName { get; set; }
}

public static class MeteoFriulProcessTreeSnapshot
{
    private const uint TH32CS_SNAPPROCESS = 0x00000002;
    private static readonly IntPtr InvalidHandleValue = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessEntry32
    {
        public uint Size;
        public uint Usage;
        public uint ProcessId;
        public IntPtr DefaultHeapId;
        public uint ModuleId;
        public uint Threads;
        public uint ParentProcessId;
        public int BasePriority;
        public uint Flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string ExecutableName;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool Process32FirstW(IntPtr snapshot, ref ProcessEntry32 entry);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool Process32NextW(IntPtr snapshot, ref ProcessEntry32 entry);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    public static MeteoFriulProcessEntry[] Capture()
    {
        IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snapshot == InvalidHandleValue) throw new Win32Exception();
        try
        {
            var result = new List<MeteoFriulProcessEntry>();
            var entry = new ProcessEntry32();
            entry.Size = (uint)Marshal.SizeOf(entry);
            if (!Process32FirstW(snapshot, ref entry)) throw new Win32Exception();
            do
            {
                result.Add(new MeteoFriulProcessEntry {
                    ProcessId = (int)entry.ProcessId,
                    ParentProcessId = (int)entry.ParentProcessId,
                    ExecutableName = entry.ExecutableName
                });
                entry.Size = (uint)Marshal.SizeOf(entry);
            }
            while (Process32NextW(snapshot, ref entry));
            return result.ToArray();
        }
        finally
        {
            CloseHandle(snapshot);
        }
    }
}
'@
  Add-Type -TypeDefinition $source -Language CSharp -ErrorAction Stop
}

function Get-ProcessTreeSnapshot {
  Initialize-ProcessTreeInspector
  return @([MeteoFriulProcessTreeSnapshot]::Capture())
}

function Get-DescendantRecords {
  param([int]$AncestorId, $Snapshot)
  $byPid = @{}
  foreach ($entry in @($Snapshot)) { $byPid[[int]$entry.ProcessId] = $entry }
  $result = @()
  foreach ($entry in @($Snapshot)) {
    $pidValue = [int]$entry.ProcessId
    if ($pidValue -eq $AncestorId) { continue }
    $current = $entry
    $visited = @{}
    $depth = 0
    while ($null -ne $current -and $depth -lt 128) {
      $parentId = [int]$current.ParentProcessId
      if ($parentId -eq $AncestorId) {
        $result += [pscustomobject]@{
          Pid = $pidValue
          ParentPid = [int]$entry.ParentProcessId
          Depth = $depth + 1
          ExecutableName = [string]$entry.ExecutableName
        }
        break
      }
      if ($parentId -le 0 -or $visited.ContainsKey($parentId) -or -not $byPid.ContainsKey($parentId)) {
        break
      }
      $visited[$parentId] = $true
      $current = $byPid[$parentId]
      $depth += 1
    }
  }
  return @($result)
}

function Test-ProcessDescendsFrom {
  param([int]$ProcessId, [int]$AncestorId, $Snapshot)
  return @(
    Get-DescendantRecords -AncestorId $AncestorId -Snapshot $Snapshot |
      Where-Object { $_.Pid -eq $ProcessId }
  ).Count -eq 1
}

function Get-ListenerRecords {
  param([int]$Port)
  $records = @()
  foreach ($connection in @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)) {
    $records += [pscustomobject]@{
      Address = [string]$connection.LocalAddress
      Pid = [int]$connection.OwningProcess
    }
  }
  if ($records.Count -eq 0) {
    $pattern = "^\s*TCP\s+(\S+):$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
    foreach ($line in (netstat -ano -p TCP 2>$null)) {
      if ($line -match $pattern) {
        $records += [pscustomobject]@{
          Address = [string]$Matches[1]
          Pid = [int]$Matches[2]
        }
      }
    }
  }
  return @($records | Sort-Object Address, Pid -Unique)
}

function Get-ProcessCommandLine {
  param([int]$ProcessId)
  $record = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
  if ($record) { return [string]$record.CommandLine }
  return ""
}

function ConvertFrom-LauncherCommandLine {
  param([string]$CommandLine)
  if ([string]::IsNullOrWhiteSpace($CommandLine)) { return @() }
  $arguments = @()
  foreach ($match in [regex]::Matches($CommandLine, '(?:^|\s)(?:"([^"]*)"|(\S+))')) {
    if ($match.Groups[1].Success) {
      $arguments += [string]$match.Groups[1].Value
    } else {
      $arguments += [string]$match.Groups[2].Value
    }
  }
  return @($arguments)
}

function Test-ProcessIdentity {
  param(
    [int]$ProcessId,
    [string[]]$Identity,
    [System.Collections.IDictionary]$ExactArguments = $null
  )
  $commandLine = Get-ProcessCommandLine -ProcessId $ProcessId
  if (-not $commandLine) { return $false }
  foreach ($fragment in $Identity) {
    if ($commandLine.IndexOf($fragment, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return $false
    }
  }
  if ($null -ne $ExactArguments) {
    $arguments = @(ConvertFrom-LauncherCommandLine -CommandLine $commandLine)
    foreach ($entry in $ExactArguments.GetEnumerator()) {
      $indexes = @(
        for ($index = 0; $index -lt $arguments.Count; $index += 1) {
          if ($arguments[$index] -ceq [string]$entry.Key) { $index }
        }
      )
      if ($indexes.Count -ne 1 -or $indexes[0] + 1 -ge $arguments.Count) {
        return $false
      }
      $actual = [string]$arguments[$indexes[0] + 1]
      $expected = [string]$entry.Value
      if ([string]$entry.Key -ceq "--object-db") {
        try {
          $actual = [System.IO.Path]::GetFullPath($actual)
          $expected = [System.IO.Path]::GetFullPath($expected)
        } catch {
          return $false
        }
      }
      if (-not [string]::Equals($actual, $expected, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
      }
    }
  }
  return $true
}

function Test-WeatherLatestPayload {
  param(
    $Payload,
    [string]$Provider,
    [string]$ExpectedRunId
  )
  return $null -ne $Payload -and `
    [int]$Payload.schema_version -eq 1 -and `
    $Payload.kind -eq "meteofriul.weather.latest" -and `
    $Payload.provider -eq $Provider -and `
    $Payload.catalog.version -eq $ExpectedCatalogVersion -and `
    $Payload.catalog.sha256 -eq $ExpectedCatalogSha256 -and `
    [int]$Payload.catalog.municipality_count -eq $ExpectedMunicipalityCount -and `
    $Payload.latest.source_run_id -eq $ExpectedRunId -and `
    $Payload.latest.manifest_path -eq "runs/$ExpectedRunId/manifest.json" -and `
    [int]$Payload.latest.manifest_json_bytes -gt 0 -and `
    [string]$Payload.latest.manifest_sha256 -match "^[0-9a-f]{64}$"
}

function Test-WeatherManifestResponse {
  param(
    $Response,
    $Latest,
    [string]$Provider,
    [string]$ExpectedRunId,
    [string]$ExpectedRunAtUtc,
    [string]$ExpectedValidToUtc,
    [string]$ExpectedFreshUntilUtc,
    [string]$ExpectedUsableUntilUtc
  )
  if ($null -eq $Response -or [int]$Response.StatusCode -ne 200) { return $false }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Response.Content)
  if ($bytes.Length -ne [int]$Latest.latest.manifest_json_bytes) { return $false }
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $digest = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
  if ($digest -ne [string]$Latest.latest.manifest_sha256) { return $false }
  $manifest = $Response.Content | ConvertFrom-Json
  $runAt = Convert-CanonicalUtcSecond -Value $manifest.run_at -Label "$Provider manifest run_at"
  $validFrom = Convert-CanonicalUtcSecond -Value $manifest.valid_from -Label "$Provider manifest valid_from"
  $validTo = Convert-CanonicalUtcSecond -Value $manifest.valid_to -Label "$Provider manifest valid_to"
  $freshUntil = Convert-CanonicalUtcSecond -Value $manifest.freshness.fresh_until -Label "$Provider manifest fresh_until"
  $usableUntil = Convert-CanonicalUtcSecond -Value $manifest.freshness.usable_until -Label "$Provider manifest usable_until"
  $expectedPolicyId = if ($Provider -eq "icon2i") {
    "icon2i_48h_v1"
  } elseif ($Provider -eq "cams_europe") {
    "cams_current_v1"
  } else {
    "cams_pollen_current_v1"
  }
  $expectedFutureHours = if ($Provider -eq "icon2i") { 48 } else { 0 }
  return [int]$manifest.schema_version -eq 1 -and `
    $manifest.kind -eq "meteofriul.weather.run_manifest" -and `
    $manifest.provider -eq $Provider -and `
    $manifest.source_run_id -eq $ExpectedRunId -and `
    $manifest.catalog.version -eq $ExpectedCatalogVersion -and `
    $manifest.catalog.sha256 -eq $ExpectedCatalogSha256 -and `
    [int]$manifest.catalog.municipality_count -eq $ExpectedMunicipalityCount -and `
    @($manifest.objects.PSObject.Properties).Count -eq $ExpectedMunicipalityCount -and `
    $runAt -eq $ExpectedRunAtUtc -and `
    $validFrom -eq $ExpectedRunAtUtc -and `
    $validTo -eq $ExpectedValidToUtc -and `
    $freshUntil -eq $ExpectedFreshUntilUtc -and `
    $usableUntil -eq $ExpectedUsableUntilUtc -and `
    $manifest.freshness.policy_id -eq $expectedPolicyId -and `
    [int]$manifest.freshness.required_future_hours -eq $expectedFutureHours -and `
    [int]$manifest.freshness.current_sample_max_lag_minutes -eq 60
}

function Get-ResponseSha256 {
  param($Response)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Response.Content)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Test-CamsFamilyReleaseDescriptor {
  param($Descriptor)
  if ($null -eq $Descriptor) { return $false }
  $expectedProperties = @(
    "release_json_bytes", "release_path", "release_sha256", "source_run_id"
  )
  $actualProperties = @($Descriptor.PSObject.Properties.Name | Sort-Object)
  if (($actualProperties -join ",") -cne (($expectedProperties | Sort-Object) -join ",")) {
    return $false
  }
  $runId = [string]$Descriptor.source_run_id
  return `
    $runId -cmatch "^\d{8}T\d{6}Z$" -and `
    $Descriptor.release_path -ceq "runs/$runId/release.json" -and `
    [int]$Descriptor.release_json_bytes -gt 0 -and `
    [string]$Descriptor.release_sha256 -cmatch "^[0-9a-f]{64}$"
}

function Test-CamsFamilyLatestPayload {
  param($Payload)
  if ($null -eq $Payload -or -not ($Payload.disabled_run_ids -is [System.Array])) {
    return $false
  }
  $expectedProperties = @(
    "catalog", "disabled_run_ids", "family", "kind", "latest",
    "previous", "published_at", "revision", "schema_version"
  )
  $actualProperties = @($Payload.PSObject.Properties.Name | Sort-Object)
  if (($actualProperties -join ",") -cne (($expectedProperties | Sort-Object) -join ",")) {
    return $false
  }
  $disabledRunIds = @($Payload.disabled_run_ids)
  $canonicalDisabledRunIds = @($disabledRunIds | Sort-Object -Unique)
  if (
    ($disabledRunIds -join ",") -cne ($canonicalDisabledRunIds -join ",") -or `
    @($disabledRunIds | Where-Object { [string]$_ -cnotmatch "^\d{8}T\d{6}Z$" }).Count -gt 0 -or `
    $disabledRunIds -contains $Payload.latest.source_run_id -or `
    ($null -ne $Payload.previous -and $disabledRunIds -contains $Payload.previous.source_run_id)
  ) { return $false }
  try {
    Convert-CanonicalUtcSecond -Value $Payload.published_at -Label "CAMS family latest published_at" | Out-Null
  } catch {
    return $false
  }
  if (-not (Test-CamsFamilyReleaseDescriptor -Descriptor $Payload.latest)) {
    return $false
  }
  if (
    $null -ne $Payload.previous -and `
    (
      -not (Test-CamsFamilyReleaseDescriptor -Descriptor $Payload.previous) -or `
      [string]::CompareOrdinal(
        [string]$Payload.previous.source_run_id,
        [string]$Payload.latest.source_run_id
      ) -ge 0
    )
  ) { return $false }
  return `
    [int]$Payload.schema_version -eq 1 -and `
    $Payload.kind -eq "meteofriul.weather.cams_family_latest" -and `
    $Payload.family -eq "cams" -and `
    [int]$Payload.revision -gt 0 -and `
    $Payload.catalog.version -eq $ExpectedCatalogVersion -and `
    $Payload.catalog.sha256 -eq $ExpectedCatalogSha256 -and `
    [int]$Payload.catalog.municipality_count -eq $ExpectedMunicipalityCount -and `
    [string]$Payload.latest.source_run_id -cmatch "^\d{8}T\d{6}Z$" -and `
    $Payload.latest.release_path -eq "runs/$($Payload.latest.source_run_id)/release.json" -and `
    [int]$Payload.latest.release_json_bytes -gt 0 -and `
    [string]$Payload.latest.release_sha256 -cmatch "^[0-9a-f]{64}$"
}

function Test-CamsFamilyReleaseResponse {
  param($Response, $FamilyLatest)
  if ($null -eq $Response -or [int]$Response.StatusCode -ne 200) { return $false }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Response.Content)
  if ($bytes.Length -ne [int]$FamilyLatest.latest.release_json_bytes) { return $false }
  if ((Get-ResponseSha256 -Response $Response) -cne [string]$FamilyLatest.latest.release_sha256) {
    return $false
  }
  $release = $Response.Content | ConvertFrom-Json
  try {
    $releasePublishedAt = Convert-CanonicalUtcSecond -Value $release.published_at -Label "CAMS family release published_at"
    $pointerPublishedAt = Convert-CanonicalUtcSecond -Value $FamilyLatest.published_at -Label "CAMS family latest published_at"
    if ([datetimeoffset]::Parse($releasePublishedAt) -gt [datetimeoffset]::Parse($pointerPublishedAt)) {
      return $false
    }
  } catch {
    return $false
  }
  $core = $release.components.core
  $pollen = $release.components.pollen
  return [int]$release.schema_version -eq 1 -and `
    $release.kind -eq "meteofriul.weather.cams_family_release" -and `
    $release.family -eq "cams" -and `
    $release.source_run_id -eq $FamilyLatest.latest.source_run_id -and `
    $release.catalog.version -eq $ExpectedCatalogVersion -and `
    $release.catalog.sha256 -eq $ExpectedCatalogSha256 -and `
    [int]$release.catalog.municipality_count -eq $ExpectedMunicipalityCount -and `
    [string]$release.validation_sha256 -cmatch "^[0-9a-f]{64}$" -and `
    @($release.components.PSObject.Properties).Count -eq 2 -and `
    $core.provider -eq "cams_europe" -and `
    $core.source_run_id -eq $FamilyLatest.latest.source_run_id -and `
    $core.manifest_key -eq "weather/v1/cams_europe/runs/$($FamilyLatest.latest.source_run_id)/manifest.json" -and `
    [int]$core.manifest_json_bytes -gt 0 -and `
    [string]$core.manifest_sha256 -cmatch "^[0-9a-f]{64}$" -and `
    $pollen.provider -eq "cams_europe_pollen" -and `
    $pollen.source_run_id -eq $FamilyLatest.latest.source_run_id -and `
    $pollen.manifest_key -eq "weather/v1/cams_europe_pollen/runs/$($FamilyLatest.latest.source_run_id)/manifest.json" -and `
    [int]$pollen.manifest_json_bytes -gt 0 -and `
    [string]$pollen.manifest_sha256 -cmatch "^[0-9a-f]{64}$"
}

function Test-WeatherObjectBlocked {
  param([string]$Url)
  try {
    Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
    return $false
  } catch {
    try {
      return [int]$_.Exception.Response.StatusCode -in @(400, 404)
    } catch {
      return $false
    }
  }
}

function Test-CamsContinuityResponse {
  param(
    $Response,
    $ReleaseResponse,
    $FamilyLatest,
    [datetimeoffset]$Now = [datetimeoffset]::UtcNow
  )
  try {
    if (
      $null -eq $Response -or [int]$Response.StatusCode -ne 200 -or `
      -not (Test-CamsFamilyLatestPayload -Payload $FamilyLatest) -or `
      -not (Test-CamsFamilyReleaseResponse -Response $ReleaseResponse -FamilyLatest $FamilyLatest)
    ) { return $false }
    $runId = [string]$FamilyLatest.latest.source_run_id
    if ($runId -cnotmatch "^\d{8}T000000Z$") { return $false }
    $runAt = Convert-CanonicalRunIdToUtcSecond -Value $runId -Label "CAMS continuity run"
    $run = [datetimeoffset]::ParseExact(
      $runAt, "yyyy-MM-dd'T'HH:mm:ss'Z'",
      [System.Globalization.CultureInfo]::InvariantCulture,
      [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
    )
    if ($Now -lt $run -or $Now -gt $run.AddHours(36)) { return $false }
    $release = $ReleaseResponse.Content | ConvertFrom-Json
    # Canonical bytes are part of the client contract. Build the complete
    # expected grant rather than accepting extra fields or coercing JSON types.
    $expected = [ordered]@{
      catalog = [ordered]@{
        municipality_count = [int]$ExpectedMunicipalityCount
        sha256 = $ExpectedCatalogSha256
        version = $ExpectedCatalogVersion
      }
      current_sample_max_lag_minutes = 60
      fresh_until = $run.AddHours(24).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
      issued_at = Convert-CanonicalUtcSecond -Value $release.published_at -Label "CAMS continuity issued_at"
      kind = "meteofriul.weather.cams_continuity"
      policy_id = "cams_continuity_36h_v1"
      release_json_bytes = [System.Text.Encoding]::UTF8.GetByteCount([string]$ReleaseResponse.Content)
      release_sha256 = Get-ResponseSha256 -Response $ReleaseResponse
      run_at = $runAt
      schema_version = 1
      source_run_id = $runId
      usable_until = $run.AddHours(36).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    }
    $body = [string]$Response.Content
    return [System.Text.Encoding]::UTF8.GetByteCount($body) -le 4096 -and `
      $body -ceq ($expected | ConvertTo-Json -Depth 4 -Compress)
  } catch {
    return $false
  }
}

function Test-CamsFamilyArtifacts {
  param(
    [string]$BaseUrl,
    $FamilyLatest,
    [int]$TimeoutSec = 2,
    [switch]$RequireCurrent
  )
  $base = $BaseUrl.TrimEnd("/")
  try {
    if (-not (Test-CamsFamilyLatestPayload -Payload $FamilyLatest)) { return $false }
    $releaseResponse = Invoke-WebRequest `
      -Uri "$base/weather/v1/families/cams/$($FamilyLatest.latest.release_path)" `
      -UseBasicParsing -TimeoutSec $TimeoutSec
    if (-not (Test-CamsFamilyReleaseResponse -Response $releaseResponse -FamilyLatest $FamilyLatest)) {
      return $false
    }

    $release = $releaseResponse.Content | ConvertFrom-Json
    $activeRunId = [string]$FamilyLatest.latest.source_run_id
    $activeRunAtUtc = Convert-CanonicalRunIdToUtcSecond `
      -Value $activeRunId `
      -Label "CAMS family active source_run_id"
    $activeRunInstant = [datetimeoffset]::ParseExact(
      $activeRunAtUtc,
      "yyyy-MM-dd'T'HH:mm:ss'Z'",
      [System.Globalization.CultureInfo]::InvariantCulture,
      [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
    )
    $activeValidToUtc = $activeRunInstant.AddHours(96).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $activeFreshUntilUtc = $activeRunInstant.AddHours(24).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $activeUsableUntilUtc = $activeRunInstant.AddHours(30).UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
    $core = $release.components.core
    $pollen = $release.components.pollen
    $coreManifest = Invoke-WebRequest `
      -Uri "$base/$($core.manifest_key)" `
      -UseBasicParsing -TimeoutSec $TimeoutSec
    $pollenManifest = Invoke-WebRequest `
      -Uri "$base/$($pollen.manifest_key)" `
      -UseBasicParsing -TimeoutSec $TimeoutSec
    $coreLatest = [pscustomobject]@{ latest = $core }
    $pollenLatest = [pscustomobject]@{ latest = $pollen }
    if (
      -not (Test-WeatherManifestResponse -Response $coreManifest -Latest $coreLatest -Provider "cams_europe" -ExpectedRunId $activeRunId -ExpectedRunAtUtc $activeRunAtUtc -ExpectedValidToUtc $activeValidToUtc -ExpectedFreshUntilUtc $activeFreshUntilUtc -ExpectedUsableUntilUtc $activeUsableUntilUtc) -or `
      -not (Test-WeatherManifestResponse -Response $pollenManifest -Latest $pollenLatest -Provider "cams_europe_pollen" -ExpectedRunId $activeRunId -ExpectedRunAtUtc $activeRunAtUtc -ExpectedValidToUtc $activeValidToUtc -ExpectedFreshUntilUtc $activeFreshUntilUtc -ExpectedUsableUntilUtc $activeUsableUntilUtc)
    ) { return $false }

    if ($RequireCurrent) {
      $now = [datetimeoffset]::UtcNow
      if ($now -lt $activeRunInstant) { return $false }
      if ($now -gt $activeRunInstant.AddHours(30)) {
        if ($now -gt $activeRunInstant.AddHours(36)) { return $false }
        $continuityResponse = Invoke-WebRequest `
          -Uri "$base/weather/v1/families/cams/runs/$activeRunId/continuity.json" `
          -UseBasicParsing -TimeoutSec $TimeoutSec
        return Test-CamsContinuityResponse -Response $continuityResponse `
          -ReleaseResponse $releaseResponse -FamilyLatest $FamilyLatest -Now $now
      }
    }
    return $true
  } catch {
    return $false
  }
}

function Test-AtomicWeatherContract {
  param([string]$BaseUrl)
  $base = $BaseUrl.TrimEnd("/")
  $iconResponse = Invoke-WebRequest `
    -Uri "$base/weather/v1/icon2i/latest.json" `
    -UseBasicParsing -TimeoutSec 2
  $familyResponse = Invoke-WebRequest `
    -Uri "$base/weather/v1/families/cams/latest.json" `
    -UseBasicParsing -TimeoutSec 2
  if ([int]$iconResponse.StatusCode -ne 200 -or [int]$familyResponse.StatusCode -ne 200) {
    return $false
  }
  $iconLatest = $iconResponse.Content | ConvertFrom-Json
  $familyLatest = $familyResponse.Content | ConvertFrom-Json
  if (
    -not (Test-WeatherLatestPayload -Payload $iconLatest -Provider "icon2i" -ExpectedRunId $ExpectedIconRunId) -or `
    -not (Test-CamsFamilyLatestPayload -Payload $familyLatest)
  ) { return $false }

  $iconManifest = Invoke-WebRequest `
    -Uri "$base/weather/v1/icon2i/$($iconLatest.latest.manifest_path)" `
    -UseBasicParsing -TimeoutSec 2
  if (
    -not (Test-WeatherManifestResponse -Response $iconManifest -Latest $iconLatest -Provider "icon2i" -ExpectedRunId $ExpectedIconRunId -ExpectedRunAtUtc $ExpectedIconRunAtUtc -ExpectedValidToUtc $ExpectedIconValidToUtc -ExpectedFreshUntilUtc $IconFreshUntilUtc -ExpectedUsableUntilUtc $IconUsableUntilUtc) -or `
    -not (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $familyLatest -TimeoutSec 2)
  ) { return $false }

  return `
    (Test-WeatherObjectBlocked -Url "$base/weather/v1/cams_europe/latest.json") -and `
    (Test-WeatherObjectBlocked -Url "$base/weather/v1/cams_europe_pollen/latest.json")
}

function Test-CurrentReadOnlyWeatherContract {
  param([string]$BaseUrl)
  $base = $BaseUrl.TrimEnd("/")
  try {
    $iconResponse = Invoke-WebRequest `
      -Uri "$base/weather/v1/icon2i/latest.json" `
      -UseBasicParsing -TimeoutSec 30
    $familyResponse = Invoke-WebRequest `
      -Uri "$base/weather/v1/families/cams/latest.json" `
      -UseBasicParsing -TimeoutSec 30
    if ([int]$iconResponse.StatusCode -ne 200 -or [int]$familyResponse.StatusCode -ne 200) {
      return $false
    }
    $iconLatest = $iconResponse.Content | ConvertFrom-Json
    $familyLatest = $familyResponse.Content | ConvertFrom-Json
    $iconRunId = [string]$iconLatest.latest.source_run_id
    if (
      [int]$iconLatest.schema_version -ne 1 -or `
      [string]$iconLatest.kind -cne "meteofriul.weather.latest" -or `
      [string]$iconLatest.provider -cne "icon2i" -or `
      [string]$iconLatest.catalog.version -cne $ExpectedCatalogVersion -or `
      [string]$iconLatest.catalog.sha256 -cne $ExpectedCatalogSha256 -or `
      [int]$iconLatest.catalog.municipality_count -ne $ExpectedMunicipalityCount -or `
      $iconRunId -cnotmatch "^\d{8}T\d{6}Z$" -or `
      [string]$iconLatest.latest.manifest_path -cne "runs/$iconRunId/manifest.json" -or `
      [int]$iconLatest.latest.manifest_json_bytes -le 0 -or `
      [string]$iconLatest.latest.manifest_sha256 -cnotmatch "^[0-9a-f]{64}$" -or `
      -not (Test-CamsFamilyLatestPayload -Payload $familyLatest)
    ) { return $false }

    $manifestResponse = Invoke-WebRequest `
      -Uri "$base/weather/v1/icon2i/$($iconLatest.latest.manifest_path)" `
      -UseBasicParsing -TimeoutSec 30
    if ([int]$manifestResponse.StatusCode -ne 200) { return $false }
    $manifestBytes = [System.Text.Encoding]::UTF8.GetBytes([string]$manifestResponse.Content)
    if (
      $manifestBytes.Length -ne [int]$iconLatest.latest.manifest_json_bytes -or `
      (Get-ResponseSha256 -Response $manifestResponse) -cne [string]$iconLatest.latest.manifest_sha256
    ) { return $false }
    $manifest = $manifestResponse.Content | ConvertFrom-Json
    $validFrom = Convert-CanonicalUtcToInstant `
      -Value $manifest.valid_from `
      -Label "ICON cloud manifest valid_from"
    $usableUntil = Convert-CanonicalUtcToInstant `
      -Value $manifest.freshness.usable_until `
      -Label "ICON cloud manifest usable_until"
    $now = [datetimeoffset]::UtcNow
    return `
      [int]$manifest.schema_version -eq 1 -and `
      [string]$manifest.kind -ceq "meteofriul.weather.run_manifest" -and `
      [string]$manifest.provider -ceq "icon2i" -and `
      [string]$manifest.source_run_id -ceq $iconRunId -and `
      [string]$manifest.catalog.version -ceq $ExpectedCatalogVersion -and `
      [string]$manifest.catalog.sha256 -ceq $ExpectedCatalogSha256 -and `
      [int]$manifest.catalog.municipality_count -eq $ExpectedMunicipalityCount -and `
      @($manifest.objects.PSObject.Properties).Count -eq $ExpectedMunicipalityCount -and `
      $now -ge $validFrom -and `
      $now -le $usableUntil -and `
      (Test-CamsFamilyArtifacts -BaseUrl $base -FamilyLatest $familyLatest -TimeoutSec 30 -RequireCurrent)
  } catch {
    return $false
  }
}

function Convert-CanonicalUtcSecond {
  param($Value, [string]$Label)
  if ($Value -is [datetime]) {
    $parsed = [datetimeoffset]::new($Value.ToUniversalTime())
  } elseif ($Value -is [datetimeoffset]) {
    $parsed = $Value.ToUniversalTime()
  } else {
    try {
      $parsed = [datetimeoffset]::ParseExact(
        [string]$Value,
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
      )
    } catch {
      throw "$Label non contiene un istante UTC canonico: $Value"
    }
  }
  return $parsed.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
}

function Convert-CanonicalUtcToRunId {
  param($Value, [string]$Label)
  $canonical = Convert-CanonicalUtcSecond -Value $Value -Label $Label
  return $canonical.Replace("-", "").Replace(":", "")
}

function Convert-CanonicalRunIdToUtcSecond {
  param($Value, [string]$Label)
  $text = [string]$Value
  if ($text -cnotmatch "^\d{8}T\d{6}Z$") {
    throw "$Label non contiene un run ID UTC canonico: $Value"
  }
  try {
    $instant = [datetimeoffset]::ParseExact(
      $text,
      "yyyyMMdd'T'HHmmss'Z'",
      [System.Globalization.CultureInfo]::InvariantCulture,
      [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
    )
  } catch {
    throw "$Label non contiene un run ID UTC valido: $Value"
  }
  return $instant.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
}

function Convert-CanonicalUtcToInstant {
  param($Value, [string]$Label, [switch]$RequireWholeHour)
  $canonical = Convert-CanonicalUtcSecond -Value $Value -Label $Label
  $instant = [datetimeoffset]::ParseExact(
    $canonical,
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::AssumeUniversal -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
  )
  if ($RequireWholeHour -and ($instant.Minute -ne 0 -or $instant.Second -ne 0)) {
    throw "$Label deve essere allineato a un'ora UTC intera: $canonical"
  }
  return $instant
}

function Format-CanonicalUtcSecond {
  param([datetimeoffset]$Value)
  return $Value.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
}

function Get-ClientFreshnessWindow {
  param(
    [ValidateSet("icon2i", "cams_europe")][string]$Provider,
    [string]$RunAtUtc,
    [string]$ValidToUtc
  )
  $run = Convert-CanonicalUtcToInstant -Value $RunAtUtc -Label "$Provider run" -RequireWholeHour
  $validTo = Convert-CanonicalUtcToInstant -Value $ValidToUtc -Label "$Provider valid_to" -RequireWholeHour
  if ($Provider -eq "icon2i") {
    $freshCap = $validTo.AddHours(-48)
    $usableCap = $validTo.AddHours(-48)
    $fresh = if ($run.AddHours(18) -lt $freshCap) { $run.AddHours(18) } else { $freshCap }
    $usable = if ($run.AddHours(30) -lt $usableCap) { $run.AddHours(30) } else { $usableCap }
  } else {
    $fresh = if ($run.AddHours(24) -lt $validTo) { $run.AddHours(24) } else { $validTo }
    $usable = if ($run.AddHours(30) -lt $validTo) { $run.AddHours(30) } else { $validTo }
  }
  if ($fresh -lt $run -or $usable -lt $fresh) {
    throw "$Provider non copre la finestra client prevista dal contratto v1."
  }
  return [pscustomobject]@{
    FreshUntilUtc = Format-CanonicalUtcSecond -Value $fresh
    UsableUntilUtc = Format-CanonicalUtcSecond -Value $usable
  }
}

function Assert-FileSizeBound {
  param([string]$Label, [string]$Path, [int64]$MaximumBytes)
  $file = Get-Item -LiteralPath $Path
  if ($file.PSIsContainer -or [int64]$file.Length -lt 1 -or [int64]$file.Length -gt $MaximumBytes) {
    throw "$Label deve essere un file tra 1 e $MaximumBytes byte: $Path"
  }
  return $file
}

function Assert-PayloadReportBinding {
  param(
    [string]$Label,
    [string]$PayloadPath,
    $Report
  )
  $expectedDigest = [string]$Report.payload_sha256
  if ($expectedDigest -cnotmatch "^[0-9a-f]{64}$") {
    throw "Report $Label privo di uno SHA-256 canonico."
  }
  try {
    $expectedBytes = [int64]$Report.payload_bytes
  } catch {
    throw "Report $Label privo di una dimensione payload valida."
  }
  $payloadFile = Get-Item -LiteralPath $PayloadPath
  if ($expectedBytes -lt 1 -or [int64]$payloadFile.Length -ne $expectedBytes) {
    throw "Dimensione payload $Label diversa dal report verificato."
  }
  $digest = (Get-FileHash -LiteralPath $PayloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($digest -cne $expectedDigest) {
    throw "SHA-256 payload $Label diverso dal report verificato."
  }
}

function Assert-ExactHourlyTimeline {
  param(
    [string]$Label,
    [object[]]$Values,
    [string]$RunAtUtc,
    [int]$ExpectedCount
  )
  if ($Values.Count -ne $ExpectedCount) {
    throw "$Label deve contenere esattamente $ExpectedCount istanti orari."
  }
  $run = Convert-CanonicalUtcToInstant -Value $RunAtUtc -Label "$Label run" -RequireWholeHour
  for ($index = 0; $index -lt $ExpectedCount; $index += 1) {
    $observed = Convert-CanonicalUtcSecond -Value $Values[$index] -Label "$Label indice $index"
    $expected = Format-CanonicalUtcSecond -Value $run.AddHours($index)
    if ($observed -cne $expected) {
      throw "$Label non e una sequenza oraria completa al passo ${index}: atteso $expected, trovato $observed."
    }
  }
}

function Assert-ObjectDatabaseTarget {
  foreach ($artifactPath in @($IconPayload, $IconReport, $CamsPayload, $CamsReport)) {
    if ([string]::Equals($ObjectDatabase, $artifactPath, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Object DB non puo coincidere con un artefatto sorgente: $ObjectDatabase"
    }
  }
  if ([System.IO.Directory]::Exists($ObjectDatabase)) {
    throw "Object DB indica una directory, non un file: $ObjectDatabase"
  }
  $databaseParent = Split-Path -Parent $ObjectDatabase
  if (-not [System.IO.Directory]::Exists($databaseParent)) {
    throw "La directory dell'Object DB deve gia esistere; il launcher non la crea automaticamente: $databaseParent"
  }
}

function Get-SelectedArtifactMetadata {
  Assert-FileSizeBound -Label "Report ICON" -Path $IconReport -MaximumBytes (4 * 1024 * 1024) | Out-Null
  Assert-FileSizeBound -Label "Report CAMS" -Path $CamsReport -MaximumBytes (4 * 1024 * 1024) | Out-Null
  Assert-FileSizeBound -Label "Payload ICON" -Path $IconPayload -MaximumBytes (32 * 1024 * 1024) | Out-Null
  Assert-FileSizeBound -Label "Payload CAMS" -Path $CamsPayload -MaximumBytes (64 * 1024 * 1024) | Out-Null
  try {
    $iconReportValue = Get-Content -Raw -LiteralPath $IconReport | ConvertFrom-Json
    $camsReportValue = Get-Content -Raw -LiteralPath $CamsReport | ConvertFrom-Json
  } catch {
    throw "Report meteo non leggibili come JSON: $($_.Exception.Message)"
  }
  Assert-PayloadReportBinding -Label "ICON" -PayloadPath $IconPayload -Report $iconReportValue
  Assert-PayloadReportBinding -Label "CAMS" -PayloadPath $CamsPayload -Report $camsReportValue
  try {
    $iconPayloadValue = Get-Content -Raw -LiteralPath $IconPayload | ConvertFrom-Json
    $camsPayloadValue = Get-Content -Raw -LiteralPath $CamsPayload | ConvertFrom-Json
  } catch {
    throw "Payload meteo non leggibili come JSON: $($_.Exception.Message)"
  }

  if ([int]$iconPayloadValue.schema_version -ne 1 -or $iconPayloadValue.status -ne "partial_pilot_not_production") {
    throw "Il payload ICON non e un artefatto pilota verificato."
  }
  if (
    [int]$camsPayloadValue.schema_version -ne 2 -or `
    $camsPayloadValue.kind -ne "cams_region_point_extraction"
  ) {
    throw "Il payload CAMS non e un'estrazione regionale verificata."
  }

  $iconRunAtUtc = Convert-CanonicalUtcSecond -Value $iconPayloadValue.run_utc -Label "Payload ICON run_utc"
  $iconReportRunAtUtc = Convert-CanonicalUtcSecond -Value $iconReportValue.run_utc -Label "Report ICON run_utc"
  if ($iconRunAtUtc -cne $iconReportRunAtUtc) {
    throw "Run ICON discordante tra payload e report."
  }
  $camsRunAtUtc = Convert-CanonicalUtcSecond -Value $camsPayloadValue.run_utc -Label "Payload CAMS run_utc"
  if ($camsReportValue.PSObject.Properties.Name -contains "run_utc") {
    $camsReportRunAtUtc = Convert-CanonicalUtcSecond -Value $camsReportValue.run_utc -Label "Report CAMS run_utc"
    if ($camsRunAtUtc -cne $camsReportRunAtUtc) {
      throw "Run CAMS discordante tra payload e report."
    }
  }

  if (
    [string]$iconReportValue.catalog_sha256 -cne $ExpectedCatalogSha256 -or `
    (($iconPayloadValue.PSObject.Properties.Name -contains "catalog_sha256") -and `
      [string]$iconPayloadValue.catalog_sha256 -cne $ExpectedCatalogSha256) -or `
    [string]$camsReportValue.catalog_sha256 -cne $ExpectedCatalogSha256 -or `
    [string]$camsPayloadValue.catalog_sha256 -cne $ExpectedCatalogSha256
  ) {
    throw "Gli artefatti selezionati non corrispondono al catalogo ufficiale atteso."
  }

  $iconMunicipalities = @($iconPayloadValue.municipalities)
  $camsMunicipalities = @($camsPayloadValue.municipalities)
  if (
    [int]$iconReportValue.municipalities -ne $ExpectedMunicipalityCount -or `
    [int]$iconReportValue.native_instants -ne 73 -or `
    [int]$camsReportValue.analysis.municipalities -ne $ExpectedMunicipalityCount -or `
    [int]$camsReportValue.analysis.variables -ne 28 -or `
    [int]$camsReportValue.analysis.hourly_instants -ne 97 -or `
    $iconMunicipalities.Count -ne $ExpectedMunicipalityCount -or `
    $camsMunicipalities.Count -ne $ExpectedMunicipalityCount
  ) {
    throw "Gli artefatti selezionati non hanno la copertura completa attesa."
  }

  $iconMunicipalityIds = @($iconMunicipalities | ForEach-Object { [string]$_.id })
  $camsMunicipalityIds = @($camsMunicipalities | ForEach-Object { [string]$_.id })
  if (
    @($iconMunicipalityIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0 -or `
    @($camsMunicipalityIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0 -or `
    @($iconMunicipalityIds | Sort-Object -Unique).Count -ne $ExpectedMunicipalityCount -or `
    @($camsMunicipalityIds | Sort-Object -Unique).Count -ne $ExpectedMunicipalityCount -or `
    (($iconMunicipalityIds | Sort-Object) -join "`n") -cne (($camsMunicipalityIds | Sort-Object) -join "`n")
  ) {
    throw "Gli artefatti ICON/CAMS non descrivono gli stessi 215 Comuni univoci."
  }

  $iconExpectedTimes = @()
  $iconRunInstant = Convert-CanonicalUtcToInstant -Value $iconRunAtUtc -Label "Payload ICON run_utc" -RequireWholeHour
  for ($lead = 0; $lead -lt 73; $lead += 1) {
    $iconExpectedTimes += Format-CanonicalUtcSecond -Value $iconRunInstant.AddHours($lead)
  }
  foreach ($municipality in $iconMunicipalities) {
    $hourly = @($municipality.hourly)
    if ($hourly.Count -ne 73) {
      throw "ICON Comune $($municipality.id) non contiene 73 campioni orari."
    }
    for ($lead = 0; $lead -lt 73; $lead += 1) {
      $observed = Convert-CanonicalUtcSecond -Value $hourly[$lead].valid_at_utc -Label "ICON $($municipality.id) ora $lead"
      if ($observed -cne $iconExpectedTimes[$lead]) {
        throw "Timeline ICON non completa per $($municipality.id) al passo $lead."
      }
    }
  }

  $camsTimes = @($camsPayloadValue.times_utc)
  Assert-ExactHourlyTimeline -Label "CAMS times_utc" -Values $camsTimes -RunAtUtc $camsRunAtUtc -ExpectedCount 97
  $camsVariables = @($camsPayloadValue.variables)
  $camsVariableIds = @($camsVariables | ForEach-Object { [string]$_.id })
  if (
    $camsVariables.Count -ne 28 -or `
    @($camsVariableIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0 -or `
    @($camsVariableIds | Sort-Object -Unique).Count -ne 28
  ) {
    throw "Il payload CAMS non contiene 28 variabili univoche."
  }
  $expectedVariableSet = ($camsVariableIds | Sort-Object) -join "`n"
  $camsCells = @($camsPayloadValue.cells)
  if ($camsCells.Count -lt 1) {
    throw "Il payload CAMS non contiene celle decodificate."
  }
  $camsCellIds = @($camsCells | ForEach-Object { [string]$_.id })
  if (
    @($camsCellIds | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0 -or `
    @($camsCellIds | Sort-Object -Unique).Count -ne $camsCells.Count
  ) {
    throw "Il payload CAMS contiene identificatori cella mancanti o duplicati."
  }
  $knownCells = @{}
  foreach ($cellId in $camsCellIds) { $knownCells[$cellId] = $true }
  foreach ($municipality in $camsMunicipalities) {
    if (-not $knownCells.ContainsKey([string]$municipality.cell_id)) {
      throw "CAMS Comune $($municipality.id) fa riferimento a una cella sconosciuta."
    }
  }
  foreach ($cell in $camsCells) {
    $valueNames = @($cell.values.PSObject.Properties | ForEach-Object { [string]$_.Name } | Sort-Object)
    $rawValueNames = @($cell.raw_values.PSObject.Properties | ForEach-Object { [string]$_.Name } | Sort-Object)
    if (($valueNames -join "`n") -cne $expectedVariableSet -or ($rawValueNames -join "`n") -cne $expectedVariableSet) {
      throw "Cella CAMS $($cell.id) priva delle 28 serie complete."
    }
    foreach ($variableId in $camsVariableIds) {
      $values = @($cell.values.PSObject.Properties[$variableId].Value)
      $rawValues = @($cell.raw_values.PSObject.Properties[$variableId].Value)
      if ($values.Count -ne 97 -or $rawValues.Count -ne 97) {
        throw "Cella CAMS $($cell.id), variabile $variableId, non contiene 97 campioni."
      }
    }
  }

  $iconRunId = Convert-CanonicalUtcToRunId -Value $iconRunAtUtc -Label "Payload ICON run_utc"
  $camsRunId = Convert-CanonicalUtcToRunId -Value $camsRunAtUtc -Label "Payload CAMS run_utc"
  $iconValidToUtc = $iconExpectedTimes[-1]
  $camsValidToUtc = Convert-CanonicalUtcSecond -Value $camsTimes[-1] -Label "CAMS ultimo istante"
  $iconWindow = Get-ClientFreshnessWindow -Provider "icon2i" -RunAtUtc $iconRunAtUtc -ValidToUtc $iconValidToUtc
  $camsWindow = Get-ClientFreshnessWindow -Provider "cams_europe" -RunAtUtc $camsRunAtUtc -ValidToUtc $camsValidToUtc

  # Detect a concurrent or accidental replacement after parsing. Source
  # artifacts are immutable inputs; only the selected object DB may be written.
  Assert-PayloadReportBinding -Label "ICON" -PayloadPath $IconPayload -Report $iconReportValue
  Assert-PayloadReportBinding -Label "CAMS" -PayloadPath $CamsPayload -Report $camsReportValue

  return [pscustomobject]@{
    IconRunId = $iconRunId
    CamsRunId = $camsRunId
    IconRunAtUtc = $iconRunAtUtc
    CamsRunAtUtc = $camsRunAtUtc
    IconValidToUtc = $iconValidToUtc
    CamsValidToUtc = $camsValidToUtc
    IconFreshUntilUtc = $iconWindow.FreshUntilUtc
    CamsFreshUntilUtc = $camsWindow.FreshUntilUtc
    IconUsableUntilUtc = $iconWindow.UsableUntilUtc
    CamsUsableUntilUtc = $camsWindow.UsableUntilUtc
  }
}

function Set-SelectedArtifactMetadata {
  param($Metadata)
  $script:ExpectedIconRunId = [string]$Metadata.IconRunId
  $script:ExpectedCamsRunId = [string]$Metadata.CamsRunId
  $script:ExpectedIconRunAtUtc = [string]$Metadata.IconRunAtUtc
  $script:ExpectedCamsRunAtUtc = [string]$Metadata.CamsRunAtUtc
  $script:ExpectedIconValidToUtc = [string]$Metadata.IconValidToUtc
  $script:ExpectedCamsValidToUtc = [string]$Metadata.CamsValidToUtc
  $script:IconFreshUntilUtc = [string]$Metadata.IconFreshUntilUtc
  $script:CamsFreshUntilUtc = [string]$Metadata.CamsFreshUntilUtc
  $script:IconUsableUntilUtc = [string]$Metadata.IconUsableUntilUtc
  $script:CamsUsableUntilUtc = [string]$Metadata.CamsUsableUntilUtc
}

function Assert-IconClockWindow {
  $now = Get-PilotClockNow
  $iconStart = [datetimeoffset]::Parse($ExpectedIconRunAtUtc)
  # The pilot uses ICON_FORECAST_WINDOW_POLICY (12 real future hourly rows),
  # independently of the unchanged v1 manifest's legacy 48-hour window.
  $iconEnd = [datetimeoffset]::Parse($ExpectedIconValidToUtc)
  $firstFutureHour = [math]::Ceiling($now.ToUnixTimeMilliseconds() / 3600000.0) * 3600000.0
  $futureHours = [math]::Floor(($iconEnd.ToUnixTimeMilliseconds() - $firstFutureHour) / 3600000.0) + 1
  if ($now -lt $iconStart) {
    throw "Lo snapshot ICON selezionato non e ancora valido rispetto all'orologio UTC."
  }
  if ($futureHours -lt 12) {
    throw "Lo snapshot ICON selezionato non copre le 12 ore future richieste dal client pilota."
  }
}

function Get-CamsClockStatus {
  $now = Get-PilotClockNow
  $start = [datetimeoffset]::Parse($ExpectedCamsRunAtUtc)
  $end = [datetimeoffset]::Parse($CamsUsableUntilUtc)
  if ($now -lt $start) { return "not-yet-valid" }
  if ($now -gt $end) { return "degraded-expired" }
  return "usable"
}

function Write-CamsClockStatus {
  $status = Get-CamsClockStatus
  if ($status -eq "usable") {
    Write-Host "CAMS utilizzabile dal client fino a $CamsUsableUntilUtc."
    return
  }
  if ($status -eq "not-yet-valid") {
    Write-Warning "CAMS non e ancora valido; ICON puo comunque essere provato senza fallback Open-Meteo."
    return
  }
  Write-Warning "CAMS e oltre la finestra v1 di 30 ore. Il client puo usare fino a 36 ore solo con la policy continuity verificata; altrimenti resta degradato. ICON richiede almeno 12 ore future native."
}

function Convert-RoundTripUtc {
  param($Value)
  if ($Value -is [datetime]) { return $Value.ToUniversalTime() }
  if ($Value -is [datetimeoffset]) { return $Value.UtcDateTime }
  return [datetimeoffset]::ParseExact(
    [string]$Value,
    "o",
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::RoundtripKind
  ).UtcDateTime
}

function Get-ExactProcess {
  param([int]$ProcessId, $StartedAtUtc, [string]$Executable)
  try {
    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    $savedStart = Convert-RoundTripUtc -Value $StartedAtUtc
    $actualStart = $process.StartTime.ToUniversalTime()
    if ([math]::Abs(($actualStart - $savedStart).TotalMilliseconds) -gt 100) { return $null }
    if (
      [System.IO.Path]::GetFullPath([string]$process.Path) -ne `
      [System.IO.Path]::GetFullPath($Executable)
    ) { return $null }
    return $process
  } catch {
    return $null
  }
}

function Get-StaticOwnershipRecord {
  param($Service)
  if (-not [System.IO.File]::Exists($Service.PidFile)) { return $null }
  try {
    $record = Get-Content -Raw -LiteralPath $Service.PidFile | ConvertFrom-Json
    $savedIdentity = @($record.identity | ForEach-Object { [string]$_ })
    if (($savedIdentity -join "`n") -ne (@($Service.Identity) -join "`n")) { return $null }
    $expectedLaunchProfile = if (
      $Service.PSObject.Properties.Name -contains "LaunchProfile"
    ) { [string]$Service.LaunchProfile } else { "" }
    if ($expectedLaunchProfile) {
      # Version-2 records created before profiles existed belong to the
      # original offline launcher. This preserves Stop and offline reuse while
      # preventing a cloud launch from silently reusing an offline Vite proxy.
      $recordedLaunchProfile = if (
        $record.PSObject.Properties.Name -contains "launch_profile" -and `
        -not [string]::IsNullOrWhiteSpace([string]$record.launch_profile)
      ) { [string]$record.launch_profile } elseif ($Service.Name -eq "community-pilot") { "community-local-v1" } else { "weather-offline-v1" }
      if ($recordedLaunchProfile -cne $expectedLaunchProfile) { return $null }
    }
    $isVersion2 = $record.PSObject.Properties.Name -contains "schema_version" -and `
      [int]$record.schema_version -eq 2
    if ($isVersion2) {
      if ($record.service -ne $Service.Name -or [int]$record.port -ne [int]$Service.Port) { return $null }
      $wrapper = $record.wrapper
    } else {
      $wrapper = [pscustomobject]@{
        pid = $record.pid
        started_at_utc = $record.started_at_utc
        executable = $record.executable
      }
    }
    if (
      $null -eq $wrapper -or `
      [int]$wrapper.pid -le 0 -or `
      -not $wrapper.started_at_utc -or `
      -not $wrapper.executable
    ) { return $null }
    return [pscustomobject]@{
      IsVersion2 = $isVersion2
      Wrapper = $wrapper
      Metadata = $record
    }
  } catch {
    return $null
  }
}

function Get-ReclaimableStaleOwnershipRecord {
  param($Service)
  if (-not [System.IO.File]::Exists($Service.PidFile)) { return $null }
  try {
    $record = Get-Content -Raw -LiteralPath $Service.PidFile | ConvertFrom-Json
    if (
      -not ($record.PSObject.Properties.Name -contains "schema_version") -or `
      [int]$record.schema_version -ne 2 -or `
      [string]$record.service -cne [string]$Service.Name -or `
      [int]$record.port -ne [int]$Service.Port -or `
      $null -eq $record.wrapper
    ) { return $null }
    $metadata = @($record.wrapper)
    if ($null -ne $record.listener) { $metadata += @($record.listener) }
    $metadata += @($record.owned_processes)
    foreach ($item in $metadata) {
      if (
        $null -eq $item -or `
        [int]$item.pid -le 0 -or `
        [string]::IsNullOrWhiteSpace([string]$item.started_at_utc) -or `
        [string]::IsNullOrWhiteSpace([string]$item.executable)
      ) { return $null }
      if (Test-ExactProcessMetadataAlive -Metadata $item) { return $null }
    }
    return $record
  } catch {
    return $null
  }
}

function Get-SavedProcessRecord {
  param($Service)
  $static = Get-StaticOwnershipRecord -Service $Service
  if (-not $static) { return $null }
  try {
    $processId = [int]$static.Wrapper.pid
    $process = Get-ExactProcess `
      -ProcessId $processId `
      -StartedAtUtc $static.Wrapper.started_at_utc `
      -Executable ([string]$static.Wrapper.executable)
    if (-not $process) { return $null }
    return [pscustomobject]@{
      Pid = $processId
      Process = $process
      Wrapper = $static.Wrapper
      Metadata = $static.Metadata
      IsVersion2 = $static.IsVersion2
    }
  } catch {
    return $null
  }
}

function Get-OwnedServiceRecord {
  param($Service, [switch]$AllowNoListener)
  $saved = Get-SavedProcessRecord -Service $Service
  if (-not $saved) { return $null }
  $snapshot = Get-ProcessTreeSnapshot
  $descendants = @(Get-DescendantRecords -AncestorId $saved.Pid -Snapshot $snapshot)
  $listeners = @(Get-ListenerRecords -Port $Service.Port)
  if ($listeners.Count -eq 0) {
    if ($AllowNoListener) {
      return [pscustomobject]@{ Saved = $saved; Listener = $null; Descendants = $descendants }
    }
    return $null
  }
  if (@($listeners | Where-Object { $_.Address -notin @("127.0.0.1", "::1", "[::1]") }).Count -gt 0) {
    return $null
  }
  $listenerPids = @($listeners | ForEach-Object { [int]$_.Pid } | Sort-Object -Unique)
  if ($listenerPids.Count -ne 1) { return $null }
  $listenerPid = $listenerPids[0]
  if (-not (Test-ProcessDescendsFrom -ProcessId $listenerPid -AncestorId $saved.Pid -Snapshot $snapshot)) {
    return $null
  }
  try {
    $listenerProcess = Get-Process -Id $listenerPid -ErrorAction Stop
    $listenerExecutable = [System.IO.Path]::GetFullPath([string]$listenerProcess.Path)
    $listenerName = [System.IO.Path]::GetFileName($listenerExecutable)
    if ($listenerName -notin @($Service.ListenerExecutableNames)) { return $null }
    if ($listenerProcess.StartTime.ToUniversalTime() -lt $saved.Process.StartTime.ToUniversalTime().AddSeconds(-1)) {
      return $null
    }
    $recordedExpected = if (
      $saved.Metadata.PSObject.Properties.Name -contains "expected_listener_executable"
    ) { [string]$saved.Metadata.expected_listener_executable } else { "" }
    if (
      $recordedExpected -and `
      $listenerExecutable -ne [System.IO.Path]::GetFullPath($recordedExpected)
    ) { return $null }
  } catch {
    return $null
  }
  return [pscustomobject]@{
    Saved = $saved
    Listener = [pscustomobject]@{
      Pid = $listenerPid
      Process = $listenerProcess
      Executable = $listenerExecutable
    }
    Descendants = $descendants
  }
}

function Test-NationalPilotReady {
  param([string]$BaseUrl, [int]$TimeoutSec = 3)
  try {
    $pointer = Invoke-RestMethod -Uri "$BaseUrl/weather/v2/icon2i/pilot.json" -TimeoutSec $TimeoutSec
    return $pointer.kind -eq "meteofriul.weather.icon.national.local_pilot_pointer" -and `
      $pointer.contract -eq "weather/v2/icon2i" -and `
      $pointer.status -eq "experimental_local_pilot_only" -and `
      $pointer.catalog.municipality_count -eq 7894 -and `
      $pointer.catalog.sha256 -eq "ee856c27ec135be45c4c7eaaf946158fdfc61bc83135cf9b6fbbce892ce3cf0d"
  } catch { return $false }
}

function Test-ServiceHealth {
  param([string]$Name, [string]$Url)
  try {
    $healthTimeout = if ($Name -eq "community-pilot" -and $CommunityCloudStore) { 25 } else { 2 }
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $healthTimeout
    if ([int]$response.StatusCode -ne 200) { return $false }
    if ($Name -eq "community-pilot") {
      $payload = $response.Content | ConvertFrom-Json
      if ($CommunityCloudStore) {
        return $payload.kind -eq "meteofriul.community.loopback-cloud-pilot.v1" -and `
          $payload.storage -eq "pilot-cloud" -and $payload.project_id -eq "meteofriul-pilot-20260906" -and `
          $payload.scope -eq "IT" -and $payload.published -eq $false -and $payload.ok -eq $true
      }
      return $payload.kind -eq "meteofriul.community.local-pilot.v1" -and `
        $payload.storage -eq "sqlite" -and $payload.scope -eq "IT" -and `
        $payload.published -eq $false
    }
    if ($Name -eq "backend") {
      $payload = $response.Content | ConvertFrom-Json
      $policy = $payload.weather_provider_policy
      if (
        $payload.status -ne "ok" -or `
        $null -eq $policy -or `
        -not [bool]$policy.valid -or `
        -not [bool]$policy.local_weather_pilot_requested -or `
        [bool]$policy.open_meteo_enabled -or `
        -not [bool]$policy.local_weather_pilot_ready
      ) { return $false }
      $identity = Invoke-WebRequest -Uri "http://127.0.0.1:8002/api/openapi.json" -UseBasicParsing -TimeoutSec 2
      $schema = $identity.Content | ConvertFrom-Json
      return [int]$identity.StatusCode -eq 200 -and $schema.info.title -eq "Meteo Friul UI3 API"
    }
    if ($Name -eq "data-plane") {
      if ($WeatherCloud -or $NationalOnly -or $NationalCloud) { return $false }
      Assert-IconClockWindow
      return Test-AtomicWeatherContract -BaseUrl "http://127.0.0.1:8781"
    }
    if ($Name -eq "frontend") {
      if ($StableFrontend) {
        $marker = Invoke-WebRequest -Uri "http://127.0.0.1:5174/" -UseBasicParsing -TimeoutSec 2
        if (
          [int]$marker.StatusCode -ne 200 -or `
          -not $marker.Content.Contains('name="meteofriul-local-weather-pilot" content="stable-static-v1"') -or `
          $marker.Content.Contains("/@vite/client")
        ) { return $false }
      } else {
        $marker = Invoke-WebRequest -Uri "http://127.0.0.1:5174/src/services/localWeatherPilot.js" -UseBasicParsing -TimeoutSec 2
        if ([int]$marker.StatusCode -ne 200 -or -not $marker.Content.Contains("/__local-weather-pilot")) {
          return $false
        }
      }
      $backendHealth = Invoke-WebRequest `
        -Uri "http://127.0.0.1:5174/api/healthz" `
        -UseBasicParsing -TimeoutSec 2
      $backendIdentity = Invoke-WebRequest `
        -Uri "http://127.0.0.1:5174/api/openapi.json" `
        -UseBasicParsing -TimeoutSec 2
      if (
        [int]$backendHealth.StatusCode -ne 200 -or `
        ($backendHealth.Content | ConvertFrom-Json).status -ne "ok" -or `
        -not [bool](($backendHealth.Content | ConvertFrom-Json).weather_provider_policy.local_weather_pilot_ready) -or `
        [bool](($backendHealth.Content | ConvertFrom-Json).weather_provider_policy.open_meteo_enabled) -or `
        [int]$backendIdentity.StatusCode -ne 200 -or `
        ($backendIdentity.Content | ConvertFrom-Json).info.title -ne "Meteo Friul UI3 API"
      ) { return $false }
      if ($WeatherCloud) {
        return Test-CurrentReadOnlyWeatherContract `
          -BaseUrl "http://127.0.0.1:5174/__local-weather-pilot"
      }
      if ($NationalCloud) {
        return (Test-CurrentReadOnlyWeatherContract -BaseUrl "http://127.0.0.1:5174/__local-weather-pilot") -and `
          (Test-NationalPilotReady -BaseUrl "http://127.0.0.1:5174/__local-weather-national" -TimeoutSec 25)
      }
      if ($NationalOnly) {
        return Test-NationalPilotReady -BaseUrl "http://127.0.0.1:5174/__local-weather-national"
      }
      Assert-IconClockWindow
      return Test-AtomicWeatherContract -BaseUrl "http://127.0.0.1:5174/__local-weather-pilot"
    }
  } catch {
    return $false
  }
  return $false
}

function Get-ServiceState {
  param($Service)
  $listeners = @(Get-ListenerRecords -Port $Service.Port)
  $listenerPids = @($listeners | ForEach-Object { [int]$_.Pid } | Sort-Object -Unique)
  $listenerPid = if ($listenerPids.Count -eq 1) { $listenerPids[0] } else { $null }
  $loopbackOnly = $listeners.Count -gt 0 -and @(
    $listeners | Where-Object { $_.Address -notin @("127.0.0.1", "::1", "[::1]") }
  ).Count -eq 0
  $processRecognizable = $false
  if ($listenerPid) {
    $exactArguments = if ($Service.PSObject.Properties.Name -contains "ExactArguments") {
      $Service.ExactArguments
    } else {
      $null
    }
    $processRecognizable = Test-ProcessIdentity `
      -ProcessId $listenerPid `
      -Identity $Service.Identity `
      -ExactArguments $exactArguments
  }
  $healthy = Test-ServiceHealth -Name $Service.Name -Url $Service.HealthUrl
  $savedRecord = Get-SavedProcessRecord -Service $Service
  $ownedRecord = if ($savedRecord) { Get-OwnedServiceRecord -Service $Service } else { $null }
  $savedPid = if ($savedRecord) { $savedRecord.Pid } else { $null }
  $identityEstablished = $processRecognizable -or [bool]$ownedRecord
  return [pscustomobject]@{
    Listening = $listeners.Count -gt 0
    ListenerPid = $listenerPid
    ListenerAddresses = @($listeners | ForEach-Object { [string]$_.Address })
    LoopbackOnly = $loopbackOnly
    Recognizable = $healthy -and $loopbackOnly -and $identityEstablished
    ProcessRecognizable = $processRecognizable
    Healthy = $healthy
    SavedPid = $savedPid
  }
}

function Write-ServiceStatus {
  param($Service)
  $state = Get-ServiceState -Service $Service
  $listener = if ($state.ListenerPid) { $state.ListenerPid } else { "-" }
  $addresses = if ($state.ListenerAddresses.Count -gt 0) { $state.ListenerAddresses -join "," } else { "-" }
  $saved = if ($state.SavedPid) { $state.SavedPid } else { "-" }
  Write-Host ("{0,-10} listening:{1,-5} loopback-only:{2,-5} endpoint-healthy:{3,-5} recognizable:{4,-5} process-id-visible:{5,-5} listener:{6}@{7} saved-pid:{8} {9}" -f
    $Service.Name, $state.Listening, $state.LoopbackOnly, $state.Healthy, $state.Recognizable, $state.ProcessRecognizable, $listener, $addresses, $saved, $Service.HealthUrl)
}

function Quote-CmdArgument {
  param([string]$Value)
  if ($Value.Contains('"') -or $Value.Contains("`r") -or $Value.Contains("`n")) {
    throw "Argomento non supportato per il processo nascosto."
  }
  return '"' + $Value + '"'
}

function New-ExactProcessMetadata {
  param($Process, [int]$ParentPid = 0, [int]$Depth = 0)
  $rawExecutable = [string]$Process.Path
  if ([string]::IsNullOrWhiteSpace($rawExecutable)) {
    try { $rawExecutable = [string]$Process.MainModule.FileName } catch { $rawExecutable = "" }
  }
  if ([string]::IsNullOrWhiteSpace($rawExecutable)) {
    throw "Percorso eseguibile non disponibile per PID $($Process.Id)."
  }
  try {
    $executable = [System.IO.Path]::GetFullPath($rawExecutable)
  } catch {
    throw "Percorso eseguibile non valido per PID $($Process.Id): $rawExecutable"
  }
  return [ordered]@{
    pid = [int]$Process.Id
    parent_pid = $ParentPid
    depth = $Depth
    started_at_utc = $Process.StartTime.ToUniversalTime().ToString("o")
    executable = $executable
  }
}

function Write-OwnershipRecord {
  param([string]$Path, $Value, [switch]$CreateNew)
  $json = $Value | ConvertTo-Json -Depth 8 -Compress
  $encoding = [System.Text.UTF8Encoding]::new($false)
  if ($CreateNew) {
    $stream = [System.IO.File]::Open(
      $Path,
      [System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::None
    )
    try {
      $writer = [System.IO.StreamWriter]::new($stream, $encoding)
      try { $writer.Write($json) } finally { $writer.Dispose() }
    } finally {
      $stream.Dispose()
    }
    return
  }
  if (-not [System.IO.File]::Exists($Path)) {
    throw "Record di proprieta scomparso durante l'aggiornamento: $Path"
  }
  $replacementId = [guid]::NewGuid().ToString('N')
  $temporaryPath = "$Path.update.$replacementId"
  $backupPath = "$Path.backup.$replacementId"
  try {
    [System.IO.File]::WriteAllText($temporaryPath, $json, $encoding)
    # Windows PowerShell/.NET Framework rejects a null backup path even
    # though newer runtimes accept it. A unique backup preserves the atomic
    # replace on both hosts and is removed only after the new record exists.
    [System.IO.File]::Replace($temporaryPath, $Path, $backupPath)
  } finally {
    if ([System.IO.File]::Exists($temporaryPath)) {
      Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
    if ([System.IO.File]::Exists($backupPath) -and [System.IO.File]::Exists($Path)) {
      Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue
    }
  }
}

function Save-ServiceOwnershipBinding {
  param($Service)
  $owned = Get-OwnedServiceRecord -Service $Service
  if (-not $owned -or -not $owned.Listener) {
    throw "Impossibile legare listener e wrapper posseduto per $($Service.Name)."
  }
  $wrapper = $owned.Saved.Process
  $ownedProcesses = @()
  foreach ($descendant in @($owned.Descendants | Sort-Object Depth, Pid)) {
    $isListener = [int]$descendant.Pid -eq [int]$owned.Listener.Pid
    try {
      $process = Get-Process -Id ([int]$descendant.Pid) -ErrorAction Stop
      if ($process.StartTime.ToUniversalTime() -lt $wrapper.StartTime.ToUniversalTime().AddSeconds(-1)) {
        throw "Processo discendente anteriore al wrapper."
      }
      $ownedProcesses += New-ExactProcessMetadata `
        -Process $process `
        -ParentPid ([int]$descendant.ParentPid) `
        -Depth ([int]$descendant.Depth)
    } catch {
      if ($isListener) {
        throw "Listener di $($Service.Name) cambiato durante il binding di proprieta."
      }
      # npm/cmd can create short-lived helper processes while the service is
      # starting. They are not required for ownership as long as the exact
      # wrapper and exact listener remain verifiable; a vanished helper must
      # not turn a healthy startup into a false failure.
      continue
    }
  }
  if (@($ownedProcesses | Where-Object { [int]$_.pid -eq $owned.Listener.Pid }).Count -ne 1) {
    throw "Il listener di $($Service.Name) non appartiene allo snapshot dei discendenti."
  }
  $record = [ordered]@{
    schema_version = 2
    service = $Service.Name
    port = [int]$Service.Port
    identity = @($Service.Identity)
    launch_profile = if (
      $Service.PSObject.Properties.Name -contains "LaunchProfile"
    ) { [string]$Service.LaunchProfile } else { $null }
    expected_listener_executable = $owned.Listener.Executable
    binding = "toolhelp_parent_chain"
    wrapper = New-ExactProcessMetadata -Process $wrapper
    listener = New-ExactProcessMetadata -Process $owned.Listener.Process
    owned_processes = $ownedProcesses
    cleanup_paths = if (
      $Service.PSObject.Properties.Name -contains "CleanupPaths"
    ) { @($Service.CleanupPaths) } else { @() }
  }
  Write-OwnershipRecord -Path $Service.PidFile -Value $record
  return $record
}

function Remove-VerifiedPilotCleanupPaths {
  param($Metadata)
  if ($null -eq $Metadata) { return }
  $cleanupPaths = if ($Metadata -is [System.Collections.IDictionary]) {
    if (-not $Metadata.Contains("cleanup_paths")) { return }
    @($Metadata["cleanup_paths"])
  } else {
    if (-not ($Metadata.PSObject.Properties.Name -contains "cleanup_paths")) { return }
    @($Metadata.cleanup_paths)
  }

  $expectedParent = [System.IO.Path]::GetFullPath($PilotTempRoot)
  foreach ($candidate in $cleanupPaths) {
    if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
    $resolved = [System.IO.Path]::GetFullPath([string]$candidate)
    $parent = [System.IO.Path]::GetFullPath((Split-Path -Parent $resolved))
    $leaf = Split-Path -Leaf $resolved
    if (
      -not [string]::Equals($parent, $expectedParent, [System.StringComparison]::OrdinalIgnoreCase) -or `
      $leaf -cnotmatch '^meteofriul-local-weather-pilot-[0-9a-f]{32}$'
    ) {
      throw "Directory temporanea frontend non conforme; nessuna rimozione: $resolved"
    }
    if (-not [System.IO.Directory]::Exists($resolved)) { continue }
    $rootItem = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
    if ($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
      throw "Directory temporanea frontend e un reparse point; nessuna rimozione: $resolved"
    }
    $reparsePoint = Get-ChildItem -LiteralPath $resolved -Force -Recurse -ErrorAction Stop |
      Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint } |
      Select-Object -First 1
    if ($reparsePoint) {
      throw "Directory temporanea frontend contiene un reparse point; nessuna rimozione: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
    if ([System.IO.Directory]::Exists($resolved)) {
      throw "Directory temporanea frontend non rimossa: $resolved"
    }
  }
}

function Start-HiddenProcess {
  param(
    $Service,
    [string]$WorkingDirectory,
    [string]$FileName,
    [string[]]$ArgumentList,
    [string]$ExpectedListenerExecutable,
    [hashtable]$Environment = @{}
  )
  if ([System.IO.File]::Exists($Service.PidFile)) {
    $staleRecord = Get-StaticOwnershipRecord -Service $Service
    $staleProcess = Get-SavedProcessRecord -Service $Service
    $currentListeners = @(Get-ListenerRecords -Port $Service.Port)
    $reclaimableMismatchedRecord = if (-not $staleRecord) {
      Get-ReclaimableStaleOwnershipRecord -Service $Service
    } else {
      $null
    }
    if (
      (($staleRecord -and -not $staleProcess) -or $reclaimableMismatchedRecord) -and `
      $currentListeners.Count -eq 0
    ) {
      # A clean Windows shutdown cannot remove the ownership files. Reclaim
      # only a valid record whose exact wrapper is gone and whose port is free.
      $cleanupMetadata = if ($staleRecord) { $staleRecord.Metadata } else { $reclaimableMismatchedRecord }
      Remove-VerifiedPilotCleanupPaths -Metadata $cleanupMetadata
      Remove-Item -LiteralPath $Service.PidFile -Force
      if ([System.IO.File]::Exists($Service.PidFile)) {
        throw "Record di proprieta obsoleto non rimovibile per $($Service.Name)."
      }
      Write-Host "Rimosso record obsoleto verificato per $($Service.Name)."
    } else {
      throw "Record di proprieta gia presente per $($Service.Name); nessun record viene sovrascritto."
    }
  }
  Add-Content -LiteralPath $Service.LogFile -Encoding UTF8 -Value "`n[$(Get-Date -Format o)] starting $($Service.Name)"
  $parts = @((Quote-CmdArgument $FileName)) + @($ArgumentList | ForEach-Object { Quote-CmdArgument ([string]$_) })
  $command = ($parts -join " ") + " >> " + (Quote-CmdArgument $Service.LogFile) + " 2>&1"
  $info = [System.Diagnostics.ProcessStartInfo]::new()
  $info.FileName = "$env:SystemRoot\System32\cmd.exe"
  $info.Arguments = '/d /s /c "' + $command + '"'
  $info.WorkingDirectory = $WorkingDirectory
  $info.UseShellExecute = $false
  $info.CreateNoWindow = $true
  foreach ($entry in $Environment.GetEnumerator()) {
    $info.Environment[[string]$entry.Key] = [string]$entry.Value
  }
  $process = [System.Diagnostics.Process]::Start($info)
  try {
    $ownership = [ordered]@{
      schema_version = 2
      service = $Service.Name
      port = [int]$Service.Port
      identity = @($Service.Identity)
      launch_profile = if (
        $Service.PSObject.Properties.Name -contains "LaunchProfile"
      ) { [string]$Service.LaunchProfile } else { $null }
      expected_listener_executable = [System.IO.Path]::GetFullPath($ExpectedListenerExecutable)
      binding = "starting_listener_not_yet_bound"
      wrapper = New-ExactProcessMetadata -Process $process
      listener = $null
      owned_processes = @()
      cleanup_paths = if (
        $Service.PSObject.Properties.Name -contains "CleanupPaths"
      ) { @($Service.CleanupPaths) } else { @() }
    }
    Write-OwnershipRecord -Path $Service.PidFile -Value $ownership -CreateNew
  } catch {
    Stop-Process -InputObject $process -Force -ErrorAction SilentlyContinue
    throw
  }
  Write-Host "Avviato $($Service.Name), PID salvato $($process.Id)."
}

function Wait-ServiceReady {
  param($Service, [int]$Seconds = 35)
  $deadline = (Get-Date).AddSeconds($Seconds)
  do {
    $state = Get-ServiceState -Service $Service
    if ($state.Healthy -and $state.Recognizable) {
      if ($state.SavedPid) { Save-ServiceOwnershipBinding -Service $Service | Out-Null }
      return $true
    }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Get-VerifiedDescendantPlan {
  param($Saved, $Snapshot)
  $result = @()
  $wrapperStart = Convert-RoundTripUtc -Value $Saved.Wrapper.started_at_utc
  foreach ($descendant in @(Get-DescendantRecords -AncestorId $Saved.Pid -Snapshot $Snapshot)) {
    try {
      $process = Get-Process -Id ([int]$descendant.Pid) -ErrorAction Stop
      if ($process.StartTime.ToUniversalTime() -lt $wrapperStart.AddSeconds(-1)) {
        continue
      }
      $result += [pscustomobject]@{
        Process = $process
        Metadata = New-ExactProcessMetadata `
          -Process $process `
          -ParentPid ([int]$descendant.ParentPid) `
          -Depth ([int]$descendant.Depth)
      }
    } catch {
      # A child can exit while the snapshot is inspected; it no longer needs stopping.
    }
  }
  return @($result)
}

function Get-RecordedChildPlan {
  param($Service, $StaticRecord)
  if (-not $StaticRecord -or -not $StaticRecord.IsVersion2) { return @() }
  if ([string]$StaticRecord.Metadata.binding -notin @(
    "toolhelp_parent_chain",
    "toolhelp_verified_stop_plan"
  )) { return @() }

  $wrapperStart = Convert-RoundTripUtc -Value $StaticRecord.Wrapper.started_at_utc
  $candidates = @($StaticRecord.Metadata.owned_processes)
  if ($null -ne $StaticRecord.Metadata.listener) {
    $candidates += $StaticRecord.Metadata.listener
  }
  $result = @()
  $seen = @{}
  foreach ($metadata in $candidates) {
    try {
      $key = "$([int]$metadata.pid)|$([string]$metadata.started_at_utc)|$([string]$metadata.executable)"
      if ($seen.ContainsKey($key)) { continue }
      $seen[$key] = $true
      $process = Get-ExactProcess `
        -ProcessId ([int]$metadata.pid) `
        -StartedAtUtc $metadata.started_at_utc `
        -Executable ([string]$metadata.executable)
      if (-not $process) { continue }
      if ($process.StartTime.ToUniversalTime() -lt $wrapperStart.AddMilliseconds(-100)) {
        continue
      }
      $result += [pscustomobject]@{
        Process = $process
        Metadata = $metadata
      }
    } catch {
      # Invalid or exited recorded children are never selected by PID alone.
    }
  }
  return @($result)
}

function Test-ExactProcessMetadataAlive {
  param($Metadata)
  return $null -ne (Get-ExactProcess `
    -ProcessId ([int]$Metadata.pid) `
    -StartedAtUtc $Metadata.started_at_utc `
    -Executable ([string]$Metadata.executable))
}

function Stop-OwnedService {
  param($Service)
  if (-not [System.IO.File]::Exists($Service.PidFile)) {
    Write-Host "Nessun PID attivo salvato per $($Service.Name); nessun listener estraneo viene fermato."
    return
  }
  $staticRecord = Get-StaticOwnershipRecord -Service $Service
  if (-not $staticRecord) {
    $currentListeners = @(Get-ListenerRecords -Port $Service.Port)
    $reclaimable = Get-ReclaimableStaleOwnershipRecord -Service $Service
    if ($reclaimable -and $currentListeners.Count -eq 0) {
      Remove-VerifiedPilotCleanupPaths -Metadata $reclaimable
      Remove-Item -LiteralPath $Service.PidFile -Force
      if ([System.IO.File]::Exists($Service.PidFile)) {
        throw "Record di proprieta obsoleto non rimovibile per $($Service.Name)."
      }
      Write-Host "Rimosso record obsoleto verificato per $($Service.Name); nessun processo era attivo."
      return
    }
    Write-Warning "Record di proprieta non verificabile per $($Service.Name): nessun processo o listener viene fermato e il record resta disponibile per l'ispezione."
    return
  }

  $saved = Get-SavedProcessRecord -Service $Service
  $recordIsBound = $staticRecord.IsVersion2 -and `
    [string]$staticRecord.Metadata.binding -in @("toolhelp_parent_chain", "toolhelp_verified_stop_plan")
  $recordWasStarting = $staticRecord.IsVersion2 -and `
    [string]$staticRecord.Metadata.binding -ceq "starting_listener_not_yet_bound"
  if (-not $saved -and $recordWasStarting -and @(Get-ListenerRecords -Port $Service.Port).Count -eq 0) {
    Remove-VerifiedPilotCleanupPaths -Metadata $staticRecord.Metadata
    Remove-Item -LiteralPath $Service.PidFile -Force
    if ([System.IO.File]::Exists($Service.PidFile)) {
      throw "Record di avvio obsoleto non rimovibile per $($Service.Name)."
    }
    Write-Host "Rimosso avvio incompleto verificato per $($Service.Name); nessun processo era attivo."
    return
  }
  if (-not $saved -and -not $recordIsBound) {
    Write-Warning "Wrapper non piu verificabile e listener mai legato per $($Service.Name): nessun PID viene fermato e il record resta disponibile per l'ispezione."
    return
  }

  $plan = @(Get-RecordedChildPlan -Service $Service -StaticRecord $staticRecord)
  if ($saved) {
    $plan += @(Get-VerifiedDescendantPlan -Saved $saved -Snapshot (Get-ProcessTreeSnapshot))
  }
  $ownedListener = if ($saved) { Get-OwnedServiceRecord -Service $Service } else { $null }
  $expectedListener = if ($ownedListener -and $ownedListener.Listener) {
    $ownedListener.Listener.Executable
  } elseif ($staticRecord.Metadata.PSObject.Properties.Name -contains "expected_listener_executable") {
    [string]$staticRecord.Metadata.expected_listener_executable
  } else {
    $null
  }
  $listenerMetadata = if ($ownedListener -and $ownedListener.Listener) {
    New-ExactProcessMetadata -Process $ownedListener.Listener.Process
  } elseif ($recordIsBound) { $staticRecord.Metadata.listener } else { $null }
  $byIdentity = @{}
  foreach ($item in $plan) {
    $key = "$($item.Metadata.pid)|$($item.Metadata.started_at_utc)|$($item.Metadata.executable)"
    $byIdentity[$key] = $item
  }
  $plan = @($byIdentity.Values)
  $stopRecord = [ordered]@{
    schema_version = 2
    service = $Service.Name
    port = [int]$Service.Port
    identity = @($Service.Identity)
    launch_profile = if (
      $staticRecord.Metadata.PSObject.Properties.Name -contains "launch_profile"
    ) { [string]$staticRecord.Metadata.launch_profile } else { $null }
    expected_listener_executable = $expectedListener
    binding = "toolhelp_verified_stop_plan"
    wrapper = $staticRecord.Wrapper
    listener = $listenerMetadata
    owned_processes = @($plan | ForEach-Object { $_.Metadata })
    cleanup_paths = if (
      $staticRecord.Metadata.PSObject.Properties.Name -contains "cleanup_paths"
    ) { @($staticRecord.Metadata.cleanup_paths) } else { @() }
  }
  Write-OwnershipRecord -Path $Service.PidFile -Value $stopRecord

  $wrapperLabel = if ($saved) { [string]$saved.Pid } else { "gia terminato" }
  Write-Host "Arresto $($Service.Name), wrapper verificato $wrapperLabel, discendenti verificati $($plan.Count)."
  if ($saved) {
    Stop-Process -InputObject $saved.Process -Force -ErrorAction SilentlyContinue
  }

  # Capture once more immediately after stopping the wrapper. Toolhelp keeps
  # the parent IDs long enough to catch a child spawned in the preceding race.
  $secondPlan = if ($saved) {
    @(Get-VerifiedDescendantPlan -Saved $saved -Snapshot (Get-ProcessTreeSnapshot))
  } else {
    @()
  }
  $byIdentity = @{}
  foreach ($item in @($plan + $secondPlan)) {
    $key = "$($item.Metadata.pid)|$($item.Metadata.started_at_utc)|$($item.Metadata.executable)"
    $byIdentity[$key] = $item
  }
  $allChildren = @($byIdentity.Values | Sort-Object { [int]$_.Metadata.depth } -Descending)
  foreach ($item in $allChildren) {
    if (Test-ExactProcessMetadataAlive -Metadata $item.Metadata) {
      Stop-Process -InputObject $item.Process -Force -ErrorAction SilentlyContinue
    }
  }

  $ownedMetadata = @($stopRecord.wrapper) + @($allChildren | ForEach-Object { $_.Metadata })
  if ($null -ne $stopRecord.listener) { $ownedMetadata += $stopRecord.listener }
  $ownedMetadata = @($ownedMetadata | Sort-Object {
    "$($_.pid)|$($_.started_at_utc)|$($_.executable)"
  } -Unique)
  $deadline = (Get-Date).AddSeconds(8)
  do {
    $remaining = @($ownedMetadata | Where-Object { Test-ExactProcessMetadataAlive -Metadata $_ })
    if ($remaining.Count -eq 0) { break }
    Start-Sleep -Milliseconds 100
  } while ((Get-Date) -lt $deadline)
  if ($remaining.Count -gt 0) {
    throw "Arresto incompleto per $($Service.Name); il record di proprieta viene conservato."
  }

  $remainingListeners = @(Get-ListenerRecords -Port $Service.Port)
  if ($remainingListeners.Count -gt 0) {
    Write-Warning "La porta $($Service.Port) e ancora occupata da un listener non posseduto; non viene fermato."
  }
  Remove-VerifiedPilotCleanupPaths -Metadata $stopRecord
  Remove-Item -LiteralPath $Service.PidFile -Force -ErrorAction SilentlyContinue
  if ([System.IO.File]::Exists($Service.PidFile)) {
    throw "Processi arrestati ma record di proprieta non rimovibile per $($Service.Name)."
  }
}

function Write-OptionalDataPlaneStatus {
  $listeners = @(Get-ListenerRecords -Port 8781)
  $listenerSummary = if ($listeners.Count -eq 0) {
    "nessun listener"
  } else {
    @($listeners | ForEach-Object { "$($_.Pid)@$($_.Address)" }) -join ","
  }
  Write-Host "data-plane regionale locale non richiesto in questo profilo; stato osservato e non modificato: $listenerSummary."
}

function Invoke-LauncherMain {
if ($Stop) {
  foreach ($service in @($Services[2], $Services[3], $Services[1], $Services[0])) {
    Stop-OwnedService -Service $service
  }
  foreach ($service in $Services) { Write-ServiceStatus -Service $service }
  return
}

Assert-ExistingFile -Label "Backend app" -Path (Join-Path $BackendDir "app\main.py")
Assert-ExistingFile -Label "Package frontend" -Path (Join-Path $FrontendDir "package.json")
if ($StableFrontend) {
  Assert-ExistingFile -Label "Server frontend stabile" -Path $StableFrontendScript
}
if ($CommunityPilot) {
  Assert-ExistingFile -Label "Community pilota" -Path (Join-Path $BackendDir "app\pilot_community.py")
  Assert-ExistingFile -Label "Confini Community pilota" -Path (Join-Path $LogDir "community-geography.sqlite3")
  if ($CommunityCloudStore) {
    Assert-ExistingFile -Label "Community cloud loopback" -Path (Join-Path $BackendDir "app\pilot_community_cloud_loopback.py")
    Assert-ExistingFile -Label "Credenziali proprietario in memoria" -Path (Join-Path $BackendDir "app\pilot_owner_credentials.py")
  }
}
if (-not $WeatherCloud -and -not $NationalOnly -and -not $NationalCloud) {
  Assert-ExistingFile -Label "Writer snapshot locale" -Path $SnapshotWriterScript
  Assert-ExistingFile -Label "Data plane locale" -Path $DataPlaneScript
  Assert-ExistingFile -Label "Payload ICON ufficiale" -Path $IconPayload
  Assert-ExistingFile -Label "Report ICON ufficiale" -Path $IconReport
  Assert-ExistingFile -Label "Payload CAMS ufficiale" -Path $CamsPayload
  Assert-ExistingFile -Label "Report CAMS ufficiale" -Path $CamsReport
  Assert-ObjectDatabaseTarget
  $ArtifactMetadata = Get-SelectedArtifactMetadata
  Set-SelectedArtifactMetadata -Metadata $ArtifactMetadata
  Assert-IconClockWindow
  Write-CamsClockStatus
}
if ($NationalOnly -and -not (Test-NationalPilotReady -BaseUrl "http://127.0.0.1:8782")) {
  throw "NationalOnly richiede il bundle nazionale verificato gia in ascolto su 127.0.0.1:8782."
}
if ($NationalCloud) {
  if (-not (Test-NationalPilotReady -BaseUrl $CloudNationalPilotBaseUrl -TimeoutSec 30)) {
    throw "Reader nazionale cloud non disponibile, non corrente o non conforme."
  }
  if (-not (Test-CurrentReadOnlyWeatherContract -BaseUrl $CloudWeatherPilotBaseUrl)) {
    throw "Reader meteo cloud non disponibile, non corrente o non conforme: $CloudWeatherPilotBaseUrl"
  }
}

$BackendPython = Resolve-Executable -Candidates @(
  (Join-Path $RepoRoot "venv\Scripts\python.exe"),
  (Join-Path $BackendDir "venv\Scripts\python.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"),
  "python.exe",
  "python"
)
$CommunityPython = $BackendPython
$CommunityListenerPython = $BackendPython
if ($CommunityCloudStore) {
  # This existing isolated environment is required; never install or fall back.
  $CommunityPython = Join-Path $RepoRoot ".dev-logs\cloud-admin-venv\Scripts\python.exe"
  Assert-ExistingFile -Label "Python Community cloud" -Path $CommunityPython
  $communityPythonOutput = @(& $CommunityPython -c "import os, sys; from google.cloud import firestore, storage; from google.oauth2.credentials import Credentials; print(os.path.realpath(getattr(sys, '_base_executable', sys.executable)))")
  if ($LASTEXITCODE -ne 0 -or $communityPythonOutput.Count -ne 1) {
    throw "Ambiente Community cloud incompleto; nessun fallback SQLite e consentito."
  }
  $CommunityListenerPython = [System.IO.Path]::GetFullPath(([string]$communityPythonOutput[0]).Trim())
  Assert-ExistingFile -Label "Python listener Community cloud" -Path $CommunityListenerPython
}
$DataPlanePython = $null
$DataPlaneListenerPython = $null
if (-not $WeatherCloud -and -not $NationalOnly -and -not $NationalCloud) {
  $DataPlanePython = Resolve-Executable -Candidates @(
    $IsolatedPilotPython,
    (Join-Path $RepoRoot "venv\Scripts\python.exe"),
    (Join-Path $BackendDir "venv\Scripts\python.exe"),
    "python.exe",
    "python"
  )
  $DataPlaneListenerPythonOutput = @(
    & $DataPlanePython -c "import os, sys; print(os.path.realpath(getattr(sys, '_base_executable', sys.executable)))"
  )
  if ($LASTEXITCODE -ne 0 -or $DataPlaneListenerPythonOutput.Count -eq 0) {
    throw "Impossibile determinare l'interprete listener del data plane da $DataPlanePython"
  }
  $DataPlaneListenerPython = [System.IO.Path]::GetFullPath(
    ([string]$DataPlaneListenerPythonOutput[-1]).Trim()
  )
  Assert-ExistingFile -Label "Python listener data plane" -Path $DataPlaneListenerPython
}
$NodeToolchain = Resolve-PilotNodeToolchain -Directory $NodeDirectory -ExplicitDirectory:$NodeDirectorySpecified
$Npm = $NodeToolchain.Npm
$Node = $NodeToolchain.Node
if ($NodeDirectorySpecified) {
  Assert-PilotNodeVersions -Toolchain $NodeToolchain
  if (-not $RestartFrontend) { Assert-PilotNodeListener -Service $Services[2] -NodePath $Node }
}

if ($CheckOnly) {
  $modeLabel = if ($NationalCloud) { "reader nazionale/CAMS cloud correnti" } elseif ($WeatherCloud) { "reader cloud sola-lettura" } elseif ($NationalOnly) { "bundle nazionale locale" } else { "snapshot locale offline" }
  Write-Host "Prerequisiti verificati per $modeLabel. Nessun processo viene avviato o fermato."
  Write-Host "Python backend: $BackendPython"
  Write-Host "npm: $Npm"
  Write-Host "Node listener: $Node"
  if ($WeatherCloud) {
    if (-not (Test-CurrentReadOnlyWeatherContract -BaseUrl $CloudWeatherPilotBaseUrl)) {
      throw "Reader meteo cloud non disponibile, non corrente o non conforme: $CloudWeatherPilotBaseUrl"
    }
    Write-Host "Contratto meteo cloud corrente verificato in sola lettura."
    Write-Host "Reader meteo selezionato: $CloudWeatherPilotBaseUrl (HTTPS, sola lettura)."
    Write-Host "Artefatti, writer, Object DB e data plane locali: non richiesti e non verificati."
  } elseif ($NationalCloud) {
    Write-Host "Reader nazionale e ICON/CAMS cloud correnti verificati in sola lettura; nessun writer locale."
  } elseif ($NationalOnly) {
    Write-Host "Bundle nazionale v2 corrente: http://127.0.0.1:8782 (verificato, riusato)."
  } else {
    Write-Host "Python data plane: $DataPlanePython"
    Write-Host "Python listener data plane: $DataPlaneListenerPython"
    Write-Host "ICON: $IconPayload"
    Write-Host "Report ICON: $IconReport"
    Write-Host "CAMS: $CamsPayload"
    Write-Host "Report CAMS: $CamsReport"
    Write-Host "Object DB: $ObjectDatabase"
    if ($WeatherTestNow) {
      Write-Host "Orologio deterministico del pilot: $WeatherTestNow"
    }
    Write-Host "Run selezionati: ICON $ExpectedIconRunId ($ExpectedIconRunAtUtc); CAMS $ExpectedCamsRunId ($ExpectedCamsRunAtUtc)"
    Write-Host "Finestra client ICON: fresh fino a $IconFreshUntilUtc; utilizzabile fino a $IconUsableUntilUtc"
    Write-Host "Finestra client CAMS: fresh fino a $CamsFreshUntilUtc; utilizzabile fino a $CamsUsableUntilUtc"
  }
  Write-ServiceStatus -Service $Services[0]
  if ($CommunityCloudStore) { Write-Host "Community: archivio cloud pilota condiviso; credenziali proprietario verificate/rinnovate solo in memoria all'avvio, nessun fallback locale." }
  if ($WeatherCloud -or $NationalOnly -or $NationalCloud) { Write-OptionalDataPlaneStatus } else { Write-ServiceStatus -Service $Services[1] }
  Write-ServiceStatus -Service $Services[2]
  if ($CommunityPilot) { Write-ServiceStatus -Service $Services[3] }
  return
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Backend = $Services[0]
$DataPlane = $Services[1]
$Frontend = $Services[2]
$Community = $Services[3]
$StartedServices = @()

try {
  if ($WeatherCloud -or $NationalOnly -or $NationalCloud) {
    Write-Host "Profilo reader: writer e data plane locali non vengono avviati."
  } else {
    $snapshotWriterOutput = @(
      & $DataPlanePython $SnapshotWriterScript `
        "--icon-payload" $IconPayload `
        "--icon-report" $IconReport `
        "--cams-payload" $CamsPayload `
        "--cams-report" $CamsReport `
        "--object-db" $ObjectDatabase
    )
    if ($LASTEXITCODE -ne 0 -or $snapshotWriterOutput.Count -lt 1) {
      throw "Writer snapshot locale non riuscito; nessun servizio viene avviato."
    }
    try {
      $snapshotWriterResult = $snapshotWriterOutput[-1] | ConvertFrom-Json -ErrorAction Stop
    } catch {
      throw "Writer snapshot locale ha restituito un esito non valido."
    }
    if (
      [int]$snapshotWriterResult.schema_version -ne 1 -or `
      [string]$snapshotWriterResult.kind -cne "meteofriul.weather.local_snapshot_writer.result" -or `
      [string]$snapshotWriterResult.status -cne "ready" -or `
      [bool]$snapshotWriterResult.socket_opened
    ) {
      throw "Writer snapshot locale non ha confermato una pubblicazione completa e senza socket."
    }
    Write-Host "Snapshot ICON/CAMS pubblicati; tutte le capacita di scrittura sono state chiuse."
  }

  $state = Get-ServiceState -Service $Backend
  if ($state.Listening) {
    if (-not ($state.Healthy -and $state.Recognizable)) {
      throw "Porta 8002 occupata da un servizio non sano o non riconoscibile. Nessun processo viene fermato."
    }
    Write-Host "Backend gia sano e riconoscibile: riuso PID listener $($state.ListenerPid)."
  } else {
    Start-HiddenProcess -Service $Backend -WorkingDirectory $BackendDir -FileName $BackendPython `
      -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002") `
      -ExpectedListenerExecutable $BackendPython `
      -Environment @{
        METEOFRIUL_LOCAL_WEATHER_PILOT = "1"
        METEOFRIUL_OPEN_METEO_ENABLED = "0"
      }
    $StartedServices += $Backend
    if (-not (Wait-ServiceReady -Service $Backend)) { throw "Backend non pronto; controlla $($Backend.LogFile)" }
  }

  if ($WeatherCloud -or $NationalOnly -or $NationalCloud) {
    Write-OptionalDataPlaneStatus
  } else {
    $state = Get-ServiceState -Service $DataPlane
    if ($state.Listening) {
      if (-not ($state.Healthy -and $state.Recognizable)) {
        throw "Porta 8781 occupata da un servizio non sano o non riconoscibile. Nessun processo viene fermato."
      }
      Write-Host "Data plane gia sano e riconoscibile: riuso PID listener $($state.ListenerPid)."
    } else {
      Start-HiddenProcess -Service $DataPlane -WorkingDirectory $RepoRoot -FileName $DataPlanePython `
        -ArgumentList @(
          $DataPlaneScript,
          "--object-db", $ObjectDatabase,
          "--port", "8781"
        ) `
        -ExpectedListenerExecutable $DataPlaneListenerPython
      $StartedServices += $DataPlane
      if (-not (Wait-ServiceReady -Service $DataPlane -Seconds 240)) {
        throw "Data plane non pronto; controlla $($DataPlane.LogFile)"
      }
    }
  }

  if ($CommunityPilot) {
    if ($RestartCommunity) {
      $requestedCommunityProfile = $Community.LaunchProfile
      $Community.LaunchProfile = $null
      try { Stop-OwnedService -Service $Community }
      finally { $Community.LaunchProfile = $requestedCommunityProfile }
    }
    $state = Get-ServiceState -Service $Community
    if ($state.Listening) {
      if (-not ($state.Healthy -and $state.Recognizable)) {
        throw "Porta 8783 occupata da un servizio non conforme. Nessun processo viene fermato."
      }
    } else {
      $communityArguments = @("-m", $CommunityModule, "--host", "127.0.0.1", "--port", "8783")
      if ($CommunityCloudStore) { $communityArguments += @("--project", "meteofriul-pilot-20260906", "--geography-path", (Join-Path $LogDir "community-geography.sqlite3")) }
      Start-HiddenProcess -Service $Community -WorkingDirectory $BackendDir -FileName $CommunityPython `
        -ArgumentList $communityArguments `
        -ExpectedListenerExecutable $CommunityListenerPython `
        -Environment @{ COMMUNITY_STORAGE = "memory"; COMMUNITY_APP_CHECK_MODE = "off"; GOOGLE_CLOUD_PROJECT = "meteofriul-pilot-20260906"; K_SERVICE = "" }
      $StartedServices += $Community
      if (-not (Wait-ServiceReady -Service $Community -Seconds 120)) {
        throw "Community pilota non pronta; controlla $($Community.LogFile)"
      }
    }
  }

  if ($RestartFrontend) {
    # Ownership verification precedes every stop; no broad port/process kill.
    $requestedProfile = $Frontend.LaunchProfile
    $Frontend.LaunchProfile = $null
    try { Stop-OwnedService -Service $Frontend }
    finally { $Frontend.LaunchProfile = $requestedProfile }
  }
  $state = Get-ServiceState -Service $Frontend
  if ($state.Listening) {
    if (-not ($state.Healthy -and $state.Recognizable)) {
      throw "Porta 5174 occupata da un servizio non sano o non riconoscibile. Nessun processo viene fermato."
    }
    if ($NodeDirectorySpecified) { Assert-PilotNodeListener -Service $Frontend -NodePath $Node }
    Write-Host "Frontend gia sano e riconoscibile: riuso PID listener $($state.ListenerPid)."
  } else {
    $frontendEnvironment = @{
      METEO_PILOT_WEATHER_CLOUD = "0"
      METEO_PILOT_COMMUNITY_LOCAL = if ($CommunityPilot) { "1" } else { "0" }
      METEO_PILOT_NATIONAL_CLOUD = if ($NationalCloud) { "1" } else { "0" }
      METEO_PILOT_STABLE_FRONTEND = if ($StableFrontend) { "1" } else { "0" }
      VITE_LOCAL_WEATHER_PILOT_MODE = $FrontendViteMode
      VITE_API_BASE = "/api"
      VITE_API_PROXY_TARGET = "http://127.0.0.1:8002"
      VITE_LOCAL_WEATHER_PILOT = "1"
      VITE_LOCAL_WEATHER_PILOT_NOW = ""
      VITE_LOCAL_WEATHER_PROXY_TARGET = if ($WeatherCloud -or $NationalCloud) {
        $CloudWeatherPilotBaseUrl
      } else {
        "http://127.0.0.1:8781"
      }
    }
    if ($NodeDirectorySpecified) { $frontendEnvironment["PATH"] = $NodeToolchain.ChildPath }
    if ($WeatherTestNow) {
      $frontendEnvironment["VITE_LOCAL_WEATHER_PILOT_NOW"] = $WeatherTestNow
    }
    if ($StableFrontend) {
      # A static Vite build normally reports PROD=true. The local pilot must
      # retain DEV semantics so it cannot enable production Firebase/Web Push.
      $frontendEnvironment["NODE_ENV"] = "development"
    }
    if ($StableFrontend) {
      Start-HiddenProcess -Service $Frontend -WorkingDirectory $FrontendDir -FileName $Node `
        -ArgumentList @(
          $StableFrontendScript,
          "--service-identity", "dev:local-pilot",
          "--mode", $FrontendViteMode,
          "--port", "5174",
          "--build-root", $StableFrontendBuildRoot
        ) `
        -ExpectedListenerExecutable $Node `
        -Environment $frontendEnvironment
    } else {
      Start-HiddenProcess -Service $Frontend -WorkingDirectory $FrontendDir -FileName $Npm `
        -ArgumentList @("run", $FrontendNpmScript) `
        -ExpectedListenerExecutable $Node `
        -Environment $frontendEnvironment
    }
    $StartedServices += $Frontend
    $frontendReadySeconds = if ($StableFrontend -or $WeatherCloud -or $NationalCloud) { 120 } else { 35 }
    if (-not (Wait-ServiceReady -Service $Frontend -Seconds $frontendReadySeconds)) {
      throw "Frontend non pronto; controlla $($Frontend.LogFile)"
    }
  }

  Write-ServiceStatus -Service $Backend
  if ($WeatherCloud -or $NationalOnly -or $NationalCloud) { Write-OptionalDataPlaneStatus } else { Write-ServiceStatus -Service $DataPlane }
  Write-ServiceStatus -Service $Frontend
  if ($CommunityPilot) { Write-ServiceStatus -Service $Community }
} catch {
  $startupError = $_
  $rollbackErrors = @()
  for ($index = $StartedServices.Count - 1; $index -ge 0; $index -= 1) {
    try {
      Stop-OwnedService -Service $StartedServices[$index]
    } catch {
      $rollbackErrors += "$($StartedServices[$index].Name): $($_.Exception.Message)"
    }
  }
  if ($rollbackErrors.Count -gt 0) {
    Write-Warning "Rollback incompleto; i record di proprieta sono stati conservati: $($rollbackErrors -join '; ')"
  }
  throw $startupError
}
Write-Host "Pilota locale pronto: http://127.0.0.1:5174/"
Write-Host "Log e PID: $LogDir"

if ($Open) {
  $openInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $openInfo.FileName = "http://127.0.0.1:5174/"
  $openInfo.UseShellExecute = $true
  [System.Diagnostics.Process]::Start($openInfo) | Out-Null
}
}

$LauncherMutexName = Get-LauncherMutexName -WorkspacePath $RepoRoot
$LauncherMutex = Enter-LauncherMutex -Name $LauncherMutexName
try {
  Invoke-LauncherMain
} finally {
  try {
    $LauncherMutex.ReleaseMutex()
  } finally {
    $LauncherMutex.Dispose()
  }
}
