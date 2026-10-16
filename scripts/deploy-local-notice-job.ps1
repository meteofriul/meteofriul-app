[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Image,

    [ValidateSet("Audit", "Apply")]
    [string]$Mode = "Audit",

    [string]$ExpectedAccount = "meteofriul@gmail.com",

    [string]$ProjectId = "meteo-friul",

    [string]$Region = "europe-west1",

    [string]$GcloudPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$jobName = "meteofriul-local-notice"
$schedulerName = $jobName
$schedule = "0 * * * *"
$timeZone = "Europe/Rome"
$runtimeServiceAccount = (
    "meteofriul-runtime@meteo-friul.iam.gserviceaccount.com"
)
$schedulerServiceAccount = (
    "official-alert-scheduler@meteo-friul.iam.gserviceaccount.com"
)
$envFile = Join-Path $PSScriptRoot `
    "..\backend\local-notice-production.env.yaml"

function Resolve-DeployGcloud {
    if ($GcloudPath) {
        $resolved = [IO.Path]::GetFullPath($GcloudPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "local_notice_gcloud_not_found"
        }
        return $resolved
    }
    foreach ($name in @("gcloud.cmd", "gcloud")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    $fallback = Join-Path $env:LOCALAPPDATA (
        "Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    )
    if (Test-Path -LiteralPath $fallback -PathType Leaf) { return $fallback }
    throw "local_notice_gcloud_not_found"
}

function Invoke-DeployGcloud {
    param([string]$Executable, [string[]]$Arguments, [string]$FailureCode)
    $output = & $Executable @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "$FailureCode`: $output" }
    return (($output | Out-String).Trim())
}

$gcloud = Resolve-DeployGcloud
$account = Invoke-DeployGcloud $gcloud @(
    "auth", "list", "--filter=status:ACTIVE", "--format=value(account)", "--quiet"
) "local_notice_account_read_failed"
if ($account -cne $ExpectedAccount) { throw "local_notice_account_mismatch" }
$project = Invoke-DeployGcloud $gcloud @(
    "config", "get-value", "project", "--quiet"
) "local_notice_project_read_failed"
if ($project -cne $ProjectId) { throw "local_notice_project_mismatch" }
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "local_notice_env_file_missing"
}

$jobInventory = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "list", "--project=$ProjectId", "--region=$Region",
    "--format=value(metadata.name)"
) "local_notice_job_inventory_failed"
$jobExists = @($jobInventory -split "`r?`n") -ccontains $jobName

$schedulerInventory = Invoke-DeployGcloud $gcloud @(
    "scheduler", "jobs", "list", "--project=$ProjectId",
    "--location=$Region", "--filter=name:$schedulerName",
    "--format=value(name.basename())"
) "local_notice_scheduler_inventory_failed"
$schedulerExists = @($schedulerInventory -split "`r?`n") -ccontains $schedulerName

if ($Mode -ceq "Apply") {
    $jobVerb = if ($jobExists) { "update" } else { "create" }
    $null = Invoke-DeployGcloud $gcloud @(
        "run", "jobs", $jobVerb, $jobName,
        "--project=$ProjectId", "--region=$Region", "--image=$Image",
        "--command=python", "--args=-m,app.jobs.send_local_weather_notices",
        "--service-account=$runtimeServiceAccount", "--task-timeout=300s",
        "--max-retries=0", "--env-vars-file=$envFile", "--quiet"
    ) "local_notice_job_apply_failed"

    $null = Invoke-DeployGcloud $gcloud @(
        "run", "jobs", "add-iam-policy-binding", $jobName,
        "--project=$ProjectId", "--region=$Region",
        "--member=serviceAccount:$schedulerServiceAccount",
        "--role=roles/run.invoker", "--quiet"
    ) "local_notice_invoker_apply_failed"

    $schedulerVerb = if ($schedulerExists) { "update" } else { "create" }
    $schedulerUri = "https://run.googleapis.com/v2/projects/$ProjectId/" +
        "locations/$Region/jobs/$jobName`:run"
    $null = Invoke-DeployGcloud $gcloud @(
        "scheduler", "jobs", $schedulerVerb, "http", $schedulerName,
        "--project=$ProjectId", "--location=$Region", "--schedule=$schedule",
        "--time-zone=$timeZone", "--uri=$schedulerUri", "--http-method=POST",
        "--oauth-service-account-email=$schedulerServiceAccount",
        "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform",
        "--quiet"
    ) "local_notice_scheduler_apply_failed"
}

