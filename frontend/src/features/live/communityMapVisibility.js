import {
  getCommunityVote,
  hasRememberedCommunityMapWithdrawal,
} from "./communityPersonalState";
import { isLocalCommunityPilot } from "../../services/localCommunityPilot";

export const COMMUNITY_MAP_WITHDRAWAL_DENIALS = 3;

function isMapWithdrawn(entry) {
  return Math.max(0, Number(entry?.confirmations?.no) || 0)
    >= COMMUNITY_MAP_WITHDRAWAL_DENIALS;
}

function isExpired(entry, now) {
  const expiresAt = Number(entry?.expiresAt ?? entry?.expires_at);
  return Number.isFinite(expiresAt) && expiresAt > 0 && expiresAt <= now;
}

export function isCommunityGroupHiddenFromMap(
  entry,
  personalState,
  { now = Date.now() } = {},
) {
  const numericNow = Number(now);
  if (isExpired(entry, Number.isFinite(numericNow) ? numericNow : Date.now())) return true;

  const groupId = String(entry?.groupId || entry?.group_id || "").trim();
  if (!groupId) return isMapWithdrawn(entry);

  const protectedGroups = isLocalCommunityPilot() && Array.isArray(entry?.lineageGroupIds)
    ? [groupId, ...entry.lineageGroupIds] : [groupId];
  return isMapWithdrawn(entry)
    || protectedGroups.some((id) => getCommunityVote(personalState, id) === "no"
      || hasRememberedCommunityMapWithdrawal(personalState, id));
}

export function filterCommunityMapMarkers(
  markers,
  personalState,
  copy = {},
  { now = Date.now() } = {},
) {
  const numericNow = Number(now);
  const resolvedNow = Number.isFinite(numericNow) ? numericNow : Date.now();

  return (Array.isArray(markers) ? markers : []).flatMap((marker) => {
    const sourcePhenomena = Array.isArray(marker?.phenomena) && marker.phenomena.length
      ? marker.phenomena
      : [marker];
    const phenomena = sourcePhenomena.filter(
      (phenomenon) => !isCommunityGroupHiddenFromMap(
        phenomenon,
        personalState,
        { now: resolvedNow },
      ),
    );
    if (!phenomena.length) return [];
    if (phenomena.length === sourcePhenomena.length) return [marker];

    const latest = phenomena.reduce((current, phenomenon) => (
      Number(phenomenon?.createdAt || 0) > Number(current?.createdAt || 0)
        ? phenomenon
        : current
    ));
    const count = phenomena.reduce(
      (total, phenomenon) => total + Math.max(1, Number(phenomenon?.count) || 1),
      0,
    );
    const sourceKeys = [...new Set(phenomena.flatMap((phenomenon) => (
      Array.isArray(phenomenon?.sourceKeys) ? phenomenon.sourceKeys : []
    )))];

    return [{
      ...marker,
      confirmations: phenomena.reduce((totals, phenomenon) => ({
        no: totals.no + Math.max(0, Number(phenomenon?.confirmations?.no) || 0),
        yes: totals.yes + Math.max(0, Number(phenomenon?.confirmations?.yes) || 0),
      }), { no: 0, yes: 0 }),
      count,
      countLabel: count === 1
        ? copy.reportCountOne
        : String(copy.reportCountMany || "{count}").replace("{count}", String(count)),
      createdAt: latest.createdAt,
      expiresAt: latest.expiresAt,
      phenomena,
      reportIds: [...new Set(phenomena.flatMap((phenomenon) => (
        Array.isArray(phenomenon?.reportIds) ? phenomenon.reportIds : []
      )))],
      sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
      sourceKeys,
      timeLabel: latest.timeLabel,
      typeId: phenomena.length > 1 ? "multiple" : latest.typeId,
      typeLabel: phenomena.length > 1 ? copy.reportMultiplePhenomena : latest.typeLabel,
    }];
  });
}

export function getAcquiredCommunityMapWithdrawals(model, personalState) {
  const entries = [
    ...(Array.isArray(model?.items) ? model.items : []),
    ...(Array.isArray(model?.markers)
      ? model.markers.flatMap((marker) => marker?.phenomena || [marker])
      : []),
  ];
  const seen = new Set();

  return entries.flatMap((entry) => {
    const groupId = String(entry?.groupId || entry?.group_id || "").trim();
    if (
      !groupId
      || seen.has(groupId)
      || !isMapWithdrawn(entry)
      || hasRememberedCommunityMapWithdrawal(personalState, groupId)
    ) return [];

    seen.add(groupId);
    return [{ expiresAt: entry.expiresAt || entry.expires_at, groupId }];
  });
}
