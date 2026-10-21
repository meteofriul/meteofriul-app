from fvg_deploy_common import *
from datetime import datetime,timezone
import requests,hashlib
sys.path.insert(0,str(REPO/'backend'))
from app.services.official_alert_sources import fetch_official_alert_observations,reconcile_official_alert_observations
now=datetime.now(timezone.utc)
r=requests.get('https://pianiemergenza.protezionecivile.fvg.it/api/alerts.jsonp',params={'callback':'pcrfvgit_widget_setup'},
 headers={'User-Agent':'MeteoFriul/3.0 (+https://meteofriul.it)','Referer':'https://www.protezionecivile.fvg.it/it/widget-allerta'},timeout=(10,45));r.raise_for_status()
(OUT/'widget-current.jsonp').write_bytes(r.content)
observations=fetch_official_alert_observations(widget_fetcher=lambda:r.text,html_fetcher=None,
 telegram_fetcher=lambda:{'alerts':[],'can_confirm_inactive':False},now=lambda:now)
result=reconcile_official_alert_observations(None,observations,now=now)
save('public-source-check',{'observed_at':now.isoformat(),'observations':observations,'result':result,'writes':0,'sends':0,'source_reads':'public GET only'})
api=requests.get(PLAY_API+'/weather/official-alerts',timeout=(10,45));api.raise_for_status();save('api-before-read',api.json())
print(json.dumps({'source_active':result.get('active'),'source_mode':result.get('source_mode'),'error':result.get('error'),
 'alerts':[{k:x.get(k) for k in ('level','zone_levels','valid_from','valid_to','pdf_url')} for x in result.get('alerts',[])],
 'api_active':api.json().get('active'),'api_alert_count':len(api.json().get('alerts',[]))},ensure_ascii=False))
