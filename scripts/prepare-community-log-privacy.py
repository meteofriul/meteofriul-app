"""Prepare a scoped Cloud Logging exclusion without cloud mutations.

Cloud Run request logs contain raw URLs, client IPs and user agents. Exclude
those records for one Community service; application logs and native aggregate
Cloud Run metrics remain available. Every other sink/ancestor route must be
reviewed before applying this policy. This tool never calls a cloud API.
"""
import argparse
import json
import re


def exclusion(project: str, service: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
        raise ValueError("Expected a Google Cloud project ID, not a name or number")
    if not re.fullmatch(r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?", service):
        raise ValueError("Expected a Cloud Run service name")
    return {
        "name": "community-http-request-privacy",
        "description": "Exclude raw Community request URLs, IPs and user agents; retain application logs and native aggregate metrics.",
        "filter": "\n".join([
            'resource.type="cloud_run_revision"',
            f'resource.labels.project_id="{project}"',
            f'resource.labels.service_name="{service}"',
            'LOG_ID("run.googleapis.com/requests")',
        ]),
        "disabled": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(exclusion(args.project, args.service), indent=2))
    except ValueError as error:
        parser.error(str(error))
