"""Add only the UV object paths to the existing pilot CAMS identity."""
from configure_pilot_worker_iam import command, PROJECT

if __name__ == '__main__':
    member = '--member=serviceAccount:pilot-cams@'+PROJECT+'.iam.gserviceaccount.com'
    for bucket, prefix in ((PROJECT+'-state', 'state/uv/'), (PROJECT+'-data', 'weather/v1/uv/')):
        expression = f'resource.name.startsWith("projects/_/buckets/{bucket}/objects/pilot/{prefix}")'
        command('storage', 'buckets', 'add-iam-policy-binding', 'gs://'+bucket, member,
                '--role=projects/'+PROJECT+'/roles/pilotObjectReadCreate',
                '--condition=title=uv-only-read-create,expression='+expression)
    command('storage', 'buckets', 'add-iam-policy-binding', 'gs://'+PROJECT+'-data', member,
            '--role=projects/'+PROJECT+'/roles/pilotObjectReplace',
            '--condition=title=uv-latest-only,expression=resource.name == "projects/_/buckets/'+PROJECT+'-data/objects/pilot/weather/v1/uv/latest.json"')
