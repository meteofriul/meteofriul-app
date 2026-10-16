import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function assertVersionParity({ packageVersion, lockVersion, lockedPackageVersion, gradleSource }) {
  const androidVersions = [...gradleSource.matchAll(/^\s*versionName\s+["']([^"']+)["']\s*$/gm)];
  if (androidVersions.length !== 1) {
    throw new Error(`Expected one Android versionName, found ${androidVersions.length}.`);
  }

  const androidVersion = androidVersions[0][1];
  if (packageVersion !== lockVersion || packageVersion !== lockedPackageVersion || packageVersion !== androidVersion) {
    throw new Error(
      `Version mismatch: frontend=${packageVersion}, lock=${lockVersion}/${lockedPackageVersion}, Android=${androidVersion}.`,
    );
  }
  return packageVersion;
}

export function assertWorkspaceVersionParity() {
  const frontendPackage = JSON.parse(readFileSync(resolve(frontendRoot, "package.json"), "utf8"));
  const frontendLock = JSON.parse(readFileSync(resolve(frontendRoot, "package-lock.json"), "utf8"));
  const gradleSource = readFileSync(resolve(frontendRoot, "android/app/build.gradle"), "utf8");
  return assertVersionParity({
    packageVersion: frontendPackage.version,
    lockVersion: frontendLock.version,
    lockedPackageVersion: frontendLock.packages[""].version,
    gradleSource,
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(`Frontend/Android version aligned: ${assertWorkspaceVersionParity()}`);
}
