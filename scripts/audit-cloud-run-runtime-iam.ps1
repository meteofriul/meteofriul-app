[CmdletBinding()]
param(
    [ValidateSet("Baseline", "TargetReady", "Cutover", "Final")][string]$Stage = "Baseline",
    [string]$FixturePath = "",
    [string]$TargetServiceAccount = "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com",
    [string]$FcmCustomRole = "projects/meteo-friul/roles/meteofriulFcmSender",
    [string]$RollbackRevision = "",
    [string]$GcloudPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot "cloud-run-runtime-iam-audit.psm1") -Force

function Assert-SafeIdentifier {
    param([string]$Value, [string]$Pattern, [string]$Code)
    if ($Value -cnotmatch $Pattern) { throw $Code }
}

function Invoke-GcloudJson {
    param([string[]]$Arguments)
    $output = & $script:GcloudExecutable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud_read_failed: $($Arguments -join ' ')"
    }
    return (($output -join [Environment]::NewLine) | ConvertFrom-Json)
}

function Invoke-GcloudText {
    param([string[]]$Arguments)
    $output = & $script:GcloudExecutable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud_read_failed: $($Arguments -join ' ')"
    }
    return [string]($output -join [Environment]::NewLine).Trim()
}

function Get-LiveSnapshot {
    Assert-SafeIdentifier $TargetServiceAccount '^[a-z][a-z0-9-]{4,28}[a-z0-9]@meteo-friul\.iam\.gserviceaccount\.com$' 'target_service_account_invalid'
    Assert-SafeIdentifier $FcmCustomRole '^projects/meteo-friul/roles/[A-Za-z0-9_.]{3,64}$' 'fcm_custom_role_invalid'
    if ($RollbackRevision) {
        Assert-SafeIdentifier $RollbackRevision '^meteofriul-api-[a-z0-9-]{1,50}$' 'rollback_revision_invalid'
    }

    if (-not $GcloudPath) {
        $command = Get-Command gcloud.cmd -ErrorAction SilentlyContinue
        if ($null -ne $command) { $script:GcloudExecutable = $command.Source }
        else {
            $fallback = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
            if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) { throw 'gcloud_not_found' }
            $script:GcloudExecutable = $fallback
        }
    } else {
        if (-not (Test-Path -LiteralPath $GcloudPath -PathType Leaf)) { throw 'gcloud_not_found' }
        $script:GcloudExecutable = (Resolve-Path -LiteralPath $GcloudPath).Path
    }

    $accountRows = @(Invoke-GcloudJson @('auth','list','--filter=status:ACTIVE','--format=json(account,status)'))
    $activeAccounts = @($accountRows | Where-Object { [string]$_.status -ceq 'ACTIVE' })
    if ($activeAccounts.Count -ne 1) { throw 'active_gcloud_account_not_unique' }
    $project = Invoke-GcloudJson @('projects','describe','meteo-friul','--format=json(projectId,projectNumber)')
    $serviceRaw = Invoke-GcloudJson @('run','services','describe','meteofriul-api','--platform=managed','--region=europe-west1','--project=meteo-friul','--format=json')
    $serviceTraffic = @($serviceRaw.status.traffic | ForEach-Object {
        [PSCustomObject]@{
            revisionName = if ($_.PSObject.Properties.Name -contains 'revisionName') { [string]$_.revisionName } else { '' }
            percent = if ($_.PSObject.Properties.Name -contains 'percent') { [int]$_.percent } else { 0 }
            tag = if ($_.PSObject.Properties.Name -contains 'tag') { [string]$_.tag } else { '' }
            url = if ($_.PSObject.Properties.Name -contains 'url') { [string]$_.url } else { '' }
        }
    })
    $latestReadyRevision = [string]$serviceRaw.status.latestReadyRevisionName
    $candidateRevisionNames = @($serviceTraffic | ForEach-Object { [string]$_.revisionName }) + @($latestReadyRevision)
    $referencedRevisionNames = @($candidateRevisionNames | Where-Object { $_ } | Sort-Object -Unique)
    $serviceRevisions = foreach ($revisionName in $referencedRevisionNames) {
        $revisionRaw = Invoke-GcloudJson @('run','revisions','describe',$revisionName,'--region=europe-west1','--project=meteo-friul','--format=json')
        $revisionContainer = @($revisionRaw.spec.containers)[0]
        [PSCustomObject]@{
            name = [string]$revisionRaw.metadata.name
            serviceAccount = [string]$revisionRaw.spec.serviceAccountName
            image = [string]$revisionContainer.image
            ready = ([string](@($revisionRaw.status.conditions | Where-Object { $_.type -eq 'Ready' })[0].status) -ceq 'True')
        }
    }
    $jobNames = @(
        'meteofriul-official-alert-sync',
        'meteofriul-event-source-publication-control',
        'meteofriul-event-source-shadow',
        'meteofriul-local-notice'
    )
    $jobs = foreach ($jobName in $jobNames) {
        $raw = Invoke-GcloudJson @('run','jobs','describe',$jobName,'--region=europe-west1','--project=meteo-friul','--format=json')
        $jobPolicy = Invoke-GcloudJson @('run','jobs','get-iam-policy',$jobName,'--region=europe-west1','--project=meteo-friul','--format=json')
        $task = $raw.spec.template.spec.template.spec
        $container = @($task.containers)[0]
        $jobBindings = if ($jobPolicy.PSObject.Properties.Name -contains 'bindings') {
            @($jobPolicy.bindings)
        } else {
            @()
        }
        [PSCustomObject]@{
            name = [string]$raw.metadata.name
            region = 'europe-west1'
            serviceAccount = [string]$task.serviceAccountName
            image = [string]$container.image
            command = @($container.command)
            args = @($container.args)
            envNames = @($container.env | ForEach-Object { [string]$_.name })
            iamBindings = @($jobBindings | ForEach-Object {
                $binding = $_
                $condition = if ($binding.PSObject.Properties.Name -contains 'condition') {
                    [PSCustomObject]@{ expression = [string]$binding.condition.expression }
                } else {
                    $null
                }
                [PSCustomObject]@{
                    role = [string]$binding.role
                    members = @($binding.members | ForEach-Object { [string]$_ } | Sort-Object -Unique)
                    condition = $condition
                }
            })
            ready = ([string](@($raw.status.conditions | Where-Object { $_.type -eq 'Ready' })[0].status) -ceq 'True')
        }
    }
    $policy = Invoke-GcloudJson @('projects','get-iam-policy','meteo-friul','--format=json(bindings)')
    $cloudBuildDefault = Invoke-GcloudText @('builds','get-default-service-account','--project=meteo-friul')
    $schedulerJobs = @(Invoke-GcloudJson @('scheduler','jobs','list','--project=meteo-friul','--location=europe-west1','--format=json(httpTarget.oidcToken.serviceAccountEmail,httpTarget.oauthToken.serviceAccountEmail)'))
    $schedulerAccounts = @($schedulerJobs | ForEach-Object {
        if ($null -ne $_.httpTarget -and $_.httpTarget.PSObject.Properties.Name -contains 'oidcToken') {
            [string]$_.httpTarget.oidcToken.serviceAccountEmail
        }
        if ($null -ne $_.httpTarget -and $_.httpTarget.PSObject.Properties.Name -contains 'oauthToken') {
            [string]$_.httpTarget.oauthToken.serviceAccountEmail
        }
    } | Where-Object { $_ } | Sort-Object -Unique)
    $roleId = ($FcmCustomRole -split '/')[-1]
    $rolePermissions = @()
    try {
        $role = Invoke-GcloudJson @('iam','roles','describe',$roleId,'--project=meteo-friul','--format=json(name,includedPermissions)')
        $rolePermissions = @([PSCustomObject]@{ role = $FcmCustomRole; permissions = @($role.includedPermissions) })
    } catch {
        $rolePermissions = @()
    }
    $serviceReady = [string](@($serviceRaw.status.conditions | Where-Object { $_.type -eq 'Ready' })[0].status) -ceq 'True'
    $serviceContainer = @($serviceRaw.spec.template.spec.containers)[0]
    return [PSCustomObject]@{
        account = [string]$activeAccounts[0].account
        project = $project
        services = @([PSCustomObject]@{
            name = [string]$serviceRaw.metadata.name
            region = 'europe-west1'
            serviceAccount = [string]$serviceRaw.spec.template.spec.serviceAccountName
            image = [string]$serviceContainer.image
            envNames = @($serviceContainer.env | ForEach-Object { [string]$_.name })
            ready = $serviceReady
            latestReadyRevision = $latestReadyRevision
            rollbackRevision = $RollbackRevision
            traffic = @($serviceTraffic)
            revisions = @($serviceRevisions)
        })
        jobs = @($jobs)
        iamBindings = @($policy.bindings)
        rolePermissions = @($rolePermissions)
        cloudBuild = [PSCustomObject]@{ defaultServiceAccount = $cloudBuildDefault }
        schedulerServiceAccounts = @($schedulerAccounts)
    }
}

try {
    $snapshot = if ($FixturePath) {
        $resolvedFixture = (Resolve-Path -LiteralPath $FixturePath -ErrorAction Stop).Path
        Get-Content -LiteralPath $resolvedFixture -Raw | ConvertFrom-Json
    } else {
        Get-LiveSnapshot
    }
    $result = Test-CloudRunRuntimeIamState -Snapshot $snapshot -Stage $Stage `
        -TargetServiceAccount $TargetServiceAccount -FcmCustomRole $FcmCustomRole
    $result | ConvertTo-Json -Depth 12
    if (-not $result.ready) { exit 2 }
    exit 0
} catch {
    [PSCustomObject]@{
        schemaVersion = 'cloud-run-runtime-iam-audit-v1'
        stage = $Stage
        ready = $false
        blockingCount = 1
        findings = @([PSCustomObject]@{ code = 'audit_failed'; message = $_.Exception.Message; blocking = $true })
    } | ConvertTo-Json -Depth 8
    exit 1
}
