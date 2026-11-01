"""Package the committed, allowlisted Markets service without local data or secrets."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tarfile
import io


FILES = (
    "backend/Dockerfile.markets", "backend/requirements.txt", "backend/app/__init__.py",
    "backend/app/markets_cloud.py", "backend/app/api/__init__.py", "backend/app/api/markets.py",
    "backend/app/infrastructure/__init__.py", "backend/app/infrastructure/firebase.py",
    "backend/app/infrastructure/app_check.py",
    "backend/app/infrastructure/markets_admin_auth.py",
    "backend/app/markets/__init__.py", "backend/app/markets/bootstrap.py",
    "backend/app/markets/model.py", "backend/app/markets/repository.py",
    "backend/app/markets/seed.py", "backend/app/markets/service.py", "backend/app/markets/data/seed.json",
    "backend/app/markets/refresh.py", "backend/app/markets/refresh_sources.py", "backend/app/markets/refresh_job.py",
    "backend/app/markets/review.py", "backend/tests/test_markets_review.py",
    "backend/app/markets/email_reminder.py", "backend/tests/test_markets_email_reminder.py",
    "backend/tests/__init__.py", "backend/tests/test_markets_archive.py",
    "backend/tests/test_markets_firestore.py", "backend/tests/test_markets_cloud.py",
    "backend/tests/test_firebase_infrastructure.py",
    "backend/tests/test_markets_refresh_contract.py", "backend/tests/test_markets_refresh_job.py",
    "backend/tests/test_markets_refresh_sources.py",
    "frontend/src/data/markets/catalogue2026.json",
    "docs/operations/evidence/MERCATI_REVISIONE_192_20261030.json",
    "docs/operations/evidence/MERCATI_RICOGNIZIONE_COMUNI_20261030.json",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(arguments.output).resolve()
    if output.exists():
        raise SystemExit("Output already exists; preserve the previous package")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
        raise SystemExit("Commit the workstream before packaging")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    output.mkdir(parents=True)
    contents = {}
    for name in FILES:
        contents[name] = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=root)
    image = f"europe-west1-docker.pkg.dev/meteo-friul/meteofriul/markets:source-{commit[:12]}"
    build = {
        "steps": [{"name":"gcr.io/cloud-builders/docker", "args":[
            "build", "--build-arg", f"SOURCE_COMMIT={commit}", "-f", "backend/Dockerfile.markets", "-t", image, ".",
        ]}],
        "images":[image], "timeout":"1200s",
        "options":{"logging":"CLOUD_LOGGING_ONLY"},
    }
    contents["cloudbuild.json"] = (json.dumps(build,indent=2)+"\n").encode()
    context = output / "context.tar.gz"
    with tarfile.open(context,"w:gz") as archive:
        for name,data in contents.items():
            item = tarfile.TarInfo(name)
            item.size = len(data)
            item.mode = 0o644
            archive.addfile(item,io.BytesIO(data))
    (output / "cloudbuild.json").write_bytes(contents["cloudbuild.json"])
    manifest = {"sourceCommit":commit,"imageTag":image,"archiveSha256":hashlib.sha256(context.read_bytes()).hexdigest(),
                "files":[{"path":name,"sha256":hashlib.sha256(data).hexdigest()} for name,data in contents.items()],
                "containsLocalArchive":False,"containsCredentials":False,"submitted":False}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"sourceCommit":commit,"files":len(contents),"imageTag":image}))


if __name__ == "__main__":
    main()
