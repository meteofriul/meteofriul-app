import { MoonStar } from "lucide-react";

import { MoonPhaseIcon } from "../almanac/MoonPhaseIcon";
import { HomeTeaserCard } from "./HomeTeaserCard";

export function HomeAlmanacTeaser({ almanac, onOpen }) {
  if (!almanac) return null;
  const moonLabel = String(almanac.moonLabel || "").trim();
  const moonPhase = String(almanac.moon?.phase || "").trim();
  const showMoonLabel = moonLabel
    && !moonPhase.toLowerCase().startsWith(moonLabel.toLowerCase());

  return (
    <section className="mf-home-section mf-home-almanac" aria-labelledby="home-almanac-title">
      <HomeTeaserCard
        className="mf-home-almanac-card"
        heading={almanac.title}
        headingId="home-almanac-title"
        label={`${almanac.actionLabel}: ${almanac.dateLabel || almanac.title}`}
        meta={almanac.dateLabel}
        onOpen={onOpen}
      >
        <div className="mf-home-almanac-card__content">
          <p>{almanac.body}</p>
          {moonPhase ? (
            <p className="mf-home-almanac-card__details">
              {showMoonLabel ? <span>{moonLabel}</span> : null}
              <strong>{moonPhase}</strong>
            </p>
          ) : null}
        </div>
        <span className="mf-home-almanac-card__icon" aria-hidden="true">
          {almanac.moon ? (
            <MoonPhaseIcon
              cycleProgress={almanac.moon.cycleProgress}
              decorative
              label={almanac.moon.phase}
            />
          ) : (
            <MoonStar size={42} strokeWidth={2.05} />
          )}
        </span>
      </HomeTeaserCard>
    </section>
  );
}
