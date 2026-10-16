$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "deploy-hosting-preview-rest.transaction.ps1")

function Assert-Contract {
  param(
    [Parameter(Mandatory = $true)][bool]$Condition,
    [Parameter(Mandatory = $true)][string]$Message
  )
  if (-not $Condition) {
    throw "Contract test fallito: $Message"
  }
}

function New-HostingTransactionMock {
  param(
    [Parameter(Mandatory = $true)][string]$Scenario,
    [Parameter(Mandatory = $true)][string]$TargetApiTag
  )

  $state = [PSCustomObject]@{
    Calls = New-Object System.Collections.ArrayList
    Channel = $null
    DelayCalls = New-Object System.Collections.ArrayList
    HiddenChannelReads = 0
    Scenario = $Scenario
    Version = $null
    VersionRootListCalls = 0
  }
  $site = "test-site"
  $channelId = "cards-contract"
  $deploymentId = ("d" * 32)
  $gitCommit = ("a" * 40)
  $liveVersionId = "0123456789abcdef"
  $versionId = "fedcba9876543210"
  $versionName = "sites/$site/versions/$versionId"
  $config = [PSCustomObject]@{
    headers = @(
      [PSCustomObject]@{ glob = "/manifest.webmanifest"; headers = [PSCustomObject]@{ "Cache-Control" = "public, max-age=300" } },
      [PSCustomObject]@{ glob = "/index.html"; headers = [PSCustomObject]@{ "Cache-Control" = "no-cache" } }
    )
    rewrites = @(
      [PSCustomObject]@{ glob = "/api/**"; run = [PSCustomObject]@{ serviceId = "meteofriul-api"; region = "europe-west1"; tag = "ui3-contract" } },
      [PSCustomObject]@{ glob = "**"; path = "/index.html" }
    )
  }
  $requiredNoCacheHeaders = @{
    "/firebase-messaging-sw.js" = "no-cache, no-store, must-revalidate"
    "/manifest.webmanifest" = "no-cache, must-revalidate"
  }
  $liveConfigJson = $config | ConvertTo-Json -Depth 100 -Compress
  $targetConfig = New-HostingTransactionTargetConfig -LiveConfig $config -ExpectedApiTag "ui3-contract" -TargetApiTag $TargetApiTag -RequiredNoCacheHeaders $requiredNoCacheHeaders
  $targetConfigJson = $targetConfig | ConvertTo-Json -Depth 100 -Compress
  # Firebase Hosting returns header rules with object properties ordered as headers, glob even
  # when newly added rules were sent as glob, headers. Keep the mock response server-shaped.
  $serverConfig = $targetConfig | ConvertTo-Json -Depth 100 -Compress | ConvertFrom-Json
  $serverConfig.headers = @($serverConfig.headers | ForEach-Object {
    [PSCustomObject][ordered]@{
      headers = $_.headers
      glob = $_.glob
    }
  })
  $versionLabels = @{
    "deployment-tool" = "codex-rest-v1"
    "deployment-id" = $deploymentId
    "git-commit" = $gitCommit
    "channel-id" = $channelId
    "source-live-version" = $liveVersionId
  }
  $channelLabels = @{
    "deployment-tool" = "codex-rest-v1"
    "deployment-id" = $deploymentId
    "git-commit" = $gitCommit
    "channel-id" = $channelId
    "source-live-version" = $liveVersionId
    "hosting-version" = $versionId
  }

  # Scriptblocks captured by GetNewClosure cannot resolve functions from a script invoked with
  # the call operator in Windows PowerShell 5.1. Keep every mock dependency in captured values.
  $makeFailure = {
    param([string]$Message, [int]$StatusCode, [bool]$Ambiguous)
    $exception = New-Object Exception($Message)
    if ($StatusCode -ne 0) {
      $exception.Data["StatusCode"] = $StatusCode
    }
    if ($Ambiguous) {
      $exception.Data["Ambiguous"] = $true
    }
    return $exception
  }.GetNewClosure()
  $require = {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
      throw "Mock contract fallito: $Message"
    }
  }.GetNewClosure()
  $requireLabels = {
    param($Actual, [hashtable]$Expected, [string]$Context)
    & $require ($null -ne $Actual) "$Context privo di labels"
    & $require ([int]$Actual.Count -eq [int]$Expected.Count) "$Context ha un numero inatteso di labels"
    foreach ($key in $Expected.Keys) {
      & $require ($Actual.ContainsKey($key)) "$Context non contiene $key"
      & $require ([string]$Actual[$key] -ceq [string]$Expected[$key]) "$Context ha un valore errato per $key"
    }
  }.GetNewClosure()

  $transport = {
    param($Request)
    $null = $state.Calls.Add($Request)
    switch ($Request.Operation) {
      "GetLive" {
        return [PSCustomObject]@{
          release = [PSCustomObject]@{
            version = [PSCustomObject]@{
              name = "sites/$site/versions/$liveVersionId"
              config = $config
            }
          }
        }
      }
      "GetChannel" {
        if ($null -eq $state.Channel) {
          throw (& $makeFailure "not found" 404 $false)
        }
        if ($state.HiddenChannelReads -gt 0) {
          $state.HiddenChannelReads -= 1
          throw (& $makeFailure "not visible yet" 404 $false)
        }
        return $state.Channel
      }
      "CreateVersion" {
        & $require ([string]$Request.Body.status -ceq "CREATED") "CreateVersion status inatteso"
        & $require (($Request.Body.config | ConvertTo-Json -Depth 100 -Compress) -ceq $targetConfigJson) "CreateVersion non usa la configurazione preview derivata"
        & $require ($config.rewrites[0].run.tag -ceq "ui3-contract") "CreateVersion ha mutato la configurazione live"
        & $requireLabels $Request.Body.labels $versionLabels "CreateVersion"
        $state.Version = [PSCustomObject]@{ name = $versionName; status = "CREATED"; config = $serverConfig; labels = $versionLabels }
        if ($state.Scenario -eq "version-timeout-owned") {
          throw (& $makeFailure "timeout after version commit" 504 $true)
        }
        return $state.Version
      }
      "ListVersions" {
        & $require ($state.Scenario -eq "version-timeout-owned") "ListVersions usato fuori dalla riconciliazione CreateVersion"
        if ($Request.Uri -match '[?&]pageToken=page-2(?:&|$)') {
          return [PSCustomObject]@{ versions = @($state.Version); nextPageToken = $null }
        }
        $state.VersionRootListCalls += 1
        if ($state.VersionRootListCalls -eq 1) {
          return [PSCustomObject]@{ versions = @(); nextPageToken = $null }
        }
        $foreignLabels = @{}
        foreach ($key in $versionLabels.Keys) { $foreignLabels[$key] = $versionLabels[$key] }
        $foreignLabels["deployment-id"] = ("e" * 32)
        $foreignVersion = [PSCustomObject]@{
          name = "sites/$site/versions/1111111111111111"
          status = "CREATED"
          config = $targetConfig
          labels = $foreignLabels
        }
        return [PSCustomObject]@{ versions = @($foreignVersion); nextPageToken = "page-2" }
      }
      "GetVersion" {
        if ($null -eq $state.Version) {
          throw (& $makeFailure "version not found" 404 $false)
        }
        return $state.Version
      }
      "ListVersionFiles" {
        if ($Request.Uri -notmatch '/files\?pageSize=1000') {
          throw "URI ListVersionFiles inatteso"
        }
        return [PSCustomObject]@{
          files = @(
            [PSCustomObject]@{ path = "/index.html"; hash = ("b" * 64); status = "ACTIVE" },
            [PSCustomObject]@{ path = "/assets/app.js"; hash = ("c" * 64); status = "ACTIVE" },
            [PSCustomObject]@{ path = "/__/firebase/init.js"; hash = ("d" * 64); status = "ACTIVE" },
            [PSCustomObject]@{ path = "/__/firebase/init.json"; hash = ("e" * 64); status = "ACTIVE" }
          )
          nextPageToken = $null
        }
      }
      "PopulateFiles" {
        return [PSCustomObject]@{ uploadRequiredHashes = @(); uploadUrl = $null }
      }
      "FinalizeVersion" {
        $state.Version = [PSCustomObject]@{ name = $versionName; status = "FINALIZED"; fileCount = $null; config = $state.Version.config; labels = $versionLabels }
        return $state.Version
      }
      "CreateChannel" {
        & $requireLabels $Request.Body.labels $channelLabels "CreateChannel"
        if ($state.Scenario -eq "channel-timeout-owned") {
          $state.Channel = [PSCustomObject]@{ name = "sites/$site/channels/$channelId"; url = "https://cards-contract--test-site.web.app"; labels = $channelLabels; release = $null }
          $state.HiddenChannelReads = 1
          throw (& $makeFailure "timeout after commit" 504 $true)
        }
        if ($state.Scenario -eq "channel-timeout-foreign") {
          $foreignLabels = @{}
          foreach ($key in $channelLabels.Keys) { $foreignLabels[$key] = $channelLabels[$key] }
          $foreignLabels["deployment-id"] = ("e" * 32)
          $state.Channel = [PSCustomObject]@{ name = "sites/$site/channels/$channelId"; url = "https://cards-contract--test-site.web.app"; labels = $foreignLabels; release = $null }
          throw (& $makeFailure "timeout with competing writer" 504 $true)
        }
        $state.Channel = [PSCustomObject]@{ name = "sites/$site/channels/$channelId"; url = "https://cards-contract--test-site.web.app"; labels = $channelLabels; release = $null }
        return $state.Channel
      }
      "CreateRelease" {
        if ($state.Scenario -eq "release-failure") {
          throw (& $makeFailure "bad release" 400 $false)
        }
        if ($state.Scenario -eq "release-timeout-committed") {
          $state.Channel.release = [PSCustomObject]@{ version = [PSCustomObject]@{ name = $versionName } }
          throw (& $makeFailure "timeout after release" 504 $true)
        }
        $state.Channel.release = [PSCustomObject]@{ version = [PSCustomObject]@{ name = $versionName } }
        return $state.Channel.release
      }
      "DeleteChannel" {
        $state.Channel = $null
        return [PSCustomObject]@{}
      }
      "DeleteVersion" {
        $state.Version = $null
        return [PSCustomObject]@{}
      }
      default {
        throw "Operazione mock inattesa: $($Request.Operation)"
      }
    }
  }.GetNewClosure()
  $delay = {
    param($Milliseconds, $Reason, $Attempt)
    $null = $state.DelayCalls.Add([PSCustomObject]@{ Milliseconds = $Milliseconds; Reason = $Reason; Attempt = $Attempt })
  }.GetNewClosure()

  return [PSCustomObject]@{
    ChannelLabels = $channelLabels
    Delay = $delay
    DeploymentId = $deploymentId
    GitCommit = $gitCommit
    LiveConfig = $config
    LiveConfigJson = $liveConfigJson
    LiveVersionId = $liveVersionId
    RequiredNoCacheHeaders = $requiredNoCacheHeaders
    ServerConfig = $serverConfig
    State = $state
    TargetApiTag = $TargetApiTag
    TargetConfig = $targetConfig
    Transport = $transport
    VersionId = $versionId
    VersionLabels = $versionLabels
  }
}

