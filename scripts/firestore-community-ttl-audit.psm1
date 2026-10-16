Set-StrictMode -Version Latest

$script:ExpectedAccount = "meteofriul@gmail.com"
$script:ExpectedProjectId = "meteo-friul"
$script:ExpectedProjectNumber = "49007668366"
$script:ExpectedDatabaseId = "(default)"
$script:ExpectedDatabaseName = "projects/meteo-friul/databases/(default)"
$script:HorizonToleranceSeconds = 5.0
$script:TtlDeletionGraceSeconds = 24 * 60 * 60
$script:ClockSkewToleranceSeconds = 5 * 60

function Get-CommunityTtlAuditProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function ConvertTo-CommunityTtlAuditTimestamp {
    param([object]$Value)
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }
    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }
    if ($Value -is [DateTime]) {
        $dateTime = [DateTime]$Value
        if ($dateTime.Kind -eq [DateTimeKind]::Unspecified) {
            $dateTime = [DateTime]::SpecifyKind($dateTime, [DateTimeKind]::Utc)
        }
        return ([DateTimeOffset]$dateTime).ToUniversalTime()
    }
    $parsed = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse(
        [string]$Value,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$parsed
    )) {
        return $null
    }
    return $parsed.ToUniversalTime()
}

function Test-CommunityTtlZeroOffset {
    param([object]$Value)
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $true
    }
    return [string]$Value -cmatch '^0(?:\.0+)?s$'
}

function Get-CommunityTtlAuditContract {
    return @(
        [PSCustomObject]@{
            collectionGroup = "community_reports"
            field = "expires_at_timestamp"
            baselineField = "created_at_timestamp"
            minimumHorizonSeconds = 3600.0
            maximumHorizonSeconds = 3600.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_report_cooldowns"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 2700.0
            maximumHorizonSeconds = 2700.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_report_confirmations"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 0.0
            maximumHorizonSeconds = 3600.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_report_flags"
            field = "expires_at_timestamp"
            baselineField = "created_at_timestamp"
            minimumHorizonSeconds = 86400.0
            maximumHorizonSeconds = 86400.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_report_moderation"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 0.0
            maximumHorizonSeconds = 86400.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_source_blocks"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 3600.0
            maximumHorizonSeconds = 86400.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_report_rate_limits"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 0.0
            maximumHorizonSeconds = 7200.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_moderation_digest_state"
            field = "expires_at_timestamp"
            baselineField = "updated_at_timestamp"
            minimumHorizonSeconds = 172800.0
            maximumHorizonSeconds = 172800.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_reputation"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 31536000.0
            maximumHorizonSeconds = 31536000.0
            requiresPositiveHorizon = $true
        },
        [PSCustomObject]@{
            collectionGroup = "community_reputation_awards"
            field = "expires_at_timestamp"
            baselineField = "updated_at"
            minimumHorizonSeconds = 31536000.0
            maximumHorizonSeconds = 31536000.0
            requiresPositiveHorizon = $true
        }
    )
}

function Test-FirestoreCommunityTtlSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Identity,
        [Parameter(Mandatory = $true)][object[]]$Policies,
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [object[]]$Documents,
        [DateTimeOffset]$CapturedAtUtc = [DateTimeOffset]::UtcNow,
        [ValidateSet("live-read-only", "fixture-read-only")]
        [string]$SourceMode = "live-read-only"
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param(
            [string]$Code,
            [string]$CollectionGroup,
            [string]$Message,
            [bool]$Blocking = $true
        )
        $findings.Add([PSCustomObject]@{
            code = $Code
            collectionGroup = $CollectionGroup
            message = $Message
            blocking = $Blocking
        })
    }
    if ($SourceMode -cne "live-read-only") {
        & $addFinding "community_ttl_fixture_evidence_not_live" "" (
            "Uno snapshot fixture puo validare il contratto, ma non attestare lo stato cloud."
        )
    }

    $activeAccounts = @(
        Get-CommunityTtlAuditProperty $Identity "activeAccounts" |
            ForEach-Object { [string]$_ } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    $configuredProject = [string](
        Get-CommunityTtlAuditProperty $Identity "configuredProject"
    )
    $configuredAccount = [string](
        Get-CommunityTtlAuditProperty $Identity "configuredAccount"
    )
    $projectId = [string](Get-CommunityTtlAuditProperty $Identity "projectId")
    $projectNumber = [string](
        Get-CommunityTtlAuditProperty $Identity "projectNumber"
    )
    $projectState = [string](
        Get-CommunityTtlAuditProperty $Identity "projectState"
    )
    $databaseName = [string](
        Get-CommunityTtlAuditProperty $Identity "databaseName"
    )
    $databaseType = [string](
        Get-CommunityTtlAuditProperty $Identity "databaseType"
    )

    if ($activeAccounts.Count -ne 1 -or $activeAccounts[0] -cne $script:ExpectedAccount) {
        & $addFinding "community_ttl_active_account_mismatch" "" (
            "Deve essere attivo un solo account Google Cloud, quello Meteo Friul."
        )
    }
    if ($configuredAccount -cne $script:ExpectedAccount) {
        & $addFinding "community_ttl_configured_account_mismatch" "" (
            "La configurazione gcloud attiva non usa l'account atteso."
        )
    }
    if ($configuredProject -cne $script:ExpectedProjectId) {
        & $addFinding "community_ttl_configured_project_mismatch" "" (
            "La configurazione gcloud attiva non punta al progetto atteso."
        )
    }
    if ($projectId -cne $script:ExpectedProjectId -or
        $projectNumber -cne $script:ExpectedProjectNumber -or
        $projectState -cne "ACTIVE") {
        & $addFinding "community_ttl_project_identity_mismatch" "" (
            "Identita, numero o stato del progetto Google Cloud non conformi."
        )
    }
    if ($databaseName -cne $script:ExpectedDatabaseName -or
        $databaseType -cne "FIRESTORE_NATIVE") {
        & $addFinding "community_ttl_database_identity_mismatch" "" (
            "Il database deve essere meteo-friul/(default) in modalita Firestore Native."
        )
    }

    $policyRows = New-Object System.Collections.Generic.List[object]
    $collectionRows = New-Object System.Collections.Generic.List[object]
    $contracts = @(Get-CommunityTtlAuditContract)
    foreach ($contract in $contracts) {
        $collectionGroup = [string]$contract.collectionGroup
        $expectedName = (
            "projects/$($script:ExpectedProjectId)/databases/" +
            "$($script:ExpectedDatabaseId)/collectionGroups/$collectionGroup/" +
            "fields/$($contract.field)"
        )
        $groupPrefix = (
            "projects/$($script:ExpectedProjectId)/databases/" +
            "$($script:ExpectedDatabaseId)/collectionGroups/$collectionGroup/fields/"
        )
        $matches = @($Policies | Where-Object {
            [string](Get-CommunityTtlAuditProperty $_ "name") -like "$groupPrefix*"
        })
        $state = "MISSING"
        $field = ""
        $offset = ""
        if ($matches.Count -ne 1) {
            & $addFinding "community_ttl_policy_missing_or_ambiguous" $collectionGroup (
                "Serve una sola policy TTL per il collection group."
            )
        } else {
            $name = [string](Get-CommunityTtlAuditProperty $matches[0] "name")
            if ($name.StartsWith($groupPrefix, [StringComparison]::Ordinal)) {
                $field = $name.Substring($groupPrefix.Length)
            }
            $ttlConfig = Get-CommunityTtlAuditProperty $matches[0] "ttlConfig"
            $state = [string](Get-CommunityTtlAuditProperty $ttlConfig "state")
            $offsetValue = Get-CommunityTtlAuditProperty $ttlConfig "expirationOffset"
            $offset = if ($null -eq $offsetValue -or
                [string]::IsNullOrWhiteSpace([string]$offsetValue)) {
                "0s"
            } else {
                [string]$offsetValue
            }
            if ($name -cne $expectedName) {
                & $addFinding "community_ttl_policy_field_mismatch" $collectionGroup (
                    "La policy TTL usa un campo diverso da expires_at_timestamp."
                )
            }
            if ($state -cne "ACTIVE") {
                & $addFinding "community_ttl_policy_not_active" $collectionGroup (
                    "La policy TTL non e' ACTIVE."
                )
            }
            if (-not (Test-CommunityTtlZeroOffset $offsetValue)) {
                & $addFinding "community_ttl_policy_offset_not_zero" $collectionGroup (
                    "La policy TTL aggiunge un offset alla retention applicativa."
                )
            }
        }
        $policyRows.Add([PSCustomObject]@{
            collectionGroup = $collectionGroup
            field = $field
            state = $state
            expirationOffset = $offset
        })

        $records = @($Documents | Where-Object {
            [string](Get-CommunityTtlAuditProperty $_ "collectionGroup") -ceq $collectionGroup
        })
        $missingExpiryCount = 0
        $wrongExpiryTypeCount = 0
        $invalidExpiryCount = 0
        $missingBaselineCount = 0
        $wrongBaselineTypeCount = 0
        $invalidBaselineCount = 0
        $futureBaselineCount = 0
        $expiredDocumentCount = 0
        $expiredBeyondGraceCount = 0
        $horizons = New-Object System.Collections.Generic.List[double]
        $recentHorizons = New-Object System.Collections.Generic.List[double]

        foreach ($record in $records) {
            $expiryType = [string](
                Get-CommunityTtlAuditProperty $record "expiryType"
            )
            $baselineType = [string](
                Get-CommunityTtlAuditProperty $record "baselineType"
            )
            if ([string]::IsNullOrWhiteSpace($expiryType) -or $expiryType -ceq "missing") {
                $missingExpiryCount += 1
                continue
            }
            if ($expiryType -cne "timestampValue") {
                $wrongExpiryTypeCount += 1
                continue
            }
            $expiresAt = ConvertTo-CommunityTtlAuditTimestamp (
                Get-CommunityTtlAuditProperty $record "expiresAt"
            )
            if ($null -eq $expiresAt) {
                $invalidExpiryCount += 1
                continue
            }
            if ($expiresAt -le $CapturedAtUtc.ToUniversalTime()) {
                $expiredDocumentCount += 1
            }
            $isRecent = $expiresAt -ge (
                $CapturedAtUtc.ToUniversalTime().AddSeconds(
                    -$script:TtlDeletionGraceSeconds
                )
            )
            if (-not $isRecent) {
                $expiredBeyondGraceCount += 1
            }
            if ([string]::IsNullOrWhiteSpace($baselineType) -or
                $baselineType -ceq "missing") {
                $missingBaselineCount += 1
                continue
            }
            if ($baselineType -cne "timestampValue") {
                $wrongBaselineTypeCount += 1
                continue
            }
            $baselineAt = ConvertTo-CommunityTtlAuditTimestamp (
                Get-CommunityTtlAuditProperty $record "baselineAt"
            )
            if ($null -eq $baselineAt) {
                $invalidBaselineCount += 1
                continue
            }
            if ($baselineAt -gt $CapturedAtUtc.ToUniversalTime().AddSeconds(
                $script:ClockSkewToleranceSeconds
            )) {
                $futureBaselineCount += 1
                continue
            }
            $horizonSeconds = ($expiresAt - $baselineAt).TotalSeconds
            $horizons.Add($horizonSeconds)
            if ($isRecent) {
                $recentHorizons.Add($horizonSeconds)
            }
        }

        foreach ($problem in @(
            [PSCustomObject]@{
                count = $missingExpiryCount
                code = "community_ttl_document_expiry_missing"
                message = "Documenti correnti privi del campo TTL."
            },
            [PSCustomObject]@{
                count = $wrongExpiryTypeCount
                code = "community_ttl_document_expiry_wrong_type"
                message = "Documenti correnti con campo TTL non timestamp."
            },
            [PSCustomObject]@{
                count = $invalidExpiryCount
                code = "community_ttl_document_expiry_invalid"
                message = "Documenti correnti con timestamp TTL non interpretabile."
            },
            [PSCustomObject]@{
                count = $missingBaselineCount
                code = "community_ttl_document_baseline_missing"
                message = "Documenti correnti privi del timestamp base della retention."
            },
            [PSCustomObject]@{
                count = $wrongBaselineTypeCount
                code = "community_ttl_document_baseline_wrong_type"
                message = "Documenti correnti con timestamp base di tipo errato."
            },
            [PSCustomObject]@{
                count = $invalidBaselineCount
                code = "community_ttl_document_baseline_invalid"
                message = "Documenti correnti con timestamp base non interpretabile."
            },
            [PSCustomObject]@{
                count = $futureBaselineCount
                code = "community_ttl_document_baseline_in_future"
                message = "Documenti correnti con timestamp base oltre la tolleranza di clock skew."
            }
        )) {
            if ([int]$problem.count -gt 0) {
                & $addFinding ([string]$problem.code) $collectionGroup (
                    "$($problem.message) Conteggio: $($problem.count)."
                )
            }
        }

        $belowMinimumCount = 0
        $aboveMaximumCount = 0
        foreach ($horizon in $horizons) {
            if (($contract.requiresPositiveHorizon -eq $true -and $horizon -le 0) -or
                ($contract.minimumHorizonSeconds -gt 0 -and
                    $horizon -lt (
                        $contract.minimumHorizonSeconds -
                        $script:HorizonToleranceSeconds
                    ))) {
                $belowMinimumCount += 1
            }
            if ($horizon -gt (
                $contract.maximumHorizonSeconds + $script:HorizonToleranceSeconds
            )) {
                $aboveMaximumCount += 1
            }
        }
        if ($belowMinimumCount -gt 0) {
            & $addFinding "community_ttl_document_horizon_too_short" $collectionGroup (
                "Uno o piu documenti hanno una retention inferiore al contratto."
            )
        }
        if ($aboveMaximumCount -gt 0) {
            & $addFinding "community_ttl_document_horizon_too_long" $collectionGroup (
                "Uno o piu documenti superano la retention massima."
            )
        }
        if ($expiredBeyondGraceCount -gt 0) {
            & $addFinding "community_ttl_document_expired_beyond_grace" $collectionGroup (
                "Documenti scaduti sono ancora presenti oltre la grace TTL di 24 ore."
            )
        }
        if ($recentHorizons.Count -eq 0) {
            & $addFinding "community_ttl_horizon_sample_missing" $collectionGroup (
                "Nessun documento corrente offre un campione recente dell'orizzonte; " +
                "la copertura storica viene attestata separatamente."
            ) $false
        }

        $minimumObserved = if ($horizons.Count -gt 0) {
            [Math]::Round(($horizons | Measure-Object -Minimum).Minimum, 3)
        } else {
            $null
        }
        $maximumObserved = if ($horizons.Count -gt 0) {
            [Math]::Round(($horizons | Measure-Object -Maximum).Maximum, 3)
        } else {
            $null
        }
        $collectionRows.Add([PSCustomObject]@{
            collectionGroup = $collectionGroup
            expiryField = [string]$contract.field
            baselineField = [string]$contract.baselineField
            contractualMinimumHorizonSeconds = [double]$contract.minimumHorizonSeconds
            contractualMaximumHorizonSeconds = [double]$contract.maximumHorizonSeconds
            documentCount = $records.Count
            validHorizonSampleCount = $horizons.Count
            recentHorizonSampleCount = $recentHorizons.Count
            missingExpiryCount = $missingExpiryCount
            wrongExpiryTypeCount = $wrongExpiryTypeCount
            invalidExpiryCount = $invalidExpiryCount
            missingBaselineCount = $missingBaselineCount
            wrongBaselineTypeCount = $wrongBaselineTypeCount
            invalidBaselineCount = $invalidBaselineCount
            futureBaselineCount = $futureBaselineCount
            expiredDocumentCount = $expiredDocumentCount
            expiredBeyondGraceCount = $expiredBeyondGraceCount
            belowMinimumHorizonCount = $belowMinimumCount
            aboveMaximumHorizonCount = $aboveMaximumCount
            minimumObservedHorizonSeconds = $minimumObserved
            maximumObservedHorizonSeconds = $maximumObserved
        })
    }

    $knownGroups = @{}
    foreach ($contract in $contracts) {
        $knownGroups[[string]$contract.collectionGroup] = $true
    }
    $unexpectedGroups = @($Documents | ForEach-Object {
        [string](Get-CommunityTtlAuditProperty $_ "collectionGroup")
    } | Where-Object {
        $_ -and -not $knownGroups.ContainsKey($_)
    } | Sort-Object -Unique)
    if ($unexpectedGroups.Count -gt 0) {
        & $addFinding "community_ttl_snapshot_collection_unexpected" "" (
            "Lo snapshot contiene collection group fuori contratto."
        )
    }

    $blockingCount = @($findings | Where-Object { $_.blocking }).Count
    $policyFindingCount = @($findings | Where-Object {
        [string]$_.code -like "community_ttl_policy_*"
    }).Count
    $identityFindingCount = @($findings | Where-Object {
        [string]$_.code -in @(
            "community_ttl_active_account_mismatch",
            "community_ttl_configured_account_mismatch",
            "community_ttl_configured_project_mismatch",
            "community_ttl_project_identity_mismatch",
            "community_ttl_database_identity_mismatch"
        )
    }).Count
    $sampleMissingCount = @($findings | Where-Object {
        [string]$_.code -ceq "community_ttl_horizon_sample_missing"
    }).Count
    $documentFindingCount = @($findings | Where-Object {
        [string]$_.code -like "community_ttl_document_*" -or
        [string]$_.code -ceq "community_ttl_snapshot_collection_unexpected"
    }).Count

    return [PSCustomObject]@{
        schemaVersion = "firestore-community-ttl-audit-v2"
        sourceMode = $SourceMode
        capturedAtUtc = $CapturedAtUtc.ToUniversalTime().ToString("o")
        ready = ($blockingCount -eq 0)
        identityReady = ($identityFindingCount -eq 0)
        policyReady = ($policyFindingCount -eq 0)
        documentReady = ($documentFindingCount -eq 0)
        sampleCoverageComplete = ($sampleMissingCount -eq 0)
        ttlDeletionGraceSeconds = $script:TtlDeletionGraceSeconds
        clockSkewToleranceSeconds = $script:ClockSkewToleranceSeconds
        identity = [PSCustomObject]@{
            activeAccount = if ($activeAccounts.Count -eq 1) { $activeAccounts[0] } else { "" }
            activeAccountCount = $activeAccounts.Count
            configuredAccount = $configuredAccount
            configuredProject = $configuredProject
            projectId = $projectId
            projectNumber = $projectNumber
            projectState = $projectState
            databaseName = $databaseName
            databaseType = $databaseType
        }
        policies = $policyRows.ToArray()
        collections = $collectionRows.ToArray()
        blockingCount = $blockingCount
        findings = $findings.ToArray()
    }
}

Export-ModuleMember -Function Get-CommunityTtlAuditContract, Test-FirestoreCommunityTtlSnapshot
