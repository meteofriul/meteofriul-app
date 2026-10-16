<#
.SYNOPSIS
  Transactional Firebase Hosting preview deployment, isolated from authentication/build concerns.

.DESCRIPTION
  Dot-source this file and call Invoke-HostingPreviewTransaction. Every network operation is
  delegated to the injected Transport scriptblock, which receives one request object. This keeps
  the state machine deterministic and contract-testable under Windows PowerShell 5.1.

  Transport request fields:
    Operation: GetLive, GetChannel, CreateVersion, ListVersions, GetVersion, ListVersionFiles, PopulateFiles, UploadFile,
               FinalizeVersion, CreateChannel, CreateRelease, DeleteChannel, DeleteVersion
    Method, Uri, Headers, Body, InFile

  A transport exception can set Exception.Data["Ambiguous"] = $true when the server might have
  committed the request despite the missing response. HTTP 408, 409, 429, 500, 502, 503 and 504
  are also treated as reconcilable for create/release operations.
#>

function Get-HostingTransactionStatusCode {
  param([Parameter(Mandatory = $true)][Exception]$Exception)

  if ($null -ne $Exception.Data["StatusCode"]) {
    return [int]$Exception.Data["StatusCode"]
  }
  if ($null -ne $Exception.Response) {
    return [int]$Exception.Response.StatusCode
  }
  return $null
}

function Test-HostingTransactionAmbiguousFailure {
  param([Parameter(Mandatory = $true)][Exception]$Exception)

  if ($null -ne $Exception.Data["Ambiguous"] -and [bool]$Exception.Data["Ambiguous"]) {
    return $true
  }
  $statusCode = Get-HostingTransactionStatusCode -Exception $Exception
  if ($null -eq $statusCode) {
    return $true
  }
  return $statusCode -in @(408, 409, 429, 500, 502, 503, 504)
}

function Get-HostingTransactionVersionId {
  param([Parameter(Mandatory = $true)][string]$VersionName)

  return ($VersionName -split "/")[-1]
}

function Test-HostingTransactionExpectedLabels {
  param(
    $Resource,
    [Parameter(Mandatory = $true)][hashtable]$ExpectedLabels
  )

  if ($null -eq $Resource -or $null -eq $Resource.labels) {
    return $false
  }
  foreach ($name in $ExpectedLabels.Keys) {
    $actual = Get-HostingTransactionLabel -Resource $Resource -Name ([string]$name)
    if ($actual -cne [string]$ExpectedLabels[$name]) {
      return $false
    }
  }
  return $true
}

function Test-HostingTransactionVersionName {
  param(
    [Parameter(Mandatory = $true)][string]$VersionName,
    [Parameter(Mandatory = $true)][string]$SiteId
  )

  return $VersionName -match ("^sites/" + [regex]::Escape($SiteId) + "/versions/[0-9a-f]{16}$")
}

function Test-HostingTransactionChannelName {
  param(
    [Parameter(Mandatory = $true)][string]$ChannelName,
    [Parameter(Mandatory = $true)][string]$SiteId,
    [Parameter(Mandatory = $true)][string]$ChannelId
  )

  return $ChannelName -ceq "sites/$SiteId/channels/$ChannelId"
}

function ConvertTo-HostingTransactionCanonicalValue {
  param($Value)

  if ($null -eq $Value) {
    return $null
  }

  if ($Value -is [System.Collections.IDictionary]) {
    $entries = New-Object System.Collections.ArrayList
    foreach ($key in $Value.Keys) {
      $null = $entries.Add([PSCustomObject]@{
        Name = [string]$key
        Value = $Value[$key]
      })
    }
    $entries.Sort([System.Collections.Generic.Comparer[object]]::Create({
      param($Left, $Right)
      return [StringComparer]::Ordinal.Compare([string]$Left.Name, [string]$Right.Name)
    }))

    $canonical = [System.Collections.Specialized.OrderedDictionary]::new([StringComparer]::Ordinal)
    foreach ($entry in $entries) {
      $canonical[[string]$entry.Name] = ConvertTo-HostingTransactionCanonicalValue -Value $entry.Value
    }
    return ,$canonical
  }

  if ($Value -is [PSCustomObject]) {
    $properties = New-Object System.Collections.ArrayList
    foreach ($property in $Value.PSObject.Properties) {
      $null = $properties.Add($property)
    }
    $properties.Sort([System.Collections.Generic.Comparer[object]]::Create({
      param($Left, $Right)
      return [StringComparer]::Ordinal.Compare([string]$Left.Name, [string]$Right.Name)
    }))

    $canonical = [System.Collections.Specialized.OrderedDictionary]::new([StringComparer]::Ordinal)
    foreach ($property in $properties) {
      $canonical[[string]$property.Name] = ConvertTo-HostingTransactionCanonicalValue -Value $property.Value
    }
    return ,$canonical
  }

  if ($Value -is [array] -or $Value -is [System.Collections.IList]) {
    $canonicalItems = New-Object System.Collections.ArrayList
    foreach ($item in $Value) {
      $null = $canonicalItems.Add((ConvertTo-HostingTransactionCanonicalValue -Value $item))
    }
    return ,([object[]]$canonicalItems.ToArray())
  }

  return $Value
}

function ConvertTo-HostingTransactionCanonicalJson {
  param($Value)

  $canonicalValue = ConvertTo-HostingTransactionCanonicalValue -Value $Value
  return $canonicalValue | ConvertTo-Json -Depth 100 -Compress
}

