export function PilotWhyCard({ content }) {
  if (!content) return null;
  return (
    <section className="mf-discover-section mf-discover-why" aria-labelledby="discover-why-title">
      <h2 id="discover-why-title">{content.rubric}</h2>
      <article className="mf-discover-card mf-discover-card--editorial mf-discover-card--why" id={content.anchor} tabIndex={-1}>
        <h3>{content.question}</h3>
        <div className="mf-discover-why__answer">
          {content.answer.map((paragraph, index) => <p key={paragraph}>
            {index === 0 && content.lead ? <strong className="mf-discover-why__lead">{content.lead}</strong> : null}
            {paragraph}
          </p>)}
        </div>
        <footer className="mf-discover-editorial-source mf-discover-why__source">
          <span className="mf-discover-why__source-label">{content.sourcesLabel}</span>
          {content.sources[0].url
            ? <a href={content.sources[0].url} target="_blank" rel="noopener noreferrer">{content.sources[0].label}</a>
            : <span className="mf-discover-why__source-text">{content.sources[0].label}</span>}
        </footer>
      </article>
    </section>
  );
}
