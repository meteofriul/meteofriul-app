Set-StrictMode -Version Latest

function Get-LiveValue {
    param([object]$Value, [string]$Name)
    if ($null -eq $Value) { return $null }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Test-LiveDigest {
    param([string]$Value)
    return $Value -cmatch '^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$'
}

function Test-FirestorePushTtlLiveWriterSet {
    param(
        [object]$Inventory,
        [object]$Contract,
        [object]$ContractGitStatus,
        [object[]]$ImageProofs,
        [string]$PushRepositorySha256,
        [object[]]$ExpectedJobs,
        [string]$ExpectedReleaseApiTag
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $fail = {
        param([string]$Code, [string]$Message)
        $findings.Add([PSCustomObject]@{ code = $Code; message = $Message; blocking = $true })
    }
    if ($null -eq $Inventory -or
        [string](Get-LiveValue $Inventory "schemaVersion") -cne "firestore-push-ttl-runtime-writers-v2" -or
        [string](Get-LiveValue $Inventory "projectId") -cne "meteo-friul" -or
        [string](Get-LiveValue $Inventory "serviceRegion") -cne "europe-west1") {
        & $fail "runtime_writer_inventory_target_mismatch" "Inventario live dei writer assente o riferito a progetto/regione inattesi."
        return $findings.ToArray()
    }
    if ($null -eq $Contract) {
        & $fail "runtime_writer_set_contract_missing" "Manca l'attestazione append-only del set di writer live."
        return $findings.ToArray()
    }
    if ([string](Get-LiveValue $Contract "schemaVersion") -cne "firestore-push-ttl-live-writer-set-v1" -or
        [string](Get-LiveValue $Contract "projectId") -cne "meteo-friul" -or
        [string](Get-LiveValue $Contract "serviceRegion") -cne "europe-west1") {
        & $fail "runtime_writer_set_contract_invalid" "Schema o destinazione del contratto writer inattesi."
    }
    if ($null -eq $ContractGitStatus -or
        (Get-LiveValue $ContractGitStatus "tracked") -ne $true -or
        (Get-LiveValue $ContractGitStatus "clean") -ne $true -or
        [int](Get-LiveValue $ContractGitStatus "commitCount") -ne 1) {
        & $fail "runtime_writer_set_contract_not_immutable" "Il contratto deve essere tracciato, pulito e aggiunto una sola volta a Git."
    }
    if ($PushRepositorySha256 -cnotmatch '^[0-9a-f]{64}$' -or
        [string](Get-LiveValue $Contract "pushRepositorySha256") -cne $PushRepositorySha256) {
        & $fail "runtime_writer_source_digest_mismatch" "Il push.py corrente non coincide con il contratto writer."
    }
    if ($ExpectedReleaseApiTag -cnotmatch '^[a-z0-9-]+$' -or
        [string](Get-LiveValue $Inventory "releaseApiTag") -cne $ExpectedReleaseApiTag -or
        [string](Get-LiveValue $Contract "releaseApiTag") -cne $ExpectedReleaseApiTag) {
        & $fail "runtime_writer_release_tag_mismatch" "Il tag API Play del controllo non coincide con il tag richiesto dalla build."
    }

    $targets = Get-LiveValue $Contract "targets"
    $service = Get-LiveValue $Inventory "service"
    if ([string](Get-LiveValue $service "name") -cne "meteofriul-api") {
        & $fail "runtime_writer_service_missing" "Il servizio API writer non e' risolto."
    }
    $traffic = @(Get-LiveValue $service "traffic")
    $defaultEntries = @($traffic | Where-Object {
        $null -ne (Get-LiveValue $_ "percent") -and [int](Get-LiveValue $_ "percent") -gt 0
    })
    $releaseEntries = @($traffic | Where-Object {
        [string](Get-LiveValue $_ "tag") -ceq $ExpectedReleaseApiTag
    })
    if ($defaultEntries.Count -ne 1 -or
        [int](Get-LiveValue $defaultEntries[0] "percent") -ne 100) {
        & $fail "runtime_writer_service_traffic_not_100" "L'API standard deve avere una sola revisione al 100%."
    }
    if ($releaseEntries.Count -ne 1) {
        & $fail "runtime_writer_release_tag_unresolved" "Il tag API Play deve risolversi in una sola revisione."
    }
    $requiredDigests = New-Object System.Collections.Generic.List[string]
    foreach ($role in @("serviceDefault", "releaseApi")) {
        $entries = @()
        if ($role -ceq "serviceDefault") { $entries = @($defaultEntries) } else { $entries = @($releaseEntries) }
        if ($entries.Count -ne 1) { continue }
        $revisionName = [string](Get-LiveValue $entries[0] "revisionName")
        $matches = @(@(Get-LiveValue $service "revisions") | Where-Object {
            [string](Get-LiveValue $_ "name") -ceq $revisionName
        })
        if (-not $revisionName -or $matches.Count -ne 1 -or
            (Get-LiveValue $matches[0] "ready") -ne $true) {
            & $fail "runtime_writer_service_revision_unresolved" "La revisione API $role non e' Ready o univoca."
            continue
        }
        $actual = [string](Get-LiveValue $matches[0] "imageDigest")
        $expected = [string](Get-LiveValue $targets $role)
        if (-not (Test-LiveDigest $actual) -or -not (Test-LiveDigest $expected) -or
            $actual -cne $expected) {
            & $fail "runtime_writer_digest_mismatch" "Il digest della revisione API $role non e' attestato dal contratto."
            continue
        }
        $requiredDigests.Add($actual)
    }

    $contractJobs = @(Get-LiveValue $targets "jobs")
    $runtimeJobs = @(Get-LiveValue $Inventory "jobs")
    if ($contractJobs.Count -ne $ExpectedJobs.Count -or
        $runtimeJobs.Count -ne $ExpectedJobs.Count) {
        & $fail "runtime_writer_job_inventory_mismatch" "Il numero di job writer non coincide con l'inventario obbligatorio."
    }
    foreach ($spec in $ExpectedJobs) {
        $name = [string](Get-LiveValue $spec "name")
        $region = [string](Get-LiveValue $spec "jobRegion")
        $schedule = [string](Get-LiveValue $spec "schedule")
        $contractMatches = @($contractJobs | Where-Object {
            [string](Get-LiveValue $_ "name") -ceq $name
        })
        $runtimeMatches = @($runtimeJobs | Where-Object {
            [string](Get-LiveValue $_ "name") -ceq $name
        })
        if ($contractMatches.Count -ne 1 -or $runtimeMatches.Count -ne 1) {
            & $fail "runtime_writer_job_missing" "Il job $name manca o non e' univoco nel contratto/live."
            continue
        }
        $job = $runtimeMatches[0]
        $contractJob = $contractMatches[0]
        $scheduler = Get-LiveValue $job "scheduler"
        $expectedUri = "https://run.googleapis.com/v2/projects/meteo-friul/locations/$region/jobs/$name" + ":run"
        if ([string](Get-LiveValue $job "region") -cne $region -or
            [string](Get-LiveValue $contractJob "region") -cne $region -or
            (Get-LiveValue $job "ready") -ne $true) {
            & $fail "runtime_writer_job_target_mismatch" "Regione o stato Ready del job $name inattesi."
        }
        if ([string](Get-LiveValue $scheduler "name") -cne $name -or
            [string](Get-LiveValue $scheduler "region") -cne "europe-west1" -or
            [string](Get-LiveValue $scheduler "state") -cne "ENABLED" -or
            [string](Get-LiveValue $scheduler "schedule") -cne $schedule -or
            [string](Get-LiveValue $scheduler "timeZone") -cne "Europe/Rome" -or
            [string](Get-LiveValue $scheduler "targetUri") -cne $expectedUri) {
            & $fail "runtime_writer_scheduler_target_mismatch" "Scheduler $name non punta al job/orario atteso."
        }
        $actual = [string](Get-LiveValue $job "imageDigest")
        $expected = [string](Get-LiveValue $contractJob "imageDigest")
        if (-not (Test-LiveDigest $actual) -or -not (Test-LiveDigest $expected) -or
            $actual -cne $expected) {
            & $fail "runtime_writer_digest_mismatch" "Il digest del job $name non e' attestato dal contratto."
            continue
        }
        $requiredDigests.Add($actual)
    }

    $uniqueDigests = @($requiredDigests | Sort-Object -Unique)
    $images = @(Get-LiveValue $Contract "images")
    if ($images.Count -ne $uniqueDigests.Count -or
        @($ImageProofs).Count -ne $uniqueDigests.Count) {
        & $fail "runtime_writer_image_coverage_mismatch" "Ogni digest live deve avere una e una sola prova, senza immagini estranee."
    }
    foreach ($digest in $uniqueDigests) {
        $imageMatches = @($images | Where-Object {
            [string](Get-LiveValue $_ "imageDigest") -ceq $digest
        })
        $proofMatches = @($ImageProofs | Where-Object {
            [string](Get-LiveValue $_ "imageDigest") -ceq $digest
        })
        if ($imageMatches.Count -ne 1 -or $proofMatches.Count -ne 1) {
            & $fail "runtime_writer_image_proof_missing" "Manca una prova univoca del digest $digest."
            continue
        }
        $image = $imageMatches[0]
        $proof = $proofMatches[0]
        $sourceCommit = [string](Get-LiveValue $image "sourceCommit")
        $buildId = [string](Get-LiveValue $image "cloudBuildId")
        $buildRegion = [string](Get-LiveValue $image "cloudBuildRegion")
        $archiveSha = [string](Get-LiveValue $image "cloudBuildSourceArchiveSha256Base64")
        if ($sourceCommit -cnotmatch '^[0-9a-f]{40}$' -or
            $buildId -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' -or
            $buildRegion -cnotin @("europe-west1", "global") -or
            $archiveSha -cnotmatch '^[A-Za-z0-9_-]{43}=$' -or
            [string](Get-LiveValue $image "sourceArchivePushRepositorySha256") -cne $PushRepositorySha256) {
            & $fail "runtime_writer_image_attestation_invalid" "Metadati sorgente della prova $digest non validi."
        }
        $git = Get-LiveValue $proof "pushRepositoryGitStatus"
        if ($null -eq $git -or
            (Get-LiveValue $git "tracked") -ne $true -or
            (Get-LiveValue $git "clean") -ne $true -or
            (Get-LiveValue $git "sourceCommitExists") -ne $true -or
            (Get-LiveValue $git "matchesSourceCommit") -ne $true) {
            & $fail "runtime_writer_source_commit_mismatch" "push.py non coincide col commit sorgente della prova $digest."
        }
        $build = Get-LiveValue $proof "buildVerification"
        $verifiedImages = @(@(Get-LiveValue $build "canonicalImageDigests") |
            ForEach-Object { [string]$_ } | Sort-Object -Unique)
        if ($null -eq $build -or
            [string](Get-LiveValue $build "schemaVersion") -cne "firestore-push-ttl-cloud-build-verification-v1" -or
            [string](Get-LiveValue $build "id") -cne $buildId -or
            [string](Get-LiveValue $build "region") -cne $buildRegion -or
            [string](Get-LiveValue $build "status") -cne "SUCCESS" -or
            $verifiedImages -cnotcontains $digest -or
            [string](Get-LiveValue $build "sourceArchiveSha256Base64") -cne $archiveSha) {
            & $fail "runtime_writer_build_verification_mismatch" "Cloud Build non conferma digest e archivio della prova $digest."
        }
    }
    return $findings.ToArray()
}

Export-ModuleMember -Function Test-FirestorePushTtlLiveWriterSet
