"""Build only the isolated Community QA APK; never installs or produces an AAB."""
import argparse,hashlib,json,os,re,shutil,subprocess,tempfile,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];front=root/'frontend';android=front/'android'
cfgpath=Path(args.config).resolve();cfg=json.loads(cfgpath.read_text())
assert cfg['projectId']=='meteofriul-comm-qa-261016' and cfg['projectNumber']=='445478488139'
assert cfg['packageName']=='com.meteofriul.app.communityqa' and re.fullmatch(r'1:445478488139:android:[0-9a-f]+',cfg['appId'])
def require_private_path(path):
 if not path.is_relative_to(root):return
 relative=path.relative_to(root).as_posix()
 tracked=subprocess.run(['git','ls-files','--error-unmatch','--',relative],cwd=root,capture_output=True).returncode==0
 ignored=subprocess.run(['git','check-ignore','-q','--',relative],cwd=root,capture_output=True).returncode==0
 if tracked or not ignored:raise ValueError('QA configuration and artifacts must be outside Git or in an ignored directory')
if cfgpath.name=='google-services.json':raise ValueError('QA requires its separate private configuration')
require_private_path(cfgpath)
out=Path(args.output).resolve();require_private_path(out/'qa-artifact-check');out.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
for k in list(env):
 if k.startswith(('VITE_','METEO_PLAY_','METEO_ANDROID_LOCAL_')):env.pop(k)
env.update(METEO_COMMUNITY_QA_BUILD='1',JAVA_HOME=r'C:\Program Files\Android\Android Studio\jbr',ANDROID_HOME=str(Path(env['LOCALAPPDATA'])/'Android/Sdk'))
env['ANDROID_SDK_ROOT']=env['ANDROID_HOME']
def run(argv,cwd=front,private=False):
 result=subprocess.run(list(map(str,argv)),cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
 if not private:print(result.stdout[-16000:]+result.stderr[-4000:],flush=True)
 if result.returncode:raise RuntimeError('QA build step failed: '+str(argv[0]))
 return result.stdout
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
tracked=[android/'capacitor.settings.gradle',android/'app/capacitor.build.gradle']
before={str(x):sha(x) for x in tracked}
(android/'app/src/main/assets/public').mkdir(parents=True,exist_ok=True)
run([shutil.which('npx.cmd'),'cap','update','android'])
assert all(sha(x)==before[str(x)] for x in tracked),'Capacitor tracked integration changed'
build=Path(tempfile.mkdtemp(prefix='meteofriul-community-qa-web-'))
run([front/'node_modules/.bin/vite.cmd','build','--mode','android-community-qa','--config','vite.community-qa.config.js','--configLoader','native','--outDir',build])
shutil.copy2(build/'qa/community/index.html',build/'index.html')
mark=build/'brand/pilot-test-orange-v1/mark.svg';mark.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(front/'public/brand/pilot-test-orange-v1/mark.svg',mark)
for f in build.rglob('*.js'):
 text=f.read_text(encoding='utf-8')
 assert '49007668366' not in text and 'AIza' not in text and 'meteofriul-community-' not in text,'Production Firebase/Community binding in QA Web build'
assert 'connect-src http://127.0.0.1:8788;' in (build/'index.html').read_text()
public=android/'app/src/communityQa/assets/public'
# Recreate only this generated QA asset directory, so stale hashed bundles
# from a previous QA version cannot remain inside the next APK.
assert public.resolve() == root/'frontend/android/app/src/communityQa/assets/public'
assert not public.is_symlink()
if public.exists():shutil.rmtree(public)
shutil.copytree(build,public)
resources=android/'app/build/generated/communityQa/res';resources.mkdir(parents=True,exist_ok=True)
origin=android/'app/src/localPilot/res'
for f in origin.rglob('*'):
 if f.is_file() and f.relative_to(origin).as_posix()!='values/strings.xml':
  dest=resources/f.relative_to(origin);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
run([android/'gradlew.bat','assembleCommunityQa','--no-daemon','-PMETEO_API_BASE=https://community-qa.invalid/api','-PMETEO_COMMUNITY_QA_CONFIG='+str(cfgpath)],cwd=android)
apk=android/'app/build/outputs/apk/communityQa/app-communityQa.apk';assert apk.is_file()
sdk=Path(env['ANDROID_HOME']);bt=sdk/'build-tools/36.1.0';java=Path(env['JAVA_HOME'])/'bin/java.exe'
certificate=run([java,'-jar',bt/'lib/apksigner.jar','verify','--min-sdk-version','24','--max-sdk-version','36','--print-certs',apk],private=True)
cert=re.search(r'certificate SHA-256 digest:\s*([0-9a-fA-F]+)',certificate).group(1)
badging=run([bt/'aapt2.exe','dump','badging',apk],private=True)
assert "package: name='com.meteofriul.app.communityqa'" in badging
assert 'application-debuggable' not in badging
for permission in ('ACCESS_FINE_LOCATION','ACCESS_COARSE_LOCATION','ACCESS_BACKGROUND_LOCATION','POST_NOTIFICATIONS','RECEIVE_BOOT_COMPLETED'):
 assert permission not in badging,'Unexpected permission: '+permission
res=run([bt/'aapt2.exe','dump','resources',apk],private=True)
assert cfg['appId'] in res and cfg['projectId'] in res and '1:49007668366:' not in res
destination=out/'meteofriul-community-qa.2.apk';shutil.copy2(apk,destination)
summary={'package':cfg['packageName'],'version':'0.1.14-community-qa.2','versionCode':300031,'apkSha256':sha(destination),'signingCertificateSha256':cert,'apkBytes':destination.stat().st_size,'firebaseProject':cfg['projectId'],'firebaseAppId':cfg['appId'],'appCheckProvider':'Firebase Android debug; registration only in QA','debuggable':False,'minified':True,'signatureVerifiedSdkRange':[24,36],'gpsAndNotificationPermissionsAbsent':True,'installed':False,'sourceWebDirectory':str(build),'apk':str(destination)}
(out/'apk-identity.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
