function TabPageTitle({ language, title }) {
  if (language !== "fur" || !title) {
    return title;
  }

  return (
    <span className="mf-tab-page__title-text" lang="fur">
      <span className="mf-tab-page__title-initial">{title.slice(0, 1)}</span>
      <span>{title.slice(1)}</span>
    </span>
  );
}

export function TabPage({ children, className = "", language = "it", title, titleMeta, titleMode = "visible" }) {
  const pageClassName = `mf-tab-page ${className}`.trim();
  const titleClassName = titleMode === "hidden" ? "mf-tab-page__title--hidden" : "";
  const titleNode = (
    <h1 className={titleClassName} id={`${title}-title`}>
      <TabPageTitle language={language} title={title} />
    </h1>
  );

  return (
    <section className={pageClassName} aria-labelledby={`${title}-title`}>
      {titleMeta ? (
        <div className="mf-tab-page__title-row">
          {titleNode}
          <span className="mf-tab-page__title-meta">{titleMeta}</span>
        </div>
      ) : titleNode}
      {children}
    </section>
  );
}