function Invoke-ContractScenario {
  param(
    [Parameter(Mandatory = $true)][string]$Scenario,
    [string]$ExpectedApiTag = "ui3-contract",
    [string]$TargetApiTag = "web-contract",
    [switch]$OmitTargetApiTag
  )

  $mock = New-HostingTransactionMock -Scenario $Scenario -TargetApiTag $TargetApiTag
  $parameters = @{
    ApiRoot = "https://firebasehosting.googleapis.com/v1beta1/sites/test-site"
    SiteId = "test-site"
    ChannelId = "cards-contract"
    ExpectedApiTag = $ExpectedApiTag
    ExpectedGitCommit = $mock.GitCommit
    ExpectedLiveVersionId = $mock.LiveVersionId
    DeploymentId = $mock.DeploymentId
    Headers = @{ Authorization = "Bearer test-only" }
    FilesMap = @{ "/index.html" = ("b" * 64); "/assets/app.js" = ("c" * 64) }
    CompressedByHash = @{}
    FileCount = 2
    RequiredNoCacheHeaders = $mock.RequiredNoCacheHeaders
    Transport = $mock.Transport
    Delay = $mock.Delay
    ReconcileAttempts = 3
    ReconcileDelayMilliseconds = 1
  }
  if (-not $OmitTargetApiTag) {
    $parameters.TargetApiTag = $TargetApiTag
  }
  try {
    $result = Invoke-HostingPreviewTransaction @parameters
    return [PSCustomObject]@{ Error = $null; Mock = $mock; Result = $result }
  } catch {
    return [PSCustomObject]@{ Error = $_.Exception; Mock = $mock; Result = $null }
  }
}

