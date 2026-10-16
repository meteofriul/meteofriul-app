import test from "node:test";
import assert from "node:assert/strict";
import { assertVersionParity, assertWorkspaceVersionParity } from "./assert-version-parity.mjs";

const aligned = {
  packageVersion: "0.1.14",
  lockVersion: "0.1.14",
  lockedPackageVersion: "0.1.14",
  gradleSource: 'defaultConfig {\n    versionName "0.1.14"\n}',
};

test("current frontend and Android release versions match", () => {
  assert.equal(assertWorkspaceVersionParity(), "0.1.14");
});

test("rejects a stale frontend version", () => {
  assert.throws(() => assertVersionParity({ ...aligned, packageVersion: "0.1.13" }), /Version mismatch/);
});

test("rejects a stale lockfile version", () => {
  assert.throws(() => assertVersionParity({ ...aligned, lockedPackageVersion: "0.1.13" }), /Version mismatch/);
});

test("rejects an ambiguous Android version", () => {
  assert.throws(() => assertVersionParity({ ...aligned, gradleSource: '' }), /Expected one Android versionName/);
});
