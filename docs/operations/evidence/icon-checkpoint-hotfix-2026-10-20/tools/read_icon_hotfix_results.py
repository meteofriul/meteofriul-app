from icon_hotfix_common import *
import requests
execution=json.loads((OUT/'execution-submission.json').read_text())['metadata']['name']
bound=json.loads((OUT/'pre-execution-checks.json').read_text())['execution_start_bound_utc']
state=cloud('execution-status','run','jobs','executions','describe',execution,'--region=europe-west1')
status=state.get('status',{});conditions=status.get('conditions',[])
print(json.dumps({'execution':execution,'conditions':conditions}),flush=True)
if not any(c['type']=='Completed' and c['status'] in ('True','False') for c in conditions):raise SystemExit(0)
logs=cloud('execution-logs','logging','read','resource.type="cloud_run_job" AND resource.labels.job_name="meteofriul-local-notice-tolerance-qa" AND labels."run.googleapis.com/execution_name"="'+execution+'"','--limit=1000','--freshness=7d')
summaries=[]
for log in logs:
 value=log.get('jsonPayload')
 if value is None:
  try:value=json.loads(log.get('textPayload',''))
  except json.JSONDecodeError:continue
 if isinstance(value,dict) and 'eligible_devices' in value and 'data_quality' in value:summaries.append(value)
if not summaries:
 print('No structured summary visible yet.');raise SystemExit(0)
assert len(summaries)==1
summary=summaries[0];(OUT/'qa-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary),flush=True)
token=subprocess.check_output([sys.executable,GC,'auth','print-access-token','--account='+ACCOUNT,'--project='+PROJECT]).decode().strip()
headers={'Authorization':'Bearer '+token}
query_url='https://firestore.googleapis.com/v1/projects/meteo-friul/databases/(default)/documents:runQuery'
bound=json.loads((OUT/'pre-execution-checks.json').read_text())['execution_start_bound_utc']
def query(collection,field,select=None):
 q={'from':[{'collectionId':collection}],'where':{'fieldFilter':{'field':{'fieldPath':field},'op':'GREATER_THAN_OR_EQUAL','value':{'timestampValue':bound}}},'limit':201}
 if select:q['select']={'fields':[{'fieldPath':f} for f in select]}
 r=requests.post(query_url,headers=headers,json={'structuredQuery':q},timeout=45);r.raise_for_status()
 docs=[x['document'] for x in r.json() if 'document' in x];assert len(docs)<201,'bounded read limit reached'
 return docs
audits=query('local_notice_pilot_runs','evaluated_at')
qa=[r for r in audits if r.get('fields',{}).get('mode',{}).get('stringValue')=='dry_run']
(OUT/'qa-audit-records.json').write_text(json.dumps(qa,indent=2)+'\n')
outbox=query('push_local_notice_outbox','updated_at',['updated_at','state'])
(OUT/'outbox-changes-during-qa.json').write_text(json.dumps(outbox,indent=2)+'\n')
assert int(summary.get('sent',-1))==0 and int(summary.get('sent_unconfirmed',-1))==0 and int(summary.get('delivery_batches',-1))==0
assert all(r['fields'].get('can_send',{}).get('booleanValue') is False for r in qa)
result={'execution':execution,'status':summary['status'],'evaluated':summary['evaluated'],'groups':summary['groups'],
 'sent':summary['sent'],'delivery_batches':summary['delivery_batches'],'audit_records':len(qa),
 'outbox_mutations_during_qa':len(outbox),'start_bound_utc':bound,
 'audit_attempt_ids':sorted({r['fields']['attempt_id']['stringValue'] for r in qa}),
 'source_failed':summary['source_failed'],'failed':summary['failed'],
 'producer_updated':True,'attribution_note':'Audit and outbox reads are time-bounded; match attempt ids before attributing concurrent activity to QA.'}
(OUT/'execution-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
