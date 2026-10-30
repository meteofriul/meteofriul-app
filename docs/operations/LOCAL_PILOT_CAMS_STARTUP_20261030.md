# Avvio locale e continuità CAMS — 30 ottobre 2026

Intervento locale necessario alla riaccensione dei servizi dopo lo spegnimento
del PC. Ramo dedicato `codex/local-pilot-cams-startup-20261030`, da main
`9f81253e`. Il ramo di lavoro da ripristinare è
`codex/mercati-integration-20261028`, salvato a `1936d8c7`; Orto resta conservato
in `codex/scopri-orto-preview-20261028` a `c27df16b`.

## Blocco riprodotto

Il preflight canonico `start-local-weather-pilot.ps1 -WeatherCloud` fallisce
sia in sandbox sia fuori dalla sandbox. Node 22.17.1 e npm 10.9.2 sono corretti.
Il controllo `Test-CamsFamilyArtifacts -RequireCurrent` ammette solo le 30 ore
originarie e non legge l'estensione pubblicata, già supportata dal client.

Letture HTTP del 30 ottobre intorno alle 07:01 Europe/Rome, tutte in sola lettura:

- ICON `20261029T120000Z`, utilizzabile fino al 30 ottobre alle 12:00 UTC.
- Famiglia CAMS `20261029T000000Z`, pubblicata il 29 ottobre alle 10:00:57 UTC.
  Manifest v1 invariati, limite originario 30 ottobre alle 06:00 UTC.
- `families/cams/runs/20261029T000000Z/continuity.json`: HTTP 200,
  policy `cams_continuity_36h_v1`, utilizzabile fino al 30 ottobre alle 12:00 UTC.
  Binding dichiarato alla release di 963 byte, SHA-256
  `46aa1716ab9f77e8499cc8041985dfc5233eab788687422bcc61ed24c08da16b`.

Questo riscontro riguarda documenti pubblici e avvio locale: non certifica
l'esecuzione di un job né la disponibilità di tutti i campioni comunali.

## Correzione e verifica

Il solo controllo di avvio riconosce ora la continuità esplicita CAMS,
preservando verifiche di identità, revoca, hash, manifest e scadenza. Dopo le
30 ore richiede il documento canonico completo e legato alla release verificata;
oltre le 36 ore rifiuta comunque l'avvio. Nessuna estensione implicita, nessun
orologio simulato e nessun fallback a snapshot storici per questa riaccensione.

- Contratti esistenti del launcher, con toolchain esplicita: 59 asserzioni PASS,
  exit 0; revisione indipendente di `build_verifica` senza rilievi bloccanti.
- Preflight reale `-WeatherCloud -NodeDirectory <toolchain prescritta> -CheckOnly`:
  PASS dopo la correzione, oltre le 30 ore della famiglia corrente. Node
  22.17.1 e npm 10.9.2 confermati; nessun processo avviato da questo controllo.
- Test comportamentali CAMS aggiuntivi: 34 asserzioni PASS, con grant valido
  oltre le 30 ore, limiti temporali, revoca, alterazioni, errore HTTP, grant
  mancante, integrità di release e manifest, percorsi legacy/offline.
  Rieseguiti e revisionati da `build_verifica`; 93 asserzioni totali.
- Avvio tramite launcher canonico con gli stessi argomenti, senza `-CheckOnly`:
  PASS; record PID obsoleti dello spegnimento recuperati dal launcher.
  Backend 8002 e frontend 5174 sani, riconoscibili e limitati a loopback.
- HTTP `http://127.0.0.1:5174/`: 200; `/api/healthz` tramite frontend:
  `status=ok`, `local_weather_pilot_ready=true`, `open_meteo_enabled=false`.

La correzione viene conservata nel ramo dedicato e riportata nel ramo Mercati
per riprendere il lavoro salvato. I controlli HTTP non sostituiscono la prova
visiva Mercati, che resta aperta insieme alla revisione friulana.

## Confini

Nessuna modifica dei dati o dei servizi cloud, dei job, delle pianificazioni,
dei pacchetti Android/Web o delle pubblicazioni. Nessun push o promozione a
main nel passaggio iniziale di riaccensione. Nessuna nuova verifica visiva o
su dispositivo dichiarata per il launcher. La successiva promozione dei
sorgenti del prerequisito CAMS è inclusa nell'allineamento autorizzato del
[ramo Home](HOME_EDITORIAL_TYPOGRAPHY_20261030.md); PR e CI sono tracciate lì.
