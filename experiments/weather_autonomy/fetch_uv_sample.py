"""Download only the existing UV sample; never submit or expose ADS credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import requests
import yaml

def main():
    root = Path(__file__).resolve().parent / 'uv-pilot-local'
    job = json.loads((root / 'job.json').read_text())
    assert job['dataset'] == 'cams-global-atmospheric-composition-forecasts'
    from uuid import UUID
    job_id = str(UUID(job['request_id']))
    gcloud = Path(os.environ['LOCALAPPDATA']) / 'Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd'
    secret = subprocess.run([str(gcloud), 'secrets', 'versions', 'access', 'latest',
        '--secret=pilot-ads', '--project=meteofriul-pilot-20260906'], capture_output=True, text=True, check=True)
    credentials = yaml.safe_load(secret.stdout)
    assert credentials['url'] == 'https://ads.atmosphere.copernicus.eu/api'
    endpoint = credentials['url'] + '/retrieve/v1/jobs/' + job_id
    session = requests.Session()
    session.trust_env = False
    response = session.get(endpoint+'/results', headers={'PRIVATE-TOKEN': credentials['key']},
                           timeout=30, allow_redirects=False)
    response.raise_for_status()
    asset = response.json()['asset']['value']
    parsed = urlsplit(asset['href'])
    assert parsed.scheme == 'https' and parsed.hostname == 'object-store.os-api.cci2.ecmwf.int'
    assert not parsed.username and not parsed.password
    expected_size = int(asset['file:size'])
    assert 0 < expected_size < 2*1024*1024
    # New unauthenticated session; never forward the ADS header to storage.
    download = requests.get(asset['href'], timeout=30, allow_redirects=False)
    download.raise_for_status()
    body = download.content
    assert len(body) == expected_size and body.startswith(b'GRIB') and body.endswith(b'7777')
    target = root / 'source.grib'
    if target.exists():
        assert target.read_bytes() == body
    else:
        with target.open('xb') as stream:
            stream.write(body)
    print(json.dumps({'status':'downloaded_pending_decode', 'bytes':len(body),
                      'sha256':hashlib.sha256(body).hexdigest()}))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status':'stopped','error_type':type(error).__name__}))
        raise SystemExit(1)
