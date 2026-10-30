import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from '../../../../frontend/node_modules/vitest/dist/index.js';
import { validateMarketsCatalogue, createMarketsCatalogueStore } from '../../../../frontend/src/services/marketsCatalogue.js';
import { mergeMarketEvents, selectMarkets } from '../../../../frontend/src/features/markets/marketsCatalog.js';
const fixtures = JSON.parse(fs.readFileSync(path.join(process.env.MF_MARKETS_QA_DIR, 'public-fixtures.json'), 'utf8'));

describe('Real Python publication consumed by JavaScript app', () => {
  it('accepts all real publication snapshots and excludes editorial practice data', () => {
    for (const name of ['initial', 'prepared', 'moved', 'final']) {
      expect(validateMarketsCatalogue(fixtures[name])).toBe(fixtures[name]);
      expect(fixtures[name].markets).toHaveLength(53);
      expect(fixtures[name]).not.toHaveProperty('drafts');
      expect(fixtures[name].markets.every(item => !('auditNote' in item))).toBe(true);
    }
  });
  it('updates the real moved edition exactly once and uses the edition venue', () => {
    const market = fixtures.moved.markets.find(item => item.id === fixtures.chosenMarketId);
    const date = fixtures.moved.dates.find(item => item.id === fixtures.chosenEditionId);
    const old = fixtures.initial.dates.find(item => item.id === fixtures.chosenEditionId);
    const location = { city: market.comune, region: 'Friuli-Venezia Giulia', countryCode: 'IT' };
    const now = new Date('2026-12-25T12:00:00Z');
    const events = mergeMarketEvents([{ id: `market:${market.id}:${old.date}`, market_id: market.id, title: market.name, event_city: market.comune, start_date: old.date, end_date: old.date, place: 'Old venue', url: old.source }], { location, catalogue: fixtures.moved, now });
    const revised = events.filter(item => item.market_edition_id === date.id);
    expect(revised).toHaveLength(1);
    expect(revised[0].start_date).toBe('2026-12-30');
    expect(revised[0].place).toBe('Piazza di verifica');
    expect(revised[0].maps_url).toContain('Piazza%20di%20verifica');
    const cards = selectMarkets({ location, catalogue: fixtures.moved, now }).items;
    expect(cards.find(item => item.id === market.id).dates.find(item => item.id === date.id).venue.place).toBe(revised[0].place);
  });
  it('persists the final real snapshot and rejects a stale earlier publication', async () => {
    const values = new Map();
    const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
    let current = fixtures.final;
    const options = { storage, apiBase: 'http://example.invalid/api', now: () => Date.parse('2026-11-01T10:00:00Z'), fetchImpl: async () => ({ ok: true, json: async () => current }) };
    const first = createMarketsCatalogueStore(options);
    await first.refresh();
    const restarted = createMarketsCatalogueStore(options);
    expect(restarted.getSnapshot().catalogue.revision).toBe(fixtures.final.revision);
    current = fixtures.initial;
    await restarted.refresh();
    expect(restarted.getSnapshot().catalogue.revision).toBe(fixtures.final.revision);
  });
  it('shows the newly created and approved panel market in its municipality', () => {
    expect(validateMarketsCatalogue(fixtures.added).markets).toHaveLength(54);
    const items = selectMarkets({ location: { city: 'Pordenone', region: 'Friuli-Venezia Giulia', countryCode: 'IT' }, catalogue: fixtures.added, now: new Date('2026-11-07T12:00:00Z'), period: 'today' }).items;
    expect(items.find(item => item.id === 'QA-new-market')).toMatchObject({ name: 'Mercato di verifica nuovo', comune: 'Pordenone', quality: 'Documentato', weekdays: [6] });
  });
});
