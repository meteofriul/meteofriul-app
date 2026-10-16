# Audit pannello video ARPA/OSMER — 29 agosto 2026

> Seguito operativo: [revisione catalogo del 30 agosto](./WEBCAM_CATALOG_REVIEW_2026-08-30.md). Corrette le fonti locali e sospesa Aquileia; nessuna nuova incorporazione pubblica di player. I risultati qui sotto restano riferiti al controllo del 29 agosto.

## Scopo e vincoli

L'audit verifica in sola lettura le fonti elencate nel [pannello video ARPA/OSMER](https://www.osmer.fvg.it/webcam_img.php?ln=&video=on). Non contatta i proprietari, non scarica né conserva fotogrammi, non modifica il catalogo pubblico e non abilita player nell'app.

Il criterio editoriale concordato è restrittivo:

1. nessun servizio esplicitamente a pagamento per l'incorporamento;
2. nessun player che possa generare costi al proprietario a sua insaputa;
3. nessuna fonte rotta;
4. nessuna incorporazione quando i termini vietano o non autorizzano chiaramente framing e ripubblicazione;
5. in assenza di tutti i requisiti, soltanto foto locale e collegamento alla pagina esterna.

L'assenza di login o paywall per lo spettatore è un dato tecnico, non una licenza di riutilizzo.

## Esito

- Fonti rilevate: **49**, non 21.
- Player o stream turistici: **21** (15 WhatsUpCams, 4 RTSP.me, 2 IPCamLive).
- Clip autostradali A23: **28** MP4 di Autostrade per l'Italia.
- Fonti tecnicamente raggiungibili: **47/49**.
- Fonti non disponibili: **2** HLS (Aquileia — Basilica e Gorizia — San Mauro).
- Fonti che superano tutti i criteri per l'incorporamento pubblico senza contatti o accordi: **0**.
- Modifiche a `backend/app/data/webcams_active.json`: **nessuna**.
- Player caricati in beta o produzione: **nessuno**.

L'inventario macchina per macchina è conservato in [WEBCAM_OSMER_VIDEO_SOURCES_2026-08-29.csv](./WEBCAM_OSMER_VIDEO_SOURCES_2026-08-29.csv).

## Valutazione per famiglia

| Famiglia | Verifica tecnica | Costo o accesso | Decisione senza contatti |
| --- | --- | --- | --- |
| WhatsUpCams | 13 manifest HLS validi; 2 rispondono `404` | Nessun gate allo spettatore | Non incorporare: i termini non concedono a Meteo Friûl il framing/ripubblicazione. Foto locale e collegamento esterno. |
| RTSP.me | 4 player inizializzati | Ogni apertura può contare come visualizzazione fatturabile al titolare | Non incorporare né precaricare. Collegamento esterno soltanto se esiste una pagina pubblica specifica. |
| IPCamLive | 2 player inizializzati | L'embed è una funzione dei piani Standard/Professional | Escluso dall'incorporamento secondo il criterio “non a pagamento”. Collegamento esterno soltanto. |
| ASPI A23 | 28 MP4 da 15 secondi caricabili | Nessun login, chiave o paywall rilevato | Non ripubblicare: non è stata trovata una licenza pubblica esplicita. Conservare come ricerca; al massimo collegamento al servizio webcam ASPI. |

## Nota su ARPA/OSMER

OSMER è un catalogo utile, ma dichiara che le webcam sono gestite dai rispettivi proprietari e non dall'Agenzia. Le note legali distinguono inoltre la licenza generale del sito dai diritti di terzi e vietano la ripubblicazione dei dati in tempo reale prima di 24 ore senza deroga.

Per questo una fonte mostrata da OSMER non riceve automaticamente il diritto di essere incorporata in Meteo Friûl.

Riferimenti:

- [Pannello video ARPA/OSMER](https://www.osmer.fvg.it/webcam_img.php?ln=&video=on)
- [Note legali ARPA/OSMER](https://www.osmer.fvg.it/note-legali.php)
- [Termini WhatsUpCams](https://www.whatsupcams.com/fr/terms-of-use/)
- [Condizioni di pagamento RTSP.me](https://rtsp.me/en/payment-terms.html)
- [Protezione degli stream RTSP.me](https://rtsp.me/en/how-to-protect-stream-from-copying.html)
- [FAQ IPCamLive](https://www.ipcamlive.com/faqs)
- [Prezzi IPCamLive](https://web.ipcamlive.com/pricing)
- [Servizio webcam Autostrade per l'Italia](https://www.autostrade.it/it/webcam)

## Decisione operativa

Con il vincolo “non chiediamo autorizzazioni”, nessuno dei 49 URL entra nell'allowlist dei player e nessun flusso viene caricato, neppure in background. Le 47 fonti raggiungibili restano una ricerca tecnica in ombra e possono servire a individuare pagine esterne specifiche; le due fonti `404` sono scartate.

Un'eventuale anteprima DEV dei player non viene attivata in questa fase: RTSP.me può addebitare visualizzazioni al proprietario, IPCamLive richiede un piano per l'embed e WhatsUpCams non autorizza il framing di terzi. Il catalogo attivo continua quindi a usare foto locali e collegamenti esterni.
