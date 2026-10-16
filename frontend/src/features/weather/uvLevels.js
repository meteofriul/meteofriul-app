// WHO reporting categories use the nearest whole UV index.
// https://www.who.int/publications/i/item/9241590076
export const UV_LEVELS = [
  { max: 2, range: '0–2', it: 'Basso', fur: 'Bas', color: '#52a447', tone: 'low' },
  { max: 5, range: '3–5', it: 'Moderato', fur: 'Moderât', color: '#e9c62e', tone: 'moderate' },
  { max: 7, range: '6–7', it: 'Alto', fur: 'Alt', color: '#ef8b30', tone: 'high' },
  { max: 10, range: '8–10', it: 'Molto alto', fur: 'Une vore alt', color: '#d74747', tone: 'very-high' },
  { max: Infinity, range: '11+', it: 'Estremo', fur: 'Estrem', color: '#9851b6', tone: 'extreme' },
];

export function uvLevel(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? UV_LEVELS.find(level => Math.round(value) <= level.max) : null;
}
