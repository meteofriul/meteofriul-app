# Verifica locale Web 0.1.15 / riferimento Android 300036 — 23 ottobre 2026

## Esito

**Verifica locale eseguita con rilievi; collaudo finale della Web pubblicabile non chiuso.**
Il pacchetto esatto si avvia, ma l'API ufficiale non ammette le origini locali.
Il pilot degli stessi sorgenti permette controlli complementari con dati reali;
non sostituisce una prova dei servizi dal bundle ufficiale. Nessuna pubblicazione.

## Identità e ambiente

- Sorgente AAB e Web: `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`.
- Main/release al controllo: `eb1095185023636efde111dd93b295a5a07ec10f`;
  nessuna differenza frontend o nello script Web rispetto alla sorgente AAB.
- Frontend tree: `65ac58a65eef88d19474af262bc6c9ec36e7198c`.
- Archivio immutato: `release-artifacts/web-candidates/20261023-0.1.15-9d5ff2f4/`.
  Ricalcolati tutti gli hash: **506 file Web e 505 Android-Web conformi**.
  Manifest SHA256 `42e81042e678be61091db42e401329f54353bddd8be28d4673eacbf898a75bc2`.
- Asset principali: `main-CWQMOusY.js`, `main-Bc2ocrwd.css`.
- API già incorporata: tag `play-b6fbe4d`, revisione attestata
  `meteofriul-api-00251-jow`, backend `e180b87abe5dac022034881ea4eb1ca60a0d4e78`.
  Il legame immagine/sorgenti è riusato dal [verbale build](ANDROID_0.1.15_300036_BUILD_20261023.md),
  non ristabilito da un semplice HTTP 200.
- Browser del PC in Codex: bundle statico a `localhost:5182`, 1280×720;
  pilot canonico a `127.0.0.1:5174`, 661×902. Non sono dispositivi mobili reali.
- Nessuna prova Brave/Galaxy in questa sessione, come richiesto.

Il server statico temporaneo serve i file archiviati senza modificarli. L'associazione
MIME Windows iniziale serviva JavaScript come testo semplice: corretto esclusivamente
il server temporaneo, poi usata una nuova origine locale. Questo incidente del
collaudo non è un difetto del bundle e non vale come verifica della cache pubblica.
Il server non emula le regole Cloudflare `_headers` e `_redirects`.

Il pilot precedente apparteneva al ramo `realtime-layout`: fermato soltanto il suo
processo Vite identificato, poi riavviato dalla release con
`scripts/start-local-weather-pilot.ps1 -WeatherCloud`, riusando il backend locale.
Nessun writer regionale, acquisizione o job manuale. Lingua e tema del pilot
riportati a italiano/chiaro; località selezionata invariata. Non modificati permessi,
destinatari o impostazioni delle app installate.

## Accesso API e sponsor

Letture HTTP finali alle 13:28 UTC: `/healthz` e `/promotions/catalog` rispondono
200. `Access-Control-Allow-Origin` è assente per `http://localhost:5182` e
`http://127.0.0.1:5182`, presente per `https://meteofriul.app`. Questo spiega il
limite della prova locale; non dimostra un guasto dei job. Nessuna modifica CORS,
proxy aggiunto, intercettazione di richieste o disattivazione della sicurezza del browser.
Non serve concludere da questo che il backend debba essere aggiornato: il dominio
pubblico è già ammesso, ma il candidato non è stato pubblicato lì.

**Sponsor disattivati:** catalogo `enabled=false`, revisione 117, zero campagne.
Nessuna attivazione sponsor, pannello o sincronizzazione dati. Non viste schede
sponsor nei percorsi osservati. I controlli HTTP non sono invii di segnalazioni.

## Percorsi osservati

| Controllo | Pacchetto statico ufficiale | Pilot complementare, stessa sorgente |
| --- | --- | --- |
| Avvio e preferenze | IT/FUR; chiaro/scuro osservati; FUR/chiaro conservati al reload | IT/chiaro e FUR/scuro |
| Impostazioni / ritorno | Ritorno alla sezione precedente osservato | Ritorno a Previsioni e Bollettino osservato |
| Previsioni | Stati indisponibili IT/FUR; dati bloccati da CORS | ICON 23/10 02:00; giorni uniformi, pioggia leggibile, selezioni giorno/ora e dettaglio orario con grafici |
| Aria e pollini | Indisponibili, coerentemente con il limite API locale | Card e dettagli IT/FUR con dati CAMS: PM2.5 3,5, PM10 5,3 µg/m³; graminacee 0,22 grani/m³ |
| Rientro / reload | Solo preferenze e UI senza servizi | Valori CAMS presenti al rientro FUR e al reload finale IT; limite iniziale registrato sotto |
| Bollettino | Percorso API non qualificato | Testi IT/FUR, pill e mappa; barra località/menù resta visibile durante scroll FUR |
| Tempo reale | Tile CARTO visibili IT/FUR; navigazione mappa/dock presente; segnalazioni non leggibili per CORS | Layout osservato, ma tile con API KEY REQUIRED: chiave assente nella configurazione pilot, non nel bundle statico |
| Eventi | Lettura remota non qualificata | Catalogo reale, filtri, dettaglio FUR; Indietro browser chiude il dettaglio e conserva la lista; barra fissa |
| Home / Scopri | Home IT/FUR; contenuti locali visibili, meteo remoto indisponibile | Home e Scopri IT con contenuti e navigazione |
| Community | Aperta e chiusa la scelta in FUR; nessuna regola accettata, conferma o invio; GPS non disponibile | Esclusa dalla configurazione pilot, non prova della Community ufficiale |

