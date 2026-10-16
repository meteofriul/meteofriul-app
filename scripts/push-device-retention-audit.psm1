Set-StrictMode -Version Latest

function Get-PushDeviceRetentionProperty {
    param([object]$InputObject, [string]$Name)
    if ($null -eq $InputObject) { return $null }
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function ConvertTo-PushDeviceRetentionTimestamp {
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

function Test-PushDeviceRetentionSnapshot {
    [CmdletBinding()]
    param(
        [object[]]$Policies,
        [object[]]$Devices,
        [int]$RetentionDays = 30
    )

    $findings = New-Object System.Collections.Generic.List[object]
    $backfill = New-Object System.Collections.Generic.List[object]
    $legacyCleanup = New-Object System.Collections.Generic.List[object]
    $addFinding = {
        param([string]$Code, [string]$Message, [bool]$Blocking)
        $findings.Add([PSCustomObject]@{
            code = $Code
            message = $Message
            blocking = $Blocking
        })
    }

    if ($RetentionDays -ne 30) {
        & $addFinding "inactive_device_retention_mismatch" "La retention dei target FCM non validi deve essere di 30 giorni." $true
    }

    $expectedName = "projects/meteo-friul/databases/(default)/collectionGroups/push_devices/fields/expires_at"
    $policyMatches = @($Policies | Where-Object {
        [string](Get-PushDeviceRetentionProperty $_ "name") -ceq $expectedName
    })
    if ($policyMatches.Count -ne 1) {
        & $addFinding "push_device_ttl_policy_missing" "Manca una policy TTL univoca per push_devices.expires_at." $true
    } else {
        $ttlConfig = Get-PushDeviceRetentionProperty $policyMatches[0] "ttlConfig"
        $state = [string](Get-PushDeviceRetentionProperty $ttlConfig "state")
        if ($state -cne "ACTIVE") {
            & $addFinding "push_device_ttl_policy_not_active" "La policy TTL push_devices.expires_at non e' ACTIVE." $true
        }
        $offset = Get-PushDeviceRetentionProperty $ttlConfig "expirationOffset"
        if ($null -ne $offset -and [string]$offset -notin @("", "0s")) {
            & $addFinding "push_device_ttl_policy_offset" "La policy TTL deve usare offset zero." $true
        }
    }

    $activeCount = 0
    $inactiveInvalidCount = 0
    $legacyCount = 0
    foreach ($device in @($Devices)) {
        $active = Get-PushDeviceRetentionProperty $device "active"
        $schemaVersion = [string](Get-PushDeviceRetentionProperty $device "schemaVersion")
        $reason = [string](Get-PushDeviceRetentionProperty $device "disabledReason")
        $expiresAt = ConvertTo-PushDeviceRetentionTimestamp (
            Get-PushDeviceRetentionProperty $device "expiresAt"
        )
        $updatedAt = ConvertTo-PushDeviceRetentionTimestamp (
            Get-PushDeviceRetentionProperty $device "updatedAt"
        )

        if ($active -eq $true) {
            $activeCount += 1
            if ($null -ne $expiresAt) {
                & $addFinding "active_device_has_expiry" "Un dispositivo attivo contiene un timestamp TTL e rischia la cancellazione." $true
            }
            continue
        }

        if ($active -ne $false) {
            $legacyCount += 1
            if ($active -ne $null -or -not [string]::IsNullOrWhiteSpace($schemaVersion)) {
                & $addFinding "legacy_push_device_state_ambiguous" "Un record push senza stato corrente contiene active o schema inattesi e non e' eliminabile automaticamente." $true
                continue
            }
            if ((Get-PushDeviceRetentionProperty $device "referencedByOwner") -eq $true -or
                (Get-PushDeviceRetentionProperty $device "referencedByCapacity") -eq $true) {
                & $addFinding "legacy_push_device_still_referenced" "Un record push legacy e' ancora presente nell'indice target o nella capacita attiva." $true
                continue
            }
            $legacyUpdateTimeValue = [string](
                Get-PushDeviceRetentionProperty $device "updateTime"
            )
            $legacyUpdateTime = ConvertTo-PushDeviceRetentionTimestamp $legacyUpdateTimeValue
            if ($null -eq $legacyUpdateTime) {
                & $addFinding "legacy_push_device_update_time_invalid" "Un record push legacy non ha updateTime valido per una cancellazione condizionata." $true
                continue
            }
            $legacyCleanup.Add([PSCustomObject]@{
                documentName = [string](Get-PushDeviceRetentionProperty $device "documentName")
                documentKeyHash = [string](Get-PushDeviceRetentionProperty $device "documentKeyHash")
                updateTime = $legacyUpdateTimeValue
            })
            & $addFinding "legacy_push_device_cleanup_pending" "Esiste un record push legacy non referenziato, eliminabile soltanto con la procedura hard-delete separata." $true
            continue
        }

        if ($schemaVersion -cnotmatch '^2\.') {
            & $addFinding "inactive_device_schema_unsupported" "Un record inattivo non appartiene allo schema push 2.x." $true
            continue
        }
        if ($reason -cne "fcm_token_invalid") {
            & $addFinding "inactive_device_reason_unsupported" "Un record inattivo ha un motivo diverso da fcm_token_invalid e non riceve una scadenza automatica." $true
            continue
        }
        $inactiveInvalidCount += 1

        if ((Get-PushDeviceRetentionProperty $device "hasTargetValue") -eq $true -or
            (Get-PushDeviceRetentionProperty $device "hasLegacyToken") -eq $true) {
            & $addFinding "inactive_device_still_has_target" "Un record inattivo conserva ancora un target di consegna in chiaro." $true
            continue
        }
        if ((Get-PushDeviceRetentionProperty $device "referencedByOwner") -eq $true -or
            (Get-PushDeviceRetentionProperty $device "referencedByCapacity") -eq $true) {
            & $addFinding "inactive_device_still_referenced" "Un record inattivo e' ancora presente nell'indice target o nella capacita attiva." $true
            continue
        }
        if ($null -eq $updatedAt) {
            & $addFinding "inactive_device_updated_at_invalid" "Un record inattivo non ha updated_at valido." $true
            continue
        }

        $expectedExpiry = $updatedAt.AddDays($RetentionDays)
        if ($null -eq $expiresAt) {
            $backfill.Add([PSCustomObject]@{
                documentName = [string](Get-PushDeviceRetentionProperty $device "documentName")
                updateTime = [string](Get-PushDeviceRetentionProperty $device "updateTime")
                expectedExpiry = $expectedExpiry
                documentKeyHash = [string](Get-PushDeviceRetentionProperty $device "documentKeyHash")
            })
            continue
        }
        if ([Math]::Abs(($expiresAt - $expectedExpiry).TotalSeconds) -gt 1) {
            & $addFinding "inactive_device_expiry_mismatch" "La scadenza di un record inattivo non corrisponde a updated_at + 30 giorni." $true
        }
    }

    $blockingCount = @($findings | Where-Object { $_.blocking }).Count
    $backfillAllowedFindingCount = @($findings | Where-Object {
        $_.code -in @(
            "push_device_ttl_policy_missing",
            "push_device_ttl_policy_not_active",
            "legacy_push_device_cleanup_pending"
        )
    }).Count
    $legacyCleanupAllowedFindingCount = @($findings | Where-Object {
        $_.code -in @(
            "push_device_ttl_policy_missing",
            "push_device_ttl_policy_not_active",
            "legacy_push_device_cleanup_pending"
        )
    }).Count
    return [PSCustomObject]@{
        schemaVersion = "push-device-retention-audit-v1"
        ready = ($blockingCount -eq 0 -and $backfill.Count -eq 0)
        readyForBackfill = ($blockingCount -eq $backfillAllowedFindingCount)
        readyForLegacyCleanup = (
            $legacyCleanup.Count -gt 0 -and
            $blockingCount -eq $legacyCleanupAllowedFindingCount
        )
        retentionDays = $RetentionDays
        activeDeviceCount = $activeCount
        inactiveInvalidTokenCount = $inactiveInvalidCount
        legacyUnclassifiedCount = $legacyCount
        legacyCleanupCount = $legacyCleanup.Count
        backfillCount = $backfill.Count
        backfill = $backfill.ToArray()
        legacyCleanup = $legacyCleanup.ToArray()
        blockingCount = $blockingCount
        findings = $findings.ToArray()
    }
}

function New-PushDeviceLegacyCleanupPlan {
    [CmdletBinding()]
    param(
        [object]$Audit,
        [string]$ExpectedTargetSetSha256,
        [string]$ActualTargetSetSha256
    )

    if ((Get-PushDeviceRetentionProperty $Audit "readyForLegacyCleanup") -ne $true) {
        throw "push_device_legacy_cleanup_preflight_failed"
    }
    $targets = @(Get-PushDeviceRetentionProperty $Audit "legacyCleanup")
    if ($targets.Count -ne 1) {
        throw "push_device_legacy_cleanup_count_changed"
    }
    if ($ExpectedTargetSetSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $ActualTargetSetSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $ExpectedTargetSetSha256 -cne $ActualTargetSetSha256) {
        throw "push_device_legacy_cleanup_target_digest_mismatch"
    }
    $target = $targets[0]
    $documentName = [string](Get-PushDeviceRetentionProperty $target "documentName")
    $updateTime = [string](Get-PushDeviceRetentionProperty $target "updateTime")
    if ($documentName -cnotmatch '^projects/meteo-friul/databases/\(default\)/documents/push_devices/[^/]+$' -or
        $null -eq (ConvertTo-PushDeviceRetentionTimestamp $updateTime)) {
        throw "push_device_legacy_cleanup_target_invalid"
    }
    return [PSCustomObject]@{
        deleteCount = 1
        writes = @([ordered]@{
            delete = $documentName
            currentDocument = [ordered]@{ updateTime = $updateTime }
        })
    }
}

Export-ModuleMember -Function Test-PushDeviceRetentionSnapshot, New-PushDeviceLegacyCleanupPlan