$happy = Invoke-ContractScenario -Scenario "happy"
Assert-Contract -Condition ($null -eq $happy.Error) -Message "happy path deve riuscire: $($happy.Error.Message)"
Assert-Contract -Condition ($happy.Result.Status -eq "Released") -Message "happy path non restituisce Released"
Assert-Contract -Condition ($happy.Result.VersionId -eq $happy.Mock.VersionId) -Message "version ID happy path inatteso"
Assert-Contract -Condition (@($happy.Mock.State.Calls | Where-Object { $_.Operation -like "Delete*" }).Count -eq 0) -Message "happy path ha eseguito cleanup"
$happyCreateVersion = @($happy.Mock.State.Calls | Where-Object { $_.Operation -eq "CreateVersion" })[0]
$happyCreateChannel = @($happy.Mock.State.Calls | Where-Object { $_.Operation -eq "CreateChannel" })[0]
$happyCreateVersionJson = $happyCreateVersion.Body | ConvertTo-Json -Depth 100 -Compress
$happyCreateVersionBytes = [Text.Encoding]::UTF8.GetBytes($happyCreateVersionJson)
$serializedCreateVersion = [Text.Encoding]::UTF8.GetString($happyCreateVersionBytes) | ConvertFrom-Json
$serializedHeaderRules = @($serializedCreateVersion.config.headers)
Assert-Contract -Condition (Test-HostingTransactionExpectedLabels -Resource ([PSCustomObject]@{ labels = $happyCreateVersion.Body.labels }) -ExpectedLabels $happy.Mock.VersionLabels) -Message "body Version non contiene ownership completa"
Assert-Contract -Condition (Test-HostingTransactionExpectedLabels -Resource ([PSCustomObject]@{ labels = $happyCreateChannel.Body.labels }) -ExpectedLabels $happy.Mock.ChannelLabels) -Message "body Channel non contiene ownership completa"
Assert-Contract -Condition ($happyCreateChannel.Body.labels["hosting-version"] -ceq $happy.Mock.VersionId) -Message "label hosting-version del Channel inattesa"
Assert-Contract -Condition ($happy.Result.ExpectedApiTag -ceq "ui3-contract") -Message "ExpectedApiTag non resta la baseline live"
Assert-Contract -Condition ($happy.Result.TargetApiTag -ceq "web-contract") -Message "TargetApiTag preview inatteso"
Assert-Contract -Condition ($happy.Mock.State.Calls[0].Operation -ceq "GetLive") -Message "la transazione non legge live come baseline"
Assert-Contract -Condition ($happyCreateVersion.Body.config.rewrites[0].run.tag -ceq "web-contract") -Message "il rewrite API preview non usa il target"
Assert-Contract -Condition ($happyCreateVersion.Body.config.rewrites[0].run.serviceId -ceq "meteofriul-api") -Message "il rewrite API ha perso serviceId"
Assert-Contract -Condition ($happyCreateVersion.Body.config.rewrites[0].run.region -ceq "europe-west1") -Message "il rewrite API ha perso region"
Assert-Contract -Condition ($happy.Mock.TargetConfig.headers.Count -eq 3) -Message "gli header live estranei non sono stati preservati"
Assert-Contract -Condition (Test-HostingTransactionNoCacheHeaders -Config $happyCreateVersion.Body.config -RequiredNoCacheHeaders $happy.Mock.RequiredNoCacheHeaders) -Message "header Web runtime non sincronizzati"
Assert-Contract -Condition ($happyCreateVersionBytes -is [byte[]]) -Message "il body CreateVersion effettivo non e stato serializzato in UTF-8"
Assert-Contract -Condition ($serializedHeaderRules.Count -eq 3) -Message "la serializzazione CreateVersion ha perso regole header"
foreach ($rule in $serializedHeaderRules) {
  $headerMap = Get-HostingTransactionHeaderMapState -HeaderMap $rule.headers
  Assert-Contract -Condition ($headerMap.IsValid -and -not ($rule.headers -is [array])) -Message "rule.headers nel JSON CreateVersion non e un object/map"
}
$legacyHeaderConfig = [PSCustomObject]@{
  headers = @([PSCustomObject]@{
    glob = "/legacy"
    headers = @([PSCustomObject]@{ key = "Cache-Control"; value = "no-cache" })
  })
}
Assert-Contract -Condition (-not (Test-HostingTransactionHeaderMaps -Config $legacyHeaderConfig)) -Message "il formato array key/value legacy non viene respinto"
Assert-Contract -Condition (($happy.Mock.ServerConfig | ConvertTo-Json -Depth 100 -Compress) -cne ($happy.Mock.TargetConfig | ConvertTo-Json -Depth 100 -Compress)) -Message "la fixture server-like non cambia l'ordine headers/glob"
Assert-Contract -Condition (Test-HostingTransactionConfig -ActualConfig $happy.Mock.ServerConfig -ExpectedConfig $happy.Mock.TargetConfig -ExpectedApiTag "web-contract" -RequiredNoCacheHeaders $happy.Mock.RequiredNoCacheHeaders) -Message "la normalizzazione server headers-before-glob produce un falso mismatch"
$mutatedServerConfig = $happy.Mock.ServerConfig | ConvertTo-Json -Depth 100 -Compress | ConvertFrom-Json
$mutatedServerConfig.headers[0].headers."Cache-Control" = "public, max-age=999"
Assert-Contract -Condition (-not (Test-HostingTransactionConfig -ActualConfig $mutatedServerConfig -ExpectedConfig $happy.Mock.TargetConfig -ExpectedApiTag "web-contract" -RequiredNoCacheHeaders $happy.Mock.RequiredNoCacheHeaders)) -Message "una mutazione reale della configurazione non viene respinta"
$mutatedTagConfig = $happy.Mock.ServerConfig | ConvertTo-Json -Depth 100 -Compress | ConvertFrom-Json
$mutatedTagConfig.rewrites[0].run.tag = "foreign-contract"
Assert-Contract -Condition (-not (Test-HostingTransactionConfig -ActualConfig $mutatedTagConfig -ExpectedConfig $happy.Mock.TargetConfig -ExpectedApiTag "web-contract" -RequiredNoCacheHeaders $happy.Mock.RequiredNoCacheHeaders)) -Message "un tag API alterato non viene respinto"
$reorderedServerConfig = $happy.Mock.ServerConfig | ConvertTo-Json -Depth 100 -Compress | ConvertFrom-Json
[Array]::Reverse($reorderedServerConfig.headers)
Assert-Contract -Condition (-not (Test-HostingTransactionConfig -ActualConfig $reorderedServerConfig -ExpectedConfig $happy.Mock.TargetConfig -ExpectedApiTag "web-contract" -RequiredNoCacheHeaders $happy.Mock.RequiredNoCacheHeaders)) -Message "l'ordine delle regole header non resta significativo"
$canonicalFixtureLeft = [PSCustomObject]@{
  nested = [ordered]@{ z = 1; a = $true }
  values = @("1", 1)
}
$canonicalFixtureRight = [PSCustomObject][ordered]@{
  values = @("1", 1)
  nested = [PSCustomObject][ordered]@{ a = $true; z = 1 }
}
Assert-Contract -Condition ((ConvertTo-HostingTransactionCanonicalJson -Value $canonicalFixtureLeft) -ceq (ConvertTo-HostingTransactionCanonicalJson -Value $canonicalFixtureRight)) -Message "la canonicalizzazione ricorsiva di object/map non e stabile"
$canonicalTypeMutation = [PSCustomObject][ordered]@{
  values = @("1", "1")
  nested = [PSCustomObject][ordered]@{ a = $true; z = 1 }
}
Assert-Contract -Condition ((ConvertTo-HostingTransactionCanonicalJson -Value $canonicalFixtureLeft) -cne (ConvertTo-HostingTransactionCanonicalJson -Value $canonicalTypeMutation)) -Message "la canonicalizzazione non conserva i tipi scalari"
$canonicalArrayMutation = [PSCustomObject][ordered]@{
  values = @(1, "1")
  nested = [PSCustomObject][ordered]@{ a = $true; z = 1 }
}
Assert-Contract -Condition ((ConvertTo-HostingTransactionCanonicalJson -Value $canonicalFixtureLeft) -cne (ConvertTo-HostingTransactionCanonicalJson -Value $canonicalArrayMutation)) -Message "la canonicalizzazione non conserva l'ordine degli array"
Assert-Contract -Condition ($happy.Mock.LiveConfig.rewrites[0].run.tag -ceq "ui3-contract") -Message "il rewrite della baseline live e stato mutato"
Assert-Contract -Condition ($happy.Mock.LiveConfig.headers[0].headers.PSObject.Properties["Cache-Control"].Value -ceq "public, max-age=300") -Message "gli header della baseline live sono stati mutati"
Assert-Contract -Condition (@($happy.Mock.LiveConfig.headers | Where-Object { $_.glob -eq "/firebase-messaging-sw.js" }).Count -eq 0) -Message "la regola service worker e stata aggiunta all'oggetto live"
Assert-Contract -Condition (($happy.Mock.LiveConfig | ConvertTo-Json -Depth 100 -Compress) -ceq $happy.Mock.LiveConfigJson) -Message "la configurazione live non e rimasta immutata byte-per-byte"
Assert-Contract -Condition ($happy.Mock.State.Calls[0].Body -eq $null -and $happy.Mock.TargetConfig -ne $null) -Message "la lettura baseline non deve inviare una configurazione"

