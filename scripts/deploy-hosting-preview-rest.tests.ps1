$ErrorActionPreference = "Stop"
$scriptPath = Join-Path $PSScriptRoot "deploy-hosting-preview-rest.ps1"
$contractTestPath = Join-Path $PSScriptRoot "deploy-hosting-preview-rest.contract.tests.ps1"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Assert-True {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) {
    throw $Message
  }
}

$contractOutput = & $contractTestPath
$contract = $contractOutput | ConvertFrom-Json
Assert-True ($contract.Result -eq "PASS") "I contract test REST Hosting non sono passati."

$selfTestOutput = & $scriptPath `
  -ChannelId "cards-selftest" `
  -ExpectedApiTag "ui3-selftest" `
  -ExpectedGitCommit "0000000000000000000000000000000000000000" `
  -ExpectedLiveVersionId "0000000000000000" `
  -SelfTest
$selfTest = $selfTestOutput | ConvertTo-Json -Depth 10 | ConvertFrom-Json
Assert-True ($selfTest.JsonByteArray -eq $true) "Il self-test JSON byte array non e passato."
Assert-True ($selfTest.MissingChannelStatus -eq 404) "Il self-test 404 non e passato."
Assert-True ($selfTest.GZip -eq "ok") "Il self-test gzip non e passato."
Assert-True ($selfTest.HostingHeaders -eq "ok") "Il self-test header Web runtime non e passato."
Assert-True ($selfTest.HttpResponseMessage -eq "ok") "Il self-test HttpResponseMessage non e passato."
Assert-True ($selfTest.RestHeaderMaps -eq "ok") "Il self-test mappe header REST non e passato."
Assert-True ($selfTest.ErrorPropagation -eq "ok") "Il self-test propagazione errori non e passato."
Assert-True ($selfTest.Transport -eq "ok") "Il self-test transport reale non e passato."

$actualCommit = (& git -C $repositoryRoot rev-parse HEAD).Trim()
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
$buildLockStream = [IO.File]::Open(
  $buildLockPath,
  [IO.FileMode]::OpenOrCreate,
  [IO.FileAccess]::ReadWrite,
  [IO.FileShare]::None
)
try {
  $concurrentBuildRejected = $false
  try {
    & $scriptPath `
      -ChannelId "cards-lock-test" `
      -ExpectedApiTag "ui3-lock-test" `
      -ExpectedGitCommit $actualCommit `
      -ExpectedLiveVersionId "0000000000000000" `
      -PreflightOnly | Out-Null
  } catch {
    if ($_.Exception.Message -like "*altro preflight/deploy*") {
      $concurrentBuildRejected = $true
    } else {
      throw
    }
  }
  Assert-True $concurrentBuildRejected "Il lock non ha respinto una seconda build concorrente."
} finally {
  $buildLockStream.Dispose()
}

$originalLocation = Get-Location
try {
  Set-Location ([IO.Path]::GetTempPath())
  $preflightOutput = & $scriptPath `
    -ChannelId "cards-preflight" `
    -ExpectedApiTag "ui3-preflight" `
    -TargetApiTag "web-preflight" `
    -ExpectedGitCommit $actualCommit `
    -ExpectedLiveVersionId "0000000000000000" `
    -PreflightOnly
} finally {
  Set-Location $originalLocation
}
$preflight = $preflightOutput | ConvertFrom-Json
Assert-True ($preflight.Mode -eq "preflight-only") "Preflight mode inatteso."
Assert-True ($preflight.JsonBodyIsByteArray -eq $true) "Il body populateFiles non e un byte array."
Assert-True ($preflight.FileCount -le 1000) "La build supera il limite populateFiles."
Assert-True ($preflight.FileCount -ge 400) "La build e incompleta."
Assert-True ($preflight.IndexAssets.Count -ge 2) "Asset index insufficienti."
Assert-True ($preflight.ExpectedApiTag -eq "ui3-preflight") "ExpectedApiTag non resta la baseline live."
Assert-True ($preflight.TargetApiTag -eq "web-preflight") "TargetApiTag preview inatteso."
Assert-True ($preflight.HostingNoCacheHeaders."/firebase-messaging-sw.js" -eq "no-cache, no-store, must-revalidate") "Header service worker non coerente con firebase.json."
Assert-True ($preflight.HostingNoCacheHeaders."/manifest.webmanifest" -eq "no-cache, must-revalidate") "Header manifest non coerente con firebase.json."

[PSCustomObject]@{
  FileCount = $preflight.FileCount
  GZip = $selfTest.GZip
  HostingHeaders = $selfTest.HostingHeaders
  HttpResponseMessage = $selfTest.HttpResponseMessage
  JsonByteArray = $selfTest.JsonByteArray
  Lock = "ok"
  MissingChannelStatus = $selfTest.MissingChannelStatus
  RestHeaderMaps = $selfTest.RestHeaderMaps
  Result = "PASS"
} | ConvertTo-Json -Compress
