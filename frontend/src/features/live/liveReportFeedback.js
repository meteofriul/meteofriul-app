import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { getPilotMutationFeedback } from "./pilotReportOperations";

export function getReportFeedback(copy, result) {
  if (result?.ok) return copy.reportSuccess;
  if (result?.reason === "review_location_changed") return copy.reportReviewLocationChanged;
  if (result?.reason === "vote_location_required") return copy.confirmGpsRequired;
  if (isLocalCommunityPilot() && (result?.code || result?.detail?.code || result?.uncertain || ["pending_operation", "persistent_identity_required"].includes(result?.reason))) {
    return getPilotMutationFeedback(result);
  }
  if (result?.reason === "cooldown") {
    const retryAfterSeconds = Number(result?.retryAfterSeconds);
    if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
      const duration = retryAfterSeconds < 60
        ? `${Math.ceil(retryAfterSeconds)} s`
        : `${Math.ceil(retryAfterSeconds / 60)} min`;
      return `${copy.reportCooldown} ${duration}.`;
    }
    return result?.error || copy.reportSendError;
  }
  if (result?.reason === "permission_denied") return copy.reportGpsDenied;
  if (result?.reason === "location_services_disabled") return copy.reportGpsServicesDisabled;
  if (result?.reason === "approximate_location") return copy.reportGpsApproximate;
  if (result?.reason === "timeout") return copy.reportGpsTimeout;
  if (result?.reason === "unsupported") return copy.reportGpsUnsupported;
  if (result?.reason === "out_of_area") return copy.reportGpsTooFar;
  if (result?.reason === "invalid_place") return copy.reportLocationInvalid;
  if (result?.reason === "terms_required") return copy.reportTermsBody;
  if (result?.reason === "community_region_not_enabled") {
    return result?.detail?.message
      || "Le segnalazioni partecipative non sono ancora attive in questa regione.";
  }
  if ([
    "location_verification_failed",
    "missing_coordinates",
    "missing_quality",
    "stale_or_imprecise",
    "unavailable",
  ].includes(result?.reason)) {
    return copy.reportGpsUnavailable;
  }
  if (result?.reason === "request_failed" && result?.error) return result.error;
  return copy.reportSendError;
}
