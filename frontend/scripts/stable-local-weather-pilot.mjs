import { readFile, readdir, realpath, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build, preview } from "vite";

const STABLE_MARKER = '<meta name="meteofriul-local-weather-pilot" content="stable-static-v1">';
const rootDir = fileURLToPath(new URL("../", import.meta.url));
const argumentsByName = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  argumentsByName.set(process.argv[index], process.argv[index + 1]);
}
const mode = argumentsByName.get("--mode");
const port = Number(argumentsByName.get("--port"));
const serviceIdentity = argumentsByName.get("--service-identity");
const buildRoot = resolve(argumentsByName.get("--build-root") || "");
const outDir = join(buildRoot, "dist");

async function listFiles(directory) {
  const entries = await readdir(directory);
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry);
    if ((await stat(path)).isDirectory()) files.push(...await listFiles(path));
    else files.push(path);
  }
  return files;
}

async function assertStaticBuild() {
  const indexHtml = await readFile(join(outDir, "index.html"), "utf8");
  if (!indexHtml.includes(STABLE_MARKER)) {
    throw new Error("stable_local_pilot_marker_missing");
  }
  const runtimeFiles = (await listFiles(outDir)).filter((path) => /\.(?:css|html|js)$/u.test(path));
  for (const path of runtimeFiles) {
    if ((await readFile(path, "utf8")).includes("/@vite/client")) {
      throw new Error(`stable_local_pilot_contains_vite_client:${path}`);
    }
  }
}

if (process.env.METEO_PILOT_STABLE_FRONTEND !== "1") {
  throw new Error("stable_local_pilot_requires_launcher_flag");
}
if (process.env.NODE_ENV !== "development") {
  throw new Error("stable_local_pilot_requires_development_environment");
}
if (!["local-pilot", "local-pilot-cloud"].includes(mode) || port !== 5174) {
  throw new Error("stable_local_pilot_requires_canonical_mode_and_port");
}
if (serviceIdentity !== "dev:local-pilot") {
  throw new Error("stable_local_pilot_requires_canonical_service_identity");
}
const canonicalParent = (await realpath(dirname(buildRoot))).toLowerCase();
const canonicalTemp = (await realpath(tmpdir())).toLowerCase();
if (canonicalParent !== canonicalTemp
  || !/^meteofriul-local-weather-pilot-[0-9a-f]{32}$/u.test(basename(buildRoot))) {
  throw new Error("stable_local_pilot_requires_guarded_temp_directory");
}

let server;
let closing = false;

async function close(code = 0) {
  if (closing) return;
  closing = true;
  try {
    if (server) await server.close();
  } finally {
    await rm(buildRoot, { force: true, recursive: true });
  }
  process.exitCode = code;
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => {
    void close(0);
  });
}

try {
  await build({
    build: { emptyOutDir: true, outDir },
    configLoader: "native",
    mode,
    root: rootDir,
  });
  await assertStaticBuild();
  server = await preview({
    build: { outDir },
    configLoader: "native",
    mode,
    preview: { host: "127.0.0.1", port, strictPort: true },
    root: rootDir,
  });
  await new Promise((resolve, reject) => {
    server.httpServer.once("close", resolve);
    server.httpServer.once("error", reject);
  });
} catch (error) {
  await close(1);
  throw error;
} finally {
  await close(process.exitCode || 0);
}
