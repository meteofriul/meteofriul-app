param(
  [Parameter(Mandatory = $true)][string]$ChannelId,
  [Parameter(Mandatory = $true)][string]$ExpectedApiTag,
  [string]$TargetApiTag = $ExpectedApiTag,
  [Parameter(Mandatory = $true)][string]$ExpectedGitCommit,
  [Parameter(Mandatory = $true)][string]$ExpectedLiveVersionId,
  [string]$ProjectId = "meteo-friul",
  [string]$SiteId = "meteo-friul",
  [switch]$PreflightOnly,
  [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
$script:GZipFactory = $null

. (Join-Path $PSScriptRoot "deploy-hosting-preview-rest.transaction.ps1")

function ConvertTo-JsonUtf8Bytes {
  param([Parameter(Mandatory = $true)]$Value)

  $json = $Value | ConvertTo-Json -Depth 100 -Compress
  return ,([Text.Encoding]::UTF8.GetBytes($json))
}

function Get-ExceptionStatusCode {
  param([Parameter(Mandatory = $true)][Exception]$Exception)

  if ($null -ne $Exception.Data["StatusCode"]) {
    return [int]$Exception.Data["StatusCode"]
  }
  if ($null -ne $Exception.Response) {
    return [int]$Exception.Response.StatusCode
  }
  return $null
}

function Get-HostingHttpErrorDetails {
  param([Parameter(Mandatory = $true)]$ErrorRecord)

  $response = $ErrorRecord.Exception.Response
  if ($null -ne $response) {
    # Windows PowerShell 5.1 exposes an HttpWebResponse, whose body is read as a stream.
    $getResponseStream = $response.PSObject.Methods["GetResponseStream"]
    if ($null -ne $getResponseStream) {
      try {
        $stream = $response.GetResponseStream()
        if ($null -ne $stream) {
          $reader = New-Object IO.StreamReader($stream)
          try {
            return $reader.ReadToEnd()
          } finally {
            $reader.Dispose()
          }
        }
      } catch {
        # Fall through to HttpContent/ErrorDetails when the legacy stream is unavailable.
      }
    }

    # PowerShell 7 exposes System.Net.Http.HttpResponseMessage instead.
    $contentProperty = $response.PSObject.Properties["Content"]
    if ($null -ne $contentProperty -and $null -ne $contentProperty.Value) {
      $content = $contentProperty.Value
      if ($null -ne $content.PSObject.Methods["ReadAsStringAsync"]) {
        try {
          $readTask = $content.ReadAsStringAsync()
          return $readTask.GetAwaiter().GetResult()
        } catch {
          # ErrorDetails is the final cross-version fallback below.
        }
      }
    }
  }

  if ($null -ne $ErrorRecord.ErrorDetails -and -not [string]::IsNullOrWhiteSpace([string]$ErrorRecord.ErrorDetails.Message)) {
    return [string]$ErrorRecord.ErrorDetails.Message
  }
  return $null
}

function New-HostingJsonFailure {
  param(
    [Parameter(Mandatory = $true)]$ErrorRecord,
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Uri
  )

  $originalException = $ErrorRecord.Exception
  $statusCode = Get-ExceptionStatusCode -Exception $originalException
  $details = Get-HostingHttpErrorDetails -ErrorRecord $ErrorRecord
  $failure = New-Object Exception("Firebase Hosting $Method $Uri fallita. $details", $originalException)
  if ($null -ne $statusCode) {
    $failure.Data["StatusCode"] = $statusCode
  }
  if ($null -ne $originalException.Data["Ambiguous"]) {
    $failure.Data["Ambiguous"] = [bool]$originalException.Data["Ambiguous"]
  }
  return $failure
}

function Get-HostingRequiredNoCacheHeaders {
  param([Parameter(Mandatory = $true)][string]$FirebaseConfigPath)

  if (-not (Test-Path -LiteralPath $FirebaseConfigPath -PathType Leaf)) {
    throw "firebase.json mancante: impossibile derivare gli header Hosting."
  }
  $firebaseConfig = [IO.File]::ReadAllText($FirebaseConfigPath) | ConvertFrom-Json
  if ($null -eq $firebaseConfig.hosting -or $firebaseConfig.hosting -is [array]) {
    throw "firebase.json deve contenere una sola configurazione hosting."
  }

  $required = @{}
  foreach ($source in @("/firebase-messaging-sw.js", "/manifest.webmanifest")) {
    $rules = @($firebaseConfig.hosting.headers | Where-Object { [string]$_.source -ceq $source })
    if ($rules.Count -ne 1) {
      throw "firebase.json deve contenere esattamente una regola header per $source."
    }
    $cacheHeaders = @($rules[0].headers | Where-Object { [string]$_.key -ieq "Cache-Control" })
    if ($cacheHeaders.Count -ne 1) {
      throw "firebase.json deve contenere esattamente un Cache-Control per $source."
    }
    $value = [string]$cacheHeaders[0].value
    $directives = @($value -split ',' | ForEach-Object { $_.Trim().ToLowerInvariant() })
    if ($directives -notcontains "no-cache") {
      throw "Il Cache-Control di $source deve contenere no-cache."
    }
    $required[$source] = $value
  }
  return $required
}

function Invoke-SelfTest {
  $payload = ConvertTo-JsonUtf8Bytes -Value @{ config = @{ tag = "ui3-test" } }
  if (-not ($payload -is [byte[]])) {
    throw "Self-test fallito: il JSON UTF-8 non e un singolo byte array."
  }
  $decoded = [Text.Encoding]::UTF8.GetString($payload)
  if ($decoded -notmatch '^\{"config":') {
    throw "Self-test fallito: JSON UTF-8 non valido."
  }

  $notFound = New-Object Exception("test 404")
  $notFound.Data["StatusCode"] = 404
  if ((Get-ExceptionStatusCode -Exception $notFound) -ne 404) {
    throw "Self-test fallito: status code 404 non preservato."
  }

  $sampleRoot = Join-Path ([IO.Path]::GetTempPath()) ("meteofriul-hosting-selftest-" + [Guid]::NewGuid().ToString("N"))
  [IO.Directory]::CreateDirectory($sampleRoot) | Out-Null
  try {
    $source = Join-Path $sampleRoot "source.txt"
    $gzip = Join-Path $sampleRoot "source.txt.gz"
    [IO.File]::WriteAllText($source, "Meteo Friul", (New-Object Text.UTF8Encoding($false)))
    Compress-HostingFile -SourcePath $source -DestinationPath $gzip
    if ((Get-Item -LiteralPath $gzip).Length -le 0) {
      throw "Self-test fallito: gzip vuoto."
    }
    $firebaseConfigPath = Join-Path $sampleRoot "firebase.json"
    [IO.File]::WriteAllText(
      $firebaseConfigPath,
      '{"hosting":{"headers":[{"source":"/firebase-messaging-sw.js","headers":[{"key":"Cache-Control","value":"no-cache, no-store, must-revalidate"}]},{"source":"/manifest.webmanifest","headers":[{"key":"Cache-Control","value":"no-cache, must-revalidate"}]}]}}',
      (New-Object Text.UTF8Encoding($false))
    )
    $requiredHeaders = Get-HostingRequiredNoCacheHeaders -FirebaseConfigPath $firebaseConfigPath
    if ($requiredHeaders.Count -ne 2 -or $requiredHeaders["/firebase-messaging-sw.js"] -cne "no-cache, no-store, must-revalidate") {
      throw "Self-test fallito: header Web runtime non derivati correttamente."
    }
    $gzipInput = [IO.File]::OpenRead($gzip)
    try {
      $decompressor = New-Object IO.Compression.GZipStream($gzipInput, [IO.Compression.CompressionMode]::Decompress)
      try {
        $reader = New-Object IO.StreamReader($decompressor, [Text.Encoding]::UTF8)
        try {
          if ($reader.ReadToEnd() -ne "Meteo Friul") {
            throw "Self-test fallito: round-trip gzip non valido."
          }
        } finally {
          $reader.Dispose()
        }
      } finally {
        $decompressor.Dispose()
      }
    } finally {
      $gzipInput.Dispose()
    }
  } finally {
    if (Test-Path -LiteralPath $sampleRoot) {
      Remove-Item -LiteralPath $sampleRoot -Recurse -Force
    }
  }

  $transportPassed = Test-HostingRestTransport
  $httpResponseMessagePassed = Test-HostingHttpResponseMessageError
  [PSCustomObject]@{
    JsonByteArray = $true
    JsonPreview = $decoded
    MissingChannelStatus = 404
    GZip = "ok"
    HostingHeaders = "ok"
    HttpResponseMessage = if ($httpResponseMessagePassed) { "ok" } else { "failed" }
    ErrorPropagation = if (Test-HostingJsonErrorPropagation) { "ok" } else { "failed" }
    RestHeaderMaps = if ($transportPassed) { "ok" } else { "failed" }
    Transport = if ($transportPassed) { "ok" } else { "failed" }
  }
}

function Compress-HostingFile {
  param(
    [Parameter(Mandatory = $true)][string]$SourcePath,
    [Parameter(Mandatory = $true)][string]$DestinationPath
  )

  if ($null -ne $script:GZipFactory) {
    & $script:GZipFactory $SourcePath $DestinationPath
    return
  }

  $inputStream = [IO.File]::OpenRead($SourcePath)
  try {
    $outputStream = [IO.File]::Create($DestinationPath)
    try {
      $gzipStream = New-Object IO.Compression.GZipStream(
        $outputStream,
        [IO.Compression.CompressionLevel]::Optimal,
        $true
      )
      try {
        $inputStream.CopyTo($gzipStream)
      } finally {
        $gzipStream.Dispose()
      }
    } finally {
      $outputStream.Dispose()
    }
  } finally {
    $inputStream.Dispose()
  }
}

function Invoke-HostingJson {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][string]$Uri,
    [ValidateSet("GET", "POST", "PATCH")][string]$Method = "GET",
    $Body
  )

  $parameters = @{
    Headers = $Headers
    Method = $Method
    Uri = $Uri
  }
  if ($null -ne $Body) {
    $parameters.ContentType = "application/json; charset=utf-8"
    $parameters.Body = ConvertTo-JsonUtf8Bytes -Value $Body
  }

  try {
    return Invoke-RestMethod @parameters
  } catch {
    throw (New-HostingJsonFailure -ErrorRecord $_ -Method $Method -Uri $Uri)
  }
}

