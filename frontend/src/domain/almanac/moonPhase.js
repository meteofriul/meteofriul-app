const SYNODIC_MONTH_DAYS = 29.530588853;
const REFERENCE_NEW_MOON_UTC = Date.UTC(2000, 0, 6, 18, 14);
const DAY_MS = 24 * 60 * 60 * 1000;

const PHASES = [
  {
    id: "new",
    it: "Luna nuova",
    fur: "Lune gnove",
    start: 0,
    end: 1.84566,
  },
  {
    id: "waxing_crescent",
    it: "Luna crescente",
    fur: "Lune cressint",
    start: 1.84566,
    end: 5.53699,
  },
  {
    id: "first_quarter",
    it: "Primo quarto",
    fur: "Prin cuart",
    start: 5.53699,
    end: 9.22831,
  },
  {
    id: "waxing_gibbous",
    it: "Gibbosa crescente",
    fur: "Lune cressint plene",
    start: 9.22831,
    end: 12.91963,
  },
  {
    id: "full",
    it: "Luna piena",
    fur: "Lune plene",
    start: 12.91963,
    end: 16.61096,
  },
  {
    id: "waning_gibbous",
    it: "Gibbosa calante",
    fur: "Lune calant plene",
    start: 16.61096,
    end: 20.30228,
  },
  {
    id: "last_quarter",
    it: "Ultimo quarto",
    fur: "Ultin cuart",
    start: 20.30228,
    end: 23.9936,
  },
  {
    id: "waning_crescent",
    it: "Luna calante",
    fur: "Lune calant",
    start: 23.9936,
    end: 27.68493,
  },
  {
    id: "new",
    it: "Luna nuova",
    fur: "Lune gnove",
    start: 27.68493,
    end: SYNODIC_MONTH_DAYS,
  },
];

function normalizeMoonAge(daysSinceReference) {
  const age = daysSinceReference % SYNODIC_MONTH_DAYS;
  return age < 0 ? age + SYNODIC_MONTH_DAYS : age;
}

export function getMoonIllumination(cyclePercent) {
  return Math.round((1 - Math.cos(2 * Math.PI * cyclePercent)) * 50);
}

export function getMoonPhase(date = new Date()) {
  const value = date instanceof Date ? date.getTime() : new Date(date).getTime();
  const daysSinceReference = (value - REFERENCE_NEW_MOON_UTC) / DAY_MS;
  const age = normalizeMoonAge(daysSinceReference);
  const phase = PHASES.find((item) => age >= item.start && age < item.end) || PHASES[0];
  const cyclePercent = age / SYNODIC_MONTH_DAYS;

  return {
    age,
    cyclePercent,
    id: phase.id,
    illuminationPercent: getMoonIllumination(cyclePercent),
    label: {
      it: phase.it,
      fur: phase.fur,
    },
  };
}
