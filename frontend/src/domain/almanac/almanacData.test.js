import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";
import saintProfiles from "../../data/almanac/saintProfiles.json";
import schedule from "../../data/almanac/schedule.json";
import saints from "../../data/almanac/saints.json";
import {
  getDiscoverTemporalRank,
  normalizeDiscoverSeason,
} from "../discover/discoverTemporalSelection";
import {
  buildAnnualProverbCalendar,
  buildAlmanacData,
  getAnnualProverbCalendarAudit,
  getAlmanacSeasonInfo,
  getSaintForDate,
  getWeatherAlmanacTags,
  isProverbTemporallyCompatible,
  pickDailyProverb,
  pickDailyTradition,
  pickEarthTips,
} from "./almanacData";

describe("almanac data archive", () => {
  it("keeps the imported saint calendar complete and readable", () => {
    const dayKeys = Object.keys(saints).filter((key) => key !== "default");

    expect(dayKeys).toHaveLength(366);
    expect(getSaintForDate(new Date("2026-06-24T12:00:00+02:00")).name_it).toBe(
      "Natività di san Giovanni Battista"
    );
    expect(JSON.stringify(saints)).not.toMatch(/Ãƒ|Ã‚/);
  });

  it("keeps curated saint profiles separate, sourced, and bounded", () => {
    expect(Object.keys(saintProfiles)).toHaveLength(366);

    for (const [dayKey, profile] of Object.entries(saintProfiles)) {
      expect(saints[dayKey], `${dayKey} must exist in the saint calendar`).toBeTruthy();
      expect(["curated", "pending_source"]).toContain(profile.description_it_status);
      if (profile.description_it_status === "curated") {
        expect(profile.description_it.length).toBeGreaterThan(0);
        expect(profile.description_it.length).toBeLessThanOrEqual(260);
        expect(profile.profile_review_status).toBe("approved_it");
        expect(profile.description_fur_status).toBe("curated");
        expect(profile.description_fur.length).toBeGreaterThan(0);
      } else {
        expect(profile.description_it).toBe("");
        expect(profile.profile_review_status).toBe("pending_source");
        expect(profile.description_fur_status).toBe("pending_review");
        expect(profile.description_fur).toBe("");
      }
      expect(profile.profile_source).toBe("CEI - Martirologio Romano");
      expect(profile.profile_source_url).toMatch(/^https:\/\/www\.chiesacattolica\.it\//);
    }
  });

  it("merges a verified profile without altering the imported calendar", () => {
    const saint = getSaintForDate(new Date("2026-07-22T12:00:00+02:00"));

    expect(saint.name_it).toBe("Santa Maria Maddalena");
    expect(saint.description_it).toContain("prima a incontrare il Risorto");
    expect(saint.description_fur_status).toBe("curated");
    expect(saint.description_fur.length).toBeGreaterThan(0);
    expect(saints["07-22"]).not.toHaveProperty("description_it");
  });
});

describe("almanac selection", () => {
  it("uses exact calendar traditions when the date has one", () => {
    const selected = pickDailyTradition(new Date("2026-06-24T12:00:00+02:00"));

    expect(selected.id).toBe("ost-0034-san-giovanni-sant-egidio");
    expect(selected.title.it).toBe("Il tempo di San Giovanni");
  });

  it("never uses a tradition outside its date, period, or season", () => {
    for (let month = 0; month < 12; month += 1) {
      const daysInMonth = new Date(2026, month + 1, 0).getDate();

      for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(2026, month, day, 12);
        const selected = pickDailyTradition(date, {
          condition: "Pioggia, neve, gelo e vento",
        });

        expect(selected).toBeTruthy();

        const season = normalizeDiscoverSeason(getAlmanacSeasonInfo(date).id);
        const recordSeasons = selected.seasons.map(normalizeDiscoverSeason);
        const temporalRank = getDiscoverTemporalRank(selected, date);

        if (temporalRank === null || temporalRank >= 3) {
          expect(
            recordSeasons.includes("all") || recordSeasons.includes(season),
            `${date.toISOString().slice(0, 10)} selected ${selected.id} for ${season}`,
          ).toBe(true);
        }

        if (selected.recurrence !== "weather") {
          expect(temporalRank).not.toBeNull();
        }

        if (["date_range", "fixed_date", "movable_date"].includes(selected.recurrence)) {
          expect(temporalRank).toBeLessThan(3);
        }
      }
    }
  });

  it("uses a generic or summer tradition instead of a winter text in July", () => {
    const selected = pickDailyTradition(new Date("2026-07-22T12:00:00+02:00"), {
      condition: "Neve e gelo",
    });

    expect(selected.id).not.toBe("ost-0029-natale-pasqua-fieno");
    expect(selected.seasons.map(normalizeDiscoverSeason)).toEqual(
      expect.arrayContaining([expect.stringMatching(/^(all|estate)$/)]),
    );
  });

  it("keeps verified scheduled proverbs fixed on special dates", () => {
    const selected = pickDailyProverb(new Date("2026-02-03T12:00:00+01:00"));

    expect(selected.id).toBe("ostermann-054-san-blas-fred");
  });

  it("does not surface catalog-only proverbs through the fixed schedule", () => {
    const catalogOnlyIds = new Set([
      "ostermann-candelora",
      "ostermann-marz-vile",
      "ostermann-san-martin",
    ]);

    expect(catalogOnlyIds.has(pickDailyProverb(new Date("2026-02-02T12:00:00+01:00")).id)).toBe(false);
    expect(catalogOnlyIds.has(pickDailyProverb(new Date("2026-03-01T12:00:00+01:00")).id)).toBe(false);
    expect(catalogOnlyIds.has(pickDailyProverb(new Date("2026-11-11T12:00:00+01:00")).id)).toBe(false);
  });

  it("shows San Biagio only on 3 February, never through the generic rotation", () => {
    const sanBiagioId = "ostermann-054-san-blas-fred";
    const julySelection = pickDailyProverb(new Date("2026-07-22T12:00:00+02:00"));

    expect(pickDailyProverb(new Date("2026-02-03T12:00:00+01:00")).id).toBe(sanBiagioId);
    expect(julySelection.id).not.toBe(sanBiagioId);
  });

  it("keeps exact-date proverbs out of every other calendar day", () => {
    const fixedDatesById = new Map(
      Object.entries(schedule.dailyProverbs)
        .filter(([dayKey]) => dayKey !== "default")
        .map(([dayKey, proverbId]) => [proverbId, dayKey]),
    );

    for (let month = 0; month < 12; month += 1) {
      const daysInMonth = new Date(2026, month + 1, 0).getDate();

      for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(2026, month, day, 12);
        const selected = pickDailyProverb(date);
        const scheduledDay = fixedDatesById.get(selected.id);
        const selectedRecord = proverbs.find((proverb) => proverb.id === selected.id);
        const isReusableTarget = [
          "almanac_lunar_cycle",
          "almanac_monthly",
          "almanac_seasonal",
          "almanac_weather_sign",
        ].includes(selectedRecord?.almanacTargetUse);

        if (scheduledDay && !isReusableTarget) {
          const currentDay = `${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          expect(currentDay).toBe(scheduledDay);
        }
      }
    }
  });

  it("uses newly promoted fixed-date Ostermann proverbs on their calendar days", () => {
    expect(pickDailyProverb(new Date("2026-01-10T12:00:00+01:00")).id).toBe(
      "ostermann-058-san-pauli-scur"
    );
    expect(pickDailyProverb(new Date("2026-01-17T12:00:00+01:00")).id).toBe(
      "ostermann-054-sant-antoni-fred"
    );
    expect(pickDailyProverb(new Date("2026-01-06T12:00:00+01:00")).id).toBe(
      "ostermann-054-epifanie-fred"
    );
    expect(pickDailyProverb(new Date("2026-02-24T12:00:00+01:00")).id).toBe(
      "ostermann-054-san-matie-glace"
    );
    expect(pickDailyProverb(new Date("2026-04-25T12:00:00+02:00")).id).toBe(
      "ostermann-141-arch-san-march-doman"
    );
    expect(pickDailyProverb(new Date("2026-06-21T12:00:00+02:00")).id).toBe(
      "ostermann-057-san-luigi-zornade-lunge"
    );
    expect(pickDailyProverb(new Date("2026-06-24T12:00:00+02:00")).id).toBe(
      "ostermann-063-san-zuan-timp"
    );
    expect(pickDailyProverb(new Date("2026-08-15T12:00:00+02:00")).id).toBe(
      "ostermann-192-assunte-vin"
    );
    expect(pickDailyProverb(new Date("2026-09-09T12:00:00+02:00")).id).toBe(
      "ostermann-061-san-gorgon-ploe"
    );
    expect(pickDailyProverb(new Date("2026-10-28T12:00:00+01:00")).id).toBe(
      "ostermann-061-san-simon-unviar"
    );
    expect(pickDailyProverb(new Date("2026-11-02T12:00:00+01:00")).id).toBe(
      "ostermann-103-muarz-novembre"
    );
    expect(pickDailyProverb(new Date("2026-12-13T12:00:00+01:00")).id).toBe(
      "ostermann-087-sante-luzie-nadal"
    );
    expect(pickDailyProverb(new Date("2026-12-21T12:00:00+01:00")).id).toBe(
      "ostermann-057-san-tomas-zornade-curte"
    );
    expect(pickDailyProverb(new Date("2026-12-25T12:00:00+01:00")).id).toBe(
      "ostermann-057-nadal-pascute-orute"
    );
  });

  it("assigns every proverb once and only inside its declared temporal rule", () => {
    const calendar = buildAnnualProverbCalendar(2026);
    const selectedIds = [...calendar.values()].map((item) => item.id);

    expect(calendar.size).toBe(365);
    expect(new Set(selectedIds).size).toBe(365);

    calendar.forEach((item, dayKey) => {
      const date = new Date(`2026-${dayKey}T12:00:00`);
      expect(isProverbTemporallyCompatible(item, date), `${item.id} on ${dayKey}`).toBe(true);
    });

    const sampleDate = new Date("2026-07-04T12:00:00+02:00");
    expect(pickDailyProverb(sampleDate, { condition: "Temporale con grandine" }).id).toBe(
      pickDailyProverb(sampleDate, { condition: "Sereno" }).id,
    );
  });

  it("keeps movable feasts on their real day and range proverbs on one compatible day", () => {
    expect(pickDailyProverb(new Date("2026-04-05T12:00:00+02:00")).id).toBe(
      "ost1876-pasche-cun-foe",
    );
    expect(pickDailyProverb(new Date("2027-03-28T12:00:00+02:00")).id).toBe(
      "ost1876-pasche-cun-foe",
    );

    const calendar = buildAnnualProverbCalendar(2026);
    const adventAssignments = [...calendar.entries()].filter(
      ([, item]) => item.id === "ost1876-nef-prime-nadal-regal",
    );

    expect(adventAssignments).toHaveLength(1);
    expect(adventAssignments[0][0] >= "12-01" && adventAssignments[0][0] <= "12-24").toBe(true);
  });

  it("applies the final targeted Ostermann records once inside their declared periods", () => {
    const canicolaId = "ostermann-029-canicule-bagnat-sut";
    const mesaisId = "ostermann-062-sis-dis-an-mesais";

    expect(pickDailyProverb(new Date("2026-04-03T12:00:00+02:00")).id).toBe(
      "ostermann-059-vinars-sant-ploe",
    );
    expect(pickDailyProverb(new Date("2026-05-14T12:00:00+02:00")).id).toBe(
      "ostermann-059-ascense-ploe"
    );

    expect(pickDailyProverb(new Date("2026-03-27T12:00:00+01:00")).id).toBe(
      "ostermann-062-san-ruperto-lui"
    );
    expect(pickDailyProverb(new Date("2026-09-01T12:00:00+02:00")).id).toBe(
      "ostermann-063-sant-egidi-color-mes"
    );

    const calendars = [2026, 2027].map((year) => buildAnnualProverbCalendar(year));
    calendars.forEach((calendar) => {
      const canicolaDays = [...calendar.entries()]
        .filter(([, item]) => item.id === canicolaId)
        .map(([dayKey]) => dayKey);
      const mesaisDays = [...calendar.entries()]
        .filter(([, item]) => item.id === mesaisId)
        .map(([dayKey]) => dayKey);

      expect(canicolaDays).toHaveLength(1);
      expect(canicolaDays[0] >= "07-21" && canicolaDays[0] <= "08-23").toBe(true);
      expect(mesaisDays).toHaveLength(1);
      expect(mesaisDays[0] >= "01-01" || mesaisDays[0] >= "12-26").toBe(true);
      expect(mesaisDays[0] <= "01-06" || mesaisDays[0] >= "12-26").toBe(true);
    });
  });

  it("keeps the new monthly and seasonal records in their period pools", () => {
    expect(
      proverbs.find((proverb) => proverb.id === "ostermann-190-marz-avril-mai")
    ).toMatchObject({
      almanacTargetUse: "almanac_monthly",
      months: ["03", "04", "05"],
    });
    expect(
      proverbs.find((proverb) => proverb.id === "ostermann-063-otubar-febrar")
    ).toMatchObject({
      almanacTargetUse: "almanac_monthly",
      months: ["10"],
    });
    expect(
      proverbs.find((proverb) => proverb.id === "ostermann-132-prime-nev-plan")
    ).toMatchObject({
      almanacTargetUse: "almanac_seasonal",
      seasons: ["winter"],
    });
    expect(
      proverbs.find((proverb) => proverb.id === "ost1876-un-fior-no-fas-primevere")
    ).toMatchObject({
      almanacTargetUse: "almanac_seasonal",
      seasons: ["spring"],
    });
  });

  it("never selects a reviewed Ostermann proverb outside its declared calendar rule", () => {
    const reviewedIds = new Set(
      proverbs
        .filter(
          (record) =>
            record.editorialReview?.reviewedAt === "2026-07-22" ||
            record.id === "ost1876-un-fior-no-fas-primevere",
        )
        .map((record) => record.id),
    );

    for (let month = 0; month < 12; month += 1) {
      const daysInMonth = new Date(2026, month + 1, 0).getDate();

      for (let day = 1; day <= daysInMonth; day += 1) {
        const date = new Date(2026, month, day, 12);
        const selected = pickDailyProverb(date);
        if (!reviewedIds.has(selected.id) || !selected.almanacTargetUse) continue;

        const dayKey = `${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        if (selected.almanacTargetUse === "almanac_dated") {
          expect(selected.dateAnchors, `${selected.id} on ${dayKey}`).toContain(dayKey);
        }
        if (selected.almanacTargetUse === "almanac_monthly") {
          expect(selected.months, `${selected.id} on ${dayKey}`).toContain(dayKey.slice(0, 2));
        }
        if (selected.almanacTargetUse === "almanac_seasonal") {
          expect(selected.seasons, `${selected.id} on ${dayKey}`).toContain(
            getAlmanacSeasonInfo(date).id,
          );
        }
        if (selected.almanacTargetUse === "almanac_date_range") {
          expect(dayKey >= "12-01" && dayKey <= "12-24", `${selected.id} on ${dayKey}`).toBe(true);
        }
        if (selected.almanacTargetUse === "almanac_movable_feast") {
          expect(dayKey, selected.id).toBe("04-05");
        }
      }
    }
  });

  it("keeps a reviewed secondary proverb out of generic rotation when its date is already occupied", () => {
    expect(pickDailyProverb(new Date("2026-01-17T12:00:00+01:00")).id).toBe(
      "ostermann-054-sant-antoni-fred"
    );
    expect(pickDailyProverb(new Date("2026-07-22T12:00:00+02:00")).id).not.toBe(
      "ost1876-sant-antoni-ore-lus"
    );
  });

  it("keeps newly promoted monthly Ostermann proverbs in the monthly rotation pool", () => {
    const promotedMonthlyIds = [
      "ostermann-062-zenar-ploe-avril",
      "ostermann-062-febrar-curt-amar",
      "ostermann-062-febrar-senze-criure",
    ];

    promotedMonthlyIds.forEach((id) => {
      const record = proverbs.find((proverb) => proverb.id === id);

      expect(record).toMatchObject({
        almanacEligible: true,
        humanReviewRequired: true,
        normalizationStatus: "lab_ready",
        almanacTargetUse: "almanac_monthly",
      });
      expect(record?.months?.length).toBeGreaterThan(0);
    });
  });

  it("keeps legacy lunar and monthly records explicit and the draft lunar text archived", () => {
    expect(proverbs.find((item) => item.id === "ostermann-lune-cresse")).toMatchObject({
      almanacEligible: false,
      almanacArchiveUse: "source_review",
    });
    expect(proverbs.find((item) => item.id === "ostermann-105-lune-cercli")).toMatchObject({
      almanacTargetUse: "almanac_lunar_cycle",
      lunarRule: { type: "any_lunar_day" },
    });
    expect(proverbs.find((item) => item.id === "ostermann-190-avril-plojos")).toMatchObject({
      almanacTargetUse: "almanac_monthly",
      months: ["04"],
    });
  });

  it("keeps the annual calendar unique and temporally valid through 2100", () => {
    for (let year = 2024; year <= 2100; year += 1) {
      const audit = getAnnualProverbCalendarAudit(year);

      expect(audit.assignedDays, `${year} assigned`).toBe(audit.daysInYear);
      expect(audit.uniqueProverbs, `${year} unique`).toBe(audit.daysInYear);
      expect(audit.duplicateIds, `${year} duplicates`).toEqual([]);
      expect(audit.missingDayKeys, `${year} missing`).toEqual([]);
      expect(audit.incompatibleAssignments, `${year} temporal`).toEqual([]);
    }
  }, 20_000);

  it("uses weather only as a practical signal for earth tips", () => {
    expect(getWeatherAlmanacTags({ condition: "Sereno", temperature: 31 })).toEqual(
      expect.arrayContaining(["caldo", "irrigazione", "orto"])
    );
    expect(getWeatherAlmanacTags({ condition: "Nebbia e nubi con garbino" })).toEqual(
      expect.arrayContaining(["nebbia", "nubi", "garbino"])
    );

    const tips = pickEarthTips(new Date("2026-06-24T12:00:00+02:00"), {
      condition: "Sereno",
      temperature: 31,
    });

    expect(tips[0].tags).toEqual(expect.arrayContaining(["irrigazione"]));
  });

  it("builds the domain contract without relying on UI fixtures", () => {
    const model = buildAlmanacData({
      date: new Date("2026-06-24T12:00:00+02:00"),
      now: new Date("2026-06-24T12:00:00+02:00"),
    });

    expect(model.dayOfYear).toBe(175);
    expect(model.season).toMatchObject({ id: "summer", day: 4 });
    expect(model.saint.name_it).toBe("Natività di san Giovanni Battista");
    expect(model.tradition.id).toBe("ost-0034-san-giovanni-sant-egidio");
    expect(model.moon.id).toBe("first_quarter");
    expect(model.sun.maxAltitudeDegrees).toBe(67);
    expect(model.tips).toHaveLength(1);
  });

  it("accepts the lat/lon coordinate contract used by the app", () => {
    const date = new Date("2026-06-24T12:00:00+02:00");
    const now = new Date("2026-06-24T12:00:00+02:00");
    const appCoordinates = buildAlmanacData({
      date,
      now,
      location: { lat: 45.9567, lon: 12.6605 },
    });
    const domainCoordinates = buildAlmanacData({
      date,
      now,
      location: { latitude: 45.9567, longitude: 12.6605 },
    });

    expect(appCoordinates.sun).toEqual(domainCoordinates.sun);
  });
});