function New-HostingRestTransport {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [scriptblock]$JsonInvoker = ${function:Invoke-HostingJson}
  )

  return {
    param($Request)

    switch ($Request.Operation) {
      { $_ -in @("GetLive", "GetChannel", "GetVersion", "ListVersions", "ListVersionFiles") } {
        return & $jsonInvoker -Headers $Headers -Uri $Request.Uri -Method GET
      }
      { $_ -in @("CreateVersion", "PopulateFiles", "CreateChannel", "CreateRelease") } {
        return & $jsonInvoker -Headers $Headers -Uri $Request.Uri -Method POST -Body $Request.Body
      }
      "FinalizeVersion" {
        return & $jsonInvoker -Headers $Headers -Uri $Request.Uri -Method PATCH -Body $Request.Body
      }
      "UploadFile" {
        $uploadResponse = Invoke-WebRequest -Uri $Request.Uri -Method POST -Headers $Headers -ContentType "application/octet-stream" -InFile $Request.InFile -UseBasicParsing
        if ([int]$uploadResponse.StatusCode -lt 200 -or [int]$uploadResponse.StatusCode -ge 300) {
          throw "Upload Hosting fallito con HTTP $($uploadResponse.StatusCode)."
        }
        return [PSCustomObject]@{ StatusCode = [int]$uploadResponse.StatusCode }
      }
      { $_ -in @("DeleteChannel", "DeleteVersion") } {
        $deleteResponse = Invoke-WebRequest -Uri $Request.Uri -Method DELETE -Headers $Headers -UseBasicParsing
        return [PSCustomObject]@{ StatusCode = [int]$deleteResponse.StatusCode }
      }
      default {
        throw "Operazione transport Hosting non supportata: $($Request.Operation)"
      }
    }
  }.GetNewClosure()
}

