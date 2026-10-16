import { getDiscoverCardAnchor } from "./discoverCardAnchor";

const MEMORY_SECTIONS = ["today-memory", "territory-stories", "local-memory-secondary"];
const TRADITION_SECTIONS = ["traditions", "rituals", "archive"];
const GREEN_TYPES = ["calendario", "agricoltura", "pianta", "animale"];
const SKY_TYPES = ["astronomia", "arcobaleno", "meteo_popolare", "grandine", "neve", "vento"];

/** Pilot-only presentation. Selection, full text and source stay in the shared model. */
export function PilotDiscoverCard({ card, sectionId = "", sourceLabel, language = "it" }) {
  const saying = sectionId === "traditional-sayings";
  const memory = MEMORY_SECTIONS.includes(sectionId);
  const variant = saying ? "saying" : memory ? "memory"
    : TRADITION_SECTIONS.includes(sectionId) ? "tradition" : "story";
  const tone = memory || saying || ["rito", "credenza"].includes(card.type) ? "gold"
    : GREEN_TYPES.includes(card.type) ? "green"
      : SKY_TYPES.includes(card.type) ? "sky" : "neutral";
  // The original category is preserved by the model; do not infer it from prose.
  const category = card.type === "musica"
    ? (language === "fur" ? "Musiche" : "Musica") : card.typeLabel;
  const metadata = [
    { kind: "category", value: category },
    { kind: "date", value: card.seasonLabel },
  ];
  if (memory) metadata.reverse();
  const visibleMetadata = metadata.filter(item => item.value);
  // Almanac fallback stores its saying in the body under a generic heading;
  // reused sayings store it in a title with no body. Other records have a
  // thematic title and commentary: never present those as a literal quotation.
  const bodyIsQuote = saying && ["Proverbio", "Proverbi"].includes(card.title) && card.text;
  const showQuote = saying && (bodyIsQuote || !card.text || !card.title || card.text === card.title);
  const quote = bodyIsQuote ? card.text : card.title || card.text;
  const visibleSourceLabel = /ostermann\s*1894/iu.test(sourceLabel || "")
    ? "Ostermann 1894"
    : sourceLabel;

  return (
    <article
      className={`mf-discover-card mf-discover-card--editorial mf-discover-card--${variant}`}
      data-editorial-tone={tone}
      id={getDiscoverCardAnchor(card.id)}
      tabIndex={-1}
    >
      {showQuote ? <>
        <span className="mf-discover-quote-mark" aria-hidden="true">“</span>
        <blockquote><p>{quote}</p></blockquote>
      </> : <>
        {!saying && visibleMetadata.length ? <div className="mf-discover-editorial-meta">
          {visibleMetadata.map(({ kind, value }, index) => <span key={kind} className={`mf-discover-editorial-meta--${kind}`}>
            {index ? <span aria-hidden="true">· </span> : null}{value}
          </span>)}
        </div> : null}
        <h3>{card.title}</h3>
        {card.text ? <p className="mf-discover-editorial-text">{card.text}</p> : null}
      </>}
      {visibleSourceLabel
        ? <footer className="mf-discover-editorial-source">{visibleSourceLabel}</footer>
        : null}
    </article>
  );
}
