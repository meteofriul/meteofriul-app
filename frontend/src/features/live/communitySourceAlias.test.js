import { describe, expect, it } from "vitest";

import {
  COMMUNITY_SOURCE_ALIASES,
  formatCommunitySourceLabel,
  getCommunitySourceAlias,
  getCommunitySourceAliasPreview,
} from "./communitySourceAlias";

const copy = {
  reportAnonymousSource: "Fonte anonima · {alias}",
  reportAnonymousSources: "Fonti anonime · {count}",
};

describe("community source aliases", () => {
  it("derives a stable friendly alias without exposing the opaque key", () => {
    const sourceKey = "opaque-source-key-42";
    const first = getCommunitySourceAlias(sourceKey);

    const parts = first.split(" · ");
    expect(parts).toHaveLength(2);
    expect(COMMUNITY_SOURCE_ALIASES).toContain(parts[0]);
    expect(COMMUNITY_SOURCE_ALIASES).toContain(parts[1]);
    expect(parts[0]).not.toBe(parts[1]);
    expect(getCommunitySourceAlias(sourceKey)).toBe(first);
    expect(formatCommunitySourceLabel([sourceKey], copy)).toBe(`Fonte anonima · ${first}`);
    expect(formatCommunitySourceLabel([sourceKey], copy)).not.toContain(sourceKey);
  });

  it("can distinguish different anonymous sources", () => {
    const sourceKeys = Array.from({ length: 800 }, (_, index) => `opaque-source-${index}`);
    const aliases = new Set(sourceKeys.map(getCommunitySourceAlias));

    expect(aliases.size).toBeGreaterThanOrEqual(400);
    aliases.forEach((alias) => {
      expect(sourceKeys).not.toContain(alias);
    });
  });

  it("falls back safely and shows only a count for multiple sources", () => {
    expect(getCommunitySourceAlias(" ")).toBe("");
    expect(formatCommunitySourceLabel([], copy)).toBe("");
    expect(formatCommunitySourceLabel(["source-a", "source-b"], copy)).toBe(
      "Fonti anonime · 2",
    );
    expect(formatCommunitySourceLabel(["source-a", "source-b"], copy)).not.toContain("source-");
  });

  it("previews at most three distinct source aliases and summarizes the remainder", () => {
    const sourceKeys = ["source-a", "source-b", "source-c", "source-d", "source-b"];
    const preview = getCommunitySourceAliasPreview(sourceKeys);

    expect(preview).toEqual({
      aliases: sourceKeys.slice(0, 3).map(getCommunitySourceAlias),
      hiddenCount: 1,
      totalCount: 4,
    });
    expect(preview.aliases.join(" ")).not.toContain("source-");

    const collisionPreview = getCommunitySourceAliasPreview([
      "opaque-source-16",
      "opaque-source-54",
    ]);
    expect(collisionPreview).toEqual({
      aliases: ["Cjapiel · Cjicare"],
      hiddenCount: 0,
      totalCount: 1,
    });
  });
});