function Test-HostingRestTransport {
  $calls = New-Object System.Collections.ArrayList
  $jsonEncoder = ${function:ConvertTo-JsonUtf8Bytes}
  $jsonInvoker = {
    param($Headers, $Uri, $Method, $Body)
    $null = $calls.Add([PSCustomObject]@{
      Body = $Body
      BodyBytes = if ($null -ne $Body) { & $jsonEncoder -Value $Body } else { $null }
      Headers = $Headers
      Method = $Method
      Uri = $Uri
    })
    return [PSCustomObject]@{ ok = $true }
  }.GetNewClosure()
  $headers = @{ Authorization = "Bearer self-test" }
  $transport = New-HostingRestTransport -Headers $headers -JsonInvoker $jsonInvoker
  $createVersionBody = [PSCustomObject]@{
    status = "CREATED"
    config = [PSCustomObject]@{
      headers = @(
        [PSCustomObject]@{
          glob = "/manifest.webmanifest"
          headers = [PSCustomObject]@{ "Cache-Control" = "no-cache, must-revalidate" }
        },
        [PSCustomObject]@{
          glob = "/index.html"
          headers = [PSCustomObject]@{ "Cache-Control" = "no-cache"; "X-Test" = "map" }
        }
      )
    }
  }
  $response = & $transport ([PSCustomObject]@{
    Body = $createVersionBody
    Headers = $headers
    InFile = $null
    Method = "POST"
    Operation = "CreateVersion"
    Uri = "https://firebasehosting.googleapis.com/v1beta1/sites/test/versions"
  })
  if (-not $response.ok -or $calls.Count -ne 1 -or $calls[0].Method -ne "POST" -or -not ($calls[0].BodyBytes -is [byte[]])) {
    throw "Self-test fallito: transport JSON reale non valido."
  }
  $serializedRequest = [Text.Encoding]::UTF8.GetString($calls[0].BodyBytes) | ConvertFrom-Json
  $serializedHeaderRules = @($serializedRequest.config.headers)
  if ($serializedHeaderRules.Count -ne 2) {
    throw "Self-test fallito: il body CreateVersion serializzato ha perso regole header."
  }
  foreach ($rule in $serializedHeaderRules) {
    $headerMap = Get-HostingTransactionHeaderMapState -HeaderMap $rule.headers
    if (-not $headerMap.IsValid -or $rule.headers -is [array]) {
      throw "Self-test fallito: rule.headers nel body CreateVersion deve essere un JSON object."
    }
  }
  return $true
}

