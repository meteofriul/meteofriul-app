import { TriangleAlert } from "lucide-react";

import { getAppShellCopy } from "../../copy/appShellCopy";
import { HomeTeaserCard } from "./HomeTeaserCard";

const ACTION_COPY = {
  it: "Apri nel bollettino",
  fur: "Vierç tal boletin",
};

export function HomeOfficialAlertCard({ alert, language = "it", onOpen }) {
  if (!alert?.label) return null;

  const languageKey = language === "fur" ? "fur" : "it";
  const copy = getAppShellCopy(languageKey);
  const alertTone = ["yellow", "orange", "red"].includes(alert.tone)
    ? alert.tone
    : "neutral";
  const alertText = String(alert.text || alert.paragraphs?.[0] || "").trim();
  const validityLabel = String(alert.validityLabel || "").trim();

  return (
    <section
      aria-labelledby="home-official-alert-title"
      className="mf-home-section mf-home-bulletin mf-home-official-alert"
      data-alert-tone={alertTone}
    >
      <HomeTeaserCard
        className="mf-home-bulletin-card"
        heading={copy.officialAlertTitle}
        headingId="home-official-alert-title"
        label={onOpen ? `${ACTION_COPY[languageKey]}: ${alert.label}` : undefined}
        meta={alert.meta || copy.officialAlertSource}
        onOpen={onOpen}
      >
        <div className="mf-home-bulletin-card__content">
          <div className="mf-home-bulletin-card__headline">
            <strong>{alert.label}</strong>
          </div>
          {alertText ? <p>{alertText}</p> : null}
          {alert.languageNotice ? (
            <small className="mf-home-official-alert__language-note">
              {alert.languageNotice}
            </small>
          ) : null}
          {validityLabel && !alert.validityIncludedInText ? (
            <small className="mf-home-official-alert__validity">{validityLabel}</small>
          ) : null}
        </div>
        <span
          aria-hidden="true"
          className={`mf-home-bulletin-card__icon mf-home-bulletin-card__icon--alert mf-home-bulletin-card__icon--${alertTone}`}
        >
          <TriangleAlert size={31} strokeWidth={2.35} />
          <span className="mf-home-bulletin-card__alert-kicker">
            {languageKey === "fur" ? "ALERTE" : "ALLERTA"}
          </span>
        </span>
      </HomeTeaserCard>
    </section>
  );
}
