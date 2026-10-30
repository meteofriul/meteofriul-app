import copy
import json
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'backend'))
from fastapi.testclient import TestClient
from app.api.markets import get_markets_service
from app.main import create_app
from app.markets.repository import SQLiteMarketRepository
from app.markets.service import MarketsService
from app.markets.seed import load_seed

HERE = Path(os.environ['MF_MARKETS_QA_DIR']).resolve()
payload = json.loads((HERE / 'panel-payload.json').read_text(encoding='utf-8'))
seed = load_seed()
results = []
with TemporaryDirectory(prefix='mf-cross-market-') as folder:
    service = MarketsService(SQLiteMarketRepository(Path(folder) / 'archive.sqlite3', seed=seed))
    app = create_app()
    app.dependency_overrides[get_markets_service] = lambda: service
    client = TestClient(app)
    local_token = secrets.token_urlsafe(32)
    headers = {'Authorization': f'Bearer {local_token}'}
    serial = 0
    def command(action, state=None):
        global serial
        serial += 1
        body = {'expectedRevision': service.state()['revision'], 'operationId': f'cross-boundary-{serial}', 'reason': 'Verifica temporanea documentata'}
        if state is not None:
            body['state'] = state
        response = client.put('/api/admin/markets/state', json=body, headers=headers) if action == 'save' else client.post('/api/admin/markets/publish', json=body, headers=headers)
        assert response.status_code == 200, (response.status_code, response.text)
        return response.json()
    with patch.dict(os.environ, {'K_SERVICE': '', 'MARKETS_ADMIN_AUTH_MODE': 'local', 'MARKETS_ADMIN_LOCAL_TOKEN': local_token}):
        original = client.get('/api/markets/catalogue').json()
        assert len(original['markets']) == 53
        command('save', payload['state'])
        assert client.get('/api/markets/catalogue').json() == original
        command('publish')
        after_drafts = client.get('/api/markets/catalogue').json()
        assert {item['id'] for item in after_drafts['markets']} == {item['id'] for item in original['markets']}
        assert {item['id']:item for item in after_drafts['dates']} == {item['id']:item for item in original['dates']}
        assert len(service.state()['markets']) == 100
        assert len(service.state()['drafts']) == 59
        results.append('59 panel-generated practices saved; 100 stable identities; 53 published projections unchanged')
        state = service.state()
        day = next(item for item in state['dates'] if item['status'] == 'published' and item['date'] >= '2026-10-30')
        chosen_id, edition_id = day['marketId'], day['id']
        original_market = next(item for item in seed['markets'] if item['id'] == chosen_id)
        state['markets'] = [copy.deepcopy(original_market) if item['id'] == chosen_id else item for item in state['markets']]
        original_day = day['date']
        day.update(date='2026-12-30', venue={'id':'qa-venue', 'place':'Piazza di verifica', 'directionsQuery':'Piazza di verifica'})
        command('save', state)
        command('publish')
        moved = client.get('/api/markets/catalogue').json()
        current_day = next(item for item in moved['dates'] if item['id'] == edition_id)
        assert current_day['date'] == '2026-12-30' and original_day in current_day['legacyDates']
        assert current_day['venue']['place'] == 'Piazza di verifica'
        results.append('Edition move preserves ID, records old date and per-edition venue')
        for status in ('suspended', 'archived', 'published'):
            state = service.state()
            next(item for item in state['markets'] if item['id'] == chosen_id)['status'] = status
            command('save', state)
            command('publish')
            public = client.get('/api/markets/catalogue').json()
            assert any(item['id'] == chosen_id for item in public['markets']) == (status == 'published')
        results.append('Suspend, archive and restore survive publication without changing identity')
        restarted = MarketsService(SQLiteMarketRepository(Path(folder) / 'archive.sqlite3'))
        assert restarted.catalogue() == service.catalogue()
        results.append('SQLite restart returns the same final published snapshot')
        added_service = MarketsService(SQLiteMarketRepository(Path(folder) / 'new-market.sqlite3', seed=seed))
        app.dependency_overrides[get_markets_service] = lambda: added_service
        saved = client.put('/api/admin/markets/state', headers=headers, json={'expectedRevision':0, 'operationId':'cross-add-market', 'reason':'Verifica aggiunta mercato', 'state':payload['newMarketState']})
        assert saved.status_code == 200, saved.text
        published = client.post('/api/admin/markets/publish', headers=headers, json={'expectedRevision':1, 'operationId':'cross-publish-market', 'reason':'Verifica pubblicazione mercato'})
        assert published.status_code == 200, published.text
        added = client.get('/api/markets/catalogue').json()
        assert len(added['markets']) == 54
        assert next(item for item in added['markets'] if item['id'] == 'QA-new-market')['quality'] == 'Documentato'
        results.append('New market from actual panel helper saves and publishes with documented projection')
        (HERE / 'public-fixtures.json').write_text(json.dumps({'initial':original, 'prepared':after_drafts, 'moved':moved, 'final':service.catalogue(), 'added':added, 'chosenMarketId':chosen_id, 'chosenEditionId':edition_id}), encoding='utf-8')

report = {'status':'pass', 'checks':results, 'preparedPractices':59, 'complete':13, 'limited':46, 'preparedIdentities':100, 'initialPublished':53, 'transport':'FastAPI TestClient', 'storage':'temporary SQLite', 'productionTouched':False}
(HERE / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