function Test-HostingJsonErrorPropagation {
  $original = New-Object Exception("synthetic transport failure")
  $original.Data["StatusCode"] = 409
  $original.Data["Ambiguous"] = $true
  $wrapped = New-Object Exception("Firebase Hosting synthetic failure", $original)
  $wrapped.Data["StatusCode"] = Get-ExceptionStatusCode -Exception $original
  $wrapped.Data["Ambiguous"] = [bool]$original.Data["Ambiguous"]
  if ($wrapped.Data["StatusCode"] -ne 409 -or -not $wrapped.Data["Ambiguous"] -or $null -eq $wrapped.InnerException) {
    throw "Self-test fallito: propagazione errore Hosting non valida."
  }
  return $true
}

function Test-HostingHttpResponseMessageError {
  Add-Type -AssemblyName System.Net.Http
  $response = New-Object System.Net.Http.HttpResponseMessage
  try {
    $response.StatusCode = [System.Net.HttpStatusCode]::NotFound
    $response.Content = New-Object System.Net.Http.StringContent('{"error":"channel missing"}')
    $original = New-Object Exception("synthetic HttpResponseMessage failure")
    $original | Add-Member -MemberType NoteProperty -Name Response -Value $response

    $errorRecord = $null
    try {
      throw $original
    } catch {
      $errorRecord = $_
    }
    $wrapped = New-HostingJsonFailure -ErrorRecord $errorRecord -Method "GET" -Uri "https://firebasehosting.googleapis.com/v1beta1/sites/test/channels/missing"
    if (
      $wrapped.Data["StatusCode"] -ne 404 -or
      $wrapped.Message -notlike '*{"error":"channel missing"}*' -or
      $null -eq $wrapped.InnerException
    ) {
      throw "Self-test fallito: HttpResponseMessage non preservato correttamente."
    }
  } finally {
    $response.Dispose()
  }
  return $true
}

