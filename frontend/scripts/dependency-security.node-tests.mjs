import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { test } from 'node:test';

const require = createRequire(import.meta.url);

test('the xcode override preserves CommonJS UUID generation and rejects truncated output', () => {
  const xcode = require('xcode');
  const xcodeRequire = createRequire(require.resolve('xcode'));
  const uuid = xcodeRequire('uuid');
  const project = xcode.project('unused.pbxproj');
  project.hash = { project: { objects: {} } };
  const ids = new Set(Array.from({ length: 100 }, () => project.generateUuid()));
  assert.equal(ids.size, 100);
  for (const id of ids) assert.match(id, /^[A-F0-9]{24}$/);
  assert.throws(() => uuid.v5('sample', uuid.v5.DNS, new Uint8Array(8), 4), RangeError);
  assert.throws(() => uuid.v6({}, new Uint8Array(8), 4), RangeError);
});

test('Firestore resolves a compatible gRPC client and server errors do not leak handler details', async () => {
  const firestoreRequire = createRequire(require.resolve('@firebase/firestore'));
  const grpc = firestoreRequire('@grpc/grpc-js');
  const serialize = (value) => Buffer.from(JSON.stringify(value));
  const deserialize = (value) => JSON.parse(value.toString());
  const service = { echo: { path: '/security.Probe/Echo', requestStream: false,
    responseStream: false, requestSerialize: serialize, requestDeserialize: deserialize,
    responseSerialize: serialize, responseDeserialize: deserialize } };
  const server = new grpc.Server();
  const secret = 'handler-private-canary';
  server.addService(service, { echo: (call, callback) => {
    if (call.request.fail) throw new Error(secret);
    callback(null, { received: call.request.value });
  } });
  let client;
  try {
    const port = await new Promise((resolve, reject) => server.bindAsync(
      '127.0.0.1:0', grpc.ServerCredentials.createInsecure(),
      (error, boundPort) => error ? reject(error) : resolve(boundPort),
    ));
    const Client = grpc.makeGenericClientConstructor(service, 'Probe');
    client = new Client(`127.0.0.1:${port}`, grpc.credentials.createInsecure());
    const request = (value) => new Promise((resolve, reject) => client.echo(
      value, { deadline: Date.now() + 5000 },
      (error, response) => error ? reject(error) : resolve(response),
    ));
    assert.deepEqual(await request({ value: 'ok' }), { received: 'ok' });
    await assert.rejects(request({ fail: true }), (error) => {
      assert.equal(error.code, grpc.status.UNKNOWN);
      assert.equal(error.details.includes(secret), false);
      return true;
    });
  } finally {
    client?.close();
    server.forceShutdown();
  }
});

test('PostCSS does not disclose an external source map, with or without from', async () => {
  const postcss = require('postcss');
  const dir = await mkdtemp(path.join(tmpdir(), 'meteo-postcss-security-'));
  const secret = 'source-map-private-canary';
  try {
    const outside = path.join(dir, 'private.map');
    await writeFile(outside, JSON.stringify({ version: 3, sources: ['private.txt'],
      names: [], mappings: 'AAAA', sourcesContent: [secret] }));
    for (const from of [undefined, path.join(dir, 'project', 'style.css')]) {
      const annotation = from ? '../private.map' : outside.replaceAll('\\', '/');
      const result = await postcss([]).process(`a{color:red}/*# sourceMappingURL=${annotation} */`,
        { from, to: 'output.css', map: { inline: false } });
      assert.equal(result.map.toString().includes(secret), false);
    }
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test('xmldom rejects malformed names and strict serialization rejects injected doctypes', () => {
  const { DOMImplementation, XMLSerializer } = require('@xmldom/xmldom');
  const impl = new DOMImplementation();
  const doc = impl.createDocument('urn:test', 'root', null);
  assert.throws(() => doc.createElementNS('urn:test', 'a\n><injected/'));
  const dt = impl.createDocumentType('root', '', '');
  dt.name = 'root><!--injected--';
  const withDoctype = impl.createDocument(null, 'root', dt);
  assert.throws(() => new XMLSerializer().serializeToString(withDoctype, { requireWellFormed: true }));
});

test('brace expansion handles adversarial non-expanding groups within a bounded child process', () => {
  const script = `const assert = require('node:assert/strict');
    const { expand } = require(${JSON.stringify(require.resolve('brace-expansion'))});
    const literal = 'a' + Array(1000).fill('{}').join(',');
    assert.deepEqual(expand(literal), [literal]);
    expand('{a}' + '}'.repeat(10000) + ',z}');`;
  execFileSync(process.execPath, ['-e', script], { timeout: 5000, stdio: 'pipe' });
});
