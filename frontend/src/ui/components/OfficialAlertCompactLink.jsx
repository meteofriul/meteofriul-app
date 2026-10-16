import { AlertTriangle, ChevronRight } from "lucide-react";

const COPY = {
  it: {
    action: "Apri nel bollettino",
    source: "Protezione Civile FVG",
    sourcePrefix: "Fonte",
  },
  fur: {
    action: "Vierç tal boletin",
    source: "Protezion Civîl FVG",
    sourcePrefix: "Font",
  },
};

const ALERT_TONES = new Set(["yellow", "orange", "red"]);

function getLanguageKey(language) {
  return language === "fur" ? "fur" : "it";
}

function getAlertTone(tone) {
  return ALERT_TONES.has(tone) ? tone : "neutral";
}

export function OfficialAlertCompactLink({
  alert,
  language = "it",
  onOpen,
}) {
  const label = String(alert?.label || "").trim();
  if (!label) return null;

  const copy = COPY[getLanguageKey(language)];
  const source = String(alert?.meta || copy.source).trim();
  const validityLabel = String(alert?.validityLabel || "").trim();
  const tone = getAlertTone(alert?.tone);
  const className = "mf-official-alert-compact";
  const content = (
    <>
      <span aria-hidden="true" className="mf-official-alert-compact__icon">
        <AlertTriangle size={21} strokeWidth={2.4} />
      </span>
      <span className="mf-official-alert-compact__copy">
        <small>{source}</small>
        <strong>{label}</strong>
        {validityLabel ? <span>{validityLabel}</span> : null}
      </span>
      <ChevronRight
        aria-hidden="true"
        className="mf-official-alert-compact__chevron"
        size={19}
        strokeWidth={2.5}
      />
    </>
  );

  if (typeof onOpen !== "function") {
    return (
      <div className={className} data-alert-tone={tone}>
        {content}
      </div>
    );
  }

  const ariaLabel = [
    `${copy.action}: ${label}`,
    `${copy.sourcePrefix}: ${source}`,
    validityLabel,
  ].filter(Boolean).join(". ");

  return (
    <button
      aria-label={ariaLabel}
      className={className}
      data-alert-tone={tone}
      onClick={onOpen}
      type="button"
    >
      {content}
    </button>
  );
}