Le verifiche selezione/card e grafici non sono un audit meteorologico dei valori.
A 1280×720 il dock Tempo reale si raggiunge anche mediante scorrimento della
pagina: dopo lo scroll il pulsante Segnala è accessibile. Non estesa la barra fissa
a Tempo reale. Radar e contenuti webcam non qualificati in questa sessione.

## Rilievi aperti

1. **WEB-300036-01 — errore GPS Community in friulano.** Nel bundle esatto il
   testo «Il GPS nol è rivât a dâ une posizion. Torne a provâ in esterni.» esce
   dal riquadro. Misura DOM: box y=338, h=52; copia y=347, h=57,97;
   fondo testo circa y=405, cioè 15 px sotto il box. Screenshot
   `static-community-gps-overflow-fur.png` e misure conservati. Non modificato CSS.
2. **WEB-300036-02 — traduzione Eventi incompleta.** «Mostra altri» rimane
   italiano in FUR, confermato anche dal literal in
   `frontend/src/features/events/EventsView.jsx:707`. Non riguarda i titoli degli
   eventi ripresi dalla fonte, che possono legittimamente restare in italiano.
3. **WEB-300036-03 — errore fonte OSMER non tradotto.** Nella Home FUR del
   bundle statico, il messaggio della fonte irraggiungibile resta in italiano.
   È distinto dal bollettino disponibile, correttamente visualizzato in friulano.
4. **WEB-300036-04 — osservazione iniziale CAMS da approfondire.** Al primo
   ingresso dopo il cambio di server il pilot mostrava modello 22/10 e dati
   ambientali indisponibili. Successivamente ha caricato la corsa 23/10 e CAMS.
   Il rientro FUR e il reload finale IT con cache aggiornata mostrano i valori.
   Non cronometrata la fase iniziale, non isolata la causa, nessun filmato di
   quella transizione: non dichiarare chiusa ogni possibile comparsa transitoria
   di «Dati non disponibili», né attribuire con certezza il fenomeno al codice nuovo.

## Cache, limiti e passo successivo

Verificati file manifest, nomi asset con hash e presenza delle regole hosting:
service worker `no-cache, no-store, must-revalidate`, manifest `no-cache`;
fallback SPA in `_redirects`. Il worker Firebase è per notifiche: non dimostra
funzionamento offline. Non effettuati aggiornamento da Web pubblica 0.1.14,
installazione PWA, prova Safari/iPhone, posizione GPS riuscita o località nazionale
in questa sessione. Nessuna simulazione può sostituire questi esiti mancanti.

Prima di qualificare la pubblicazione: correggere e ricontrollare i rilievi UI,
isolare l'osservazione iniziale CAMS; completare le letture del pacchetto ufficiale
da un'origine autorizzata e verificare l'aggiornamento cache. L'eventuale
pubblicazione richiede un'azione autorizzata separatamente. La verifica reale
Safari/iPhone resta aperta secondo il [runbook](WEB_ANDROID_RELEASE_PARITY.md).

Non generati AAB/APK o nuove build Web; nessuna installazione, push, deploy,
invio manuale, modifica sorgenti applicativi, API o configurazione cloud.
Non eseguiti nuovamente suite/test di build: artefatto immutato e verifica browser
sono il perimetro di questa attività. Questi documenti restano locali sul ramo release.

## Evidenze

[Indice sanificato, hash e risultati](evidence/web-0.1.15-300036-final-20261023/verification.json).
Screenshot, alberi accessibili e helper di sola lettura sono nell'archivio locale
ignorato `release-artifacts/web-candidates/verification-300036-final-20261023/`;
non aggiungere a Git dati locali o alias presenti nelle schermate Impostazioni.
Il fascicolo originale della candidata resta immutato.
