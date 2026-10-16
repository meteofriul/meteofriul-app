import weatherContextReview from "../../data/discover/weatherContextReview.json";
import { isCuratedDiscoverPublished } from "./discoverCulturalReadiness";

const ARCHIVE_ONLY_IDS = new Set(weatherContextReview.editorialDecision.recordIds);

export function isDiscoverWeatherArchiveStory(record) {
  return ARCHIVE_ONLY_IDS.has(record?.id)
    && record.section === "archivio_tradizioni"
    && ["always", "seasonal"].includes(record.recurrence);
}

// This is a Scopri-only editorial interpretation, not weather detection.
// Keep the shared Ostermann source (also used by Almanacco) unchanged.
export function applyDiscoverWeatherEditorialPolicy(records, policy = weatherContextReview) {
  const decision = policy?.editorialDecision;
  if (decision?.approvalBasis !== "user_delegated_assisted_editorial_review"
    || decision.independentHumanReview !== false) return records;

  const approvedIds = new Set(decision.recordIds || []);
  const reviews = new Map((policy.records || []).map((review) => [review.recordId, review]));

  return records.map((record) => {
    const review = reviews.get(record.id);
    if (!approvedIds.has(record.id)
      || review?.disposition !== "archive_rotation"
      || !isCuratedDiscoverPublished(record)
      || record.recurrence !== "weather"
      || review.original?.recurrence !== record.recurrence
      || review.original?.section !== record.section
      || JSON.stringify(review.original?.seasons) !== JSON.stringify(record.seasons)
      || record.dateAnchors?.length
      || record.dateRanges?.length
      || record.movableDates?.length
      || record.movableDateRanges?.length
      || Object.hasOwn(record, "nthWeekdayDates")
      || record.months?.length
      || review.override?.section !== "archivio_tradizioni"
      || !["always", "seasonal"].includes(review.override?.recurrence)) return record;

    // Whitelist these two fields only: copy, identity, geography, seasons,
    // source notes and language approval are inherited from the original.
    return {
      ...record,
      section: review.override.section,
      recurrence: review.override.recurrence,
    };
  });
}
