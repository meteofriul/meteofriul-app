Set-StrictMode -Version Latest

Import-Module (Join-Path $PSScriptRoot "firestore-push-ttl-live-writer-set.psm1") -Force
$script:ExpectedProjectId = "meteo-friul"
$script:ExpectedDatabaseId = "(default)"
$script:ExpectedRegion = "europe-west1"
$script:ExpectedRuntimeWriters = @(
    [PSCustomObject]@{ kind = "service"; name = "meteofriul-api" },
    [PSCustomObject]@{ kind = "job"; name = "meteofriul-official-alert-sync" },
    [PSCustomObject]@{ kind = "job"; name = "meteofriul-local-notice" },
    [PSCustomObject]@{ kind = "job"; name = "meteofriul-morning-forecast" },
    [PSCustomObject]@{ kind = "job"; name = "meteofriul-evening-forecast" }
)

$script:ExpectedScheduledWriters = @(
    [PSCustomObject]@{ name = "meteofriul-official-alert-sync"; jobRegion = "europe-west8"; schedule = "0 */2 * * *" },
    [PSCustomObject]@{ name = "meteofriul-local-notice"; jobRegion = "europe-west1"; schedule = "0 * * * *" },
    [PSCustomObject]@{ name = "meteofriul-morning-forecast"; jobRegion = "europe-west1"; schedule = "30 7 * * *" },
    [PSCustomObject]@{ name = "meteofriul-evening-forecast"; jobRegion = "europe-west1"; schedule = "45 20 * * *" }
)

function Get-FirestorePushTtlScheduledWriterTargets {
    return @($script:ExpectedScheduledWriters)
}

function Get-FirestorePushTtlWriterJobNames {
    return @($script:ExpectedRuntimeWriters | Where-Object { $_.kind -ceq "job" } |
        ForEach-Object { [string]$_.name })
}
$script:ExpectedTtlPolicies = @(
    [PSCustomObject]@{
        collectionGroup = "push_official_alert_outbox"
        field = "expires_at"
        retentionConstant = "PUSH_OFFICIAL_ALERT_OUTBOX_RETENTION_DAYS"
        horizonDays = 30
    },
    [PSCustomObject]@{
        collectionGroup = "push_local_notice_outbox"
        field = "expires_at"
        retentionConstant = "PUSH_LOCAL_NOTICE_OUTBOX_RETENTION_DAYS"
        horizonDays = 14
    }
)

function Get-PropertyValue {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    if ($Object.PSObject.Properties.Name -ccontains $Name) {
        return $Object.$Name
    }
    return $null
}

function Get-PythonIntegerConstant {
    param([string]$SourceText, [string]$Name)
    $escapedName = [regex]::Escape($Name)
    $match = [regex]::Match(
        $SourceText,
        "(?m)^\s*$escapedName\s*=\s*(?<value>[0-9]+)\s*$"
    )
    if (-not $match.Success) { return $null }
    return [int]$match.Groups["value"].Value
}

function Get-PythonStringConstant {
    param([string]$SourceText, [string]$Name)
    $escapedName = [regex]::Escape($Name)
    $match = [regex]::Match(
        $SourceText,
        ('(?m)^\s*{0}\s*=\s*[''"](?<value>[^''"]+)[''"]\s*$' -f $escapedName)
    )
    if (-not $match.Success) { return $null }
    return [string]$match.Groups["value"].Value
}

function Test-RetentionConstantUsed {
    param([string]$SourceText, [string]$Name)
    $escapedName = [regex]::Escape($Name)
    return [regex]::IsMatch(
        $SourceText,
        "(?s)timedelta\s*\(\s*days\s*=\s*$escapedName\s*\)"
    )
}

function Test-ExpirationOffsetIsZero {
    param([object]$Offset)
    if ($null -eq $Offset) { return $true }
    if ($Offset -is [string]) {
        return [string]$Offset -cmatch '^0(?:\.0+)?s$'
    }
    $seconds = Get-PropertyValue $Offset "seconds"
    $nanos = Get-PropertyValue $Offset "nanos"
    if ($null -eq $seconds -and $null -eq $nanos) { return $false }
    return (($null -eq $seconds -or [int64]$seconds -eq 0) -and
        ($null -eq $nanos -or [int]$nanos -eq 0))
}

function Test-ImmutableImageDigest {
    param([string]$Value)
    return $Value -cmatch '^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$'
}