function Get-BuildManifest {
  param(
    [Parameter(Mandatory = $true)][string]$BuildRoot,
    [Parameter(Mandatory = $true)][string]$TemporaryRoot
  )

  $files = @(Get-ChildItem -LiteralPath $BuildRoot -Recurse -File | Sort-Object FullName)
  if ($files.Count -lt 400) {
    throw "Build incompleta: trovati solo $($files.Count) file."
  }
  if ($files.Count -gt 1000) {
    throw "Build troppo grande per un singolo populateFiles: $($files.Count) file."
  }
  $dotFiles = @($files | Where-Object {
    $segments = $_.FullName.Substring($BuildRoot.Length).TrimStart("\") -split '[\\/]'
    @($segments | Where-Object { $_.StartsWith(".") }).Count -ne 0
  })
  if ($dotFiles.Count -ne 0) {
    throw "La build contiene dotfile non ammessi dal contratto Hosting."
  }

  $filesMap = @{}
  $compressedByHash = @{}
  $counter = 0
  foreach ($file in $files) {
    $counter += 1
    $relativePath = $file.FullName.Substring($BuildRoot.Length).TrimStart("\").Replace("\", "/")
    $hostingPath = "/$relativePath"
    $gzipPath = Join-Path $TemporaryRoot ("{0:D4}.gz" -f $counter)
    Compress-HostingFile -SourcePath $file.FullName -DestinationPath $gzipPath

    $hash = (Get-FileHash -LiteralPath $gzipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $filesMap[$hostingPath] = $hash
    if (-not $compressedByHash.ContainsKey($hash)) {
      $compressedByHash[$hash] = $gzipPath
    }
  }

  if (-not $filesMap.ContainsKey("/index.html")) {
    throw "index.html non incluso nella mappa Hosting."
  }
  if ($filesMap.Count -ne $files.Count) {
    throw "Collisione tra path Hosting: $($files.Count) file, $($filesMap.Count) path unici."
  }

  return [PSCustomObject]@{
    CompressedByHash = $compressedByHash
    FileCount = $files.Count
    FilesMap = $filesMap
  }
}

if ($SelfTest) {
  Invoke-SelfTest
  return
}

if ($ChannelId -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
  throw "ChannelId non valido."
}
if ($ChannelId -eq "live") {
  throw "Il canale live non puo essere usato come preview."
}
if ($ExpectedApiTag -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
  throw "ExpectedApiTag non valido."
}
if ($TargetApiTag -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
  throw "TargetApiTag non valido."
}
if ($ExpectedGitCommit -notmatch '^[0-9a-f]{40}$') {
  throw "ExpectedGitCommit deve essere uno SHA Git completo."
}
if ($ExpectedLiveVersionId -notmatch '^[0-9a-f]{16}$') {
  throw "ExpectedLiveVersionId non valido."
}
if ($ProjectId -notmatch '^[a-z][a-z0-9-]{4,29}$') {
  throw "ProjectId non valido."
}
if ($SiteId -notmatch '^[a-z0-9][a-z0-9-]{0,29}$') {
  throw "SiteId non valido."
}

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$resolvedDistRoot = Join-Path $repositoryRoot "frontend\dist"
$frontendRoot = Join-Path $repositoryRoot "frontend"
$firebaseConfigPath = Join-Path $repositoryRoot "firebase.json"
$requiredNoCacheHeaders = Get-HostingRequiredNoCacheHeaders -FirebaseConfigPath $firebaseConfigPath
$actualGitCommit = (& git -C $repositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualGitCommit -ne $ExpectedGitCommit) {
  throw "HEAD Git inatteso: atteso $ExpectedGitCommit, trovato $actualGitCommit."
}
$trackedChanges = @(& git -C $repositoryRoot status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0 -or $trackedChanges.Count -ne 0) {
  throw "Il worktree contiene modifiche tracked: il deploy richiede un commit pulito."
}
$untrackedFrontend = @(& git -C $repositoryRoot ls-files --others --exclude-standard -- frontend)
if ($LASTEXITCODE -ne 0 -or $untrackedFrontend.Count -ne 0) {
  throw "Frontend contiene file non tracciati: il deploy richiede sorgenti interamente committate."
}
$ignoredPublicFiles = @(& git -C $repositoryRoot ls-files --others --ignored --exclude-standard -- frontend/public)
if ($LASTEXITCODE -ne 0 -or $ignoredPublicFiles.Count -ne 0) {
  throw "frontend/public contiene file ignorati da Git: il deploy richiede asset interamente committati."
}
$localEnvFiles = @(Get-ChildItem -LiteralPath $frontendRoot -Force -File | Where-Object {
  $_.Name -like ".env*" -and $_.Name -ne ".env.example"
})
if ($localEnvFiles.Count -ne 0) {
  throw "Trovati file .env locali nel frontend: la build di produzione deve dipendere solo dal commit."
}
$processEnvironment = [Environment]::GetEnvironmentVariables()
$viteEnvironment = @($processEnvironment.Keys | Where-Object { [string]$_ -like "VITE_*" })
if ($viteEnvironment.Count -ne 0) {
  throw "Trovate variabili VITE_* nel processo: la build di produzione deve dipendere solo dal commit."
}
$buildEnvironmentOverrides = @($processEnvironment.Keys | Where-Object {
  [string]$_ -eq "NODE_ENV" -or [string]$_ -eq "NODE_OPTIONS"
})
if ($buildEnvironmentOverrides.Count -ne 0) {
  throw "Trovate variabili NODE_ENV/NODE_OPTIONS nel processo: la build deve usare l'ambiente controllato."
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npmCommand) {
  $npmCommand = Get-Command npm -ErrorAction Stop
}
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
  $nodeCommand = Get-Command node -ErrorAction Stop
}
$nodeVersion = (& $nodeCommand.Source --version).Trim().TrimStart("v")
$npmVersion = (& $npmCommand.Source --version).Trim()
if ($nodeVersion -ne "22.17.1" -or $npmVersion -ne "10.9.2") {
  throw "Runtime build inatteso: richiesti Node 22.17.1 e npm 10.9.2, trovati Node $nodeVersion e npm $npmVersion."
}

$repositoryHashAlgorithm = [Security.Cryptography.SHA256]::Create()
try {
  $repositoryHash = $repositoryHashAlgorithm.ComputeHash(
    [Text.Encoding]::UTF8.GetBytes($repositoryRoot.ToLowerInvariant())
  )
} finally {
  $repositoryHashAlgorithm.Dispose()
}
$repositoryHashText = ([BitConverter]::ToString($repositoryHash)).Replace("-", "").ToLowerInvariant()
$buildLockPath = Join-Path ([IO.Path]::GetTempPath()) ("meteofriul-hosting-build-" + $repositoryHashText + ".lock")
$buildLockStream = $null
try {
  try {
    $buildLockStream = [IO.File]::Open(
      $buildLockPath,
      [IO.FileMode]::OpenOrCreate,
      [IO.FileAccess]::ReadWrite,
      [IO.FileShare]::None
    )
  } catch [IO.IOException] {
    throw "Un altro preflight/deploy sta gia installando o compilando questo frontend. Attendere che termini e riprovare."
  }

  & $npmCommand.Source --prefix $frontendRoot ci --ignore-scripts --no-audit --no-fund | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "npm ci fallito; nessuna richiesta cloud e stata eseguita."
  }
  & $npmCommand.Source --prefix $frontendRoot run build | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "Build frontend fallita; nessuna richiesta cloud e stata eseguita."
  }
  $commitAfterBuild = (& git -C $repositoryRoot rev-parse HEAD).Trim()
  if ($LASTEXITCODE -ne 0 -or $commitAfterBuild -ne $ExpectedGitCommit) {
    throw "HEAD Git e cambiato durante la build."
  }
  $changesAfterBuild = @(& git -C $repositoryRoot status --porcelain --untracked-files=no)
  if ($LASTEXITCODE -ne 0 -or $changesAfterBuild.Count -ne 0) {
    throw "La build ha modificato file tracciati; deploy interrotto."
  }
} finally {
  if ($null -ne $buildLockStream) {
    $buildLockStream.Dispose()
  }
}

