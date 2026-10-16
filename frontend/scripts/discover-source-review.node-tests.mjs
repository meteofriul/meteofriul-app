import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (name) => JSON.parse(readFileSync(new URL(`../src/data/discover/${name}.json`, import.meta.url), "utf8"));
const review = read("municipalitySourceReview.ud-quality-10");
const catalog = read("municipalityProfiles");

test("source review retains the catalog checkpoint and does not claim promotion", () => {
  assert.equal(review.runtimeIntegration, false);
  assert.equal(catalog.profiles.length, review.baseline.profiles);
  assert.equal(catalog.profiles.reduce((sum, p) => sum + p.milestones.length, 0), review.baseline.milestones);
  assert.equal(catalog.profiles.filter(p => p.milestones.length < 3).length, review.baseline.profilesBelowThreeMilestones);
});

test("verified sources refer to existing facts without changing IT/FUR", () => {
  for (const item of review.reviews) {
    const profile = catalog.profiles.find(p => p.istatCode === item.istatCode);
    const fact = profile.milestones.find(m => m.id === item.recordId);
    assert.equal(fact.year, item.year);
    assert.equal(item.copyChange, false);
    assert.equal(item.method, "full_public_html_read");
    assert.match(item.source.url, /^https:\/\/(www\.)?(regione\.fvg\.it|vigilfuoco\.it)\//);
    assert.ok(fact.label.it && fact.label.fur);
  }
});

test("unverified candidate cannot be mistaken for a published bilingual fact", () => {
  for (const candidate of review.candidates) {
    assert.equal(candidate.readyForUi, false);
    assert.equal(candidate.label.fur, null);
    assert.ok(!catalog.profiles.some(p => p.milestones.some(m => m.id === candidate.recordId)));
  }
});
