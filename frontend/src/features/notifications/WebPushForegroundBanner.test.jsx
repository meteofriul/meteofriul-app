import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WebPushForegroundBanner } from "./WebPushForegroundBanner";

describe("WebPushForegroundBanner", () => {
  it("announces foreground notification copy with bulletin and close actions", () => {
    const html = renderToStaticMarkup(
      <WebPushForegroundBanner
        language="it"
        message={{ body: "Allerta gialla in corso.", title: "Protezione Civile FVG" }}
      />,
    );

    expect(html).toContain('aria-live="polite"');
    expect(html).toContain("Protezione Civile FVG");
    expect(html).toContain("Allerta gialla in corso.");
    expect(html).toContain("Apri Bollettino");
    expect(html).toContain('aria-label="Chiudi notifica"');
  });
});
