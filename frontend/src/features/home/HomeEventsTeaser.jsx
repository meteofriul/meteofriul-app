import { useState } from "react";
import { CalendarDays, MapPin, Ticket } from "lucide-react";
import { HomeTeaserCard } from "./HomeTeaserCard";

function HomeEventVisual({ event }) {
  const [imageBroken, setImageBroken] = useState(false);
  const hasImage = Boolean(event?.image && !imageBroken);

  return (
    <span
      className={`mf-home-events-card__icon${hasImage ? " mf-home-events-card__icon--image" : ""}`}
      aria-hidden="true"
    >
      {hasImage ? (
        <img
          alt=""
          decoding="async"
          loading="lazy"
          onError={() => setImageBroken(true)}
          onLoad={(imageEvent) => {
            const image = imageEvent.currentTarget;
            if (image.naturalWidth < 96 || image.naturalHeight < 96) {
              setImageBroken(true);
            }
          }}
          src={event.image}
        />
      ) : (
        <Ticket size={36} strokeWidth={1.9} />
      )}
    </span>
  );
}

export function HomeEventsTeaser({ events, onOpen }) {
  const featuredEvent = events.items[0];
  const eventTags = [
    featuredEvent?.location
      ? { id: "location", icon: MapPin, label: featuredEvent.location }
      : null,
    featuredEvent?.dateLabel
      ? { id: "date", icon: CalendarDays, label: featuredEvent.dateLabel }
      : null,
  ].filter(Boolean);
  const cardLabel = featuredEvent
    ? `${events.actionLabel}: ${featuredEvent.title}`
    : events.actionLabel;

  return (
    <section className="mf-home-section mf-home-events" aria-labelledby="home-events-title">
      <HomeTeaserCard
        className="mf-home-events-card"
        heading={events.title}
        headingId="home-events-title"
        key={featuredEvent?.id || "empty"}
        label={cardLabel}
        meta={featuredEvent ? events.countValue ?? events.countLabel : undefined}
        metaLabel={featuredEvent ? events.countLabel : undefined}
        onOpen={featuredEvent ? onOpen : undefined}
      >
        {featuredEvent ? (
          <>
            <div className="mf-home-events-card__content">
              <span className="mf-home-events-card__headline">
                <strong>{featuredEvent.title}</strong>
              </span>
              {eventTags.length ? (
                <div className="mf-home-events-card__details" aria-label={events.tagsLabel}>
                  {eventTags.map((tag) => {
                    const TagIcon = tag.icon;

                    return (
                      <span key={tag.id}>
                        <TagIcon aria-hidden="true" size={14} strokeWidth={2.2} />
                        {tag.label}
                      </span>
                    );
                  })}
                </div>
              ) : null}
            </div>
            <HomeEventVisual event={featuredEvent} />
          </>
        ) : events.message ? <p className="mf-home-events__message">{events.message}</p> : null}
      </HomeTeaserCard>
    </section>
  );
}
