import { ExternalLink, Megaphone } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { recordPromotionEvent } from "../../services/promotionCatalog";

import {
  PROMOTION_ROTATION_INTERVAL_MS,
  getPromotionRotationSlot,
  getPromotionSessionId,
  recordPromotionImpression,
  selectPromotion,
} from "./promotionDelivery";
import { usePromotionCatalog } from "./usePromotionCatalog";

const COPY = {
  fur: {
    action: "Scuvierç la ativitât",
    label: "Publicitât",
  },
  it: {
    action: "Scopri l’attività",
    label: "Pubblicità",
  },
};

export function PromotionPlacementCard({ campaigns, language = "it", now, placement = "home" }) {
  const cardRef = useRef(null);
  const impressionRecordedRef = useRef("");
  const copy = COPY[language] || COPY.it;
  const sessionId = useMemo(() => getPromotionSessionId(), []);
  const usesRemoteCatalog = !Array.isArray(campaigns);
  const remoteCatalog = usePromotionCatalog(usesRemoteCatalog);
  const activeCampaigns = usesRemoteCatalog ? remoteCatalog.campaigns : campaigns;
  const dailyCap = usesRemoteCatalog ? remoteCatalog.dailyCap : undefined;
  const maxRotationCampaigns = usesRemoteCatalog ? remoteCatalog.maxRotationCampaigns : undefined;
  const rotationIntervalMs = usesRemoteCatalog
    ? Number(remoteCatalog.placementRotationIntervals?.[placement] || 120) * 1000
    : PROMOTION_ROTATION_INTERVAL_MS;
  const [rotationClock, setRotationClock] = useState(() => Date.now());
  const rotationNow = now ?? rotationClock;

  useEffect(() => {
    if (now !== undefined) return undefined;
    let timer;
    const schedule = () => {
      const current = Date.now();
      setRotationClock(current);
      const nextBoundary = (getPromotionRotationSlot(current, rotationIntervalMs) + 1) * rotationIntervalMs;
      timer = globalThis.setTimeout?.(schedule, Math.max(250, nextBoundary - current + 25));
    };
    schedule();
    return () => globalThis.clearTimeout?.(timer);
  }, [now, rotationIntervalMs]);

  const campaign = useMemo(() => selectPromotion({
    campaigns: activeCampaigns,
    maxRotationCampaigns,
    now: rotationNow,
    placement,
    rotationIntervalMs,
  }), [activeCampaigns, maxRotationCampaigns, placement, rotationIntervalMs, rotationNow]);

  useEffect(() => {
    const node = cardRef.current;
    if (!campaign || !node || typeof globalThis.IntersectionObserver !== "function") return undefined;
    let visibilityTimer;
    const slot = getPromotionRotationSlot(rotationNow, rotationIntervalMs);
    const impressionKey = `${placement}:${campaign.id}:${slot}`;
    const observer = new globalThis.IntersectionObserver((entries) => {
      const visible = entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.5);
      globalThis.clearTimeout?.(visibilityTimer);
      if (!visible || impressionRecordedRef.current === impressionKey) return;
      visibilityTimer = globalThis.setTimeout?.(() => {
        impressionRecordedRef.current = impressionKey;
        const counted = recordPromotionImpression({
          campaign,
          dailyCap,
          now: rotationNow,
          placement,
          rotationIntervalMs,
          sessionId,
        });
        if (counted && usesRemoteCatalog) {
          void recordPromotionEvent({ campaignId: campaign.id, placement, type: "impression" });
        }
      }, 1000);
    }, { threshold: [0.5] });
    observer.observe(node);
    return () => {
      globalThis.clearTimeout?.(visibilityTimer);
      observer.disconnect();
    };
  }, [campaign, dailyCap, placement, rotationIntervalMs, rotationNow, sessionId, usesRemoteCatalog]);

  if (!campaign) return null;

  const titleId = `promotion-${placement}-${campaign.id}-title`;
  return (
    <article
      aria-labelledby={titleId}
      className={`mf-home-promotion mf-promotion-card mf-promotion-card--${placement}`}
      data-promotion-id={campaign.id}
      data-promotion-placement={placement}
      ref={cardRef}
    >
      <a
        aria-label={`${campaign.ctaLabel || copy.action}: ${campaign.title}`}
        className="mf-home-promotion__link"
        href={campaign.url}
        onClick={() => {
          if (usesRemoteCatalog) void recordPromotionEvent({ campaignId: campaign.id, placement, type: "open" });
        }}
        rel="sponsored noopener noreferrer"
        target="_blank"
      >
        <span className="mf-home-promotion__media" aria-hidden="true">
          {campaign.image ? <img alt="" decoding="async" loading="lazy" src={campaign.image} /> : (
            <span className="mf-home-promotion__fallback">
              <Megaphone size={30} strokeWidth={1.9} />
            </span>
          )}
        </span>
        <span className="mf-home-promotion__body">
          <span className="mf-home-promotion__label">{copy.label}</span>
          <strong id={titleId}>
            {campaign.title}{campaign.location ? ` · ${campaign.location}` : ""}
          </strong>
          {campaign.category || campaign.businessAddress ? (
            <span className="mf-home-promotion__details">{[campaign.category, campaign.businessAddress].filter(Boolean).join(" · ")}</span>
          ) : null}
          {campaign.headline ? <span className="mf-home-promotion__headline">{campaign.headline}</span> : null}
          <span className="mf-home-promotion__text">{campaign.text}</span>
          <span className="mf-home-promotion__cta">
            {campaign.ctaLabel || copy.action}<ExternalLink aria-hidden="true" size={15} strokeWidth={2.2} />
          </span>
        </span>
      </a>
    </article>
  );
}
