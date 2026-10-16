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

$jobName = "meteofriul-national-official-alert-sync"
$schedulerName = $jobName
$schedule = "35 */2 * * *"
$timeZone = "Europe/Rome"
$runtimeServiceAccount = "49007668366-compute@developer.gserviceaccount.com"
$schedulerServiceAccount = (
    "official-alert-scheduler@meteo-friul.iam.gserviceaccount.com"
)
$envFile = Join-Path $PSScriptRoot `
    "..\backend\national-official-alert-production.env.yaml"

function Resolve-DeployGcloud {
    if ($GcloudPath) {
        $resolved = [IO.Path]::GetFullPath($GcloudPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "national_alert_gcloud_not_found"
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
    throw "national_alert_gcloud_not_found"
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
) "national_alert_account_read_failed"
if ($account -cne $ExpectedAccount) { throw "national_alert_account_mismatch" }
$project = Invoke-DeployGcloud $gcloud @(
    "config", "get-value", "project", "--quiet"
) "national_alert_project_read_failed"
if ($project -cne $ProjectId) { throw "national_alert_project_mismatch" }
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "national_alert_env_file_missing"
}

$jobInventory = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "list", "--project=$ProjectId", "--region=$Region",
    "--filter=metadata.name=$jobName", "--format=value(metadata.name)"
) "national_alert_job_inventory_failed"
$jobExists = $jobInventory -ceq $jobName

$schedulerInventory = Invoke-DeployGcloud $gcloud @(
    "scheduler", "jobs", "list", "--project=$ProjectId",
    "--location=$Region", "--filter=name:$schedulerName",
    "--format=value(name.basename())"
) "national_alert_scheduler_inventory_failed"
$schedulerExists = @($schedulerInventory -split "`r?`n") -ccontains $schedulerName

if ($Mode -ceq "Apply") {
    $jobVerb = if ($jobExists) { "update" } else { "create" }
    $null = Invoke-DeployGcloud $gcloud @(
        "run", "jobs", $jobVerb, $jobName,
        "--project=$ProjectId", "--region=$Region", "--image=$Image",
        "--command=python", "--args=-m,app.jobs.sync_national_official_alerts",
        "--service-account=$runtimeServiceAccount", "--task-timeout=300s",
        "--max-retries=0", "--env-vars-file=$envFile", "--quiet"
    ) "national_alert_job_apply_failed"

    $null = Invoke-DeployGcloud $gcloud @(
        "run", "jobs", "add-iam-policy-binding", $jobName,
        "--project=$ProjectId", "--region=$Region",
        "--member=serviceAccount:$schedulerServiceAccount",
        "--role=roles/run.invoker", "--quiet"
    ) "national_alert_invoker_apply_failed"

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
    ) "national_alert_scheduler_apply_failed"
}

$job = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "describe", $jobName,
    "--project=$ProjectId", "--region=$Region", "--format=json"
) "national_alert_job_readback_failed" | ConvertFrom-Json
$scheduler = Invoke-DeployGcloud $gcloud @(
    "scheduler", "jobs", "describe", $schedulerName,
    "--project=$ProjectId", "--location=$Region", "--format=json"
) "national_alert_scheduler_readback_failed" | ConvertFrom-Json
$jobPolicy = Invoke-DeployGcloud $gcloud @(
    "run", "jobs", "get-iam-policy", $jobName,
    "--project=$ProjectId", "--region=$Region", "--format=json"
) "national_alert_invoker_readback_failed" | ConvertFrom-Json

$container = $job.spec.template.spec.template.spec.containers[0]
$actualCommand = @($container.command) -join " "
$actualArgs = @($container.args) -join " "
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
    $actualArgs -ceq "-m app.jobs.sync_national_official_alerts" -and
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
    schedulerInvokerReady = $invokerReady
    ready = $ready
} | ConvertTo-Json -Depth 6
if (-not $ready) { exit 2 }