function Resolve-RuntimeWriterContractCandidate {
    param(
        [object[]]$Candidates,
        [string]$PushRepositorySha256,
        [object]$RuntimeWriters
    )

    $matchingCandidates = @($Candidates | Where-Object {
        $contract = Get-PropertyValue $_ "contract"
        [string](Get-PropertyValue $contract "schemaVersion") -ceq "firestore-push-ttl-runtime-writer-contract-v1" -and
        [string](Get-PropertyValue $contract "pushRepositorySha256") -ceq $PushRepositorySha256
    })
    if ($matchingCandidates.Count -eq 0) { return $null }

    $service = Get-PropertyValue $RuntimeWriters "service"
    if ($null -eq $service -or
        [string](Get-PropertyValue $service "name") -cne "meteofriul-api") {
        throw "runtime_writer_contract_service_revision_unresolved"
    }
    $nonzeroTraffic = @(@(Get-PropertyValue $service "traffic") | Where-Object {
        $null -ne (Get-PropertyValue $_ "percent") -and
        [int](Get-PropertyValue $_ "percent") -gt 0
    })
    if ($nonzeroTraffic.Count -ne 1 -or
        [int](Get-PropertyValue $nonzeroTraffic[0] "percent") -ne 100) {
        throw "runtime_writer_contract_service_traffic_not_unique"
    }
    $revisionName = [string](Get-PropertyValue $nonzeroTraffic[0] "revisionName")
    $revisionMatches = @(@(Get-PropertyValue $service "revisions") | Where-Object {
        [string](Get-PropertyValue $_ "name") -ceq $revisionName
    })
    if ([string]::IsNullOrWhiteSpace($revisionName) -or
        $revisionMatches.Count -ne 1) {
        throw "runtime_writer_contract_service_revision_unresolved"
    }
    if ((Get-PropertyValue $revisionMatches[0] "ready") -ne $true) {
        throw "runtime_writer_contract_service_revision_not_ready"
    }
    $servingDigest = [string](Get-PropertyValue $revisionMatches[0] "imageDigest")
    if (-not (Test-ImmutableImageDigest -Value $servingDigest)) {
        throw "runtime_writer_contract_service_digest_invalid"
    }

    $servingCandidates = @($matchingCandidates | Where-Object {
        $contract = Get-PropertyValue $_ "contract"
        [string](Get-PropertyValue $contract "expectedImageDigest") -ceq $servingDigest
    })
    if ($servingCandidates.Count -eq 0) {
        throw "runtime_writer_contract_for_serving_digest_missing"
    }
    if ($servingCandidates.Count -ne 1) {
        throw "runtime_writer_contract_for_serving_digest_ambiguous"
    }
    return $servingCandidates[0]
}

