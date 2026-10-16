import {
  CircleCheck,
  CloudLightning,
  Eye,
  Snowflake,
  Sun,
  Thermometer,
  Umbrella,
  Wind,
} from "lucide-react";

import { HomeMeteoconIcon } from "./HomeMeteoconIcon";
import { HomeTeaserCard } from "./HomeTeaserCard";

const ADVICE_ICONS = {
  cold: Snowflake,
  fog: Eye,
  heat: Sun,
  rain: Umbrella,
  snow: Snowflake,
  stable: CircleCheck,
  storm: CloudLightning,
  temperature: Thermometer,
  wind: Wind,
};

export function HomeBulletinSummary({ bulletin, onOpen }) {
  if (!bulletin) return null;
  const cardAriaLabel = onOpen ? `${bulletin.actionLabel}: ${bulletin.headline}` : undefined;
  const AdviceIcon = ADVICE_ICONS[bulletin.advice?.group] || null;
  const adviceStatus = bulletin.advice ? "ready" : bulletin.adviceStatus || "unavailable";

  return (
    <section className="mf-home-section mf-home-bulletin" aria-labelledby="home-bulletin-title">
      <HomeTeaserCard
        className="mf-home-bulletin-card"
        heading={bulletin.title}
        headingId="home-bulletin-title"
        label={cardAriaLabel}
        meta={bulletin.dateLabel}
        onOpen={onOpen}
      >
        <div className="mf-home-bulletin-card__content">
          <div className="mf-home-bulletin-card__headline">
            <strong>{bulletin.headline}</strong>
          </div>
          {adviceStatus === "ready" ? (
            <div
              className="mf-home-bulletin-card__advice"
              data-advice-group={bulletin.advice.group}
              data-advice-source={bulletin.advice.source}
              data-advice-status="ready"
            >
              {AdviceIcon ? (
                <span className="mf-home-bulletin-card__advice-icon" aria-hidden="true">
                  <AdviceIcon size={20} strokeWidth={2.25} />
                </span>
              ) : null}
              <span className="mf-home-bulletin-card__advice-copy">{bulletin.advice.label}</span>
            </div>
          ) : adviceStatus === "pending" ? (
            <div
              aria-hidden="true"
              className="mf-home-bulletin-card__advice mf-home-bulletin-card__advice--pending"
              data-advice-status="pending"
            >
              <span className="mf-home-bulletin-card__advice-icon mf-home-bulletin-card__advice-skeleton-icon" />
              <span className="mf-home-bulletin-card__advice-skeleton-copy">
                <span />
                <span />
              </span>
            </div>
          ) : null}
          {bulletin.body ? <p>{bulletin.body}</p> : null}
        </div>
        <span
          className="mf-home-bulletin-card__icon mf-home-bulletin-card__icon--weather"
          aria-hidden="true"
        >
          <HomeMeteoconIcon icon={bulletin.icon} size={54} />
        </span>
      </HomeTeaserCard>
    </section>
  );
}
