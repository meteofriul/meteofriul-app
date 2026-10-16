// In-memory UX simulation only. These rules are not the production backend.
export const MINUTE = 60_000;
export const HOUR = 60 * MINUTE;
export const PREVIEW_TYPES = [
  { id: "rain", label: "Pioggia", color: "#2674a9" },
  { id: "storm", label: "Temporale", color: "#7654a0" },
  { id: "snow", label: "Neve", color: "#51889e" },
  { id: "hail", label: "Grandine", color: "#53639a" },
  { id: "fog", label: "Nebbia", color: "#62747b" },
  { id: "wind", label: "Vento forte", color: "#317a79" },
  { id: "ice", label: "Ghiaccio", color: "#466baa" },
  { id: "quiet", label: "Tranquillo", color: "#9a791c" },
];

export function createPreviewState(now = Date.now()) {
  const observation = (id, type, minutes, mine, extra = {}) => ({
    id, type, mine, place: "Pordenone", createdAt: now - minutes * MINUTE,
    expiresAt: now + (60 - minutes) * MINUTE, status: "active", yes: 0,
    no: 0, voted: "", validated: false, point: false, ...extra,
  });
  return {
    now, sequence: 1, total: 8, validated: 5, points: 4,
    creations: [now - 80 * MINUTE, now - 8 * MINUTE],
    awards: { "wind:Pordenone": now - 6 * MINUTE },
    notice: "", error: "",
    records: [
      observation("own-wind", "wind", 8, true, { validated: true, point: true, yes: 1 }),
      observation("other-rain", "rain", 12, false, { yes: 2, validated: true }),
      observation("other-fog", "fog", 25, false),
      observation("old-rain", "rain", 80, true, { status: "expired", validated: true, point: true }),
      observation("old-wind", "wind", 105, false, { status: "replaced" }),
    ],
  };
}

export function currentRecords(state) {
  return state.records.map((report) => report.status === "active" && report.expiresAt <= state.now
    ? { ...report, status: "expired" } : report);
}

export function historyRecords(state) {
  return currentRecords(state).filter((report) => report.createdAt > state.now - 48 * HOUR);
}

export function creationWait(state) {
  const recent = state.creations.filter((time) => time > state.now - 24 * HOUR);
  const hourly = recent.filter((time) => time > state.now - HOUR);
  const deadlines = [
    { at: (recent.at(-1) ?? -Infinity) + 3 * MINUTE, reason: "interval" },
    ...(hourly.length >= 4 ? [{ at: hourly.at(-4) + HOUR, reason: "hour" }] : []),
    ...(recent.length >= 12 ? [{ at: recent.at(-12) + 24 * HOUR, reason: "day" }] : []),
  ].sort((a, b) => b.at - a.at);
  return { seconds: Math.max(0, Math.ceil((deadlines[0].at - state.now) / 1000)), reason: deadlines[0].reason };
}

export function rankFor(points) {
  return points >= 15 ? "Sentinele dal Teritori" : points >= 5 ? "Vuaite dal Timp" : "Osservadôr dal Cîl";
}

function awardReport(state, records, index) {
  const report = records[index];
  const key = `${report.type}:${report.place}`;
  const firstValidation = !report.validated;
  const eligible = report.type !== "quiet" && !report.point && state.now >= (state.awards[key] ?? -Infinity) + 3 * HOUR;
  records[index] = { ...report, validated: true, point: report.point || eligible };
  return {
    ...state, records, validated: state.validated + Number(firstValidation),
    points: state.points + Number(eligible),
    awards: eligible ? { ...state.awards, [key]: state.now } : state.awards,
    notice: report.type === "quiet" ? "Conferma registrata. Tranquillo non assegna punti."
      : eligible ? "La tua segnalazione è stata confermata: +1 punto."
      : report.point ? "Segnalazione già premiata: il punto resta uno."
        : "Segnalazione confermata. Hai già ricevuto un punto per questo fenomeno qui nelle ultime 3 ore.",
  };
}

export function previewReducer(state, action) {
  const records = currentRecords(state);
  const base = { ...state, records, error: "", notice: "" };
  if (action.type === "advance") return { ...base, now: state.now + action.minutes * MINUTE };
  if (action.type === "clear") return { ...base };
  if (action.type === "submit") {
    if (!action.gps) return { ...base, error: "Serve una posizione recente per verificare il Comune. La segnalazione precedente resta attiva." };
    if (!PREVIEW_TYPES.some((type) => type.id === action.phenomenon)) return { ...base, error: "Scegli un fenomeno." };
    if (creationWait(state).seconds) return { ...base, error: "È troppo presto per un nuovo invio. Attendi il tempo indicato." };
    if (action.fail) return { ...base, error: "Invio non riuscito. La segnalazione precedente resta attiva. Puoi riprovare." };
    const id = `preview-${state.sequence}`;
    const nextRecords = records.map((item) => item.mine && item.status === "active" ? { ...item, status: "replaced" } : item);
    const newReport = {
      id, type: action.phenomenon, mine: true, place: "Pordenone", createdAt: state.now,
      expiresAt: state.now + HOUR, status: "active", yes: 0, no: 0, voted: "", validated: false, point: false,
    };
    const next = {
      ...base, sequence: state.sequence + 1, creations: [...state.creations, state.now],
      total: state.total + 1, records: [newReport, ...nextRecords], notice: "Segnalazione inviata. Rimarrà attiva per 60 minuti.",
    };
    // Only other ACTIVE observations count as independent evidence; archived
    // votes are not copied, even when an old record described the same type.
    const independent = nextRecords.some((item) => !item.mine && item.status === "active"
      && item.type === newReport.type && item.place === newReport.place
      && Math.floor(item.createdAt / HOUR) === Math.floor(newReport.createdAt / HOUR));
    return independent ? awardReport(next, next.records, 0) : next;
  }
  if (action.type === "witness") {
    const index = records.findIndex((item) => item.id === action.id && item.mine && item.status === "active");
    if (index < 0) return { ...base, error: "La segnalazione non è più attiva e non può ricevere conferme." };
    records[index] = { ...records[index], yes: records[index].yes + 1 };
    return awardReport(base, records, index);
  }
  if (action.type === "vote") {
    if (!["yes", "no"].includes(action.vote)) return state;
    const index = records.findIndex((item) => item.id === action.id && !item.mine && item.status === "active");
    if (index < 0) return { ...base, error: "Puoi votare solo segnalazioni attive di altre installazioni." };
    if (!action.gps) return { ...base, error: "Per votare serve una posizione recente compatibile con il Comune." };
    const report = records[index];
    if (report.voted === action.vote || report.voted === "no") return base;
    const no = report.no + Number(action.vote === "no");
    records[index] = {
      ...report, voted: action.vote, no, validated: report.validated || action.vote === "yes",
      yes: report.yes + Number(action.vote === "yes") - Number(report.voted === "yes"),
      status: no >= 3 ? "ceased" : "active",
    };
    return { ...base, records, notice: action.vote === "yes" ? "Conferma registrata. Grazie!" : "Grazie. Il fenomeno è nascosto dalla tua mappa; con 3 voti viene rimosso per tutti." };
  }
  return state;
}
