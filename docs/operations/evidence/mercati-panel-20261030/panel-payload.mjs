import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const root = fileURLToPath(new URL('../../../../', import.meta.url));
const panelRoot = process.argv[2] || path.join(root, '..', 'PANNELLO INSERZIONI');
const { newMarket, preparePractice, replaceMarketInState } = await import(pathToFileURL(path.join(panelRoot, 'src/marketsEditor.js')));
const outputDir = process.env.MF_MARKETS_QA_DIR;
if (!outputDir) throw new Error('MF_MARKETS_QA_DIR must identify a temporary test directory');
fs.mkdirSync(outputDir, { recursive: true });
const seed = JSON.parse(fs.readFileSync(path.join(root, 'backend/app/markets/data/seed.json'), 'utf8'));
let state = structuredClone(seed);
const perPractice = [];
for (const practice of seed.drafts) {
  const prepared = preparePractice(practice, state.markets, state.dates);
  state = { ...state, ...replaceMarketInState(state, prepared.market, prepared.dates) };
  perPractice.push({ id: practice.id, target: prepared.market.id, market: prepared.market, dates: prepared.dates });
}
const added = { ...newMarket('QA-new-market'), name: 'Mercato di verifica nuovo', comune: 'Pordenone', prov: 'PN', place: 'Piazza di verifica', url: 'https://example.test/nuovo-mercato', checked: '2026-10-30', validThrough: '2026-12-31', weekdaysIso: [6], status: 'published', publicationReady: true, evidenceStatus: 'documented' };
const output = { state, perPractice, newMarketState: replaceMarketInState(seed, added, []) };
fs.writeFileSync(path.join(outputDir, 'panel-payload.json'), JSON.stringify(output));
console.log(JSON.stringify({prepared: perPractice.length, markets: state.markets.length, drafts: state.drafts.length, uniqueMarkets: new Set(state.markets.map(item => item.id)).size}));