$baselineMismatch = Invoke-ContractScenario -Scenario "baseline-mismatch" -ExpectedApiTag "unexpected-live" -TargetApiTag "web-contract"
Assert-Contract -Condition ($null -ne $baselineMismatch.Error) -Message "ExpectedApiTag errato deve bloccare la transazione"
Assert-Contract -Condition ($baselineMismatch.Error.Data["TransactionStage"] -eq "ReadLive") -Message "baseline errata non viene respinta durante ReadLive"
Assert-Contract -Condition ($baselineMismatch.Mock.State.Calls.Count -eq 1 -and $baselineMismatch.Mock.State.Calls[0].Operation -eq "GetLive") -Message "baseline errata ha eseguito operazioni mutanti"

$backwardCompatible = Invoke-ContractScenario -Scenario "backward-compatible" -TargetApiTag "ui3-contract" -OmitTargetApiTag
Assert-Contract -Condition ($null -eq $backwardCompatible.Error) -Message "TargetApiTag omesso deve usare la baseline: $($backwardCompatible.Error.Message)"
Assert-Contract -Condition ($backwardCompatible.Result.TargetApiTag -ceq "ui3-contract") -Message "default TargetApiTag non coincide con ExpectedApiTag"

$versionFilesCall = @($happy.Mock.State.Calls | Where-Object { $_.Operation -eq "ListVersionFiles" })
Assert-Contract -Condition ($versionFilesCall.Count -eq 1) -Message "happy path non verifica l'elenco file Hosting"

