import candidateArchive from "../../data/almanac/proverbCandidates.json";
import candidateReview from "../../data/almanac/proverbCandidateReview.json";

const POSITIVE_REVIEW_HINTS = [
  /candidato forte/i,
  /candidato chiaro/i,
  /candidato breve/i,
  /candidato naturale/i,
  /candidato databile/i,
  /candidato leggibile/i,
  /molto leggibile/i,
  /semplice e databile/i,
  /datato e leggibile/i,
  /forte e leggibile/i,
];

const CONTEXT_OR_HOLD_HINTS = [
  /contradditt/i,
  /opposta/i,
  /Del Negro/i,
  /smentite/i,
  /doppia data/i,
  /o viceversa/i,
  /non immediat/i,
  /Scopri/i,
  /locale/i,
  /iperbolico/i,
  /prosa/i,
  /senza fur/i,
  /variant/i,
  /culturale/i,
  /cautela/i,
  /tono/i,
  /archivio/i,
  /non proverbio/i,
  /non promuovere/i,
  /duplicazione/i,
  /mancata verifica/i,
  /incert/i,
  /oscura/i,
  /spiegazione/i,
  /richiede nota/i,
  /contesto/i,
  /piu' culturale/i,
  /poco immediato/i,
];

function getRecords(archive) {
  return Array.isArray(archive?.records) ? archive.records : [];
}

function hasFurText(candidate) {
  return typeof candidate?.fur === "string" && candidate.fur.trim().length > 0;
}

function matchesAny(value, patterns) {
  return patterns.some((pattern) => pattern.test(value));
}

function routeUnreviewedCandidate(candidate) {
  const status = candidate?.review?.status || "missing";
  const notes = candidate?.review?.notes || "";

  if (status === "candidate" || !hasFurText(candidate)) {
    return {
      queue: "discoverArchive",
      reason: "candidate_or_no_fur",
    };
  }

  if (matchesAny(notes, CONTEXT_OR_HOLD_HINTS)) {
    return {
      queue: "needsContextOrHold",
      reason: "needs_context_or_editorial_hold",
    };
  }

  if (status === "source_checked" && matchesAny(notes, POSITIVE_REVIEW_HINTS)) {
    return {
      queue: "almanacReview",
      reason: "source_checked_with_positive_review_hint",
    };
  }

  return {
    queue: "needsContextOrHold",
    reason: "no_clear_promotion_signal",
  };
}

function pushRoute(queues, candidate, route) {
  queues[route.queue].push({
    id: candidate.id,
    category: candidate.category || null,
    status: candidate.review?.status || null,
    dateAnchors: candidate.dateAnchors || [],
    seasons: candidate.seasons || [],
    reason: route.reason,
  });
}

export function getProverbCandidateRoutingSummary(
  candidates = candidateArchive,
  review = candidateReview,
) {
  const candidateRecords = getRecords(candidates);
  const reviewedIds = new Set(getRecords(review).map((record) => record.id));
  const unreviewed = candidateRecords.filter((candidate) => !reviewedIds.has(candidate.id));
  const queues = {
    almanacReview: [],
    needsContextOrHold: [],
    discoverArchive: [],
  };

  unreviewed.forEach((candidate) => {
    pushRoute(queues, candidate, routeUnreviewedCandidate(candidate));
  });

  const routedIds = Object.values(queues)
    .flat()
    .map((item) => item.id);
  const duplicateRoutedIds = routedIds.filter((id, index) => routedIds.indexOf(id) !== index);

  return {
    totalCandidates: candidateRecords.length,
    reviewedCandidates: reviewedIds.size,
    unreviewedCandidates: unreviewed.length,
    unreviewedSourceChecked: unreviewed.filter(
      (candidate) => candidate.review?.status === "source_checked",
    ).length,
    unreviewedCandidateStatus: unreviewed.filter(
      (candidate) => candidate.review?.status === "candidate",
    ).length,
    queues,
    queueCounts: {
      almanacReview: queues.almanacReview.length,
      needsContextOrHold: queues.needsContextOrHold.length,
      discoverArchive: queues.discoverArchive.length,
    },
    duplicateRoutedIds: [...new Set(duplicateRoutedIds)],
  };
}
