import { ChevronRight } from "lucide-react";

export function HomeTeaserCard({
  children,
  className,
  heading,
  headingId,
  label,
  meta,
  metaLabel,
  onOpen,
}) {
  return (
    <article className={`${className}${onOpen ? ` ${className}--interactive` : ""}`}>
      {onOpen ? (
        <button
          aria-label={label}
          className="mf-home-teaser-action"
          onClick={onOpen}
          type="button"
        />
      ) : null}
      <header className="mf-home-card-heading">
        <h2 id={headingId}>
          {heading}
          {onOpen ? <ChevronRight aria-hidden="true" size={18} strokeWidth={2.35} /> : null}
        </h2>
        {meta !== undefined && meta !== null && meta !== "" ? (
          <span className="mf-home-card-heading__meta">
            {metaLabel ? (
              <>
                <span aria-hidden="true">{meta}</span>
                <span className="mf-home-card-heading__meta-label">{metaLabel}</span>
              </>
            ) : meta}
          </span>
        ) : null}
      </header>
      {children}
    </article>
  );
}
