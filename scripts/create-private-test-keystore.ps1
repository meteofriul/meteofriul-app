[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $workspaceRoot "frontend\android"
$keystorePath = Join-Path $androidRoot "meteofriul-private-test.keystore"
$propertiesPath = Join-Path $androidRoot "keystore.properties"
$alias = "meteofriul-private-test"

if ((Test-Path -LiteralPath $keystorePath) -or (Test-Path -LiteralPath $propertiesPath)) {
    throw "Private-test signing already exists; refusing to overwrite it."
}

$keytoolCandidates = @(
    $(if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME "bin\keytool.exe" }),
    "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$keytool = $keytoolCandidates | Select-Object -First 1
if (-not $keytool) {
    throw "keytool.exe was not found in JAVA_HOME or Android Studio JBR."
}

$randomBytes = New-Object byte[] 36
$randomNumberGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $randomNumberGenerator.GetBytes($randomBytes)
} finally {
    $randomNumberGenerator.Dispose()
}
$password = [Convert]::ToBase64String($randomBytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
$passwordEnvironmentName = "METEOFRIUL_PRIVATE_TEST_KEYSTORE_PASSWORD"

try {
    [Environment]::SetEnvironmentVariable(
        $passwordEnvironmentName,
        $password,
        [EnvironmentVariableTarget]::Process
    )
    & $keytool `
        -genkeypair `
        -keystore $keystorePath `
        -storetype PKCS12 `
        -alias $alias `
        -keyalg RSA `
        -keysize 4096 `
        -validity 10000 `
        -dname "CN=Meteo Friul Private Test, OU=Private Testing, O=Meteo Friul, L=Pordenone, ST=Friuli-Venezia Giulia, C=IT" `
        -storepass:env $passwordEnvironmentName `
        -keypass:env $passwordEnvironmentName
    if ($LASTEXITCODE -ne 0) {
        throw "keytool failed to create the private-test signing key."
    }

    $properties = @(
        "storeFile=meteofriul-private-test.keystore",
        "storePassword=$password",
        "keyAlias=$alias",
        "keyPassword=$password"
    ) -join "`n"
    [System.IO.File]::WriteAllText(
        $propertiesPath,
        "$properties`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $certificateDetails = & $keytool `
        -list `
        -v `
        -keystore $keystorePath `
        -alias $alias `
        -storepass:env $passwordEnvironmentName
    if ($LASTEXITCODE -ne 0) {
        throw "keytool failed to verify the private-test signing key."
    }
    $sha256 = $certificateDetails |
        Select-String -Pattern "SHA256:" |
        Select-Object -First 1
    if (-not $sha256) {
        throw "The private-test certificate SHA-256 fingerprint was not found."
    }

    [pscustomobject]@{
        keystore = $keystorePath
        properties = $propertiesPath
        alias = $alias
        certificate_sha256 = ($sha256.Line -replace ".*SHA256:\s*", "").Trim()
    } | ConvertTo-Json -Compress
} finally {
    [Environment]::SetEnvironmentVariable(
        $passwordEnvironmentName,
        $null,
        [EnvironmentVariableTarget]::Process
    )
    $password = $null
}
