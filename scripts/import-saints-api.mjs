// Offline data refresh. Credentials are read into memory, never written to output.
import fs from 'node:fs/promises';
import os from 'node:os';
import pathModule from 'node:path';
const checkpoint = pathModule.join(os.tmpdir(), 'meteofriul-saints-import-2026-09-07');
await fs.mkdir(checkpoint, { recursive: true });
const base = 'https://santodelgiorno.marcointroini.it/api/v1';
const tokenFile = process.argv[2];
if (!tokenFile) throw new Error('Supply the local token file path');
const token = (await fs.readFile(tokenFile, 'utf8')).match(/\b\d+\|[A-Za-z0-9]+/)?.[0];
if (!token) throw new Error('Token not found');
async function get(url) {
  if (!url.startsWith(`${base}/`)) throw new Error('Unexpected API origin');
  const saved = pathModule.join(checkpoint, encodeURIComponent(url.slice(base.length)) + '.json');
  try { return JSON.parse(await fs.readFile(saved, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  for (let attempt = 0; attempt < 5; attempt++) {
    const response = await fetch(url, { headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000) });
    if (response.ok) {
      const body = await response.json();
      await fs.writeFile(saved, JSON.stringify(body));
      return body;
    }
    if (response.status === 429) throw new Error('API rate limit (429); archive unchanged. Retry after the service limit resets.');
    if (response.status < 500) throw new Error(`API status ${response.status}`);
    await new Promise(resolve => setTimeout(resolve, Math.max(2000 * (attempt + 1), Number(response.headers.get('retry-after') || 0) * 1000)));
  }
  throw new Error('API retries exhausted; archive unchanged');
}
const dayOnly = process.argv[3];
if (dayOnly && !/^\d{2}-\d{2}$/.test(dayOnly)) throw new Error('Expected MM-DD');
const first = dayOnly ? await get(`${base}/santo/data/${Number(dayOnly.slice(0, 2))}/${Number(dayOnly.slice(3))}`) : await get(`${base}/santo`);
if (dayOnly) first.meta = { total: first.data.length, last_page: 1 };
console.log(`API export: ${first.meta.total} records, ${first.meta.last_page} pages`);
const records = [...first.data];
for (let page = 2; page <= first.meta.last_page; page++) {
  const result = await get(`${base}/santo?page=${page}`);
  records.push(...result.data);
  if (page % 10 === 0) console.log(`Downloaded ${page}/${first.meta.last_page} pages`);
  await new Promise(resolve => setTimeout(resolve, 1100));
}
if (records.length !== first.meta.total || new Set(records.map(r => r.uuid)).size !== records.length) throw new Error('Incomplete or duplicate API export; archive unchanged');
const sources = {};
for (const record of records) {
  const relation = record.relationships?.fonte;
  const id = relation?.data?.id;
  if (id != null && !sources[id]) sources[id] = await get(relation.links.self);
}
const path = new URL('../frontend/src/data/almanac/saints.json', import.meta.url);
const archive = JSON.parse(await fs.readFile(path, 'utf8'));
const groups = new Map();
for (const record of records) {
  const a = record.attributes;
  const date = new Date(Date.UTC(2024, Number(a.mese) - 1, Number(a.giorno)));
  if (date.getUTCMonth() + 1 !== Number(a.mese) || date.getUTCDate() !== Number(a.giorno) || !a.nome || typeof a.onomastico !== 'boolean' || typeof a.onomasticoSecondario !== 'boolean') throw new Error('Invalid API record; archive unchanged');
  const key = `${String(a.mese).padStart(2, '0')}-${String(a.giorno).padStart(2, '0')}`;
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(record);
}
for (const [key, items] of groups) {
  if (!archive[key]) throw new Error(`Missing local day ${key}`);
  const day = archive[key];
  const names = [...(day.all_names || [])];
  for (const item of items) {
    const a = item.attributes;
    let existing = names.find(n => n.api_uuid === item.uuid || (n.name_it === a.nome && Boolean(n.is_name_day) === a.onomastico && Boolean(n.is_secondary_name_day) === a.onomasticoSecondario));
    if (!existing) { existing = { name_it: a.nome, name_fur: a.nome, name_fur_status: 'pending_review' }; names.push(existing); }
    Object.assign(existing, { is_name_day: a.onomastico, is_secondary_name_day: a.onomasticoSecondario, api_uuid: item.uuid, api_source_id: item.relationships?.fonte?.data?.id ?? null });
  }
  day.all_names = names;
}
const report = { imported_at: new Date().toISOString(), service: base, records: records.length, days: groups.size, rights_review: 'not_performed_user_requested_import', sources };
// Mechanical JSON merge: preserves principal saints, curated translations and existing profiles.
await fs.writeFile(path, JSON.stringify(archive, null, 2) + '\n');
await fs.writeFile(new URL('../frontend/src/data/almanac/saints-api-provenance.json', import.meta.url), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ records: report.records, days: report.days, sources: Object.keys(sources).length, september7NameDays: archive['09-07'].all_names.filter(n => n.is_name_day).map(n => n.name_it) }));