function Test-RuntimeWriterParity {
    param(
        [object]$RuntimeWriters,
        [object]$RuntimeWriterContract,
        [object]$RuntimeContractGitStatus,
        [object]$RuntimeBuildVerification,
        [object]$PushRepositoryGitStatus,
        [string]$PushRepositorySha256,
        [System.Collections.Generic.List[object]]$Findings,
        [scriptblock]$AddFinding
    )

    $expectedDigest = ""
    if ($null -eq $RuntimeWriterContract) {
        & $AddFinding "runtime_writer_contract_missing" "Manca l'attestazione immutabile che lega il digest backend al writer expires_at verificato." $true
    } else {
        if ($null -eq $RuntimeContractGitStatus -or
            (Get-PropertyValue $RuntimeContractGitStatus "tracked") -ne $true -or
            (Get-PropertyValue $RuntimeContractGitStatus "clean") -ne $true -or
            [int](Get-PropertyValue $RuntimeContractGitStatus "commitCount") -ne 1) {
            & $AddFinding "runtime_writer_contract_not_immutable" "L'attestazione del digest writer deve essere tracciata, pulita e aggiunta una sola volta nella cronologia Git." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "schemaVersion") -cne "firestore-push-ttl-runtime-writer-contract-v1") {
            & $AddFinding "runtime_writer_contract_schema_invalid" "Schema dell'attestazione runtime inatteso." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "projectId") -cne $script:ExpectedProjectId -or
            [string](Get-PropertyValue $RuntimeWriterContract "region") -cne $script:ExpectedRegion) {
            & $AddFinding "runtime_writer_contract_target_mismatch" "L'attestazione runtime non appartiene al progetto e alla regione attesi." $true
        }

        $expectedDigest = [string](Get-PropertyValue $RuntimeWriterContract "expectedImageDigest")
        if (-not (Test-ImmutableImageDigest -Value $expectedDigest)) {
            & $AddFinding "runtime_writer_contract_digest_invalid" "Il digest backend atteso deve essere un riferimento immutabile completo @sha256." $true
        }
        $sourceDigest = [string](Get-PropertyValue $RuntimeWriterContract "pushRepositorySha256")
        if ($sourceDigest -cnotmatch '^[0-9a-f]{64}$' -or
            $PushRepositorySha256 -cnotmatch '^[0-9a-f]{64}$' -or
            $sourceDigest -cne $PushRepositorySha256) {
            & $AddFinding "runtime_writer_source_digest_mismatch" "Il push.py locale non coincide con il writer attestato nell'immagine backend." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "verificationMethod") -cne "cloud-build-result-plus-source-sha256") {
            & $AddFinding "runtime_writer_verification_method_invalid" "Metodo di verifica build/source inatteso nell'attestazione runtime." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "sourceCommit") -cnotmatch '^[0-9a-f]{40}$') {
            & $AddFinding "runtime_writer_source_commit_invalid" "Commit sorgente non valido nell'attestazione runtime." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "cloudBuildId") -cnotmatch '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') {
            & $AddFinding "runtime_writer_build_id_invalid" "Cloud Build ID non valido nell'attestazione runtime." $true
        }
        if ([string](Get-PropertyValue $RuntimeWriterContract "cloudBuildStatus") -cne "SUCCESS" -or
            [string](Get-PropertyValue $RuntimeWriterContract "cloudBuildResultImageDigest") -cne $expectedDigest) {
            & $AddFinding "runtime_writer_build_result_invalid" "L'attestazione non registra una build SUCCESS dello stesso digest backend." $true
        }
        $contractSourceArchiveSha = [string](Get-PropertyValue $RuntimeWriterContract "cloudBuildSourceArchiveSha256Base64")
        if ($contractSourceArchiveSha -cnotmatch '^[A-Za-z0-9_-]{43}=$') {
            & $AddFinding "runtime_writer_build_source_digest_invalid" "Digest SHA-256 dell'archivio sorgente Cloud Build non valido." $true
        }

        if ($null -eq $PushRepositoryGitStatus -or
            (Get-PropertyValue $PushRepositoryGitStatus "tracked") -ne $true -or
            (Get-PropertyValue $PushRepositoryGitStatus "clean") -ne $true -or
            (Get-PropertyValue $PushRepositoryGitStatus "sourceCommitExists") -ne $true -or
            (Get-PropertyValue $PushRepositoryGitStatus "matchesSourceCommit") -ne $true) {
            & $AddFinding "runtime_writer_source_commit_mismatch" "push.py deve essere pulito, tracciato e identico al commit sorgente attestato." $true
        }

        if ($null -eq $RuntimeBuildVerification) {
            & $AddFinding "runtime_writer_build_verification_missing" "Manca il read-back Cloud Build della build attestata." $true
        } else {
            if ([string](Get-PropertyValue $RuntimeBuildVerification "schemaVersion") -cne "firestore-push-ttl-cloud-build-verification-v1" -or
                [string](Get-PropertyValue $RuntimeBuildVerification "id") -cne [string](Get-PropertyValue $RuntimeWriterContract "cloudBuildId") -or
                [string](Get-PropertyValue $RuntimeBuildVerification "status") -cne "SUCCESS") {
                & $AddFinding "runtime_writer_build_verification_invalid" "Il read-back Cloud Build non coincide con la build SUCCESS attestata." $true
            }
            $verifiedImages = @(
                @(Get-PropertyValue $RuntimeBuildVerification "canonicalImageDigests") |
                    ForEach-Object { [string]$_ } |
                    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
                    Sort-Object -Unique
            )
            if ($verifiedImages.Count -ne 1 -or
                $verifiedImages[0] -cne $expectedDigest) {
                & $AddFinding "runtime_writer_build_digest_mismatch" "Cloud Build non conferma in modo univoco il digest backend attestato." $true
            }
            if ([string](Get-PropertyValue $RuntimeBuildVerification "sourceArchiveSha256Base64") -cne $contractSourceArchiveSha) {
                & $AddFinding "runtime_writer_build_source_mismatch" "L'archivio sorgente letto da Cloud Build non coincide con l'attestazione." $true
            }
        }
    }

    if ($null -eq $RuntimeWriters) {
        & $AddFinding "runtime_writer_inventory_missing" "Manca l'inventario live dei writer Cloud Run." $true
        return
    }
    if ([string](Get-PropertyValue $RuntimeWriters "schemaVersion") -cne "firestore-push-ttl-runtime-writers-v1" -or
        [string](Get-PropertyValue $RuntimeWriters "projectId") -cne $script:ExpectedProjectId -or
        [string](Get-PropertyValue $RuntimeWriters "region") -cne $script:ExpectedRegion) {
        & $AddFinding "runtime_writer_inventory_target_mismatch" "L'inventario writer non appartiene al progetto e alla regione attesi." $true
    }

    $servingDigest = ""
    $service = Get-PropertyValue $RuntimeWriters "service"
    if ($null -eq $service -or
        [string](Get-PropertyValue $service "name") -cne "meteofriul-api") {
        & $AddFinding "runtime_writer_service_missing" "Il servizio meteofriul-api non e' presente in modo univoco nell'inventario." $true
    } else {
        $traffic = @(Get-PropertyValue $service "traffic")
        $nonzeroTraffic = @($traffic | Where-Object {
            $null -ne (Get-PropertyValue $_ "percent") -and
            [int](Get-PropertyValue $_ "percent") -gt 0
        })
        if ($nonzeroTraffic.Count -ne 1 -or
            [int](Get-PropertyValue $nonzeroTraffic[0] "percent") -ne 100) {
            & $AddFinding "runtime_writer_service_traffic_not_100" "meteofriul-api deve avere una sola revisione servente al 100% del traffico." $true
        } else {
            $revisionName = [string](Get-PropertyValue $nonzeroTraffic[0] "revisionName")
            $revisionMatches = @(@(Get-PropertyValue $service "revisions") | Where-Object {
                [string](Get-PropertyValue $_ "name") -ceq $revisionName
            })
            if ([string]::IsNullOrWhiteSpace($revisionName) -or $revisionMatches.Count -ne 1) {
                & $AddFinding "runtime_writer_traffic_revision_unresolved" "La revisione Cloud Run con il 100% del traffico non e' risolta in modo univoco." $true
            } else {
                $revision = $revisionMatches[0]
                if ((Get-PropertyValue $revision "ready") -ne $true) {
                    & $AddFinding "runtime_writer_service_revision_not_ready" "La revisione servente di meteofriul-api non e' Ready." $true
                }
                $actualDigest = [string](Get-PropertyValue $revision "imageDigest")
                if (-not (Test-ImmutableImageDigest -Value $actualDigest)) {
                    & $AddFinding "runtime_writer_service_digest_not_immutable" "La revisione servente non espone un imageDigest immutabile." $true
                } else {
                    $servingDigest = $actualDigest
                }
                if ((Test-ImmutableImageDigest -Value $expectedDigest) -and
                    $actualDigest -cne $expectedDigest) {
                    & $AddFinding "runtime_writer_digest_mismatch" "La revisione servente non usa il digest backend attestato." $true
                }
            }
        }
    }

    $jobs = @(Get-PropertyValue $RuntimeWriters "jobs")
    foreach ($expectedJob in @(Get-FirestorePushTtlWriterJobNames)) {
        $jobMatches = @($jobs | Where-Object {
            [string](Get-PropertyValue $_ "name") -ceq $expectedJob
        })
        if ($jobMatches.Count -ne 1) {
            & $AddFinding "runtime_writer_job_missing" "Il job $expectedJob non e' presente in modo univoco nell'inventario." $true
            continue
        }
        $job = $jobMatches[0]
        if ((Get-PropertyValue $job "ready") -ne $true) {
            & $AddFinding "runtime_writer_job_not_ready" "Il job $expectedJob non e' Ready." $true
        }
        $actualDigest = [string](Get-PropertyValue $job "imageDigest")
        if (-not (Test-ImmutableImageDigest -Value $actualDigest)) {
            & $AddFinding "runtime_writer_job_digest_not_immutable" "Il job $expectedJob usa un tag mobile o un riferimento immagine non valido." $true
        } elseif ((Test-ImmutableImageDigest -Value $expectedDigest) -and
            $actualDigest -cne $expectedDigest) {
            & $AddFinding "runtime_writer_digest_mismatch" "Il job $expectedJob non usa lo stesso digest backend attestato del servizio." $true
        } elseif ((Test-ImmutableImageDigest -Value $servingDigest) -and
            $actualDigest -cne $servingDigest) {
            & $AddFinding "runtime_writer_digest_mismatch" "Il job $expectedJob non usa lo stesso digest backend della revisione servente." $true
        }
    }
}