function Test-HostingTransactionConfig {
  param(
    $ActualConfig,
    $ExpectedConfig,
    [Parameter(Mandatory = $true)][string]$ExpectedApiTag,
    [hashtable]$RequiredNoCacheHeaders = @{}
  )

  if ($null -eq $ActualConfig -or $null -eq $ExpectedConfig) {
    return $false
  }
  $apiRewrite = @($ActualConfig.rewrites | Where-Object { $_.glob -eq "/api/**" })
  if ($apiRewrite.Count -ne 1 -or $apiRewrite[0].run.tag -cne $ExpectedApiTag) {
    return $false
  }
  $spaRewrite = @($ActualConfig.rewrites | Where-Object { $_.glob -eq "**" -and $_.path -eq "/index.html" })
  if ($spaRewrite.Count -ne 1) {
    return $false
  }
  if (-not (Test-HostingTransactionHeaderMaps -Config $ActualConfig)) {
    return $false
  }
  if (-not (Test-HostingTransactionNoCacheHeaders -Config $ActualConfig -RequiredNoCacheHeaders $RequiredNoCacheHeaders)) {
    return $false
  }

  # Firebase can reorder JSON object/map properties in its response. Canonicalize only those
  # properties; array order, scalar values and scalar types remain contract-significant.
  $actualJson = ConvertTo-HostingTransactionCanonicalJson -Value $ActualConfig
  $expectedJson = ConvertTo-HostingTransactionCanonicalJson -Value $ExpectedConfig
  return $actualJson -ceq $expectedJson
}

function Get-HostingTransactionHeaderMapState {
  param($HeaderMap)

  $entries = New-Object System.Collections.ArrayList
  if ($null -eq $HeaderMap -or $HeaderMap -is [array] -or $HeaderMap -is [System.Collections.IList]) {
    return [PSCustomObject]@{ Entries = @(); IsValid = $false }
  }

  if ($HeaderMap -is [System.Collections.IDictionary]) {
    foreach ($name in $HeaderMap.Keys) {
      $null = $entries.Add([PSCustomObject]@{
        Name = [string]$name
        Value = $HeaderMap[$name]
      })
    }
  } elseif ($HeaderMap -is [PSCustomObject]) {
    foreach ($property in $HeaderMap.PSObject.Properties) {
      $null = $entries.Add([PSCustomObject]@{
        Name = [string]$property.Name
        Value = $property.Value
      })
    }
  } else {
    return [PSCustomObject]@{ Entries = @(); IsValid = $false }
  }

  return [PSCustomObject]@{ Entries = @($entries); IsValid = $true }
}

function Set-HostingTransactionHeaderMapValue {
  param(
    [Parameter(Mandatory = $true)]$HeaderMap,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Value
  )

  $state = Get-HostingTransactionHeaderMapState -HeaderMap $HeaderMap
  if (-not $state.IsValid) {
    throw "La regola header Hosting REST deve contenere una mappa JSON."
  }
  $matches = @($state.Entries | Where-Object { [string]$_.Name -ieq $Name })
  if ($matches.Count -gt 1) {
    throw "Configurazione Hosting ambigua: piu header $Name."
  }

  $actualName = if ($matches.Count -eq 1) { [string]$matches[0].Name } else { $Name }
  if ($HeaderMap -is [System.Collections.IDictionary]) {
    $HeaderMap[$actualName] = $Value
  } elseif ($matches.Count -eq 1) {
    $HeaderMap.PSObject.Properties[$actualName].Value = $Value
  } else {
    $HeaderMap | Add-Member -MemberType NoteProperty -Name $Name -Value $Value
  }
}

function Test-HostingTransactionHeaderMaps {
  param($Config)

  foreach ($rule in @($Config.headers)) {
    $state = Get-HostingTransactionHeaderMapState -HeaderMap $rule.headers
    if (-not $state.IsValid) {
      return $false
    }
  }
  return $true
}

function Test-HostingTransactionNoCacheHeaders {
  param(
    $Config,
    [Parameter(Mandatory = $true)][hashtable]$RequiredNoCacheHeaders
  )

  foreach ($source in $RequiredNoCacheHeaders.Keys) {
    $rules = @($Config.headers | Where-Object { [string]$_.glob -ceq [string]$source })
    if ($rules.Count -ne 1) {
      return $false
    }
    $headerMap = Get-HostingTransactionHeaderMapState -HeaderMap $rules[0].headers
    if (-not $headerMap.IsValid) {
      return $false
    }
    $cacheHeaders = @($headerMap.Entries | Where-Object { [string]$_.Name -ieq "Cache-Control" })
    if ($cacheHeaders.Count -ne 1 -or [string]$cacheHeaders[0].Value -cne [string]$RequiredNoCacheHeaders[$source]) {
      return $false
    }
  }
  return $true
}