if (-not $jobExists -and $Mode -ceq "Audit") {
    [PSCustomObject]@{
        mode = $Mode
        job = $jobName
        scheduler = $schedulerName
        ready = $false
        status = "job_missing"
    } | ConvertTo-Json -Depth 6
    exit 2
}
if (-not $schedulerExists -and $Mode -ceq "Audit") {
    [PSCustomObject]@{
        mode = $Mode
        job = $jobName
        scheduler = $schedulerName
        ready = $false
        status = "scheduler_missing"
    } | ConvertTo-Json -Depth 6
    exit 2
}

$job = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "describe", $jobName,
    "--project=$ProjectId", "--region=$Region", "--format=json"
) "local_notice_job_readback_failed" | ConvertFrom-Json
$scheduler = Invoke-DeployGcloud $gcloud @(
    "scheduler", "jobs", "describe", $schedulerName,
    "--project=$ProjectId", "--location=$Region", "--format=json"
) "local_notice_scheduler_readback_failed" | ConvertFrom-Json
$jobPolicy = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "get-iam-policy", $jobName,
    "--project=$ProjectId", "--region=$Region", "--format=json"
) "local_notice_invoker_readback_failed" | ConvertFrom-Json

$container = $job.spec.template.spec.template.spec.containers[0]
$actualCommand = @($container.command) -join " "
$actualArgs = @($container.args) -join " "
$actualEnv = @{}
foreach ($entry in @($container.env)) {
    $actualEnv[[string]$entry.name] = [string]$entry.value
}
$environmentReady = (
    $actualEnv["LOCAL_NOTICE_DELIVERY_MODE"] -ceq "send" -and
    $actualEnv["LOCAL_NOTICE_SOURCE_TIMEOUT_SECONDS"] -ceq "30"
)
$invokerMember = "serviceAccount:$schedulerServiceAccount"
$jobBindings = if ($null -ne $jobPolicy.PSObject.Properties["bindings"]) {
    @($jobPolicy.bindings)
} else { @() }
$invokerReady = @($jobBindings | Where-Object {
    [string]$_.role -ceq "roles/run.invoker" -and
    @($_.members | ForEach-Object { [string]$_ }) -ccontains $invokerMember
}).Count -eq 1
$schedulerUri = "https://run.googleapis.com/v2/projects/$ProjectId/" +
    "locations/$Region/jobs/$jobName`:run"
$ready = (
    [string]$container.image -ceq $Image -and
    $actualCommand -ceq "python" -and
    $actualArgs -ceq "-m app.jobs.send_local_weather_notices" -and
    [string]$job.spec.template.spec.template.spec.serviceAccountName -ceq
        $runtimeServiceAccount -and
    [string]$job.spec.template.spec.template.spec.timeoutSeconds -ceq "300" -and
    [int]$job.spec.template.spec.template.spec.maxRetries -eq 0 -and
    $environmentReady -and
    $invokerReady -and
    [string]$scheduler.schedule -ceq $schedule -and
    [string]$scheduler.timeZone -ceq $timeZone -and
    [string]$scheduler.state -ceq "ENABLED" -and
    [string]$scheduler.httpTarget.uri -ceq $schedulerUri -and
    [string]$scheduler.httpTarget.httpMethod -ceq "POST" -and
    [string]$scheduler.httpTarget.oauthToken.serviceAccountEmail -ceq
        $schedulerServiceAccount
)
[PSCustomObject]@{
    mode = $Mode
    job = $jobName
    image = [string]$container.image
    scheduler = $schedulerName
    schedule = [string]$scheduler.schedule
    timeZone = [string]$scheduler.timeZone
    state = [string]$scheduler.state
    runtimeServiceAccount = [string](
        $job.spec.template.spec.template.spec.serviceAccountName
    )
    schedulerInvokerReady = $invokerReady
    environmentReady = $environmentReady
    ready = $ready
} | ConvertTo-Json -Depth 6
if (-not $ready) { exit 2 }