$releaseFailure = Invoke-ContractScenario -Scenario "release-failure"
Assert-Contract -Condition ($null -ne $releaseFailure.Error) -Message "release failure deve fallire"
Assert-Contract -Condition ($releaseFailure.Error.Data["TransactionStage"] -eq "CreateRelease") -Message "fase release failure inattesa"
Assert-Contract -Condition ($releaseFailure.Error.Data["CleanupChannel"] -eq "Deleted") -Message "release failure non elimina il canale owned"
Assert-Contract -Condition ($releaseFailure.Error.Data["CleanupVersion"] -eq "Deleted") -Message "release failure non elimina la versione owned"
$releaseFailureCleanup = @($releaseFailure.Mock.State.Calls | Where-Object { $_.Operation -in @("GetChannel", "DeleteChannel", "GetVersion", "DeleteVersion") } | Select-Object -Last 4 | ForEach-Object { $_.Operation })
Assert-Contract -Condition (($releaseFailureCleanup -join ",") -eq "GetChannel,DeleteChannel,GetVersion,DeleteVersion") -Message "cleanup non verifica ownership o usa un ordine inatteso"

$channelOwned = Invoke-ContractScenario -Scenario "channel-timeout-owned"
Assert-Contract -Condition ($null -eq $channelOwned.Error) -Message "timeout create channel owned deve riconciliarsi: $($channelOwned.Error.Message)"
Assert-Contract -Condition ([bool]$channelOwned.Result.ChannelCreateReconciled) -Message "manca flag riconciliazione canale"
Assert-Contract -Condition ($channelOwned.Mock.State.DelayCalls.Count -eq 1) -Message "delay iniettato non usato tra i tentativi di riconciliazione"
Assert-Contract -Condition (@($channelOwned.Mock.State.Calls | Where-Object { $_.Operation -like "Delete*" }).Count -eq 0) -Message "timeout owned riuscito ha eseguito cleanup"

