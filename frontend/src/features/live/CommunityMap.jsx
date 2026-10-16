import {
  ArrowLeft,
  Check,
  Clock3,
  EyeOff,
  Flag,
  MapPin,
  MoreHorizontal,
  Pencil,
  RefreshCw,
  Trash2,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";

import { AppIconButton } from "../../ui/components/AppIconButton";
import {
  hideCommunityModerationSources,
  submitCommunityModerationFlag,
} from "./communityModerationActions";
import {
  isolateCommunityModalBackground,
  trapCommunityModerationFocus,
} from "./communityModerationFocus";
import { formatCommunitySourceLabel } from "./communitySourceAlias";
import {
  getCommunityVote,
  getOwnCommunityReport,
} from "./communityPersonalState";
import {
  getCommunityConfirmationSummary,
  getCommunityDenialLabel,
  getCommunityMapWithdrawalLabel,
  getOwnReportExpiryLabel,
} from "./communitySocialPresentation";
import { LIVE_REPORT_ICONS } from "./liveReportIcons";
import { getPilotMutationFeedback } from "./pilotReportOperations";
import { mountTerritoryBasemapLayer } from "./territoryBasemapLayer";
import { getTerritoryBasemapConfig } from "./territoryMapConfig";

const FVG_BOUNDS = [[45.55, 12.25], [46.75, 13.95]];
const PILOT_UPDATE_SUCCESS_FEEDBACK_MS = 2_000;
const LOCATION_UPDATE_FAILURE_REASONS = new Set([
  "location_mismatch",
  "location_required",
  "stale_or_imprecise",
  "permission_denied",
  "timeout",
  "unavailable",
  "missing_coordinates",
  "missing_quality",
  "native_location_unavailable",
  "location_services_disabled",
  "location_verification_failed",
  "out_of_area",
]);
function buildFallbackPositions(markers) {
  return Object.fromEntries(markers.map((marker, index) => {
    const x = Number(marker.x);
    const y = Number(marker.y);

    return [marker.id, {
      left: Number.isFinite(x) ? `${x}%` : `${42 + (index % 3) * 8}%`,
      top: Number.isFinite(y) ? `${y}%` : `${42 + (index % 2) * 12}%`,
    }];
  }));
}

function getMarkerLabel(marker) {
  return [marker.typeLabel, marker.place, marker.timeLabel, marker.countLabel]
    .filter(Boolean)
    .join(" · ");
}

export function CommunityModerationDialog({
  copy,
  onClose,
  onFlag,
  onHideSources,
  phenomenon,
}) {
  const [selectedReason, setSelectedReason] = useState("");
  const [submitStatus, setSubmitStatus] = useState("idle");
  const dialogRef = useRef(null);
  const dialogId = useId();
  const descriptionId = `${dialogId}-description`;
  const titleId = `${dialogId}-title`;
  const sourceKeys = Array.isArray(phenomenon?.sourceKeys)
    ? phenomenon.sourceKeys.filter(Boolean)
    : [];
  const sourceLabel = formatCommunitySourceLabel(sourceKeys, copy);
  const isSubmitting = submitStatus === "loading";
  usePilotBackHandler(() => { if (!isSubmitting) onClose?.(); });
  const canFlag = Boolean(onFlag);
  const hidesMultipleSources = sourceKeys.length > 1;
  const hideSourceBody = hidesMultipleSources
    ? copy.reportHideSourcesBody
    : copy.reportHideSourceBody;
  const hideSourceLabel = hidesMultipleSources
    ? copy.reportHideSources
    : copy.reportHideSource;

  useEffect(() => {
    const releaseBackground = isolateCommunityModalBackground();
    return releaseBackground;
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        if (!isSubmitting) onClose?.();
        return;
      }
      trapCommunityModerationFocus(event, dialogRef.current);
    };
    globalThis.document?.addEventListener?.("keydown", handleKeyDown);
    return () => globalThis.document?.removeEventListener?.("keydown", handleKeyDown);
  }, [isSubmitting, onClose]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!selectedReason || !onFlag || isSubmitting) {
      if (!selectedReason) setSubmitStatus("missing");
      return;
    }

    setSubmitStatus("loading");
    const result = await submitCommunityModerationFlag({
      onClose,
      onFlag,
      phenomenon,
      reason: selectedReason,
    });
    setSubmitStatus(result?.ok ? "success" : "error");
  };

  const dialog = (
    <div className="mf-live-moderation-backdrop">
      <form
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className="mf-live-moderation-dialog"
        onSubmit={handleSubmit}
        ref={dialogRef}
        role="dialog"
      >
        <div className="mf-live-moderation-dialog__heading">
          <div>
            <strong id={titleId}>{canFlag ? copy.reportFlagTitle : copy.reportManageContent}</strong>
            <p id={descriptionId}>{canFlag ? copy.reportFlagBody : hideSourceBody}</p>
          </div>
          <AppIconButton
            ariaLabel={copy.reportFlagClose}
            disabled={isSubmitting}
            icon={X}
            onClick={onClose}
          />
        </div>
        {sourceLabel ? (
          <p className="mf-live-moderation-dialog__source">{sourceLabel}</p>
        ) : null}
        {canFlag ? (
          <>
            <fieldset className="mf-live-moderation-dialog__reasons">
              <legend>{copy.reportFlagAction}</legend>
              {Object.entries(copy.reportFlagReasons).map(([reason, label], index) => (
                <label key={reason}>
                  <input
                    autoFocus={index === 0}
                    checked={selectedReason === reason}
                    disabled={isSubmitting}
                    name="community-flag-reason"
                    onChange={() => {
                      setSelectedReason(reason);
                      setSubmitStatus("idle");
                    }}
                    type="radio"
                    value={reason}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </fieldset>
            <button
              className="mf-live-moderation-dialog__submit mf-live-moderation-dialog__submit--flag"
              disabled={!selectedReason || isSubmitting}
              type="submit"
            >
              <Flag aria-hidden="true" fill="currentColor" size={16} strokeWidth={2.3} />
              {isSubmitting ? copy.reportFlagSending : copy.reportFlagSubmit}
            </button>
          </>
        ) : null}
        {sourceKeys.length > 0 && onHideSources ? (
          <button
            autoFocus={!canFlag}
            className="mf-live-moderation-dialog__hide-source"
            disabled={isSubmitting}
            onClick={() => {
              hideCommunityModerationSources({
                onClose,
                onHideSources,
                phenomenon,
              });
            }}
            type="button"
          >
            <EyeOff aria-hidden="true" size={16} strokeWidth={2.3} />
            {hideSourceLabel}
          </button>
        ) : null}
        {submitStatus === "error" || submitStatus === "missing" ? (
          <p aria-live="polite" className="mf-live-moderation-dialog__status" role="status">
            {submitStatus === "missing" ? copy.reportFlagReasonRequired : copy.reportFlagError}
          </p>
        ) : null}
      </form>
    </div>
  );

  return globalThis.document?.body
    ? createPortal(dialog, globalThis.document.body)
    : dialog;
}

export function CommunityGuidelinesConsentDialog({ copy, onAccept, onClose }) {
  const [accepted, setAccepted] = useState(false);
  const [isSubmitting, setSubmitting] = useState(false);
  usePilotBackHandler(() => { if (!isSubmitting) onClose?.(); });
  const dialogRef = useRef(null);
  const dialogId = useId();
  const descriptionId = `${dialogId}-description`;
  const titleId = `${dialogId}-title`;

  useEffect(() => isolateCommunityModalBackground(), []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        if (!isSubmitting) onClose?.();
        return;
      }
      trapCommunityModerationFocus(event, dialogRef.current);
    };
    globalThis.document?.addEventListener?.("keydown", handleKeyDown);
    return () => globalThis.document?.removeEventListener?.("keydown", handleKeyDown);
  }, [isSubmitting, onClose]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!accepted || isSubmitting) return;

    setSubmitting(true);
    await onAccept?.();
    setSubmitting(false);
  };

  const dialog = (
    <div className="mf-live-moderation-backdrop">
      <form
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className="mf-live-moderation-dialog mf-live-consent-dialog"
        onSubmit={handleSubmit}
        ref={dialogRef}
        role="dialog"
      >
        <div className="mf-live-moderation-dialog__heading">
          <div>
            <strong id={titleId}>{copy.reportTermsTitle}</strong>
            <p id={descriptionId}>{copy.confirmationTermsPrompt}</p>
          </div>
          <AppIconButton
            ariaLabel={copy.reportFlagClose}
            disabled={isSubmitting}
            icon={X}
            onClick={onClose}
          />
        </div>
        <p className="mf-live-consent-dialog__terms">{copy.reportTermsBody}</p>
        <label className="mf-live-consent-dialog__accept">
          <input
            autoFocus
            checked={accepted}
            disabled={isSubmitting}
            onChange={(event) => setAccepted(event.target.checked)}
            type="checkbox"
          />
          <span>{copy.confirmationTermsAccept}</span>
        </label>
        <button
          className="mf-live-moderation-dialog__submit"
          disabled={!accepted || isSubmitting}
          type="submit"
        >
          <Check aria-hidden="true" size={17} strokeWidth={2.4} />
          {copy.confirmationConsentSubmit}
        </button>
      </form>
    </div>
  );

  return globalThis.document?.body
    ? createPortal(dialog, globalThis.document.body)
    : dialog;
}