function Test-HistoricalEvidence {
    param(
        [object]$Evidence,
        [object]$EvidenceGitStatus,
        [System.Collections.Generic.List[object]]$Findings,
        [scriptblock]$AddFinding
    )

    if ($null -eq $Evidence) {
        & $AddFinding "historical_cleanup_evidence_missing" "Manca l'evidenza della verifica/backfill una tantum dei documenti storici privi di expires_at." $true
        return
    }
    if ($null -eq $EvidenceGitStatus -or
        (Get-PropertyValue $EvidenceGitStatus "tracked") -ne $true -or
        (Get-PropertyValue $EvidenceGitStatus "clean") -ne $true -or
        [int](Get-PropertyValue $EvidenceGitStatus "commitCount") -ne 1) {
        & $AddFinding "historical_cleanup_evidence_not_immutable" "L'evidenza storica deve essere tracciata, pulita e aggiunta una sola volta nella cronologia Git." $true
    }
    if ([string](Get-PropertyValue $Evidence "schemaVersion") -cne "firestore-push-ttl-history-v1") {
        & $AddFinding "historical_cleanup_evidence_schema_invalid" "Schema dell'evidenza storica inatteso." $true
    }
    if ([string](Get-PropertyValue $Evidence "projectId") -cne $script:ExpectedProjectId -or
        [string](Get-PropertyValue $Evidence "databaseId") -cne $script:ExpectedDatabaseId) {
        & $AddFinding "historical_cleanup_evidence_target_mismatch" "L'evidenza storica non appartiene al database Firestore atteso." $true
    }

    $verifiedAtValue = Get-PropertyValue $Evidence "verifiedAtUtc"
    $verifiedAt = [DateTimeOffset]::MinValue
    $verifiedAtParsed = $false
    if ($verifiedAtValue -is [DateTimeOffset]) {
        $verifiedAt = [DateTimeOffset]$verifiedAtValue
        $verifiedAtParsed = $true
    } elseif ($verifiedAtValue -is [DateTime]) {
        $verifiedAt = [DateTimeOffset]([DateTime]$verifiedAtValue)
        $verifiedAtParsed = $true
    } else {
        $verifiedAtText = [string]$verifiedAtValue
        $verifiedAtParsed = [DateTimeOffset]::TryParse($verifiedAtText, [ref]$verifiedAt)
    }
    if (-not $verifiedAtParsed -or
        $verifiedAt.Offset -ne [TimeSpan]::Zero -or
        $verifiedAt -gt [DateTimeOffset]::UtcNow.AddMinutes(5)) {
        & $AddFinding "historical_cleanup_evidence_time_invalid" "verifiedAtUtc deve essere una data UTC valida e non futura." $true
    }

    $policyRows = @(Get-PropertyValue $Evidence "ttlPolicies")
    foreach ($expected in $script:ExpectedTtlPolicies) {
        $matches = @($policyRows | Where-Object {
            [string](Get-PropertyValue $_ "collectionGroup") -ceq $expected.collectionGroup -and
            [string](Get-PropertyValue $_ "field") -ceq $expected.field
        })
        if ($matches.Count -ne 1) {
            & $AddFinding "historical_ttl_policy_missing" "L'evidenza deve registrare una sola policy TTL per $($expected.collectionGroup).$($expected.field)." $true
            continue
        }
        $policy = $matches[0]
        if ([string](Get-PropertyValue $policy "state") -cne "ACTIVE" -or
            [int](Get-PropertyValue $policy "expirationOffsetSeconds") -ne 0 -or
            [int](Get-PropertyValue $policy "appHorizonDays") -ne $expected.horizonDays) {
            & $AddFinding "historical_ttl_policy_invalid" "Snapshot TTL storico non conforme per $($expected.collectionGroup)." $true
        }
    }

    $rows = @(Get-PropertyValue $Evidence "collections")
    foreach ($expected in $script:ExpectedTtlPolicies) {
        $matches = @($rows | Where-Object {
            [string](Get-PropertyValue $_ "collectionGroup") -ceq $expected.collectionGroup -and
            [string](Get-PropertyValue $_ "field") -ceq $expected.field
        })
        if ($matches.Count -ne 1) {
            & $AddFinding "historical_cleanup_collection_missing" "L'evidenza deve contenere una sola verifica per $($expected.collectionGroup).$($expected.field)." $true
            continue
        }
        $row = $matches[0]
        $action = [string](Get-PropertyValue $row "action")
        if ($action -notin @("backfilled", "cleaned", "verified-empty")) {
            & $AddFinding "historical_cleanup_action_invalid" "Azione storica non verificabile per $($expected.collectionGroup)." $true
        }
        if ([string](Get-PropertyValue $row "readbackMethod") -cne "firestore.runQuery.expires_at-projection") {
            & $AddFinding "historical_cleanup_readback_missing" "Manca la prova read-back Firestore per $($expected.collectionGroup)." $true
        }
        $observed = Get-PropertyValue $row "observedDocumentCount"
        if ($null -eq $observed -or [int]$observed -lt 0) {
            & $AddFinding "historical_cleanup_document_count_invalid" "Conteggio documenti storico non valido per $($expected.collectionGroup)." $true
        }
        $remaining = Get-PropertyValue $row "missingOrInvalidExpiresAt"
        if ($null -eq $remaining -or [int]$remaining -ne 0) {
            & $AddFinding "historical_rows_without_expiry" "Restano documenti storici senza expires_at in $($expected.collectionGroup)." $true
        }
        $provenance = Get-PropertyValue $row "provenance"
        if ($null -eq $provenance) {
            & $AddFinding "historical_cleanup_provenance_missing" "Manca la provenienza strutturata dell'intervento per $($expected.collectionGroup)." $true
            continue
        }
        $mutationKind = [string](Get-PropertyValue $provenance "mutationKind")
        $allowedMutationKind = switch ($action) {
            "backfilled" { "atomic-backfill" }
            "cleaned" { "explicit-cleanup" }
            "verified-empty" { "none-readback-only" }
        }
        if ($mutationKind -cne $allowedMutationKind) {
            & $AddFinding "historical_cleanup_provenance_action_mismatch" "La provenienza non coincide con l'azione storica per $($expected.collectionGroup)." $true
        }
        $operationAtValue = Get-PropertyValue $provenance "operationAtUtc"
        $operationAt = [DateTimeOffset]::MinValue
        $operationAtParsed = $false
        if ($operationAtValue -is [DateTimeOffset]) {
            $operationAt = [DateTimeOffset]$operationAtValue
            $operationAtParsed = $true
        } elseif ($operationAtValue -is [DateTime]) {
            $operationAt = [DateTimeOffset]([DateTime]$operationAtValue)
            $operationAtParsed = $true
        } else {
            $operationAtParsed = [DateTimeOffset]::TryParse([string]$operationAtValue, [ref]$operationAt)
        }
        if (-not $operationAtParsed -or $operationAt.Offset -ne [TimeSpan]::Zero -or
            ($verifiedAtParsed -and $operationAt -gt $verifiedAt.AddMinutes(5))) {
            & $AddFinding "historical_cleanup_provenance_time_invalid" "operationAtUtc non e' una data UTC coerente per $($expected.collectionGroup)." $true
        }
        $targetDigest = [string](Get-PropertyValue $provenance "targetSetSha256")
        if ($action -in @("backfilled", "cleaned") -and $targetDigest -cnotmatch '^[0-9a-f]{64}$') {
            & $AddFinding "historical_cleanup_target_digest_invalid" "Digest dei record interessati non valido per $($expected.collectionGroup)." $true
        }
        $postReadbackDigest = [string](Get-PropertyValue $provenance "postReadbackSha256")
        if ($postReadbackDigest -cnotmatch '^[0-9a-f]{64}$') {
            & $AddFinding "historical_cleanup_readback_digest_invalid" "Digest del read-back post-intervento non valido per $($expected.collectionGroup)." $true
        }
    }
}