$indexPath = Join-Path $resolvedDistRoot "index.html"
if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
  throw "Build index.html mancante."
}

$indexMarkup = [IO.File]::ReadAllText($indexPath)
$assetMatches = [regex]::Matches($indexMarkup, '/assets/[^"''<>]+\.(?:js|css)')
if ($assetMatches.Count -lt 2) {
  throw "index.html non contiene gli asset JS/CSS attesi."
}
foreach ($assetMatch in $assetMatches) {
  $assetPath = Join-Path $resolvedDistRoot $assetMatch.Value.TrimStart("/").Replace("/", "\")
  if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
    throw "Asset referenziato ma mancante: $($assetMatch.Value)"
  }
}
foreach ($requiredWebAsset in $requiredNoCacheHeaders.Keys) {
  $requiredWebAssetPath = Join-Path $resolvedDistRoot ([string]$requiredWebAsset).TrimStart("/").Replace("/", "\")
  if (-not (Test-Path -LiteralPath $requiredWebAssetPath -PathType Leaf)) {
    throw "Asset Web runtime richiesto ma mancante dalla build: $requiredWebAsset"
  }
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempRoot = Join-Path $tempBase ("meteofriul-hosting-" + [Guid]::NewGuid().ToString("N"))
$resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
  throw "Directory temporanea fuori dal percorso atteso."
}
[IO.Directory]::CreateDirectory($tempRoot) | Out-Null

try {
  $manifest = Get-BuildManifest -BuildRoot $resolvedDistRoot -TemporaryRoot $tempRoot
  if ($PreflightOnly) {
    [PSCustomObject]@{
      ApiTag = $TargetApiTag
      Channel = $ChannelId
      FileCount = $manifest.FileCount
      GitCommit = $ExpectedGitCommit
      ExpectedApiTag = $ExpectedApiTag
      HostingNoCacheHeaders = $requiredNoCacheHeaders
      IndexAssets = @($assetMatches | ForEach-Object { $_.Value })
      JsonBodyIsByteArray = ((ConvertTo-JsonUtf8Bytes -Value @{ files = $manifest.FilesMap }) -is [byte[]])
      LiveVersion = $ExpectedLiveVersionId
      Mode = "preflight-only"
      TargetApiTag = $TargetApiTag
      UniqueHashes = $manifest.CompressedByHash.Count
    } | ConvertTo-Json -Depth 5
    return
  }

  $gcloudCommand = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
  $gcloudPath = if ($null -ne $gcloudCommand) { $gcloudCommand.Source } else { $null }
  if ([string]::IsNullOrWhiteSpace($gcloudPath)) {
    throw "gcloud.cmd non trovato nel PATH. Installa Google Cloud CLI o aggiungilo al PATH prima del deploy."
  }
  $escapedSiteId = [Uri]::EscapeDataString($SiteId)
  $apiRoot = "https://firebasehosting.googleapis.com/v1beta1/sites/$escapedSiteId"
  $token = & $gcloudPath auth print-access-token
  if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Impossibile ottenere un access token breve da gcloud."
  }
  $headers = @{
    Authorization = "Bearer $token"
    "x-goog-user-project" = $ProjectId
  }
  $deploymentId = [Guid]::NewGuid().ToString("N")
  $transport = New-HostingRestTransport -Headers $headers
  $result = Invoke-HostingPreviewTransaction `
    -ApiRoot $apiRoot `
    -SiteId $SiteId `
    -ChannelId $ChannelId `
    -ExpectedApiTag $ExpectedApiTag `
    -TargetApiTag $TargetApiTag `
    -ExpectedGitCommit $ExpectedGitCommit `
    -ExpectedLiveVersionId $ExpectedLiveVersionId `
    -DeploymentId $deploymentId `
    -Headers $headers `
    -FilesMap $manifest.FilesMap `
    -CompressedByHash $manifest.CompressedByHash `
    -FileCount $manifest.FileCount `
    -RequiredNoCacheHeaders $requiredNoCacheHeaders `
    -Transport $transport
  $result | ConvertTo-Json -Compress
} finally {
  $token = $null
  $headers = $null
  if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  }
}