$channelForeign = Invoke-ContractScenario -Scenario "channel-timeout-foreign"
Assert-Contract -Condition ($null -ne $channelForeign.Error) -Message "timeout create channel foreign deve fallire"
Assert-Contract -Condition (@($channelForeign.Mock.State.Calls | Where-Object { $_.Operation -eq "DeleteChannel" }).Count -eq 0) -Message "cleanup ha eliminato canale foreign"
Assert-Contract -Condition (@($channelForeign.Mock.State.Calls | Where-Object { $_.Operation -eq "DeleteVersion" }).Count -eq 0) -Message "cleanup non deve eliminare la versione finche un canale foreign potrebbe referenziarla"
Assert-Contract -Condition ($null -ne $channelForeign.Mock.State.Channel) -Message "canale foreign non e stato preservato"
Assert-Contract -Condition ($channelForeign.Error.Data["CleanupVersion"] -eq "PreservedForSafety") -Message "versione owned non preservata esplicitamente dopo canale foreign"

$releaseTimeout = Invoke-ContractScenario -Scenario "release-timeout-committed"
Assert-Contract -Condition ($null -eq $releaseTimeout.Error) -Message "release timeout committed deve riuscire: $($releaseTimeout.Error.Message)"
Assert-Contract -Condition ([bool]$releaseTimeout.Result.ReleaseReconciled) -Message "manca flag riconciliazione release"
Assert-Contract -Condition (@($releaseTimeout.Mock.State.Calls | Where-Object { $_.Operation -like "Delete*" }).Count -eq 0) -Message "release committed riconciliata ha eseguito cleanup"