function Test-CurrentReadback {
    param(
        [object]$Readback,
        [System.Collections.Generic.List[object]]$Findings,
        [scriptblock]$AddFinding
    )
    if ($null -eq $Readback) {
        & $AddFinding "firestore_readback_missing" "Manca il read-back corrente delle due collection push." $true
        return
    }
    if ([string](Get-PropertyValue $Readback "schemaVersion") -cne "firestore-push-ttl-readback-v1" -or
        [string](Get-PropertyValue $Readback "projectId") -cne $script:ExpectedProjectId -or
        [string](Get-PropertyValue $Readback "databaseId") -cne $script:ExpectedDatabaseId) {
        & $AddFinding "firestore_readback_target_mismatch" "Il read-back non appartiene al database Firestore atteso." $true
    }
    if ([string](Get-PropertyValue $Readback "method") -cne "firestore.runQuery.expires_at-projection") {
        & $AddFinding "firestore_readback_method_invalid" "Metodo read-back inatteso." $true
    }
    $rows = @(Get-PropertyValue $Readback "collections")
    foreach ($expected in $script:ExpectedTtlPolicies) {
        $matches = @($rows | Where-Object {
            [string](Get-PropertyValue $_ "collectionGroup") -ceq $expected.collectionGroup -and
            [string](Get-PropertyValue $_ "field") -ceq $expected.field
        })
        if ($matches.Count -ne 1) {
            & $AddFinding "firestore_readback_collection_missing" "Il read-back deve contenere una sola riga per $($expected.collectionGroup)." $true
            continue
        }
        $row = $matches[0]
        $documents = Get-PropertyValue $row "documentCount"
        $valid = Get-PropertyValue $row "validExpiresAtCount"
        $missing = Get-PropertyValue $row "missingOrInvalidExpiresAt"
        if ($null -eq $documents -or $null -eq $valid -or $null -eq $missing -or
            [int]$documents -lt 0 -or [int]$valid -lt 0 -or [int]$missing -lt 0 -or
            ([int]$valid + [int]$missing) -ne [int]$documents) {
            & $AddFinding "firestore_readback_counts_invalid" "Conteggi read-back incoerenti per $($expected.collectionGroup)." $true
            continue
        }
        if ([int]$missing -ne 0) {
            & $AddFinding "firestore_current_rows_without_expiry" "Il read-back corrente trova $missing documenti senza timestamp expires_at valido in $($expected.collectionGroup)." $true
        }
        if ([string](Get-PropertyValue $row "documentSetSha256") -cnotmatch '^[0-9a-f]{64}$') {
            & $AddFinding "firestore_readback_digest_invalid" "Digest del read-back non valido per $($expected.collectionGroup)." $true
        }
    }
}

