import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CommunityAvatar } from "./CommunityAvatar";
import {
  buildCommunityIdentity,
  buildPublicCommunityIdentitySnapshot,
} from "./communityIdentity";

describe("CommunityAvatar", () => {
  it("renders an accessible deterministic vector avatar", () => {
    const identity = buildCommunityIdentity({
      placeName: "Pordenon",
      revision: 2,
      subjectId: "acuile",
    });
    const html = renderToStaticMarkup(
      <CommunityAvatar identity={identity} label="Profilo di Acuile" size={52} />,
    );

    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Profilo di Acuile"');
    expect(html).toContain('data-subject="acuile"');
    expect(html).toContain(`data-palette="${identity.avatar.paletteId}"`);
    expect(html).toContain('height:52px;width:52px');
    expect(html).toContain("<svg");
    expect(html).toContain("mf-community-avatar__glyph");
  });

  it("accepts a public snapshot and can be decorative beside visible alias text", () => {
    const snapshot = buildPublicCommunityIdentitySnapshot(buildCommunityIdentity({
      placeName: "Udin",
      subjectId: "claf",
    }));
    const html = renderToStaticMarkup(
      <CommunityAvatar decorative snapshot={snapshot} size="2rem" />,
    );

    expect(html).toContain('aria-hidden="true"');
    expect(html).not.toContain('role="img"');
    expect(html).toContain('data-subject="claf"');
    expect(html).toContain('height:2rem;width:2rem');
  });

  it("can enlarge only the glyph while preserving the avatar circle size", () => {
    const html = renderToStaticMarkup(
      <CommunityAvatar glyphScale={1.18} size={34} />,
    );

    expect(html).toContain("height:34px;width:34px");
    expect(html).toContain('class="mf-community-avatar__background" cx="24" cy="24" r="22"');
    expect(html).toContain("scale(1.18)");
  });

  it("falls back to a valid anonymous avatar for missing input", () => {
    const html = renderToStaticMarkup(<CommunityAvatar />);

    expect(html).toContain('data-subject="claf"');
    expect(html).toContain("Avatar community anonimo: Clâf ");
  });
});