export function CommunityMapPhenomenon({
  confirmationActionLabel,
  confirmationCounts = null,
  confirmationEndedActionLabel,
  confirmationStatus = "idle",
  confirmationVote = "",
  copy,
  hideConfirmationDetails = false,
  hideConfirmationQuestion = false,
  hideSummary = false,
  ownReport = null,
  onConfirm,
  onEdit,
  onOpenModeration,
  onUpdate,
  onWithdraw,
  onCorrect,
  onReplace,
  pilotStyle = false,
  compactManagement = false,
  compactVoting = false,
  phenomenon,
}) {
  const updateAnnouncementId = useId();
  const [updateState, setUpdateState] = useState("idle");
  const [updateAnnouncement, setUpdateAnnouncement] = useState("");
  const [updateErrorReason, setUpdateErrorReason] = useState("");
  const updatePromiseRef = useRef(null);
  const updateAttemptVersionRef = useRef(null);
  const [withdrawState, setWithdrawState] = useState("idle");
  const withdrawButtonRef = useRef(null);
  const keepReportButtonRef = useRef(null);
  const previousWithdrawStateRef = useRef("idle");
  const [replaceState, setReplaceState] = useState("idle");
  const [replaceError, setReplaceError] = useState("");
  const [managementStep, setManagementStep] = useState("summary");
  const managementHeadingRef = useRef(null);
  const manageButtonRef = useRef(null);
  const ownHeadingRef = useRef(null);
  const previousManagementStepRef = useRef("summary");
  const managementId = useId();
  const [correctionExpired, setCorrectionExpired] = useState(() => Number(ownReport?.correctionUntil) <= Date.now());
  const withdrawalPromiseRef = useRef(null);
  const Icon = LIVE_REPORT_ICONS[phenomenon.typeId] || MapPin;
  const sourceLabel = formatCommunitySourceLabel(phenomenon.sourceKeys, copy);
  const resolvedConfirmationCounts = confirmationCounts || phenomenon.confirmations || {};
  const yesCount = Math.max(0, Number(resolvedConfirmationCounts.yes) || 0);
  const noCount = Math.max(0, Number(resolvedConfirmationCounts.no) || 0);
  const contextualActions = copy?.confirmationActions?.[phenomenon.typeId]
    || copy?.confirmationActions?.unknown
    || {};
  const positiveActionLabel = confirmationActionLabel
    || (compactVoting ? copy.confirmationCompactYes : "")
    || contextualActions.yes
    || (confirmationVote === "yes" ? copy.confirmationDone : copy.confirmationAction);
  const negativeActionLabel = confirmationEndedActionLabel
    || (compactVoting ? copy.confirmationCompactNo : "")
    || contextualActions.no
    || (confirmationVote === "no" ? copy.denialDone : copy.confirmationEndedAction);
  const confirmationSummary = getCommunityConfirmationSummary(copy, resolvedConfirmationCounts);
  const denialLabel = getCommunityDenialLabel(copy, resolvedConfirmationCounts);
  const withdrawalLabel = getCommunityMapWithdrawalLabel(copy, {
    ...phenomenon,
    confirmations: resolvedConfirmationCounts,
  });
  const votingLocked = confirmationVote === "no";
  const ownReportExpiry = ownReport
    ? getOwnReportExpiryLabel(
      copy,
      ownReport.expiresAt,
      undefined,
      { maxMinutes: pilotStyle ? 60 : undefined },
    )
    : "";
  const pilotUpdateSucceeded = pilotStyle && updateState === "success";
  const pilotUpdateFailed = pilotStyle && updateState === "error";
  const pilotUpdateHint = LOCATION_UPDATE_FAILURE_REASONS.has(updateErrorReason)
    ? copy.reportUpdateLocationHint
    : copy.reportUpdateRetryHint;
  const UpdateIcon = pilotUpdateSucceeded ? Check : RefreshCw;
  const updateButtonLabel = updateState === "loading"
    ? copy.reportUpdating
    : pilotUpdateSucceeded
      ? copy.reportUpdateDone
      : updateState === "error"
        ? copy.reportUpdateRetry
        : copy.reportUpdate;
  const canCorrect = Boolean(onCorrect && !correctionExpired && Number(ownReport?.correctionUntil) > 0);
  const canReplace = Boolean(onReplace && ownReport?.replacementAvailable === true);
  const managementBusy = updateState === "loading" || withdrawState === "loading" || replaceState === "loading";
  const canManage = Boolean(ownReport?.reportId && (onEdit || onUpdate || canCorrect || canReplace));
  const compactPilotWithdrawal = pilotStyle && compactManagement;

  useEffect(() => {
    if (!compactPilotWithdrawal) return;
    if (withdrawState === "confirm" || withdrawState === "error") keepReportButtonRef.current?.focus();
    else if (withdrawState === "idle" && previousWithdrawStateRef.current !== "idle") withdrawButtonRef.current?.focus();
    previousWithdrawStateRef.current = withdrawState;
  }, [compactPilotWithdrawal, withdrawState]);

  useEffect(() => {
    if (!compactManagement) return;
    if (managementStep !== "summary" && replaceState !== "loading") managementHeadingRef.current?.focus();
    else if (previousManagementStepRef.current !== "summary") {
      if (manageButtonRef.current?.disabled) ownHeadingRef.current?.focus();
      else manageButtonRef.current?.focus();
    }
    previousManagementStepRef.current = managementStep;
  }, [compactManagement, managementStep, replaceState]);

  useEffect(() => {
    if (!ownReport?.correctionUntil) return;
    const timeout = globalThis.setTimeout(() => setCorrectionExpired(true), Math.max(0, Number(ownReport.correctionUntil) - Date.now()));
    return () => globalThis.clearTimeout(timeout);
  }, [ownReport?.correctionUntil]);

  const confirmReplacement = async () => {
    if (!onReplace || !ownReport || replaceState === "loading" || updatePromiseRef.current || withdrawalPromiseRef.current) return;
    setReplaceState("loading");
    const result = await Promise.resolve(onReplace(ownReport)).catch(() => ({ ok: false }));
    if (!result?.ok) {
      setReplaceState("error");
      setReplaceError(getPilotMutationFeedback(result));
    }
  };

  useEffect(() => {
    if (!pilotUpdateSucceeded) return undefined;

    const timeoutId = globalThis.setTimeout?.(
      () => setUpdateState("idle"),
      PILOT_UPDATE_SUCCESS_FEEDBACK_MS,
    );
    return () => {
      if (timeoutId !== undefined) globalThis.clearTimeout?.(timeoutId);
    };
  }, [pilotUpdateSucceeded]);

  useEffect(() => {
    if (updateState !== "error") return;

    const attemptedVersion = updateAttemptVersionRef.current;
    const reportId = String(ownReport?.reportId || "").trim();
    if (!attemptedVersion || attemptedVersion.reportId !== reportId) return;

    const revision = Number(ownReport?.revision);
    const rawUpdatedAt = ownReport?.updatedAt ?? ownReport?.updated_at;
    const numericUpdatedAt = Number(rawUpdatedAt);
    const updatedAt = Number.isFinite(numericUpdatedAt)
      ? numericUpdatedAt
      : Date.parse(String(rawUpdatedAt || ""));
    const revisionAdvanced = Number.isFinite(revision)
      && Number.isFinite(attemptedVersion.revision)
      && revision > attemptedVersion.revision;
    const updatedAtAdvanced = Number.isFinite(updatedAt)
      && Number.isFinite(attemptedVersion.updatedAt)
      && updatedAt > attemptedVersion.updatedAt;

    if (revisionAdvanced || updatedAtAdvanced) {
      updateAttemptVersionRef.current = null;
      setUpdateAnnouncement(copy.reportUpdateSuccess);
      setUpdateErrorReason("");
      setUpdateState("success");
    }
  }, [
    ownReport?.reportId,
    ownReport?.revision,
    ownReport?.updatedAt,
    ownReport?.updated_at,
    copy.reportUpdateSuccess,
    updateState,
  ]);

  const confirmWithdrawal = async () => {
    const reportId = String(ownReport?.reportId || "").trim();
    if (!reportId || !onWithdraw || withdrawalPromiseRef.current || updatePromiseRef.current) return;
    setWithdrawState("loading");
    const operation = Promise.resolve(onWithdraw(reportId));
    withdrawalPromiseRef.current = operation;
    const result = await operation.catch(() => ({ ok: false }));
    withdrawalPromiseRef.current = null;
    if (!result?.ok) setWithdrawState("error");
  };

  const updateOwnReport = async () => {
    if (!ownReport?.reportId || !onUpdate || updatePromiseRef.current || withdrawalPromiseRef.current) return;
    const rawUpdatedAt = ownReport.updatedAt ?? ownReport.updated_at;
    const numericUpdatedAt = Number(rawUpdatedAt);
    updateAttemptVersionRef.current = {
      reportId: String(ownReport.reportId).trim(),
      revision: Number(ownReport.revision),
      updatedAt: Number.isFinite(numericUpdatedAt)
        ? numericUpdatedAt
        : Date.parse(String(rawUpdatedAt || "")),
    };
    setUpdateAnnouncement("");
    setUpdateErrorReason("");
    setUpdateState("loading");
    const operation = Promise.resolve().then(() => onUpdate(ownReport));
    updatePromiseRef.current = operation;
    const result = await operation.catch(() => ({ ok: false, reason: "request_failed" }));
    updatePromiseRef.current = null;
    if (result?.ok) {
      updateAttemptVersionRef.current = null;
      setUpdateAnnouncement(copy.reportUpdateSuccess);
      setUpdateState("success");
      if (compactManagement) setManagementStep("summary");
    }
    else if ([
      "observation_expired",
      "observation_conflict",
      "observation_rejected",
    ].includes(result?.reason)) {
      updateAttemptVersionRef.current = null;
      setUpdateAnnouncement("");
      setUpdateErrorReason("");
      setUpdateState("idle");
    }
    else {
      const errorReason = String(result?.reason || "request_failed");
      setUpdateAnnouncement(
        LOCATION_UPDATE_FAILURE_REASONS.has(errorReason)
          ? copy.reportUpdateLocationError
          : copy.reportUpdateError,
      );
      setUpdateErrorReason(errorReason);
      setUpdateState("error");
    }
  };

  return (
    <div className={`mf-live-community-map__phenomenon${hideSummary ? " mf-live-community-map__phenomenon--summary-hidden" : ""}`}>
      {!hideSummary ? (
        <>
          <span aria-hidden="true" className="mf-live-community-map__phenomenon-icon">
            <Icon size={17} strokeWidth={2.35} />
          </span>
          <div className="mf-live-community-map__phenomenon-copy">
            <strong>{phenomenon.typeLabel}</strong>
            <small>
              {[phenomenon.timeLabel, phenomenon.countLabel].filter(Boolean).join(" · ")}
            </small>
            {sourceLabel ? (
              <small className="mf-live-community-source">{sourceLabel}</small>
            ) : null}
          </div>
        </>
      ) : null}
      {ownReport ? (
        <div className={`mf-live-community-own-report ${pilotStyle ? "mf-live-community-own-report--pilot" : ""} ${compactManagement ? "mf-live-community-own-report--compact" : ""}`.trim()}>
          {compactManagement ? (
            <div className="mf-live-community-own-report__summary">
              <strong ref={ownHeadingRef} tabIndex={-1}>{copy.ownReportLabel}</strong>
              {ownReportExpiry ? <small className="mf-live-community-own-report__expiry"><Clock3 aria-hidden="true" size={13} />{ownReportExpiry}</small> : null}
            </div>
          ) : (
            <>
              <strong ref={ownHeadingRef}>{copy.ownReportLabel}</strong>
              {ownReportExpiry ? <small>{ownReportExpiry}</small> : null}
            </>
          )}
          {compactManagement && managementStep === "summary" && canManage && (!compactPilotWithdrawal || withdrawState === "idle") ? (
            <>
              <button
                aria-describedby={pilotUpdateFailed ? updateAnnouncementId : undefined}
                className={`mf-live-community-own-report__update mf-live-community-own-report__manage is-${updateState}`}
                disabled={managementBusy || pilotUpdateSucceeded || withdrawState !== "idle"}
                onClick={() => {
                  if (managementBusy || pilotUpdateSucceeded || withdrawState !== "idle" || updatePromiseRef.current || withdrawalPromiseRef.current) return;
                  if (onEdit) onEdit(ownReport);
                  else setManagementStep("manage");
                }}
                ref={manageButtonRef}
                type="button"
              >
                {pilotUpdateSucceeded ? <Check aria-hidden="true" size={16} /> : <Pencil aria-hidden="true" size={16} />}
                <span className="mf-live-community-own-report__update-label">{pilotUpdateSucceeded ? copy.reportUpdateDone : pilotUpdateFailed ? copy.reportUpdatePendingTitle : copy.reportManage}</span>
                {pilotUpdateFailed ? <small aria-hidden="true" className="mf-live-community-own-report__update-hint">{pilotUpdateHint}</small> : null}
              </button>
              {updateAnnouncement ? <span aria-live="polite" className="mf-live-community-own-report__update-announcement" id={updateAnnouncementId} role="status">{updateAnnouncement}</span> : null}
            </>
          ) : null}
          {compactManagement && managementStep !== "summary" ? (
            <div className="mf-live-community-own-report__management-heading">
              <button
                aria-label={copy.reportManageBack}
                className="mf-live-community-own-report__back"
                disabled={managementBusy}
                onClick={() => {
                  setReplaceState("idle");
                  setReplaceError("");
                  setManagementStep(managementStep === "change" ? "manage" : "summary");
                }}
                type="button"
              ><ArrowLeft aria-hidden="true" size={16} />{copy.reportManageBack}</button>
              <h3 ref={managementHeadingRef} tabIndex={-1}>{managementStep === "change" ? copy.reportChangeTitle : copy.reportManageTitle}</h3>
            </div>
          ) : null}
          {onUpdate && ownReport.reportId && (!compactManagement || managementStep === "manage") ? (
            <>
              <button
                aria-busy={updateState === "loading"}
                aria-describedby={pilotUpdateFailed ? updateAnnouncementId : compactManagement ? `${managementId}-renew` : undefined}
                className={`mf-live-community-own-report__update is-${updateState}`}
                disabled={updateState === "loading" || pilotUpdateSucceeded || withdrawState !== "idle" || replaceState !== "idle"}
                onClick={updateOwnReport}
                type="button"
              >
                <UpdateIcon aria-hidden="true" size={14} strokeWidth={2.3} />
                <span className="mf-live-community-own-report__update-label">
                  {compactManagement && updateState === "idle" ? copy.reportContinues : updateButtonLabel}
                </span>
                {pilotUpdateFailed ? (
                  <small aria-hidden="true" className="mf-live-community-own-report__update-hint">
                    {pilotUpdateHint}
                  </small>
                ) : null}
              </button>
              {compactManagement ? <p className="mf-live-community-own-report__explanation" id={`${managementId}-renew`}>{copy.reportContinuesHint}</p> : null}
              {pilotStyle && updateAnnouncement ? (
                <span
                  aria-live="polite"
                  className="mf-live-community-own-report__update-announcement"
                  id={updateAnnouncementId}
                  role="status"
                >
                  {updateAnnouncement}
                </span>
              ) : updateState === "success" || updateState === "error" ? (
                <small
                  aria-live="polite"
                  className={`mf-live-community-own-report__update-status is-${updateState}`}
                  role="status"
                >
                  {updateState === "success" ? copy.reportUpdateSuccess : copy.reportUpdateError}
                </small>
              ) : null}
            </>
          ) : null}
          {compactManagement && managementStep === "manage" ? (
            canCorrect || canReplace ? (
              <button
                className="mf-live-community-own-report__choice"
                disabled={managementBusy || pilotUpdateSucceeded}
                onClick={() => {
                  setManagementStep("change");
                  if (!canCorrect && canReplace) setReplaceState("confirm");
                }}
                type="button"
              ><Pencil aria-hidden="true" size={16} />{copy.reportChange}</button>
            ) : <p className="mf-live-community-own-report__explanation">{copy.reportChangeUnavailable}</p>
          ) : null}
          {compactManagement && managementStep === "change" ? (
            <div className="mf-live-community-own-report__change-options">
              {replaceState === "idle" ? (
                <>
                  {canCorrect ? <div className="mf-live-community-own-report__choice-group">
                    <button
                      aria-describedby={`${managementId}-correct`}
                      className="mf-live-community-own-report__choice"
                      disabled={managementBusy}
                      onClick={() => {
                        if (Number(ownReport.correctionUntil) <= Date.now()) { setCorrectionExpired(true); return; }
                        onCorrect(ownReport);
                      }}
                      type="button"
                    ><Pencil aria-hidden="true" size={16} />{copy.reportCorrectIntent}</button>
                    <p className="mf-live-community-own-report__explanation" id={`${managementId}-correct`}>{copy.reportCorrectionHint}</p>
                  </div> : null}
                  {canReplace ? <div className="mf-live-community-own-report__choice-group">
                    <button aria-describedby={`${managementId}-replace`} className="mf-live-community-own-report__choice" disabled={managementBusy} onClick={() => setReplaceState("confirm")} type="button"><RefreshCw aria-hidden="true" size={16} />{copy.reportReplaceIntent}</button>
                    <p className="mf-live-community-own-report__explanation" id={`${managementId}-replace`}>{copy.reportReplaceHint}</p>
                  </div> : null}
                  {!canCorrect && !canReplace ? <p className="mf-live-community-own-report__explanation" role="status">{copy.reportChangeUnavailable}</p> : null}
                </>
              ) : (
                <div className="mf-live-community-own-report__withdraw-confirm">
                  <p className="mf-live-community-own-report__explanation">{copy.reportReplacementBody}</p>
                  {replaceError ? <small className="mf-live-community-own-report__withdraw-error" role="status">{replaceError}</small> : null}
                  <button className="is-destructive" disabled={managementBusy} onClick={confirmReplacement} type="button"><RefreshCw aria-hidden="true" size={16} />{replaceState === "loading" ? copy.reportWithdrawing : copy.reportReplacementConfirm}</button>
                </div>
              )}
            </div>
          ) : null}
          {!compactManagement && (onCorrect || onReplace) ? (
            <div className="mf-live-community-own-report__secondary-actions">
              {onCorrect && !correctionExpired && Number(ownReport.correctionUntil) > 0 ? (
                <button disabled={updateState === "loading" || withdrawState !== "idle" || replaceState !== "idle"} onClick={() => onCorrect(ownReport)} type="button">
                  Correggi <small>Entro 5 minuti; scadenza invariata</small>
                </button>
              ) : null}
              {onReplace && ownReport.replacementAvailable === true ? (
                replaceState === "idle" ? (
                  <button disabled={updateState === "loading" || withdrawState !== "idle"} onClick={() => setReplaceState("confirm")} type="button">Ritira e sostituisci</button>
                ) : (
                  <div className="mf-live-community-own-report__withdraw-confirm">
                    <small>Ritira questa osservazione e apre un nuovo invio. Una sola sostituzione senza attesa; conta nei limiti di 4/60 minuti e 12/24 ore.</small>
                    {replaceError ? <small role="status">{replaceError}</small> : null}
                    <div>
                      <button disabled={replaceState === "loading"} onClick={() => setReplaceState("idle")} type="button">Indietro</button>
                      <button disabled={replaceState === "loading"} onClick={confirmReplacement} type="button">{replaceState === "loading" ? "Ritiro…" : "Ritira e continua"}</button>
                    </div>
                  </div>
                )
              ) : null}
            </div>
          ) : null}
          {onWithdraw && ownReport.reportId && (!compactManagement || managementStep === "summary") ? (
            withdrawState === "confirm" || withdrawState === "loading" || withdrawState === "error" ? (
              <div className="mf-live-community-own-report__withdraw-confirm">
                <small>{copy.reportWithdrawBody}</small>
                {withdrawState === "error" ? (
                  <small aria-live="polite" className="mf-live-community-own-report__withdraw-error" role="status">
                    {copy.reportWithdrawError}
                  </small>
                ) : null}
                <div>
                  <button
                    disabled={withdrawState === "loading" || updateState === "loading"}
                    onClick={() => setWithdrawState("idle")}
                    ref={keepReportButtonRef}
                    type="button"
                  >
                    {compactPilotWithdrawal ? <ThumbsUp aria-hidden="true" size={14} strokeWidth={2.3} /> : null}
                    {compactPilotWithdrawal ? copy.reportWithdrawKeepCompact : copy.reportWithdrawCancel}
                  </button>
                  <button
                    className="is-destructive"
                    disabled={withdrawState === "loading" || updateState === "loading"}
                    onClick={confirmWithdrawal}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={14} strokeWidth={2.3} />
                    {withdrawState === "loading" ? copy.reportWithdrawing : copy.reportWithdrawConfirm}
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="mf-live-community-own-report__withdraw"
                disabled={updateState === "loading" || replaceState !== "idle"}
                onClick={() => setWithdrawState("confirm")}
                ref={withdrawButtonRef}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} strokeWidth={2.3} />
                {compactManagement ? copy.reportWithdrawCompact : copy.reportWithdraw}
              </button>
            )
          ) : null}
        </div>
      ) : onConfirm ? (
        <div
          aria-label={hideConfirmationQuestion ? copy.confirmQuestion : undefined}
          className={`mf-live-community-map__confirm${hideConfirmationQuestion ? " mf-live-community-map__confirm--actions-only" : ""}${compactVoting ? " mf-live-community-map__confirm--compact" : ""}`}
        >
          {!hideConfirmationQuestion ? <span>{copy.confirmQuestion}</span> : null}
          <div className="mf-live-community-map__confirm-actions">
            <button
              aria-label={`${positiveActionLabel}. ${copy.confirmScore}: ${yesCount}`}
              aria-pressed={confirmationVote === "yes"}
              className="mf-live-community-map__confirm-button mf-live-community-map__confirm-button--yes"
              disabled={confirmationStatus === "loading" || votingLocked}
              onClick={(event) => onConfirm(
                phenomenon.groupId,
                "yes",
                event.currentTarget,
              )}
              type="button"
            >
              <ThumbsUp aria-hidden="true" size={16} strokeWidth={2.35} />
              <span className="mf-live-community-map__confirm-label">
                {positiveActionLabel}
              </span>
              <span aria-hidden="true" className="mf-live-community-map__confirm-count">
                {yesCount}
              </span>
            </button>
            <button
              aria-label={`${negativeActionLabel}. ${copy.confirmNoScore}: ${noCount}`}
              aria-pressed={confirmationVote === "no"}
              className="mf-live-community-map__confirm-button mf-live-community-map__confirm-button--no"
              disabled={confirmationStatus === "loading" || votingLocked}
              onClick={(event) => onConfirm(
                phenomenon.groupId,
                "no",
                event.currentTarget,
              )}
              type="button"
            >
              <ThumbsDown aria-hidden="true" size={16} strokeWidth={2.35} />
              <span className="mf-live-community-map__confirm-label">
                {negativeActionLabel}
              </span>
              <span aria-hidden="true" className="mf-live-community-map__confirm-count">
                {noCount}
              </span>
            </button>
          </div>
          {!hideConfirmationDetails ? (
            <>
              <small className="mf-live-community-map__denial-explanation">
                {copy.denialExplanation}
              </small>
              <small
                aria-live="polite"
                className="mf-live-community-map__confirmation-summary"
              >
                {confirmationStatus === "error"
                  ? copy.confirmError
                  : confirmationStatus === "success"
                    ? votingLocked
                      ? copy.denialDone
                      : copy.confirmationDoneFeedback
                    : confirmationSummary}
              </small>
              {denialLabel || withdrawalLabel ? (
                <small className="mf-live-community-map__denial-status">
                  {[denialLabel, withdrawalLabel].filter(Boolean).join(" · ")}
                </small>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
      {!ownReport && onOpenModeration ? (
        <button
          aria-label={copy.reportManageContent}
          className="mf-live-community-map__flag-action"
          onClick={onOpenModeration}
          type="button"
        >
          <MoreHorizontal aria-hidden="true" size={18} strokeWidth={2.4} />
        </button>
      ) : null}
    </div>
  );
}

export function CommunityMap({
  confirmationCountsByGroup = {},
  confirmationStatuses = {},
  copy,
  immersive = false,
  inferredOwnGroupIds = [],
  markers,
  onConfirm,
  onDetailOpenChange,
  onEdit,
  onFlag,
  onHideSources,
  onUpdate,
  onWithdraw,
  onCorrect,
  onReplace,
  personalState,
  theme = "light",
}) {
  const containerRef = useRef(null);
  const detailRef = useRef(null);
  const detailSwipeRef = useRef(null);
  const detailTriggerRef = useRef(null);
  const moderationTriggerRef = useRef(null);
  const regionRef = useRef(null);
  const mapRef = useRef(null);
  const [isMapReady, setMapReady] = useState(false);
  const [positions, setPositions] = useState(() => buildFallbackPositions(markers));
  const [selectedMarkerId, setSelectedMarkerId] = useState("");
  const [moderationTarget, setModerationTarget] = useState(null);
  const selectedMarker = useMemo(
    () => markers.find((marker) => marker.id === selectedMarkerId) || null,
    [markers, selectedMarkerId],
  );
  const totalReports = useMemo(
    () => markers.reduce((total, marker) => total + Math.max(1, Number(marker.count) || 0), 0),
    [markers],
  );
  const hasImmersiveDetail = immersive && Boolean(selectedMarker);
  const closeSelectedMarker = useCallback(({ restoreFocus = true } = {}) => {
    setSelectedMarkerId("");
    detailSwipeRef.current = null;
    if (!restoreFocus) return;

    globalThis.requestAnimationFrame?.(() => {
      const trigger = detailTriggerRef.current;
      if (trigger?.isConnected) trigger.focus?.({ preventScroll: true });
      else regionRef.current?.focus?.({ preventScroll: true });
    });
  }, []);
  const withdrawOwnReport = async (reportId) => {
    if (!onWithdraw) return { ok: false, reason: "unavailable" };
    const result = await onWithdraw(reportId);
    if (result?.ok) closeSelectedMarker();
    return result;
  };
  const updateOwnReport = async (report) => {
    if (!onUpdate) return { ok: false, reason: "unavailable" };
    const result = await onUpdate(report);
    if (result?.reason === "observation_expired") closeSelectedMarker({ restoreFocus: false });
    else if (["observation_conflict", "observation_rejected"].includes(result?.reason)) {
      closeSelectedMarker();
    }
    return result;
  };
  usePilotBackHandler(closeSelectedMarker, hasImmersiveDetail);

  useEffect(() => {
    onDetailOpenChange?.(hasImmersiveDetail);
    return () => {
      if (hasImmersiveDetail) onDetailOpenChange?.(false);
    };
  }, [hasImmersiveDetail, onDetailOpenChange]);

  useEffect(() => {
    if (!hasImmersiveDetail || !globalThis.document) return undefined;

    const documentLike = globalThis.document;
    const focusFrame = globalThis.requestAnimationFrame?.(
      () => detailRef.current?.focus?.({ preventScroll: true }),
    );
    const handleKeyDown = (event) => {
      if (documentLike.querySelector?.(".mf-live-moderation-backdrop")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeSelectedMarker();
        return;
      }

      if (trapCommunityModerationFocus(
        event,
        detailRef.current,
        documentLike.activeElement,
      )) {
        event.stopPropagation();
      }
    };

    documentLike.addEventListener("keydown", handleKeyDown, true);
    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      documentLike.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [closeSelectedMarker, hasImmersiveDetail]);

  const beginDetailSwipe = (event) => {
    const swipeSurface = event.target.closest?.(
      ".mf-live-community-map__detail-grabber, .mf-live-community-map__detail-heading",
    );
    if (
      !immersive
      || (event.pointerType && !["pen", "touch"].includes(event.pointerType))
      || event.currentTarget.scrollTop > 0
      || !swipeSurface
      || event.target.closest?.("a, button, input, select, textarea")
    ) return;

    detailSwipeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const finishDetailSwipe = (event) => {
    const swipe = detailSwipeRef.current;
    detailSwipeRef.current = null;
    if (!swipe || swipe.pointerId !== event.pointerId) return;

    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    const deltaX = Math.abs(event.clientX - swipe.startX);
    const deltaY = event.clientY - swipe.startY;
    if (deltaY >= 72 && deltaY > deltaX * 1.25) closeSelectedMarker();
  };

  useEffect(() => {
    let cancelled = false;
    let resizeFrame;
    let removeBasemap;

    async function mountMap() {
      const leafletModule = await import("leaflet");
      if (cancelled || !containerRef.current || mapRef.current) return;

      const L = leafletModule.default || leafletModule;
      const basemap = getTerritoryBasemapConfig(import.meta.env, { theme });
      const map = L.map(containerRef.current, {
        attributionControl: true,
        doubleClickZoom: true,
        maxBounds: [[45.2, 11.7], [47.0, 14.5]],
        maxBoundsViscosity: 0.8,
        maxZoom: basemap.primary.maxZoom,
        minZoom: basemap.primary.minZoom,
        scrollWheelZoom: false,
        touchZoom: true,
        zoomControl: false,
      });

      map.attributionControl.setPrefix(false);
      removeBasemap = mountTerritoryBasemapLayer({ basemap, leaflet: L, map });
      map.fitBounds(FVG_BOUNDS, immersive ? {
        paddingBottomRight: [24, 104],
        paddingTopLeft: [24, 96],
      } : { padding: [8, 8] });
      if (immersive) {
        map.on("click", () => closeSelectedMarker({ restoreFocus: false }));
        resizeFrame = globalThis.requestAnimationFrame?.(
          () => map.invalidateSize?.({ pan: false }),
        );
      }
      mapRef.current = map;
      setMapReady(true);
    }

    mountMap();

    return () => {
      cancelled = true;
      if (resizeFrame !== undefined) globalThis.cancelAnimationFrame?.(resizeFrame);
      removeBasemap?.();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [closeSelectedMarker, immersive, theme]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) {
      setPositions(buildFallbackPositions(markers));
      return undefined;
    }

    const projectMarkers = () => {
      const projected = {};

      markers.forEach((marker) => {
        if (!Number.isFinite(marker.lat) || !Number.isFinite(marker.lon)) return;
        const point = map.latLngToContainerPoint([marker.lat, marker.lon]);
        projected[marker.id] = { left: `${point.x}px`, top: `${point.y}px` };
      });

      setPositions({ ...buildFallbackPositions(markers), ...projected });
    };

    projectMarkers();
    map.on("move zoom resize", projectMarkers);

    return () => {
      map.off("move zoom resize", projectMarkers);
    };
  }, [isMapReady, markers]);

  const handleConfirmation = async (groupId, vote, trigger) => {
    if (!groupId || !onConfirm || confirmationStatuses[groupId] === "loading") return;
    await onConfirm(groupId, vote, trigger);
  };

  const closeModeration = () => {
    setModerationTarget(null);
    globalThis.setTimeout?.(() => {
      const trigger = moderationTriggerRef.current;
      if (trigger?.isConnected) trigger.focus();
      else regionRef.current?.focus?.({ preventScroll: true });
    }, 0);
  };

  return (
    <div
      aria-label={copy.liveMapAriaLabel}
      className={`mf-live-community-map ${immersive ? "mf-live-community-map--immersive" : ""}`.trim()}
      ref={regionRef}
      role="region"
      tabIndex={-1}
    >
      <div aria-hidden="true" className="mf-live-community-map__canvas" ref={containerRef} />
      {totalReports ? (
        <span className="mf-live-community-map__count">
          {totalReports === 1
            ? copy.liveMapCountOne
            : copy.liveMapCountMany.replace("{count}", String(totalReports))}
        </span>
      ) : null}
      {!markers.length ? (
        <div className="mf-live-community-map__empty">
          <MapPin aria-hidden="true" size={22} strokeWidth={2.25} />
          <strong>{copy.liveMapEmptyTitle}</strong>
          <span>{copy.liveMapEmptyBody}</span>
        </div>
      ) : null}
      <div aria-label={copy.communityFeedTitle} className="mf-live-community-map__markers">
        {markers.map((marker) => {
          const Icon = LIVE_REPORT_ICONS[marker.typeId] || MapPin;
          const position = positions[marker.id] || {};

          return (
            <button
              aria-label={getMarkerLabel(marker)}
              aria-pressed={selectedMarkerId === marker.id}
              className={`mf-live-community-map__marker mf-live-community-map__marker--${marker.typeId}`}
              key={marker.id}
              onClick={(event) => {
                detailTriggerRef.current = event.currentTarget;
                setSelectedMarkerId((current) => current === marker.id ? "" : marker.id);
              }}
              style={position}
              title={getMarkerLabel(marker)}
              type="button"
            >
              <Icon aria-hidden="true" size={17} strokeWidth={2.45} />
              {marker.count > 1 ? <span>{marker.count}</span> : null}
            </button>
          );
        })}
      </div>
      {selectedMarker ? (
        <div
          aria-label={immersive
            ? [selectedMarker.place, selectedMarker.countLabel].filter(Boolean).join(" · ")
            : undefined}
          className="mf-live-community-map__detail"
          onPointerCancel={() => { detailSwipeRef.current = null; }}
          onPointerDown={beginDetailSwipe}
          onPointerUp={finishDetailSwipe}
          ref={detailRef}
          role={immersive ? "dialog" : undefined}
          tabIndex={immersive ? -1 : undefined}
        >
          {immersive ? (
            <span
              aria-hidden="true"
              className="mf-live-community-map__detail-grabber"
            />
          ) : null}
          <div className="mf-live-community-map__detail-heading">
            <div>
              <strong>{selectedMarker.place}</strong>
              <span>{selectedMarker.countLabel}</span>
            </div>
            <AppIconButton
              ariaLabel={copy.liveMapDetailClose}
              icon={X}
              onClick={() => closeSelectedMarker()}
            />
          </div>
          <div className="mf-live-community-map__phenomena">
            {(selectedMarker.phenomena || [selectedMarker]).map((phenomenon) => {
              const confirmationStatus = confirmationStatuses[phenomenon.groupId] || "idle";
              const confirmationVote = getCommunityVote(personalState, phenomenon.groupId);
              const storedOwnReport = getOwnCommunityReport(personalState, phenomenon.groupId);
              const ownReport = storedOwnReport || (
                inferredOwnGroupIds.includes(phenomenon.groupId)
                  ? { expiresAt: phenomenon.expiresAt }
                  : null
              );
              const canManage = !ownReport && Boolean(
                onFlag
                || (onHideSources && phenomenon.sourceKeys?.length > 0),
              );

              return (
                <CommunityMapPhenomenon
                  confirmationCounts={confirmationCountsByGroup[phenomenon.groupId]}
                  confirmationStatus={confirmationStatus}
                  confirmationVote={confirmationVote}
                  copy={copy}
                  key={`${phenomenon.groupId || phenomenon.id}:${ownReport?.reportId || "guest"}`}
                  onConfirm={!ownReport && onConfirm ? handleConfirmation : undefined}
                  onEdit={storedOwnReport?.reportId && onEdit ? (report) => { closeSelectedMarker({ restoreFocus: false }); onEdit(report); } : undefined}
                  onOpenModeration={canManage ? (event) => {
                    moderationTriggerRef.current = event.currentTarget;
                    setModerationTarget(phenomenon);
                  } : undefined}
                  onUpdate={storedOwnReport?.reportId && onUpdate ? updateOwnReport : undefined}
                  onWithdraw={storedOwnReport?.reportId && onWithdraw ? withdrawOwnReport : undefined}
                  onCorrect={onCorrect ? (report) => { closeSelectedMarker({ restoreFocus: false }); onCorrect(report); } : undefined}
                  onReplace={onReplace ? async (report) => { const result = await onReplace(report); if (result?.ok) closeSelectedMarker({ restoreFocus: false }); return result; } : undefined}
                  ownReport={ownReport}
                  phenomenon={phenomenon}
                />
              );
            })}
          </div>
        </div>
      ) : null}
      {moderationTarget ? (
        <CommunityModerationDialog
          copy={copy}
          onClose={closeModeration}
          onFlag={onFlag}
          onHideSources={onHideSources}
          phenomenon={moderationTarget}
        />
      ) : null}
    </div>
  );
}
