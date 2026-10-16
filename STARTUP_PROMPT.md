# Meteo Friûl — avvio canonico

La base di lavoro ufficiale è:

```text
F:\proggetto Meteo Friul App\meteo FRIUL
```

Le altre cartelle con nomi simili sono archivi storici. Non vanno usate come
sorgente, backend, cartella di avvio o destinazione delle modifiche.

## Prima di lavorare

1. Aprire la cartella canonica oppure un worktree Git creato da essa.
2. Leggere `AGENTS.md` e la sezione operativa di `README.md`.
3. Controllare `git status --short --branch` e preservare modifiche già presenti.
4. Non copiare codice dagli archivi storici senza un confronto esplicito e test.

Il repository contiene già frontend, API, wrapper Android, contratti, strumenti
meteo autonomi, script di rilascio e documentazione operativa. Non dipende da
un'altra cartella dell'app per avviarsi.

## App pilota nel browser

La pilota aggiornata si avvia esclusivamente con il launcher protetto:

```powershell
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud
```

Se si deve lavorare senza il reader cloud, usare un istante compatibile con lo
snapshot locale dichiarato dal launcher:

```powershell
.\scripts\start-local-weather-pilot.ps1 -WeatherTestNow 2026-09-04T12:00:00Z
```

In una clone nuova il launcher inizializza automaticamente i quattro artefatti
ICON/CAMS verificati dal pacchetto versionato; database e log restano locali e
rigenerabili.

Indirizzo: `http://127.0.0.1:5174/`.

Non usare `npm run dev`, `start-dev.ps1` o una vecchia cartella per convalidare
la pilota: avviano la modalità tecnica ordinaria e possono mostrare una UI o un
contratto dati diversi.

Per fermare la pilota:

```powershell
.\scripts\start-local-weather-pilot.ps1 -Stop
```

## Modalità tecnica ordinaria

`start-dev.ps1` è riservato a test frontend/API non-pilota ed è completamente
autonomo nel repository:

```powershell
.\scripts\start-dev.ps1 -Restart
.\scripts\start-dev.ps1 -CheckOnly
.\scripts\start-dev.ps1 -Stop
```

Avvia API su `127.0.0.1:8002` e frontend su `localhost:5173`. Non possiede più
alcuna opzione o dipendenza verso il backend storico.

## Preparazione di una clone nuova

```powershell
python -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm --prefix frontend ci
```

I file `.env.*.local`, chiavi, keystore, build, cache, log, `node_modules` e
virtual environment restano locali e non devono essere versionati.

## Controlli minimi

Pulizia della base canonica:

```powershell
.\scripts\test-canonical-workspace-cleanliness.ps1
```

Frontend:

```powershell
Push-Location frontend
npm test
npm run lint
Pop-Location
```

Backend:

```powershell
Push-Location backend
.\venv\Scripts\python.exe -m pytest tests -q
.\venv\Scripts\python.exe -m compileall -q app
Pop-Location
```

Android e Play devono seguire `ANDROID_PILOT_RUNBOOK.md`; non sostituire i
comandi protetti con build manuali.

## Regola di consegna

Una modifica è completa soltanto quando codice, test, documentazione attiva e
asset della variante interessata sono coerenti. Per il branding pilota valgono
sempre insieme launcher adattivo, monocromatico, sfondo, splash e marchio Web.
