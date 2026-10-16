"""Grant only individual object GET on pilot data to the HTTPS reader."""
from configure_pilot_worker_iam import command, PROJECT

if __name__ == '__main__':
    command('iam', 'roles', 'create', 'pilotObjectRead', '--title=pilotObjectRead',
            '--permissions=storage.objects.get', '--stage=GA')
    command('storage', 'buckets', 'add-iam-policy-binding', 'gs://' + PROJECT + '-data',
            '--member=serviceAccount:pilot-reader@' + PROJECT + '.iam.gserviceaccount.com',
            '--role=projects/' + PROJECT + '/roles/pilotObjectRead',
            '--condition=title=weather-read-only,expression=resource.name.startsWith("projects/_/buckets/' + PROJECT + '-data/objects/pilot/weather/v1/")')
