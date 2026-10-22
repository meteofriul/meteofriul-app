# Aggiornamento di sicurezza Vite — 22 ottobre 2026

## Stato e perimetro

Aggiornamento locale sul ramo `codex/vite-security-update`, derivato da `main`
`e6e73fcc48852b2601fe1c4264d739c86882fcfe`. Aggiornamento e verbale raccolti
nel commit `df6280b697d0bdec6bc82451dd64893c72e2dbc7`. La verifica
su Brave del Galaxy è completata: soddisfatti i controlli per la promozione
locale su main autorizzata dal proprietario. Nessun push, deploy, AAB,
installazione sul telefono o invio.

Vite passa da **8.0.16** (versione risolta nel lockfile di main) a **8.1.6**,
fissata esplicitamente nel manifest. Il lockfile aggiorna anche le dipendenze
necessarie della toolchain, tra cui Rolldown 1.0.3 → 1.1.5 e i suoi binding.
React, Capacitor, Firebase, plugin React e Vitest non cambiano versione risolta.
Nessuna modifica a componenti, stile, configurazione applicativa o servizi.

## Avviso corretto

- [Dependabot #33](https://github.com/meteofriul/meteofriul-app/security/dependabot/33).
- [GHSA-698v-4r3x-3vcv / CVE-2026-112943](https://github.com/vitejs/launch-editor/security/advisories/GHSA-698v-4r3x-3vcv): severità moderata, apertura dell'editor su Windows durante lo sviluppo.
- [Vite 8.1.6](https://github.com/vitejs/vite/releases/tag/v8.1.6) include `launch-editor` 2.14.2. Verificata nel pacchetto installato la versione incorporata e la validazione degli argomenti Windows. Nessun exploit eseguito.
- `npm audit --json`: zero vulnerabilità rilevate, a ogni severità.

L'avviso sul repository remoto non viene dichiarato chiuso: il ramo è locale.

## Controlli automatici

Ambiente Windows, Node 22.17.1, npm 10.9.2. Dipendenze installate dal lockfile
con `npm ci --no-audit --no-fund`, senza junction o copie da altri worktree.

| Controllo | Esito |
| --- | --- |
| Vitest completo, loader nativo, massimo 2 worker | 5.008 test passati, 13 saltati, zero falliti; 549 file passati e 5 saltati |
| `npm run lint` | Passato |
| `test:release-guard` | 9/9 |
| `test:local-pilot-guard` | 11/11 |
| `test:android-local-pilot-guard` | 7/7 |
| `test:android-community-qa-guard` | 2/2 |
| `test:dependency-security` | 5/5 |
| Build Web production con `--configLoader native` | Passata |
| Build service worker e controllo standalone | Passati |
| `git diff --check` | Passato |

Le build usano una directory univoca nella cartella temporanea del sistema.
Sono build Web generiche: non una AAB, una build Android o un artefatto
Cloudflare pronto alla pubblicazione. Restano gli avvisi già noti sulla
dimensione del bundle e sull'import dinamico dell'Almanacco. Il controllo del
service worker non registra dispositivi né invia notifiche. I test saltati
non sono presentati come verifiche riuscite.

## Anteprima: primo controllo e completamento

Avvio esclusivamente con `scripts/start-local-weather-pilot.ps1`, porta 5174,
parametro `-WeatherTestNow 2026-09-04T13:00:00Z` per lo snapshot locale
versionato. Log di avvio: Vite 8.1.6, HMR connesso. Backend, data plane e
frontend risultano sani e vincolati al loopback.

Verificati nel browser integrato, viewport 661 × 902:

- Bollettino in italiano chiaro, mappa e barra località/menù fissa allo scroll.
- Catalogo Eventi, apertura e chiusura del dettaglio.
- Passaggio al friulano e al tema scuro, resa del catalogo Eventi.
- Ripristino finale di italiano/chiaro; anteprima lasciata aperta sul Bollettino.

**Primo controllo: previsioni con dati non verificate.** Il profilo
locale richiede il resolver nazionale su `127.0.0.1:8782`, che non è avviato:
la richiesta restituisce `ECONNREFUSED` e l'app mostra correttamente
“Previsioni non disponibili”; anche aria e pollini non sono disponibili nella
vista osservata. Il medesimo errore del resolver è documentato nel log
dell'anteprima precedente (`section-sticky-navigation`) prima del cambio
Vite. Configurazione e codice di questo percorso sono invariati: il limite
locale non è una nuova regressione attribuibile all'aggiornamento.

### Completamento con i servizi pubblicati

Il 22 ottobre, su autorizzazione del proprietario, il controllo mancante è
stato completato tramite il profilo già previsto dal launcher:

```powershell
./scripts/start-local-weather-pilot.ps1 -NationalCloud -CheckOnly
./scripts/start-local-weather-pilot.ps1 -NationalCloud -RestartFrontend
```

Il profilo usa l'orologio reale e legge i reader regionali ICON/CAMS e il
reader nazionale già pubblicati. Nessun nuovo servizio cloud, acquisizione,
job o invio manuale. Riavviato solo il frontend locale dopo il controllo
positivo dei contratti; codice e configurazione versionata invariati.

Riscontri nella stessa anteprima Vite 8.1.6, browser integrato 661 × 902:

- Previsioni di Gradisca d'Isonzo caricate: modello ICON-2I del 22/10/2026,
  ore 02:00 locali; giorni, fascia oraria, temperature e precipitazioni visibili.
- Cambio giorno fino a sabato 24 ottobre e selezione dell'ora 00:00 riusciti.
  Giorno e ora selezionati conservano contorno e sfumatura interna coerenti.
- Dettaglio dell'ora aperto e richiuso: 9 mm nell'intervallo 23:00–00:00,
  13 °C, vento, raffiche, umidità e grafici leggibili.
- Qualità dell'aria e pollini CAMS caricati nella stessa vista (PM2.5 2,9
  µg/m³ e graminacee 0,21 grani/m³ al momento dell'osservazione).
- Nessun nuovo errore o avviso nella console dalla ricarica delle 15:00:41 UTC.
- Controllo finale del launcher: backend e frontend sani, riconoscibili e
  vincolati al loopback; contratto dei reader cloud verificato in sola lettura.

**Il limite della prova delle previsioni è chiuso.** L'anteprima resta aperta
sulle previsioni in italiano e tema chiaro. I log e gli screenshot del primo
controllo restano conservati per distinguere i due profili.

### Verifica sul Galaxy e criterio di promozione

Il 22 ottobre, completato il controllo autorizzato sul Galaxy A52 (SM-A525F),
Android 14, Brave 1.97.59, schermo 1080 × 2400. Connessione USB reverse alla
sola anteprima locale sulla porta 5174. Nessuna installazione o modifica ai
permessi di posizione/notifiche; località Pordenone mantenuta.

Candidato verificato: `df6280b697d0bdec6bc82451dd64893c72e2dbc7`. Gli SHA-256
di manifest e lockfile coincidono con quelli dei controlli automatici già
passati; dopo la prova si aggiungono soltanto questo verbale e le evidenze.

| Verifica su Brave | Riscontro |
| --- | --- |
| Previsioni reali | ICON-2I 22/10, 02:00 locali; cambio giorno, ore e dettaglio con grafici funzionanti |
| Dettaglio orario | Chiusura tramite Indietro Android e ritorno alle previsioni |
| Bollettino | Mappa leggibile; località e menù mantengono le stesse coordinate durante lo scroll |
| Eventi | Catalogo reale, 4 eventi oggi; località e filtri fissi; dettaglio a copertura della sezione |
| Indietro dal dettaglio Eventi | Ritorno alla stessa posizione della lista, verificato anche nella gerarchia |
| Italiano/chiaro e friulano/scuro | Previsioni ed Eventi leggibili; contorno e sfumatura interna coerenti tra giorno e ora |
| Aria e pollini | PM2.5 2,8 µg/m³, PM10 4,4 µg/m³, graminacee 0,24 grani/m³ nella vista osservata |
| Ripristino | Italiano, tema chiaro, Pordenone; anteprima lasciata sulle previsioni |

Evidenze selezionate e confronti di coordinate:
[risultati e hash](evidence/vite-security-update-2026-10-22/phone-verification.json),
[previsioni chiare](evidence/vite-security-update-2026-10-22/weather-final.png),
[previsioni friulane scure](evidence/vite-security-update-2026-10-22/weather-fur-dark.png),
[Bollettino dopo lo scroll](evidence/vite-security-update-2026-10-22/bulletin-scrolled.png),
[dettaglio Eventi](evidence/vite-security-update-2026-10-22/event-detail.png).
Gli screenshot di Impostazioni e le gerarchie grezze restano ignorati in locale.

**Limiti:** la prova riguarda Brave, non l'app Android installata, la AAB
minificata o Safari/iPhone. Da Impostazioni, Indietro Android ha lasciato Brave;
la freccia nell'app ha invece ripristinato correttamente la sezione. Il gestore
di pagina nativo in `pilotBackNavigation.js` è riservato a Capacitor e non cambia
con questo aggiornamento: non si certifica qui la parità completa della
cronologia Web. Il ritorno dai dettagli orario ed Eventi è verificato.
Nessuna nuova certificazione di tutti i job o degli invii.

Esito del controllo richiesto per Vite: **passato**. La promozione prevista è
un fast-forward locale di main che comprende il commit Vite e il successivo
commit documentale. Nessuna modifica aggiuntiva al codice applicativo.

## Evidenze locali

Directory ignorata nella radice canonica: `.tmp/vite-security-update-20261022/`.
Contiene `vitest.json`, `vitest.log`, `npm-audit.json`, `lint.log`, i cinque
log dei guard, `build-main.log`, `build-sw.log`, `build-sw-check.log`,
`build-location.json`, `checks.json` e screenshot:

- `preview-bulletin-it-light.png`
- `preview-bulletin-sticky.png`
- `preview-event-detail-it.png`
- `preview-events-fur-dark.png`
- `preview-weather-local-limitation.png` (primo controllo)
- `preview-weather-live-it-light.png`
- `preview-weather-hour-live.png`
- `preview-live-browser.json` (console dal nuovo avvio)
- `preview-live-check.log` (controllo finale del launcher)

I log grezzi e le dipendenze restano locali; questo verbale è il riepilogo
destinato al repository, insieme alle evidenze selezionate della prova sul Galaxy.
La promozione locale non aggiorna GitHub e non chiude da sola Dependabot.
