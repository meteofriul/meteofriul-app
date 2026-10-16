import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";
import {
  getProverbPromotionPlan,
  PROVERB_PROMOTION_TARGETS,
} from "./proverbPromotionPlan";

describe("proverb promotion plan", () => {
  it("separates already published lab proverbs from pending promotion candidates", () => {
    const plan = getProverbPromotionPlan();

    expect(plan.totalReviewed).toBe(122);
    expect(plan.promotionCandidateCount).toBe(66);
    expect(plan.alreadyPublishedCount).toBe(66);
    expect(plan.pendingPromotionCount).toBe(0);
    expect(plan.byTargetUse[PROVERB_PROMOTION_TARGETS.PUBLISHED_PROVERB]).toBe(13);
    expect(plan.alreadyPublishedByTargetUse[PROVERB_PROMOTION_TARGETS.DATED]).toBe(22);
    expect(plan.alreadyPublishedByTargetUse[PROVERB_PROMOTION_TARGETS.MONTHLY]).toBe(12);
    expect(plan.alreadyPublishedByTargetUse[PROVERB_PROMOTION_TARGETS.SEASONAL]).toBe(4);
    expect(plan.alreadyPublishedByTargetUse[PROVERB_PROMOTION_TARGETS.WEATHER_SIGN]).toBe(13);
    expect(plan.alreadyPublishedByTargetUse[PROVERB_PROMOTION_TARGETS.LUNAR_CYCLE]).toBe(2);
  });

  it("tracks the pending promotion matrix after the final candidate review", () => {
    const plan = getProverbPromotionPlan();

    expect(plan.pendingByTargetUse).toMatchObject({
      [PROVERB_PROMOTION_TARGETS.DATED]: 0,
      [PROVERB_PROMOTION_TARGETS.MONTHLY]: 0,
      [PROVERB_PROMOTION_TARGETS.SEASONAL]: 0,
      [PROVERB_PROMOTION_TARGETS.WEATHER_SIGN]: 0,
      [PROVERB_PROMOTION_TARGETS.LUNAR_CYCLE]: 0,
    });
    expect(plan.fixedDateCandidateCount).toBe(22);
    expect(plan.pendingFixedDateCandidateCount).toBe(0);
    expect(plan.pendingFixedDateCandidates.map((candidate) => candidate.id)).toEqual([]);
    expect(plan.monthlyCandidates.map((candidate) => candidate.id)).toEqual([]);
    expect(plan.seasonalCandidates.map((candidate) => candidate.id)).toEqual([]);
    expect(plan.weatherSignCandidates.map((candidate) => candidate.id)).toEqual([]);
    expect(plan.lunarCycleCandidates.map((candidate) => candidate.id)).toEqual([]);
  });

  it("allows only fixed-date candidates to become daily schedule slots", () => {
    const plan = getProverbPromotionPlan();
    const fixedDateIds = plan.fixedDateCandidates.map((candidate) => candidate.id);

    expect(fixedDateIds).toEqual(
      expect.arrayContaining([
        "ostermann-054-epifanie-fred",
        "ostermann-054-san-blas-fred",
        "ostermann-054-san-valantin-fin-inviar",
        "ostermann-060-sant-ane-furmiar",
        "ostermann-060-san-lurinz-seren",
        "ostermann-060-san-bortolomio-bon-timp",
        "ostermann-061-san-maurizi-seren",
        "ostermann-061-san-simon-unviar",
        "ostermann-192-san-barnaba-vin",
        "ostermann-192-assunte-vin",
        "ostermann-054-sant-antoni-fred",
        "ostermann-054-san-matie-glace",
        "ostermann-097-san-grivor-vint",
        "ostermann-141-arch-san-march-doman",
        "ostermann-058-san-pauli-scur",
        "ostermann-087-sante-luzie-nadal",
        "ostermann-057-nadal-pascute-orute",
        "ostermann-057-san-tomas-zornade-curte",
        "ostermann-057-san-luigi-zornade-lunge",
        "ostermann-063-san-zuan-timp",
        "ostermann-061-san-gorgon-ploe",
        "ostermann-103-muarz-novembre",
      ]),
    );
    expect(plan.fixedDateScheduleSlots).toHaveLength(22);
    expect(plan.fixedDateScheduleSlots.map((slot) => slot.dateAnchor)).toEqual(
      expect.arrayContaining([
        "01-06",
        "01-10",
        "01-17",
        "02-03",
        "02-14",
        "02-24",
        "03-26",
        "04-25",
        "06-21",
        "06-24",
        "06-11",
        "07-26",
        "08-10",
        "08-15",
        "08-24",
        "09-09",
        "09-22",
        "10-28",
        "11-02",
        "12-13",
        "12-21",
        "12-25",
      ]),
    );
    expect(plan.pendingPromotionCount).toBe(0);
  });

  it("keeps publication manual until final FUR review and controlled schedule update", () => {
    const plan = getProverbPromotionPlan();

    expect(plan.guardrails.readyForAutomaticPublication).toBe(false);
    expect(plan.guardrails.manualStepRequired).toBe(
      "final_fur_review_then_controlled_proverbs_and_schedule_update",
    );
    expect(plan.guardrails.fixedDateCandidatesWithoutDate).toEqual([]);
    expect(plan.guardrails.nonFixedDateCandidatesWithDate).toEqual([]);
    expect(plan.guardrails.missingTargetCandidates).toEqual([]);
    expect(plan.guardrails.unknownTargetCandidates).toEqual([]);
    expect(plan.duplicateDateAnchors).toEqual([]);
  });

  it("confirms all promoted review candidates are already present in proverbs.json", () => {
    const plan = getProverbPromotionPlan();
    const publishedProverbIds = new Set(proverbs.map((proverb) => proverb.id));
    const missingPublishedCandidates = plan.alreadyPublishedCandidates.filter(
      (candidate) => !publishedProverbIds.has(candidate.id),
    );

    expect(missingPublishedCandidates).toEqual([]);
  });
});