function Test-FirestorePushTtlState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object[]]$TtlPolicies,
        [Parameter(Mandatory = $true)][string]$PushRepositorySource,
        [string]$PushRepositorySha256 = "",
        [object]$CurrentReadback = $null,
        [object]$HistoricalEvidence = $null,
        [object]$EvidenceGitStatus = $null,
        [object]$RuntimeWriters = $null,
        [object]$RuntimeWriterContract = $null,
        [object]$RuntimeContractGitStatus = $null,
        [object]$RuntimeBuildVerification = $null,
        [object]$PushRepositoryGitStatus = $null,
        [object]$RuntimeWriterSetContract = $null,
        [object]$RuntimeWriterSetGitStatus = $null,
        [object[]]$RuntimeWriterSetProofs = @(),
        [string]$ExpectedReleaseApiTag = "",
        [string]$ProjectId = "meteo-friul",
        [string]$DatabaseId = "(default)"
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param([string]$Code, [string]$Message, [bool]$Blocking)
        $findings.Add([PSCustomObject]@{
            code = $Code
            message = $Message
            blocking = $Blocking
        })
    }

    if ($ProjectId -cne $script:ExpectedProjectId -or $DatabaseId -cne $script:ExpectedDatabaseId) {
        & $addFinding "firestore_target_mismatch" "Il gate e' vincolato a meteo-friul/(default)." $true
    }

    $expectedCollectionConstants = [ordered]@{
        PUSH_OUTBOX_COLLECTION = "push_official_alert_outbox"
        PUSH_LOCAL_NOTICE_OUTBOX_COLLECTION = "push_local_notice_outbox"
    }
    foreach ($entry in $expectedCollectionConstants.GetEnumerator()) {
        $actual = Get-PythonStringConstant -SourceText $PushRepositorySource -Name $entry.Key
        if ($actual -cne $entry.Value) {
            & $addFinding "app_collection_contract_mismatch" "La collection $($entry.Key) non coincide col contratto TTL." $true
        }
    }

    foreach ($expected in $script:ExpectedTtlPolicies) {
        $actualHorizon = Get-PythonIntegerConstant -SourceText $PushRepositorySource -Name $expected.retentionConstant
        if ($null -eq $actualHorizon -or $actualHorizon -ne $expected.horizonDays) {
            & $addFinding "app_retention_horizon_mismatch" "La retention applicativa $($expected.retentionConstant) deve essere $($expected.horizonDays) giorni." $true
        }
        if (-not (Test-RetentionConstantUsed -SourceText $PushRepositorySource -Name $expected.retentionConstant)) {
            & $addFinding "app_retention_constant_unused" "$($expected.retentionConstant) non alimenta expires_at tramite timedelta." $true
        }

        $expectedName = "projects/$ProjectId/databases/$DatabaseId/collectionGroups/$($expected.collectionGroup)/fields/$($expected.field)"
        $matches = @($TtlPolicies | Where-Object { [string](Get-PropertyValue $_ "name") -ceq $expectedName })
        if ($matches.Count -eq 0) {
            & $addFinding "ttl_policy_missing" "Policy TTL mancante per $($expected.collectionGroup).$($expected.field)." $true
            continue
        }
        if ($matches.Count -ne 1) {
            & $addFinding "ttl_policy_ambiguous" "Policy TTL non univoca per $($expected.collectionGroup).$($expected.field)." $true
            continue
        }
        $ttlConfig = Get-PropertyValue $matches[0] "ttlConfig"
        $state = [string](Get-PropertyValue $ttlConfig "state")
        if ($state -cne "ACTIVE") {
            & $addFinding "ttl_policy_not_active" "Policy TTL non ACTIVE per $($expected.collectionGroup).$($expected.field): $state." $true
        }
        $offset = Get-PropertyValue $ttlConfig "expirationOffset"
        if (-not (Test-ExpirationOffsetIsZero -Offset $offset)) {
            & $addFinding "ttl_expiration_offset_not_zero" "La policy $($expected.collectionGroup) aggiunge un offset oltre alla retention applicativa." $true
        }
    }

    Test-CurrentReadback -Readback $CurrentReadback -Findings $findings -AddFinding $addFinding
    Test-HistoricalEvidence -Evidence $HistoricalEvidence -EvidenceGitStatus $EvidenceGitStatus -Findings $findings -AddFinding $addFinding
    if ([string](Get-PropertyValue $RuntimeWriters "schemaVersion") -ceq "firestore-push-ttl-runtime-writers-v2") {
        $liveArgs = @{
            Inventory = $RuntimeWriters
            Contract = $RuntimeWriterSetContract
            ContractGitStatus = $RuntimeWriterSetGitStatus
            ImageProofs = $RuntimeWriterSetProofs
            PushRepositorySha256 = $PushRepositorySha256
            ExpectedJobs = @(Get-FirestorePushTtlScheduledWriterTargets)
            ExpectedReleaseApiTag = $ExpectedReleaseApiTag
        }
        foreach ($finding in @(Test-FirestorePushTtlLiveWriterSet @liveArgs)) {
            $findings.Add($finding)
        }
    } else {
        Test-RuntimeWriterParity -RuntimeWriters $RuntimeWriters `
            -RuntimeWriterContract $RuntimeWriterContract `
            -RuntimeContractGitStatus $RuntimeContractGitStatus `
            -RuntimeBuildVerification $RuntimeBuildVerification `
            -PushRepositoryGitStatus $PushRepositoryGitStatus `
            -PushRepositorySha256 $PushRepositorySha256 `
            -Findings $findings -AddFinding $addFinding
    }

    $blocking = @($findings | Where-Object { $_.blocking -eq $true })
    return [PSCustomObject]@{
        schemaVersion = "firestore-push-ttl-audit-v1"
        ready = ($blocking.Count -eq 0)
        blockingCount = $blocking.Count
        findings = $findings.ToArray()
        expected = [PSCustomObject]@{
            projectId = $script:ExpectedProjectId
            databaseId = $script:ExpectedDatabaseId
            region = $script:ExpectedRegion
            policies = @($script:ExpectedTtlPolicies | ForEach-Object {
                [PSCustomObject]@{
                    collectionGroup = $_.collectionGroup
                    field = $_.field
                    requiredState = "ACTIVE"
                    appHorizonDays = $_.horizonDays
                    expirationOffsetSeconds = 0
                }
            })
            runtimeWriters = @($script:ExpectedRuntimeWriters)
        }
        observed = [PSCustomObject]@{
            readback = $CurrentReadback
            evidenceGitStatus = $EvidenceGitStatus
            runtimeWriters = $RuntimeWriters
            runtimeWriterContract = $RuntimeWriterContract
            runtimeContractGitStatus = $RuntimeContractGitStatus
            runtimeBuildVerification = $RuntimeBuildVerification
            pushRepositoryGitStatus = $PushRepositoryGitStatus
            runtimeWriterSetContract = $RuntimeWriterSetContract
            runtimeWriterSetGitStatus = $RuntimeWriterSetGitStatus
            runtimeWriterSetProofs = @($RuntimeWriterSetProofs)
        }
        semantics = [PSCustomObject]@{
            ttlDeletesOnlyAfterDocumentTimestamp = $true
            missingOrNullFieldNeverExpires = $true
            deletionIsAsynchronous = $true
            historicalBackfillOrCleanupRequired = $true
            currentReadbackRequired = $true
            evidenceMustBeSingleAddGitHistory = $true
            runtimeWriterDigestParityRequired = ([string](Get-PropertyValue $RuntimeWriters "schemaVersion") -cne "firestore-push-ttl-runtime-writers-v2")
            runtimeWriterEachDigestAttestedRequired = ([string](Get-PropertyValue $RuntimeWriters "schemaVersion") -ceq "firestore-push-ttl-runtime-writers-v2")
            runtimeWriterImagesMustBeDigestPinned = $true
            runtimeWriterContractMustBeSingleAddGitHistory = $true
        }
    }
}

Export-ModuleMember -Function Test-FirestorePushTtlState, Resolve-RuntimeWriterContractCandidate, Get-FirestorePushTtlWriterJobNames, Get-FirestorePushTtlScheduledWriterTargets
