"""Explicit pilot-only, per-provider object permissions; no project-wide grants."""
import os
from pathlib import Path
import subprocess

PROJECT = "meteofriul-pilot-20260906"
GCLOUD = str(Path(os.environ["LOCALAPPDATA"]) / "Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd")

def command(*args):
    subprocess.run([GCLOUD, *args, "--project=" + PROJECT, "--quiet"], check=True)

def main():
    for name, permissions in (
        ("pilotObjectReadCreate", "storage.objects.get,storage.objects.create"),
        ("pilotObjectReplace", "storage.objects.delete"),
    ):
        command("iam", "roles", "create", name, "--title=" + name,
                "--permissions=" + permissions, "--stage=GA")
    for provider in ("icon", "cams"):
        member = f"--member=serviceAccount:pilot-{provider}@{PROJECT}.iam.gserviceaccount.com"
        state_prefixes = [f"state/dispatch/{provider}/", f"state/publication/{provider}/"]
        if provider == "cams":
            state_prefixes += ["state/plans/cams/", "state/ads/", "state/runs/"]
        data_prefixes = (["weather/v1/icon2i/"] if provider == "icon" else
                         ["weather/v1/cams_europe/", "weather/v1/cams_europe_pollen/", "weather/v1/families/cams/"])
        for suffix, prefixes in (("state", state_prefixes), ("data", data_prefixes)):
            bucket = PROJECT + "-" + suffix
            root = f"projects/_/buckets/{bucket}/objects/pilot/"
            expr = " || ".join(f'resource.name.startsWith("{root}{p}")' for p in prefixes)
            command("storage", "buckets", "add-iam-policy-binding", "gs://" + bucket,
                    member, f"--role=projects/{PROJECT}/roles/pilotObjectReadCreate",
                    "--condition=title=provider-read-create,expression=" + expr)
            # Delete permission is necessary to REPLACE an existing GCS object;
            # immutable run payloads are never granted this permission.
            replace = (["state/runs/"] if suffix == "state" and provider == "cams" else [])
            exact = (["weather/v1/icon2i/latest.json"] if suffix == "data" and provider == "icon" else
                     ["weather/v1/families/cams/latest.json"] if suffix == "data" else [])
            terms = [f'resource.name.startsWith("{root}{p}")' for p in replace]
            terms += [f'resource.name == "{root}{p}"' for p in exact]
            if terms:
                command("storage", "buckets", "add-iam-policy-binding", "gs://" + bucket,
                        member, f"--role=projects/{PROJECT}/roles/pilotObjectReplace",
                        "--condition=title=mutable-pointer-only,expression=" + " || ".join(terms))

if __name__ == "__main__":
    main()
