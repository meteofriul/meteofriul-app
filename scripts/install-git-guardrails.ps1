$ErrorActionPreference = "Stop"

$repositoryRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
    throw "Eseguire lo script dentro il repository Meteo Friul."
}

Push-Location $repositoryRoot
try {
    if (-not (Test-Path ".githooks/pre-push")) {
        throw "Hook .githooks/pre-push non trovato."
    }

    git config core.hooksPath .githooks
    if ($LASTEXITCODE -ne 0) {
        throw "Impossibile configurare core.hooksPath."
    }

    $configuredPath = git config --get core.hooksPath
    if ($configuredPath -ne ".githooks") {
        throw "Guardrail non attivato: core.hooksPath=$configuredPath"
    }

    Write-Host "Guardrail Git attivo: i push diretti a main sono bloccati."
}
finally {
    Pop-Location
}
