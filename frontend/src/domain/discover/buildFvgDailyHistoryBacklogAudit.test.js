import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { execPath } from "node:process";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SCRIPT_PATH = fileURLToPath(new URL(
  "../../../../scripts/build-fvg-daily-history-backlog-audit.mjs",
  import.meta.url,
));

function writeJson(filePath, value) {
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function candidate(id, dayKey, type = "Nascita") {
  return {
    sourceCandidateId: `master-fvg-${dayKey}-Q${id}`,
    wikidataId: `Q${id}`,
    sourceDayKey: dayKey,
    dateAnchor: dayKey.split("-").reverse().join("-"),
    sourceTitle: `Candidate Q${id}`,
    year: 1900 + Number(id),
    place: "Trieste",
    type,
    category: "arte_cultura",
    score: 60,
    editorialClass: "B",
    publicationTriage: "review_for_light_daily",
  };
}

describe("build FVG daily history backlog audit", () => {
  it("does not requeue candidates already held or excluded in Italian review waves", () => {
    const directory = mkdtempSync(join(tmpdir(), "mf-discover-backlog-"));

    try {
      const sourcePath = join(directory, "source.json");
      const localMemoryPath = join(directory, "localMemory.json");
      const reviewPackPath = join(directory, "reviewPack.json");
      const expandedReviewPath = join(directory, "expandedReview.json");
      const reviewWaveDir = join(directory, "waves");
      const outputPath = join(directory, "audit.json");

      writeJson(sourcePath, {
        days: [
          { dayKey: "01-01", dateAnchor: "01-01", candidates: [candidate(100, "01-01")] },
          { dayKey: "02-01", dateAnchor: "01-02", candidates: [candidate(200, "02-01")] },
          { dayKey: "03-01", dateAnchor: "01-03", candidates: [candidate(300, "03-01")] },
          { dayKey: "04-01", dateAnchor: "01-04", candidates: [candidate(400, "04-01", "Morte")] },
        ],
      });
      writeJson(localMemoryPath, { records: [] });
      writeJson(reviewPackPath, { records: [] });
      writeJson(expandedReviewPath, { records: [] });
      writeJson(join(reviewWaveDir, "discoverDailyItalianReviewWave24.json"), {
        hold: [{ id: "master-fvg-01-01-Q100", reason: "already held" }],
      });
      writeJson(join(reviewWaveDir, "discoverDailyItalianReviewWave25.json"), {
        excluded: [{ id: "master-fvg-02-01-Q200", reason: "already excluded" }],
      });

      const result = spawnSync(execPath, [
        SCRIPT_PATH,
        "--source", sourcePath,
        "--local-memory", localMemoryPath,
        "--review-pack", reviewPackPath,
        "--expanded-review", expandedReviewPath,
        "--review-wave-dir", reviewWaveDir,
        "--output", outputPath,
        "--next-limit", "10",
      ], {
        encoding: "utf8",
      });

      expect(result.status, result.stderr).toBe(0);

      const audit = JSON.parse(readFileSync(outputPath, "utf8"));
      const queuedIds = [
        ...audit.nextReviewCandidates,
        ...audit.nextLightReviewCandidates,
      ].map((record) => record.wikidataId);

      expect(new Set(queuedIds)).toEqual(new Set(["Q300"]));
      expect(audit.days.find((day) => day.dayKey === "01-01").unqueuedEligibleCandidates).toBe(0);
      expect(audit.days.find((day) => day.dayKey === "02-01").unqueuedEligibleCandidates).toBe(0);
      expect(audit.days.find((day) => day.dayKey === "03-01").unqueuedEligibleCandidates).toBe(1);
      expect(audit.days.find((day) => day.dayKey === "04-01").eligibleCandidates).toBe(0);
      expect(audit.policy.excludesDeaths).toBe(true);
      expect(audit.summary.byEligibleType.Morte).toBeUndefined();
      expect(audit.sourceInput.excludedItalianReviewWaves).toEqual([
        "discoverDailyItalianReviewWave24.json",
        "discoverDailyItalianReviewWave25.json",
      ]);
      expect(audit.summary.knownOrQueuedWikidataIds).toBe(2);
      expect(audit.summary.knownOrQueuedSourceCandidateIds).toBe(2);
      expect(audit.summary.readyPrimaryDays).toBe(0);
      expect(audit.summary.missingPrimaryDays).toBe(366);
      expect(audit.summary.missingPrimaryDaysWithUnqueuedCandidates).toBe(1);
      expect(audit.nextPrimaryGapCandidates.map((record) => record.wikidataId)).toEqual(["Q300"]);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
