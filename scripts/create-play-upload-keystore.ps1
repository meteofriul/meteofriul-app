[CmdletBinding()]
param(
    [string]$SecureDirectory = (Join-Path $env:USERPROFILE (
        "Documents\MeteoFriul-secure\play-upload-key"
    ))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = [IO.Path]::GetFullPath($workspaceRoot)
$androidRoot = Join-Path $workspaceRoot "frontend\android"
$propertiesPath = Join-Path $androidRoot "play-keystore.properties"
$secureRoot = [IO.Path]::GetFullPath($SecureDirectory)
$keystorePath = Join-Path $secureRoot "meteofriul-play-upload.jks"
$certificatePath = Join-Path $secureRoot "meteofriul-play-upload-cert.der"
$propertiesTemporaryPath = Join-Path $androidRoot (
    "play-keystore.properties.{0}.tmp" -f [Guid]::NewGuid().ToString("N")
)
$lockPath = Join-Path $secureRoot ".play-upload-keystore.lock"
$alias = "meteofriul-play-upload"
$passwordEnvironmentName = "METEOFRIUL_PLAY_UPLOAD_KEYSTORE_PASSWORD"

if ([string]::Equals(
    $secureRoot,
    $workspaceRoot,
    [StringComparison]::OrdinalIgnoreCase
) -or $secureRoot.StartsWith(
    $workspaceRoot + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "The Play upload key must be stored outside the Git workspace."
}
$fileSystemRoot = [IO.Path]::GetPathRoot($secureRoot)
if ([string]::Equals(
    $secureRoot.TrimEnd('\', '/'),
    $fileSystemRoot.TrimEnd('\', '/'),
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "A filesystem root cannot store the Play upload key."
}
if (Test-Path -LiteralPath $secureRoot) {
    throw "The Play upload key requires a new dedicated directory."
}
$secureParent = Split-Path -Parent $secureRoot
if (-not (Test-Path -LiteralPath $secureParent -PathType Container)) {
    throw "The parent of the Play upload key directory must already exist."
}
$ancestor = Get-Item -LiteralPath $secureParent -Force
while ($null -ne $ancestor) {
    if (($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "A reparse-point path is not accepted for the Play upload key."
    }
    $parentPath = Split-Path -Parent $ancestor.FullName
    if ([string]::IsNullOrWhiteSpace($parentPath) -or
        [string]::Equals(
            $parentPath.TrimEnd('\', '/'),
            $ancestor.FullName.TrimEnd('\', '/'),
            [StringComparison]::OrdinalIgnoreCase
        )) {
        break
    }
    $ancestor = Get-Item -LiteralPath $parentPath -Force
}

foreach ($path in @(
    $keystorePath,
    $certificatePath,
    $propertiesPath,
    $propertiesTemporaryPath,
    $lockPath
)) {
    if (Test-Path -LiteralPath $path) {
        throw "Play upload signing already exists; refusing to overwrite: $path"
    }
}

$jbrRoot = "C:\Program Files\Android\Android Studio\jbr"
$keytool = Join-Path $jbrRoot "bin\keytool.exe"
$java = Join-Path $jbrRoot "bin\java.exe"
if (-not (Test-Path -LiteralPath $keytool -PathType Leaf) -or
    -not (Test-Path -LiteralPath $java -PathType Leaf)) {
    throw "Android Studio JBR 21 keytool/java were not found."
}
$javaVersion = (& $java -version 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $javaVersion -notmatch 'version\s+"21(?:\.|\")') {
    throw "Android Studio JBR major version 21 is required."
}

$createdSecureRoot = $false
$lockStream = $null
$randomBytes = $null
$password = $null
$previousPasswordEnvironmentValue = $null
$environmentCaptured = $false
$completed = $false
try {
    [void](New-Item -ItemType Directory -Path $secureRoot)
    $createdSecureRoot = $true
$directorySecurity = [Security.AccessControl.DirectorySecurity]::new()
$directorySecurity.SetAccessRuleProtection($true, $false)
$inheritanceFlags = (
    [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
    [Security.AccessControl.InheritanceFlags]::ObjectInherit
)
$accessIdentities = @(
    [Security.Principal.WindowsIdentity]::GetCurrent().User,
    [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
    [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
)
foreach ($identity in $accessIdentities) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        [Security.AccessControl.FileSystemRights]::FullControl,
        $inheritanceFlags,
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow
    )
    [void]$directorySecurity.AddAccessRule($rule)
}
Set-Acl -LiteralPath $secureRoot -AclObject $directorySecurity
$fileSecurity = [Security.AccessControl.FileSecurity]::new()
$fileSecurity.SetAccessRuleProtection($true, $false)
foreach ($identity in $accessIdentities) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new(
        $identity,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.AccessControlType]::Allow
    )
    [void]$fileSecurity.AddAccessRule($rule)
}
$resolvedSecureRoot = [IO.Path]::GetFullPath(
    (Resolve-Path -LiteralPath $secureRoot).Path
)
if ([string]::Equals(
    $resolvedSecureRoot,
    $workspaceRoot,
    [StringComparison]::OrdinalIgnoreCase
) -or $resolvedSecureRoot.StartsWith(
    $workspaceRoot + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "The resolved Play upload key directory is inside the Git workspace."
}
$secureItem = Get-Item -LiteralPath $resolvedSecureRoot -Force
if (($secureItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw "A reparse-point directory is not accepted for the Play upload key."
}

    $lockStream = [IO.File]::Open(
        $lockPath,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )

    $randomBytes = New-Object byte[] 36
    $randomNumberGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $randomNumberGenerator.GetBytes($randomBytes)
    } finally {
        $randomNumberGenerator.Dispose()
    }
    $password = [Convert]::ToBase64String($randomBytes).
        TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $previousPasswordEnvironmentValue = [Environment]::GetEnvironmentVariable(
        $passwordEnvironmentName,
        [EnvironmentVariableTarget]::Process
    )
    $environmentCaptured = $true
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
        -dname "CN=Meteo Friul Play Upload, OU=Meteo Friul, O=Riccardo Rosset, L=Pordenone, ST=Friuli-Venezia Giulia, C=IT" `
        -storepass:env $passwordEnvironmentName `
        -keypass:env $passwordEnvironmentName
    if ($LASTEXITCODE -ne 0 -or
        -not (Test-Path -LiteralPath $keystorePath -PathType Leaf)) {
        throw "keytool failed to create the Play upload signing key."
    }

    & $keytool `
        -exportcert `
        -keystore $keystorePath `
        -alias $alias `
        -file $certificatePath `
        -storepass:env $passwordEnvironmentName
    if ($LASTEXITCODE -ne 0 -or
        -not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
        throw "keytool failed to export the Play upload certificate."
    }
    $sha256 = (Get-FileHash `
        -Algorithm SHA256 `
        -LiteralPath $certificatePath).Hash.ToLowerInvariant()
    if ($sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "The Play upload certificate SHA-256 fingerprint is invalid."
    }

    $storeFile = $keystorePath.Replace("\", "/")
    $properties = @(
        "storeFile=$storeFile",
        "storePassword=$password",
        "keyAlias=$alias",
        "keyPassword=$password"
    ) -join "`n"
    [void](New-Item -ItemType File -Path $propertiesTemporaryPath)
    Set-Acl -LiteralPath $propertiesTemporaryPath -AclObject $fileSecurity
    [IO.File]::WriteAllText(
        $propertiesTemporaryPath,
        "$properties`n",
        [Text.UTF8Encoding]::new($false)
    )
    Move-Item `
        -LiteralPath $propertiesTemporaryPath `
        -Destination $propertiesPath `
        -ErrorAction Stop
    $propertiesAcl = Get-Acl -LiteralPath $propertiesPath
    if (-not $propertiesAcl.AreAccessRulesProtected) {
        throw "The Play signing properties ACL still inherits permissions."
    }
    $allowedSids = @($accessIdentities | ForEach-Object { $_.Value })
    $unexpectedAllow = @(
        $propertiesAcl.Access | Where-Object {
            $_.AccessControlType -eq `
                [Security.AccessControl.AccessControlType]::Allow -and
            $_.IdentityReference.Translate(
                [Security.Principal.SecurityIdentifier]
            ).Value -notin $allowedSids
        }
    )
    if ($unexpectedAllow.Count -ne 0) {
        throw "The Play signing properties ACL contains an unexpected identity."
    }

    $result = [pscustomobject]@{
        keystore = $keystorePath
        certificate = $certificatePath
        properties = $propertiesPath
        alias = $alias
        certificate_sha256 = $sha256
    }
    $completed = $true
    $result | ConvertTo-Json -Compress
} catch {
    foreach ($path in @(
        $propertiesTemporaryPath,
        $propertiesPath,
        $certificatePath,
        $keystorePath
    )) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Remove-Item -LiteralPath $path -Force
        }
    }
    throw
} finally {
    if ($environmentCaptured) {
        [Environment]::SetEnvironmentVariable(
            $passwordEnvironmentName,
            $previousPasswordEnvironmentValue,
            [EnvironmentVariableTarget]::Process
        )
    }
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
    if (Test-Path -LiteralPath $lockPath -PathType Leaf) {
        Remove-Item -LiteralPath $lockPath -Force
    }
    if (-not $completed -and
        $createdSecureRoot -and
        (Test-Path -LiteralPath $secureRoot -PathType Container) -and
        @(Get-ChildItem -LiteralPath $secureRoot -Force).Count -eq 0) {
        Remove-Item -LiteralPath $secureRoot -Force
    }
    $password = $null
    if ($null -ne $randomBytes) {
        [Array]::Clear($randomBytes, 0, $randomBytes.Length)
    }
}
