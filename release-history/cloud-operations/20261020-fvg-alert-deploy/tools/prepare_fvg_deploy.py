from fvg_deploy_common import *
import hashlib,io,shutil,tarfile,zipfile
oldroot=ROOT/'.tmp/icon-fvg-readiness-20261020';oldpkg=oldroot/'package'
manifest=json.loads((oldpkg/'manifest.json').read_text())
assert manifest['base_image']==BASE
for path,digest in manifest['files'].items():assert hashlib.sha256((oldpkg/path).read_bytes()).hexdigest()==digest,path
assert git('rev-parse','HEAD').decode().strip()==COMMIT and not git('status','--porcelain').strip()
for path,digest in manifest['candidate_overlay'].items():
    raw=git('show',COMMIT+':backend/'+path).replace(b'\r\n',b'\n')
    assert hashlib.sha256(raw).hexdigest()==digest,path
context=OUT/'context';assert not context.exists();context.mkdir()
verification=context/'verification';verification.mkdir()
shutil.copytree(oldpkg,verification/'package')
paths=git('ls-tree','-r','--name-only',COMMIT,'backend/tests').decode().splitlines()
paths+=['release-history/cloud-operations/20261020-services-attestation/public-alert-local-check.json']
with tarfile.open(fileobj=io.BytesIO(git('archive',COMMIT,'--',*paths))) as tf:
    for path in paths:
        member=tf.getmember(path)
        assert member.isfile()
        target=verification/'repo'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tf.extractfile(member).read())
api_zip=ROOT/'.tmp/release-services-readiness-20261020/api-source.zip'
assert hashlib.sha256(api_zip.read_bytes()).hexdigest()=='b322c0e9887bc151e700909d32c034fce3cbbf444057164626d44c2a4f51e4de'
with zipfile.ZipFile(api_zip) as z:api_reader=z.read('app/services/official_alerts.py')
assert hashlib.sha256(api_reader.replace(b'\r\n',b'\n')).hexdigest()=='73774cce7a46afb2c0a7c12f783686dd93a5a40236d479305515786bc5463f03'
(verification/'api-reader.py').write_bytes(api_reader)
checker=(oldroot/'check_fvg_alert_rollout.py').read_text()
start=checker.index('assert base64.urlsafe_b64encode');end=checker.index('api_hash =',start)
checker=checker[:start]+"api_raw = args.api_source.read_bytes()\nassert hashlib.sha256(api_raw.replace(b'\\r\\n',b'\\n')).hexdigest() == '73774cce7a46afb2c0a7c12f783686dd93a5a40236d479305515786bc5463f03'\n"+checker[end:]
checker=checker.replace('Local installed dependencies, not a built Linux image; synthetic ARPA corroboration, captured widget','Pinned image dependencies; synthetic ARPA and captured public-source regressions; no live source calls')
(verification/'check.py').write_text(checker,encoding='utf-8',newline='\n')
image_check='''from pathlib import Path
import hashlib,json,subprocess,sys
root=Path('/verification');kind=sys.argv[1]
expected=root/'package/verification'/kind
checked=0
for p in expected.rglob('*.py'):
 actual=Path('/app')/p.relative_to(expected)
 assert actual.read_bytes().replace(b'\\r\\n',b'\\n')==p.read_bytes().replace(b'\\r\\n',b'\\n'),str(p.relative_to(expected))
 checked+=1
repository=Path('/app/app/repositories/push.py')
assert hashlib.sha256(repository.read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=='989a05445be31c46fa8d23e9613d0fd54c83dd29aae999402a7cd3b41bbae71c'
r=subprocess.run([sys.executable,str(root/'check.py'),'--package',str(root/'package'),'--repo',str(root/'repo'),'--api-source',str(root/'api-reader.py'),'--results','/tmp/result.json'])
summary=json.loads(Path('/tmp/result.json').read_text())
summary.update(verification=kind,actual_image_modules_checked=checked,push_repository_unchanged=True)
print(json.dumps(summary),flush=True)
raise SystemExit(r.returncode)
'''
(verification/'image_check.py').write_text(image_check,encoding='utf-8',newline='\n')
tags={kind:'europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend:fvg-alert-'+kind+'-20261020-'+COMMIT[:8] for kind in ('rollback','candidate')}
for kind in tags:
    lines=['FROM '+BASE,'ENV PUSH_OFFICIAL_ALERTS_MODE=off PUSH_OFFICIAL_ALERTS_REQUIRED=false']
    for path in manifest[kind+'_overlay']:lines.append('COPY verification/package/'+kind+'/'+path+' /app/'+path)
    lines+=['COPY verification/ /verification/','LABEL io.meteofriul.fix="fvg-mixed-alerts-'+kind+'" io.meteofriul.commit="'+COMMIT+'"']
    (context/('Dockerfile.'+kind)).write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
(context/'.gcloudignore').write_text('.git\n__pycache__/\n*.pyc\n',encoding='utf-8',newline='\n')
steps=[]
for kind,tag in tags.items():
    steps.append({'name':'gcr.io/cloud-builders/docker','args':['build','-f','Dockerfile.'+kind,'-t',tag,'.']})
    steps.append({'name':'gcr.io/cloud-builders/docker','args':['run','--rm','--network=none','--memory=512m',tag,'python','/verification/image_check.py',kind]})
save('cloudbuild',{'timeout':'900s','options':{'logging':'CLOUD_LOGGING_ONLY'},'steps':steps,'images':list(tags.values())})
provenance={'source_commit':COMMIT,'base_image':BASE,'base_build_id':manifest['source_build_id'],'base_source_sha256':manifest['source_archive_sha256'],
 'candidate_overlay':manifest['candidate_overlay'],'rollback_overlay':manifest['rollback_overlay'],'tags':tags,
 'approved_send_policy':'Keep existing send/true, recipient rules and required persistence unchanged, as subsequently authorized by owner',
 'historical_package_policy':'off/false was the earlier preparation only; not the current rollout policy',
 'api_reader_sha256':hashlib.sha256(api_reader.replace(b'\r\n',b'\n')).hexdigest(),
 'push_repository_sha256':'989a05445be31c46fa8d23e9613d0fd54c83dd29aae999402a7cd3b41bbae71c',
 'files':{p.relative_to(context).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(context.rglob('*')) if p.is_file()}}
save('source-provenance',provenance)
print(json.dumps({'context_files':len(provenance['files']),'candidate_matches_main':True,'build_order':['rollback','candidate'],'send_policy':provenance['approved_send_policy']}))
