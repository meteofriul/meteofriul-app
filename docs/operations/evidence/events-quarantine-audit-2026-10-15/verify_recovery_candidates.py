"""Diagnostic recovery experiments on frozen public responses. No production mutations."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch
import json,re,sys
sys.path.insert(0,str(Path('backend').resolve()))
from app.events import engine,pilot_schedule,pilot_sagrefvg
from app.events.pilot_regional_year_control import inspect_item
from app.events.pilot_regional_display_audit import create_year_display_audit
from app.events.pilot_source_policy import validate_candidate
ROOT=Path('.tmp/quarantine-audit-2026-10-15')
items={x['number']:x for x in json.loads((ROOT/'live-pages.json').read_text(encoding='utf-8'))}
control=json.loads((ROOT/'control-baseline.json').read_text(encoding='utf-8'))
base=create_year_display_audit(control,today=date(2026,10,15))
assert len(base['review'])==4 and len(base['quarantined'])==10
changed=deepcopy(control)
experiments=[]
# Repair the missing space only in the weather-condition recognizer.
pattern=re.compile(pilot_schedule.WEATHER_CONDITION.pattern.replace(r'in\s+caso\s+di',r'in\s+caso\s*di'),re.I)
with patch.object(pilot_schedule,'WEATHER_CONDITION',pattern):
    for n in (1,2):
        item=items[n]
        result=inspect_item(item['url'],item['prior_entry'],(ROOT/f'{n:02}.html').read_text(encoding='utf-8'),today=date(2026,10,15))
        assert result['status']==('review_required' if n==1 else 'detail_aligned')
        if n==2:changed['results'][item['url']]=result
        experiments.append({'number':n,'normalization':'weather condition accepts casodi typo','status':result['status'],'reason':result['reason']})
# Show the exact one-day schedule already present in the official calendar.
for n in (11,12,13,14):
    item=items[n];result=deepcopy(item['prior_result']);event=result['event'];entry=item['prior_entry']
    days=entry['candidate']['listing_occurrences']; assert len(days)==1 and event['occurrences']==days
    day=date.fromisoformat(days[0]);label=result['detail_date_full'].lower().strip()
    assert label=='ottobre 2026' and day.year==2026 and day.month==10
    assert event['start_date']==event['end_date']==days[0]
    result['resolved_date_full']=f'{day.day} ottobre {day.year}'
    changed['results'][item['url']]=result
    experiments.append({'number':n,'normalization':'resolve one exact official calendar date within labelled month/year','date':days[0],'status':'detail_aligned'})
# A reviewed title reconciliation must be URL/date/town scoped, not fuzzy matching.
for n in (7,10):
    item=items[n];entry=deepcopy(item['prior_entry']);html=(ROOT/f'{n:02}.html').read_text(encoding='utf-8')
    heading=re.search(r'<h1\b[^>]*>(.*?)</h1>',html,re.I|re.S)
    title=engine.clean_event_text(heading[1]);prior_title=entry['candidate']['title']
    entry['candidate']['title']=title
    result=inspect_item(item['url'],entry,html,today=date(2026,10,15))
    assert result['status']=='detail_aligned',result
    changed['results'][item['url']]=result
    experiments.append({'number':n,'normalization':'reviewed candidate/detail title correspondence','previous_title':prior_title,'detail_title':title,'status':result['status']})
after=create_year_display_audit(changed,today=date(2026,10,15))
old_urls={x['url'] for x in base['cards']};new_urls={x['url'] for x in after['cards']}
expected={items[n]['url'] for n in (2,7,10,11,12,13,14)}
assert new_urls-old_urls==expected and old_urls<=new_urls
recovered=[]
for card in after['cards']:
    if card['url'] in expected:
        assert not validate_candidate(card,today=date(2026,10,15)),card['url']
        recovered.append({k:card.get(k) for k in ('url','title','start_date','end_date','event_city','date_label','schedule_kind')})
for n in (17,18):
    row=json.loads((ROOT/f'sagre-{n}.txt').read_text(encoding='utf-8'))
    if n==17:
        assert row['title'].startswith('San Quirino (PN)- ')
        row['title']=row['title'].replace('(PN)- ','(PN) - ',1)
        event=pilot_sagrefvg.event_from_api(row)
    else:
        assert row['venue']['address']=='Tribil superiore 45, 33040 Stregna UD'
        assert row['venue']['province']=='Udine' and row['venue']['city']=='Tribil Superiore'
        with patch.dict(pilot_sagrefvg.PARENT_ALIAS,{'tribil superiore':'Stregna'}):
            event=pilot_sagrefvg.event_from_api(row)
    assert not validate_candidate(event,today=date(2026,10,15))
    experiments.append({'number':n,'normalization':'province separator spacing' if n==17 else 'source-verified hamlet parent Stregna','status':'valid_event'})
    recovered.append({k:event.get(k) for k in ('url','title','start_date','end_date','event_city','place','lat','lon')})
assert len(recovered)==9
report={'baseline_snapshot':'2026-10-15T14:26:55.958729+00:00','diagnostic_only':True,'runtime_code_modified':False,'cloud_writes':False,'recoverable_with_reviewed_normalization':9,'regional_before':len(base['cards']),'regional_after':len(after['cards']),'preexisting_regional_cards_preserved':True,'cancelled_event_still_quarantined':True,'experiments':experiments,'candidate_cards':recovered,'remaining_unimplemented':[3,4,6,15,16],'remaining_unreachable':[5,8,9]}
(ROOT/'recovery-experiments.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