function New-HostingTransactionTargetConfig {
  param(
    $LiveConfig,
    [Parameter(Mandatory = $true)][string]$ExpectedApiTag,
    [Parameter(Mandatory = $true)][string]$TargetApiTag,
    [Parameter(Mandatory = $true)][hashtable]$RequiredNoCacheHeaders
  )

  $requiredSources = @(
    "/firebase-messaging-sw.js",
    "/manifest.webmanifest"
  )
  if ($RequiredNoCacheHeaders.Count -ne $requiredSources.Count) {
    throw "La configurazione header preview deve contenere esattamente i due asset Web runtime richiesti."
  }
  foreach ($source in $requiredSources) {
    if (-not $RequiredNoCacheHeaders.ContainsKey($source)) {
      throw "Header Cache-Control preview mancante per $source."
    }
    $value = [string]$RequiredNoCacheHeaders[$source]
    $cacheDirectives = @($value -split ',' | ForEach-Object { $_.Trim().ToLowerInvariant() })
    if ($cacheDirectives -notcontains "no-cache") {
      throw "L'header Cache-Control per $source non contiene no-cache."
    }
  }

  if (-not (Test-HostingTransactionConfig -ActualConfig $LiveConfig -ExpectedConfig $LiveConfig -ExpectedApiTag $ExpectedApiTag)) {
    throw "La configurazione live non contiene i rewrite API/SPA attesi."
  }

  # The REST object returned for live is never reused or mutated. A JSON round-trip produces a
  # detached config so the preview can target another Cloud Run tag without changing live state.
  $targetConfig = $LiveConfig | ConvertTo-Json -Depth 100 -Compress | ConvertFrom-Json
  $apiRewrite = @($targetConfig.rewrites | Where-Object { $_.glob -eq "/api/**" })
  $apiRewrite[0].run.tag = $TargetApiTag

  foreach ($source in $requiredSources) {
    $rules = @($targetConfig.headers | Where-Object { [string]$_.glob -ceq $source })
    if ($rules.Count -gt 1) {
      throw "Configurazione Hosting ambigua: piu regole header per $source."
    }
    if ($rules.Count -eq 0) {
      $rule = [PSCustomObject]@{
        glob = $source
        headers = [PSCustomObject]@{
          "Cache-Control" = [string]$RequiredNoCacheHeaders[$source]
        }
      }
      $allRules = @($targetConfig.headers) + @($rule)
      if ($null -eq $targetConfig.PSObject.Properties["headers"]) {
        $targetConfig | Add-Member -MemberType NoteProperty -Name "headers" -Value $allRules
      } else {
        $targetConfig.headers = $allRules
      }
      continue
    }

    Set-HostingTransactionHeaderMapValue `
      -HeaderMap $rules[0].headers `
      -Name "Cache-Control" `
      -Value ([string]$RequiredNoCacheHeaders[$source])
  }

  if (-not (Test-HostingTransactionConfig -ActualConfig $targetConfig -ExpectedConfig $targetConfig -ExpectedApiTag $TargetApiTag -RequiredNoCacheHeaders $RequiredNoCacheHeaders)) {
    throw "La configurazione preview derivata non conserva rewrite e header Web richiesti."
  }
  return $targetConfig
}

function Get-HostingTransactionLabel {
  param(
    $Resource,
    [Parameter(Mandatory = $true)][string]$Name
  )

  if ($null -eq $Resource -or $null -eq $Resource.labels) {
    return $null
  }
  $property = $Resource.labels.PSObject.Properties[$Name]
  if ($null -ne $property) {
    return [string]$property.Value
  }
  if ($Resource.labels -is [System.Collections.IDictionary] -and $Resource.labels.Contains($Name)) {
    return [string]$Resource.labels[$Name]
  }
  return $null
}

function Get-HostingTransactionVersionFiles {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][string]$VersionUri,
    [ValidateRange(1, 20)][int]$MaximumPages = 10
  )

  $files = New-Object System.Collections.ArrayList
  $pageToken = $null
  for ($page = 1; $page -le $MaximumPages; $page++) {
    $uri = "$VersionUri/files?pageSize=1000"
    if (-not [string]::IsNullOrWhiteSpace($pageToken)) {
      $uri += "&pageToken=$([Uri]::EscapeDataString($pageToken))"
    }
    $response = Invoke-HostingTransactionTransport -Transport $Transport -Operation "ListVersionFiles" -Method "GET" -Uri $uri -Headers $Headers
    foreach ($file in @($response.files)) {
      $null = $files.Add($file)
    }
    $pageToken = [string]$response.nextPageToken
    if ([string]::IsNullOrWhiteSpace($pageToken)) {
      return ,@($files)
    }
  }
  throw "Elenco file Hosting oltre il limite di paginazione previsto."
}

function Get-HostingTransactionVersionFilesError {
  param(
    [Parameter(Mandatory = $true)][object[]]$VersionFiles,
    [Parameter(Mandatory = $true)][hashtable]$ExpectedFiles
  )

  $firebaseReservedPaths = @(
    "/__/firebase/init.js",
    "/__/firebase/init.json"
  )
  $actualByPath = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
  foreach ($file in $VersionFiles) {
    $path = [string]$file.path
    $hash = [string]$file.hash
    if ([string]::IsNullOrWhiteSpace($path) -or $actualByPath.ContainsKey($path)) {
      return "Path Hosting mancante o duplicato: $path"
    }
    if ([string]$file.status -cne "ACTIVE") {
      return "File Hosting non ACTIVE: $path"
    }
    if ($hash -notmatch '^[0-9a-f]{64}$') {
      return "Hash Hosting non valido: $path"
    }
    if ($ExpectedFiles.ContainsKey($path)) {
      if ($hash -cne [string]$ExpectedFiles[$path]) {
        return "Hash Hosting diverso dalla build locale: $path"
      }
    } elseif ($path -notin $firebaseReservedPaths) {
      return "File Hosting estraneo alla build: $path"
    }
    $actualByPath.Add($path, $file)
  }

  foreach ($path in $ExpectedFiles.Keys) {
    if (-not $actualByPath.ContainsKey([string]$path)) {
      return "File della build mancante su Hosting: $path"
    }
  }
  foreach ($reservedPath in $firebaseReservedPaths) {
    if (-not $actualByPath.ContainsKey($reservedPath)) {
      return "File riservato Firebase mancante: $reservedPath"
    }
  }
  if ($actualByPath.Count -ne ($ExpectedFiles.Count + $firebaseReservedPaths.Count)) {
    return "Conteggio file Hosting inatteso: $($actualByPath.Count)"
  }
  return $null
}

function Invoke-HostingTransactionTransport {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [Parameter(Mandatory = $true)][string]$Operation,
    [Parameter(Mandatory = $true)][string]$Method,
    [Parameter(Mandatory = $true)][string]$Uri,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    $Body,
    [string]$InFile
  )

  $request = [PSCustomObject]@{
    Body = $Body
    Headers = $Headers
    InFile = $InFile
    Method = $Method
    Operation = $Operation
    Uri = $Uri
  }
  return & $Transport $request
}

function Invoke-HostingTransactionDelay {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$Delay,
    [Parameter(Mandatory = $true)][int]$Milliseconds,
    [Parameter(Mandatory = $true)][string]$Reason,
    [Parameter(Mandatory = $true)][int]$Attempt
  )

  & $Delay $Milliseconds $Reason $Attempt | Out-Null
}

function Get-HostingTransactionChannelState {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [Parameter(Mandatory = $true)][scriptblock]$Delay,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][string]$ChannelUri,
    [Parameter(Mandatory = $true)][string]$SiteId,
    [Parameter(Mandatory = $true)][string]$ChannelId,
    [Parameter(Mandatory = $true)][hashtable]$ExpectedLabels,
    [Parameter(Mandatory = $true)][int]$Attempts,
    [Parameter(Mandatory = $true)][int]$DelayMilliseconds,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  $lastException = $null
  for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
    try {
      $channel = Invoke-HostingTransactionTransport -Transport $Transport -Operation "GetChannel" -Method "GET" -Uri $ChannelUri -Headers $Headers
      $owner = Get-HostingTransactionLabel -Resource $channel -Name "deployment-id"
      $validName = Test-HostingTransactionChannelName -ChannelName ([string]$channel.name) -SiteId $SiteId -ChannelId $ChannelId
      $kind = if ($validName -and (Test-HostingTransactionExpectedLabels -Resource $channel -ExpectedLabels $ExpectedLabels)) { "Owned" } else { "Foreign" }
      return [PSCustomObject]@{
        Channel = $channel
        Kind = $kind
        Owner = $owner
      }
    } catch {
      $lastException = $_.Exception
      $statusCode = Get-HostingTransactionStatusCode -Exception $_.Exception
      if ($statusCode -eq 404) {
        if ($attempt -eq $Attempts) {
          return [PSCustomObject]@{ Channel = $null; Kind = "Missing"; Owner = $null }
        }
      } elseif (-not (Test-HostingTransactionAmbiguousFailure -Exception $_.Exception)) {
        throw
      }
    }

    if ($attempt -lt $Attempts) {
      Invoke-HostingTransactionDelay -Delay $Delay -Milliseconds $DelayMilliseconds -Reason $Reason -Attempt $attempt
    }
  }

  $failure = New-Object Exception("Impossibile riconciliare il canale Hosting dopo $Attempts tentativi.", $lastException)
  $failure.Data["Ambiguous"] = $true
  throw $failure
}

function Get-HostingTransactionCreatedVersionState {
  param(
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [Parameter(Mandatory = $true)][scriptblock]$Delay,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][string]$ApiRoot,
    [Parameter(Mandatory = $true)][string]$SiteId,
    [Parameter(Mandatory = $true)][hashtable]$ExpectedLabels,
    $ExpectedConfig,
    [Parameter(Mandatory = $true)][string]$ExpectedApiTag,
    [Parameter(Mandatory = $true)][hashtable]$RequiredNoCacheHeaders,
    [Parameter(Mandatory = $true)][int]$Attempts,
    [Parameter(Mandatory = $true)][int]$DelayMilliseconds,
    [Parameter(Mandatory = $true)][string]$Reason
  )

  $lastException = $null
  for ($attempt = 1; $attempt -le $Attempts; $attempt += 1) {
    try {
      $owned = New-Object System.Collections.ArrayList
      $pageToken = $null
      $seenPageTokens = @{}
      do {
        $uri = "$ApiRoot/versions?pageSize=100"
        if (-not [string]::IsNullOrWhiteSpace($pageToken)) {
          if ($seenPageTokens.ContainsKey($pageToken)) {
            throw "Firebase ha restituito un ciclo nella paginazione delle versioni."
          }
          $seenPageTokens[$pageToken] = $true
          $uri += "&pageToken=$([Uri]::EscapeDataString($pageToken))"
        }
        $page = Invoke-HostingTransactionTransport -Transport $Transport -Operation "ListVersions" -Method "GET" -Uri $uri -Headers $Headers
        foreach ($candidate in @($page.versions)) {
          $candidateName = [string]$candidate.name
          if (-not (Test-HostingTransactionVersionName -VersionName $candidateName -SiteId $SiteId)) {
            continue
          }
          if (-not (Test-HostingTransactionExpectedLabels -Resource $candidate -ExpectedLabels $ExpectedLabels)) {
            continue
          }
          if ([string]$candidate.status -cne "CREATED") {
            continue
          }
          if (-not (Test-HostingTransactionConfig -ActualConfig $candidate.config -ExpectedConfig $ExpectedConfig -ExpectedApiTag $ExpectedApiTag -RequiredNoCacheHeaders $RequiredNoCacheHeaders)) {
            continue
          }
          $null = $owned.Add($candidate)
        }
        $pageToken = [string]$page.nextPageToken
      } while (-not [string]::IsNullOrWhiteSpace($pageToken))

      if ($owned.Count -gt 1) {
        throw "Riconciliazione CreateVersion non sicura: trovate piu versioni owned compatibili."
      }
      if ($owned.Count -eq 1) {
        return [PSCustomObject]@{ Kind = "Owned"; Version = $owned[0] }
      }
    } catch {
      $lastException = $_.Exception
      if (-not (Test-HostingTransactionAmbiguousFailure -Exception $_.Exception)) {
        throw
      }
    }

    if ($attempt -lt $Attempts) {
      Invoke-HostingTransactionDelay -Delay $Delay -Milliseconds $DelayMilliseconds -Reason $Reason -Attempt $attempt
    }
  }

  $failure = New-Object Exception("Impossibile trovare esattamente una versione Hosting owned dopo $Attempts tentativi.", $lastException)
  $failure.Data["Ambiguous"] = $true
  throw $failure
}

function Remove-HostingTransactionOwnedResource {
  param(
    [Parameter(Mandatory = $true)][ValidateSet("Channel", "Version")][string]$ResourceType,
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][string]$ResourceUri,
    [Parameter(Mandatory = $true)][hashtable]$ExpectedLabels,
    [Parameter(Mandatory = $true)][string]$SiteId,
    [string]$ChannelId,
    [string]$VersionId,
    [Parameter(Mandatory = $true)][string]$ExpectedLiveVersionId,
    [string]$LiveChannelUri
  )

  if ($ResourceType -eq "Channel") {
    if ($ChannelId -eq "live" -or [string]::IsNullOrWhiteSpace($ChannelId)) {
      return "Protected"
    }
  } else {
    if ($VersionId -notmatch '^[0-9a-f]{16}$' -or $VersionId -ceq $ExpectedLiveVersionId) {
      return "Protected"
    }
    if ([string]::IsNullOrWhiteSpace($LiveChannelUri)) {
      return "LookupFailed"
    }
    try {
      $currentLive = Invoke-HostingTransactionTransport -Transport $Transport -Operation "GetLive" -Method "GET" -Uri $LiveChannelUri -Headers $Headers
      $currentLiveName = [string]$currentLive.release.version.name
      if (-not (Test-HostingTransactionVersionName -VersionName $currentLiveName -SiteId $SiteId)) {
        return "LookupFailed"
      }
      if ((Get-HostingTransactionVersionId -VersionName $currentLiveName) -ceq $VersionId) {
        return "Protected"
      }
    } catch {
      return "LookupFailed"
    }
  }

  $getOperation = if ($ResourceType -eq "Channel") { "GetChannel" } else { "GetVersion" }
  $deleteOperation = if ($ResourceType -eq "Channel") { "DeleteChannel" } else { "DeleteVersion" }
  try {
    $resource = Invoke-HostingTransactionTransport -Transport $Transport -Operation $getOperation -Method "GET" -Uri $ResourceUri -Headers $Headers
  } catch {
    if ((Get-HostingTransactionStatusCode -Exception $_.Exception) -eq 404) {
      return "AlreadyMissing"
    }
    return "LookupFailed"
  }

  $validName = if ($ResourceType -eq "Channel") {
    Test-HostingTransactionChannelName -ChannelName ([string]$resource.name) -SiteId $SiteId -ChannelId $ChannelId
  } else {
    (Test-HostingTransactionVersionName -VersionName ([string]$resource.name) -SiteId $SiteId) -and ((Get-HostingTransactionVersionId -VersionName ([string]$resource.name)) -ceq $VersionId)
  }
  if (-not $validName -or -not (Test-HostingTransactionExpectedLabels -Resource $resource -ExpectedLabels $ExpectedLabels)) {
    return "Foreign"
  }

  try {
    $null = Invoke-HostingTransactionTransport -Transport $Transport -Operation $deleteOperation -Method "DELETE" -Uri $ResourceUri -Headers $Headers
    return "Deleted"
  } catch {
    if ((Get-HostingTransactionStatusCode -Exception $_.Exception) -eq 404) {
      return "AlreadyMissing"
    }
    return "DeleteFailed"
  }
}

function Invoke-HostingPreviewTransaction {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$ApiRoot,
    [Parameter(Mandatory = $true)][string]$SiteId,
    [Parameter(Mandatory = $true)][string]$ChannelId,
    [Parameter(Mandatory = $true)][string]$ExpectedApiTag,
    [string]$TargetApiTag = $ExpectedApiTag,
    [Parameter(Mandatory = $true)][string]$ExpectedGitCommit,
    [Parameter(Mandatory = $true)][string]$ExpectedLiveVersionId,
    [Parameter(Mandatory = $true)][string]$DeploymentId,
    [Parameter(Mandatory = $true)][hashtable]$Headers,
    [Parameter(Mandatory = $true)][hashtable]$FilesMap,
    [Parameter(Mandatory = $true)][hashtable]$CompressedByHash,
    [Parameter(Mandatory = $true)][int]$FileCount,
    [Parameter(Mandatory = $true)][hashtable]$RequiredNoCacheHeaders,
    [Parameter(Mandatory = $true)][scriptblock]$Transport,
    [scriptblock]$Delay = { param($Milliseconds) Start-Sleep -Milliseconds $Milliseconds },
    [ValidateRange(1, 10)][int]$ReconcileAttempts = 4,
    [ValidateRange(0, 30000)][int]$ReconcileDelayMilliseconds = 500,
    [string]$ChannelTtl = "604800s",
    [ValidateRange(1, 100)][int]$RetainedReleaseCount = 10
  )

  if ($ApiRoot -notmatch '^https://firebasehosting\.googleapis\.com/v1beta1/sites/[a-z0-9-]+$') {
    throw "ApiRoot Hosting non valido."
  }
  if ($SiteId -notmatch '^[a-z0-9][a-z0-9-]{0,29}$') {
    throw "SiteId non valido."
  }
  if ($ChannelId -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
    throw "ChannelId non valido."
  }
  if ($ChannelId -ceq "live") {
    throw "Il canale live non puo essere una destinazione preview."
  }
  if ($ExpectedApiTag -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
    throw "ExpectedApiTag non valido."
  }
  if ($TargetApiTag -notmatch '^[a-z0-9][a-z0-9-]{0,62}$') {
    throw "TargetApiTag non valido."
  }
  if ($ExpectedGitCommit -notmatch '^[0-9a-f]{40}$') {
    throw "ExpectedGitCommit deve essere uno SHA completo."
  }
  if ($ExpectedLiveVersionId -notmatch '^[0-9a-f]{16}$') {
    throw "ExpectedLiveVersionId non valido."
  }
  if ($DeploymentId -notmatch '^[0-9a-f]{32}$') {
    throw "DeploymentId deve contenere esattamente 32 caratteri esadecimali."
  }
  if ($FileCount -lt 1 -or $FilesMap.Count -ne $FileCount) {
    throw "FileCount non corrisponde alla mappa dei file."
  }

  $apiRootNormalized = $ApiRoot.TrimEnd("/")
  if ($apiRootNormalized -cne "https://firebasehosting.googleapis.com/v1beta1/sites/$SiteId") {
    throw "ApiRoot e SiteId non identificano lo stesso sito Hosting."
  }
  $escapedChannelId = [Uri]::EscapeDataString($ChannelId)
  $channelUri = "$apiRootNormalized/channels/$escapedChannelId"
  $versionName = $null
  $versionId = $null
  $channelOwned = $false
  $releaseCommitted = $false
  $stage = "ReadLive"
  $channelCreateReconciled = $false
  $versionCreateReconciled = $false
  $releaseReconciled = $false
  $cleanup = [ordered]@{ Channel = "NotNeeded"; Version = "NotNeeded" }
  $versionLabels = @{
    "deployment-tool" = "codex-rest-v1"
    "deployment-id" = $DeploymentId
    "git-commit" = $ExpectedGitCommit
    "channel-id" = $ChannelId
    "source-live-version" = $ExpectedLiveVersionId
  }
  $channelLabels = $null

  try {
    $live = Invoke-HostingTransactionTransport -Transport $Transport -Operation "GetLive" -Method "GET" -Uri "$apiRootNormalized/channels/live" -Headers $Headers
    $liveVersionName = [string]$live.release.version.name
    if (-not (Test-HostingTransactionVersionName -VersionName $liveVersionName -SiteId $SiteId)) {
      throw "La risorsa live non contiene un nome versione valido per il sito atteso."
    }
    $liveVersionId = Get-HostingTransactionVersionId -VersionName $liveVersionName
    if ($liveVersionId -ne $ExpectedLiveVersionId) {
      throw "La versione live e cambiata: attesa $ExpectedLiveVersionId, trovata $liveVersionId."
    }
    $targetConfig = New-HostingTransactionTargetConfig `
      -LiveConfig $live.release.version.config `
      -ExpectedApiTag $ExpectedApiTag `
      -TargetApiTag $TargetApiTag `
      -RequiredNoCacheHeaders $RequiredNoCacheHeaders

    $stage = "AssertChannelMissing"
    try {
      $null = Invoke-HostingTransactionTransport -Transport $Transport -Operation "GetChannel" -Method "GET" -Uri $channelUri -Headers $Headers
      throw "Il canale $ChannelId esiste gia; la procedura non lo sovrascrive."
    } catch {
      if ((Get-HostingTransactionStatusCode -Exception $_.Exception) -ne 404) {
        throw
      }
    }

    $stage = "CreateVersion"
    try {
      $version = Invoke-HostingTransactionTransport -Transport $Transport -Operation "CreateVersion" -Method "POST" -Uri "$apiRootNormalized/versions" -Headers $Headers -Body @{
        status = "CREATED"
        config = $targetConfig
        labels = $versionLabels
      }
    } catch {
      if (-not (Test-HostingTransactionAmbiguousFailure -Exception $_.Exception)) {
        throw
      }
      # Never retry CreateVersion: a timeout can mean that Firebase committed the first POST.
      $versionState = Get-HostingTransactionCreatedVersionState -Transport $Transport -Delay $Delay -Headers $Headers -ApiRoot $apiRootNormalized -SiteId $SiteId -ExpectedLabels $versionLabels -ExpectedConfig $targetConfig -ExpectedApiTag $TargetApiTag -RequiredNoCacheHeaders $RequiredNoCacheHeaders -Attempts $ReconcileAttempts -DelayMilliseconds $ReconcileDelayMilliseconds -Reason "create-version-timeout"
      $version = $versionState.Version
      $versionCreateReconciled = $true
    }
    $versionName = [string]$version.name
    if (-not (Test-HostingTransactionVersionName -VersionName $versionName -SiteId $SiteId)) {
      throw "Firebase non ha restituito un nome versione valido."
    }
    if (-not (Test-HostingTransactionExpectedLabels -Resource $version -ExpectedLabels $versionLabels)) {
      throw "La versione creata non conserva tutte le label di ownership."
    }
    if ([string]$version.status -cne "CREATED") {
      throw "La versione creata non e nello stato CREATED."
    }
    $versionId = Get-HostingTransactionVersionId -VersionName $versionName
    if ($versionId -ceq $ExpectedLiveVersionId) {
      throw "Firebase ha restituito la versione live come nuova versione preview."
    }
    $versionUri = "$apiRootNormalized/versions/$([Uri]::EscapeDataString($versionId))"
    if (-not (Test-HostingTransactionConfig -ActualConfig $version.config -ExpectedConfig $targetConfig -ExpectedApiTag $TargetApiTag -RequiredNoCacheHeaders $RequiredNoCacheHeaders)) {
      throw "La nuova versione non conserva la configurazione derivata e il tag API $TargetApiTag."
    }

    $stage = "PopulateFiles"
    $populate = Invoke-HostingTransactionTransport -Transport $Transport -Operation "PopulateFiles" -Method "POST" -Uri "$versionUri`:populateFiles" -Headers $Headers -Body @{ files = $FilesMap }
    $requiredHashes = @($populate.uploadRequiredHashes | Where-Object { $_ })
    if ($requiredHashes.Count -gt 0) {
      $uploadBaseUri = $null
      if (-not [Uri]::TryCreate([string]$populate.uploadUrl, [UriKind]::Absolute, [ref]$uploadBaseUri)) {
        throw "uploadUrl Firebase non valido."
      }
      $expectedUploadPath = "/upload/sites/$([Uri]::EscapeDataString($SiteId))/versions/$versionId/files"
      if ($uploadBaseUri.Scheme -ne "https" -or $uploadBaseUri.Host -ne "upload-firebasehosting.googleapis.com" -or $uploadBaseUri.AbsolutePath.TrimEnd("/") -ne $expectedUploadPath -or -not [string]::IsNullOrEmpty($uploadBaseUri.Query) -or -not [string]::IsNullOrEmpty($uploadBaseUri.Fragment)) {
        throw "uploadUrl Firebase inatteso."
      }
    }
    foreach ($hash in $requiredHashes) {
      if ($hash -notmatch '^[0-9a-f]{64}$' -or -not $CompressedByHash.ContainsKey($hash)) {
        throw "Firebase richiede un hash non presente localmente: $hash"
      }
      $stage = "UploadFile"
      $null = Invoke-HostingTransactionTransport -Transport $Transport -Operation "UploadFile" -Method "POST" -Uri ($populate.uploadUrl.TrimEnd("/") + "/" + $hash) -Headers $Headers -InFile ([string]$CompressedByHash[$hash])
    }

    $stage = "FinalizeVersion"
    $finalized = Invoke-HostingTransactionTransport -Transport $Transport -Operation "FinalizeVersion" -Method "PATCH" -Uri "$versionUri`?updateMask=status" -Headers $Headers -Body @{ status = "FINALIZED" }
    if ($finalized.status -ne "FINALIZED") {
      throw "Finalizzazione Hosting non verificata."
    }
    if (-not (Test-HostingTransactionVersionName -VersionName ([string]$finalized.name) -SiteId $SiteId) -or (Get-HostingTransactionVersionId -VersionName ([string]$finalized.name)) -cne $versionId) {
      throw "La finalizzazione ha restituito una versione inattesa."
    }
    if (-not (Test-HostingTransactionExpectedLabels -Resource $finalized -ExpectedLabels $versionLabels)) {
      throw "La versione finalizzata non conserva tutte le label di ownership."
    }
    if (-not (Test-HostingTransactionConfig -ActualConfig $finalized.config -ExpectedConfig $targetConfig -ExpectedApiTag $TargetApiTag -RequiredNoCacheHeaders $RequiredNoCacheHeaders)) {
      throw "La configurazione o il tag API sono cambiati durante la finalizzazione."
    }

    $stage = "VerifyVersionFiles"
    $versionFiles = Get-HostingTransactionVersionFiles -Transport $Transport -Headers $Headers -VersionUri $versionUri
    $versionFilesError = Get-HostingTransactionVersionFilesError -VersionFiles $versionFiles -ExpectedFiles $FilesMap
    if ($null -ne $versionFilesError) {
      throw $versionFilesError
    }

    $stage = "CreateChannel"
    $channelLabels = @{
      "deployment-tool" = "codex-rest-v1"
      "deployment-id" = $DeploymentId
      "git-commit" = $ExpectedGitCommit
      "channel-id" = $ChannelId
      "source-live-version" = $ExpectedLiveVersionId
      "hosting-version" = $versionId
    }
    $channelBody = @{
      ttl = $ChannelTtl
      retainedReleaseCount = $RetainedReleaseCount
      labels = $channelLabels
    }
    try {
      $channel = Invoke-HostingTransactionTransport -Transport $Transport -Operation "CreateChannel" -Method "POST" -Uri "$apiRootNormalized/channels?channelId=$escapedChannelId" -Headers $Headers -Body $channelBody
      if ((Test-HostingTransactionChannelName -ChannelName ([string]$channel.name) -SiteId $SiteId -ChannelId $ChannelId) -and (Test-HostingTransactionExpectedLabels -Resource $channel -ExpectedLabels $channelLabels)) {
        $channelOwned = $true
      } else {
        $channelState = Get-HostingTransactionChannelState -Transport $Transport -Delay $Delay -Headers $Headers -ChannelUri $channelUri -SiteId $SiteId -ChannelId $ChannelId -ExpectedLabels $channelLabels -Attempts $ReconcileAttempts -DelayMilliseconds $ReconcileDelayMilliseconds -Reason "create-channel-response"
        if ($channelState.Kind -ne "Owned") {
          throw "Il canale restituito non appartiene al deployment corrente."
        }
        $channel = $channelState.Channel
        $channelOwned = $true
        $channelCreateReconciled = $true
      }
    } catch {
      if (-not (Test-HostingTransactionAmbiguousFailure -Exception $_.Exception)) {
        throw
      }
      $channelState = Get-HostingTransactionChannelState -Transport $Transport -Delay $Delay -Headers $Headers -ChannelUri $channelUri -SiteId $SiteId -ChannelId $ChannelId -ExpectedLabels $channelLabels -Attempts $ReconcileAttempts -DelayMilliseconds $ReconcileDelayMilliseconds -Reason "create-channel-timeout"
      if ($channelState.Kind -eq "Foreign") {
        throw "Dopo l'esito ambiguo esiste un canale non appartenente al deployment corrente."
      }
      if ($channelState.Kind -ne "Owned") {
        throw "Creazione del canale non confermata dopo l'esito ambiguo."
      }
      $channel = $channelState.Channel
      $channelOwned = $true
      $channelCreateReconciled = $true
    }

    $stage = "CreateRelease"
    try {
      $release = Invoke-HostingTransactionTransport -Transport $Transport -Operation "CreateRelease" -Method "POST" -Uri "$channelUri/releases?versionName=$([Uri]::EscapeDataString($versionName))" -Headers $Headers -Body @{
        message = "frontend $($ExpectedGitCommit.Substring(0, 7)) deployment $DeploymentId"
      }
      $releasedVersionName = [string]$release.version.name
      if (-not (Test-HostingTransactionVersionName -VersionName $releasedVersionName -SiteId $SiteId) -or (Get-HostingTransactionVersionId -VersionName $releasedVersionName) -cne $versionId) {
        throw "Il canale non punta alla versione appena creata."
      }
      $releaseCommitted = $true
    } catch {
      if (-not (Test-HostingTransactionAmbiguousFailure -Exception $_.Exception)) {
        throw
      }
      $channelState = Get-HostingTransactionChannelState -Transport $Transport -Delay $Delay -Headers $Headers -ChannelUri $channelUri -SiteId $SiteId -ChannelId $ChannelId -ExpectedLabels $channelLabels -Attempts $ReconcileAttempts -DelayMilliseconds $ReconcileDelayMilliseconds -Reason "create-release-timeout"
      $releasedName = if ($null -ne $channelState.Channel -and $null -ne $channelState.Channel.release) { [string]$channelState.Channel.release.version.name } else { $null }
      $releasedVersionMatches = -not [string]::IsNullOrWhiteSpace($releasedName) -and (Test-HostingTransactionVersionName -VersionName $releasedName -SiteId $SiteId) -and (Get-HostingTransactionVersionId -VersionName $releasedName) -ceq $versionId
      if ($channelState.Kind -eq "Owned" -and $releasedVersionMatches) {
        $releaseCommitted = $true
        $releaseReconciled = $true
      } else {
        throw "Release Hosting non confermata dopo l'esito ambiguo."
      }
    }

    return [PSCustomObject]@{
      ApiTag = $TargetApiTag
      Channel = $ChannelId
      ChannelCreateReconciled = $channelCreateReconciled
      ChannelUrl = $channel.url
      DeploymentId = $DeploymentId
      FileCount = $FileCount
      GitCommit = $ExpectedGitCommit
      ExpectedApiTag = $ExpectedApiTag
      ReleaseReconciled = $releaseReconciled
      RequiredUploads = $requiredHashes.Count
      Status = "Released"
      TargetApiTag = $TargetApiTag
      VersionCreateReconciled = $versionCreateReconciled
      VersionId = $versionId
      VersionName = $versionName
    }
  } catch {
    $originalFailure = $_.Exception
    if (-not $releaseCommitted) {
      if ($channelOwned -or $stage -in @("CreateChannel", "CreateRelease")) {
        if ($null -ne $channelLabels) {
          $cleanup.Channel = Remove-HostingTransactionOwnedResource -ResourceType "Channel" -Transport $Transport -Headers $Headers -ResourceUri $channelUri -ExpectedLabels $channelLabels -SiteId $SiteId -ChannelId $ChannelId -ExpectedLiveVersionId $ExpectedLiveVersionId
        }
      }
      $channelCleanupSafeForVersion = $null -eq $channelLabels -or $cleanup.Channel -in @("Deleted", "AlreadyMissing")
      if (-not [string]::IsNullOrWhiteSpace($versionId) -and $channelCleanupSafeForVersion) {
        $cleanup.Version = Remove-HostingTransactionOwnedResource -ResourceType "Version" -Transport $Transport -Headers $Headers -ResourceUri $versionUri -ExpectedLabels $versionLabels -SiteId $SiteId -VersionId $versionId -ExpectedLiveVersionId $ExpectedLiveVersionId -LiveChannelUri "$apiRootNormalized/channels/live"
      } elseif (-not [string]::IsNullOrWhiteSpace($versionId)) {
        $cleanup.Version = "PreservedForSafety"
      }
    }

    $failure = New-Object Exception("Transazione Hosting fallita nella fase $stage. $($originalFailure.Message)", $originalFailure)
    $failure.Data["CleanupChannel"] = [string]$cleanup.Channel
    $failure.Data["CleanupVersion"] = [string]$cleanup.Version
    $failure.Data["DeploymentId"] = $DeploymentId
    $failure.Data["TransactionStage"] = $stage
    throw $failure
  }
}
