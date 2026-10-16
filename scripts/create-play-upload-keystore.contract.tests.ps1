[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "create-play-upload-keystore.ps1"
$source = Get-Content -LiteralPath $scriptPath -Raw

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

function Assert-ThrowsLike {
    param([scriptblock]$Action, [string]$Pattern, [string]$Message)
    try {
        & $Action
    } catch {
        if ($_.Exception.Message -like $Pattern) { return }
        throw "$Message Actual: $($_.Exception.Message)"
    }
    throw $Message
}

$tokens = $null
$errors = $null
[void][Management.Automation.Language.Parser]::ParseFile(
    $scriptPath,
    [ref]$tokens,
    [ref]$errors
)
Assert-True ($errors.Count -eq 0) "Play upload key script must parse."
Assert-True ($source.Contains(
    'C:\Program Files\Android\Android Studio\jbr'
)) "Play upload key script must pin Android Studio JBR."
Assert-True (-not $source.Contains('$env:JAVA_HOME')) `
    "Play upload key script must not fall back to machine JAVA_HOME."
Assert-True ($source.Contains('-keysize 4096')) `
    "Play upload key must use RSA 4096."
Assert-True ($source.Contains('[IO.FileMode]::CreateNew')) `
    "Play upload key creation must use an exclusive lock."
Assert-True ($source.Contains('play-keystore.properties.{0}.tmp')) `
    "Properties must be staged before the same-volume move."
Assert-True ($source.Contains('$previousPasswordEnvironmentValue')) `
    "The process environment must be restored."
Assert-True ($source.Contains('$propertiesAcl.AreAccessRulesProtected')) `
    "The clear-text signing properties must retain the restricted staged ACL."
Assert-True ($source.Contains('[Array]::Clear($randomBytes')) `
    "Random password bytes must be cleared."
Assert-True ($source.Contains('Get-FileHash')) `
    "Certificate trust must come from the exported DER bytes."

$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Assert-ThrowsLike `
    -Action { & $scriptPath -SecureDirectory (Join-Path $workspaceRoot 'tmp-key') } `
    -Pattern '*outside the Git workspace*' `
    -Message 'A key path inside the repository must fail closed.'
Assert-ThrowsLike `
    -Action { & $scriptPath -SecureDirectory $workspaceRoot.ToUpperInvariant() } `
    -Pattern '*outside the Git workspace*' `
    -Message 'Workspace containment must be case-insensitive on Windows.'

$testRoot = Join-Path (
    [IO.Path]::GetTempPath()
) ("meteofriul-play-key-contract-{0}" -f [Guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $testRoot)
try {
    $sddlBefore = (Get-Acl -LiteralPath $testRoot).Sddl
    Assert-ThrowsLike `
        -Action { & $scriptPath -SecureDirectory $testRoot } `
        -Pattern '*requires a new dedicated directory*' `
        -Message 'A pre-existing key directory must fail closed.'
    $sddlAfter = (Get-Acl -LiteralPath $testRoot).Sddl
    Assert-True ($sddlAfter -ceq $sddlBefore) `
        'A rejected pre-existing directory must keep its original ACL.'
} finally {
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}

Write-Output "create_play_upload_keystore_contract_ok"