$versionTimeout = Invoke-ContractScenario -Scenario "version-timeout-owned"
Assert-Contract -Condition ($null -eq $versionTimeout.Error) -Message "timeout CreateVersion owned deve riconciliarsi: $($versionTimeout.Error.Message)"
Assert-Contract -Condition ([bool]$versionTimeout.Result.VersionCreateReconciled) -Message "manca flag riconciliazione versione"
Assert-Contract -Condition (@($versionTimeout.Mock.State.Calls | Where-Object { $_.Operation -eq "CreateVersion" }).Count -eq 1) -Message "CreateVersion e stato ritentato dopo un timeout ambiguo"
Assert-Contract -Condition (@($versionTimeout.Mock.State.Calls | Where-Object { $_.Operation -eq "ListVersions" }).Count -eq 3) -Message "riconciliazione versione non ha usato retry e paginazione"
Assert-Contract -Condition (@($versionTimeout.Mock.State.DelayCalls | Where-Object { $_.Reason -eq "create-version-timeout" }).Count -eq 1) -Message "retry riconciliazione versione privo di delay iniettato"
Assert-Contract -Condition (@($versionTimeout.Mock.State.Calls | Where-Object { $_.Operation -like "Delete*" }).Count -eq 0) -Message "version timeout owned riuscito ha eseguito cleanup"

# Protection rules are evaluated before transport: live can never be queried or deleted by cleanup.
$unexpectedTransport = { param($Request) throw "transport non deve essere invocato per risorse protette" }
$protectedVersion = Remove-HostingTransactionOwnedResource -ResourceType "Version" -Transport $unexpectedTransport -Headers @{} -ResourceUri "unused" -ExpectedLabels $happy.Mock.VersionLabels -SiteId "test-site" -VersionId $happy.Mock.LiveVersionId -ExpectedLiveVersionId $happy.Mock.LiveVersionId
$protectedChannel = Remove-HostingTransactionOwnedResource -ResourceType "Channel" -Transport $unexpectedTransport -Headers @{} -ResourceUri "unused" -ExpectedLabels $happy.Mock.ChannelLabels -SiteId "test-site" -ChannelId "live" -ExpectedLiveVersionId $happy.Mock.LiveVersionId
Assert-Contract -Condition ($protectedVersion -eq "Protected") -Message "cleanup non protegge la versione live"
Assert-Contract -Condition ($protectedChannel -eq "Protected") -Message "cleanup non protegge il canale live"

[PSCustomObject]@{
  HappyPath = "PASS"
  SeparateTargetApiTag = "PASS"
  LiveBaselineGuard = "PASS"
  BackwardCompatibleTarget = "PASS"
  WebRuntimeHeaders = "PASS"
  RestHeaderMaps = "PASS"
  VersionFilesVerified = "PASS"
  ReleaseFailureCleanup = "PASS"
  ChannelTimeoutOwned = "PASS"
  ChannelTimeoutForeign = "PASS"
  ReleaseTimeoutCommitted = "PASS"
  VersionTimeoutOwned = "PASS"
  ProtectedResources = "PASS"
  Result = "PASS"
} | ConvertTo-Json -Compress
