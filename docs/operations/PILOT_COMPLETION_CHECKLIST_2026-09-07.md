# Pilota — piano di completamento e confine con la beta chiusa

Aggiornato il 7 settembre 2026. Stato: lavoro da completare, non una release.

## Confine operativo

- Lavorare sulla pilota affiancata `com.meteofriul.app.localpilot`.
- Non aggiornare, disinstallare o cancellare i dati di `com.meteofriul.app`.
- Nessuna pubblicazione sul canale Play chiuso e nessuna promozione automatica
  del codice condiviso o dei cataloghi verso la beta.
- Backend, Firebase, job e configurazione della beta restano invariati.
- I servizi effettivamente condivisi non diventano isolati solo perché il client
  si chiama pilota: verificare l'endpoint prima di qualunque modifica remota.
- Build/installazione sul telefono, commit e deploy sono operazioni distinte;
  questo piano non le esegue e non ne attesta il completamento.

## Checkpoint per la prossima sostituzione — 14 settembre 2026

Il frontend corrente è già visibile nell'anteprima browser, mentre worker
allerte e nuova APK pilota non sono ancora distribuiti. La beta ufficiale deve
restare invariata. Identità delle revisioni, ordine delle operazioni e collaudo
end-to-end obbligatorio sono fissati in
[`PILOT_NEXT_REPLACEMENT_CHECKPOINT_2026-09-14.md`](./PILOT_NEXT_REPLACEMENT_CHECKPOINT_2026-09-14.md).

## Affidabilità e navigazione — stato dell'audit

- [x] Estremi giornalieri: accettare il recupero della corsa precedente anche
  quando la cache è già alla versione 2 ma contiene una giornata incompleta.
  Testare il passaggio parziale → arricchito con identità ICON invariata,
  preservando i controlli d'integrità e senza inventare minime o massime.
- [ ] UV: diagnosticare acquisizione e aggiornamento nel solo progetto pilota;
  distinguere successo del job CAMS da effettiva pubblicazione UV.
- [x] UV: mantenere l'ultimo dato valido in caso di errore temporaneo/offline,
  con data e scadenza esplicite; non presentare come attuale un dato scaduto.
- [x] Android: il tasto Indietro deve chiudere il dettaglio orario prima di
  cambiare pagina o uscire. Verificare sul Samsung, non soltanto nel browser.
- [ ] Allineare test e lint ai requisiti correnti senza rimuovere controlli utili;
  aggiungere prove interattive specifiche della pilota.

### Intervento e collaudo del 7 settembre, ore 23

- Cache giornaliera v2: il recupero verificato della corsa precedente può ora
  arricchire la giornata senza attendere una nuova corsa ICON. Le correzioni
  non sono perse al successivo errore di recupero. Controlli di identità,
  copertura e coerenza degli estremi mantenuti; nessun valore inventato.
- UV: cache locale validata e recupero in memoria, aggiornamento su riconnessione
  e ripresa dell'app, timeout e protezione dalle risposte fuori ordine. La
  scadenza resta legata alla corsa del modello, non al momento del salvataggio.
  Il comando di reset della pilota cancella anche questa cache.
- L'acquisizione UV cloud resta da diagnosticare: sul telefono il dato letto
  durante il collaudo riferisce ancora la corsa del 6 settembre alle 02:00
  locali. La resilienza del client non risolve la pubblicazione di nuove corse.
- Indietro nativo: un solo gestore, attivo esclusivamente nella pilota Android,
  con priorità alle schede sovrapposte e cronologia delle pagine in memoria.
  Integrati anche Impostazioni, ricerca località, dettagli eventi, webcam,
  editor di segnalazione, moderazione e informativa posizione. Durante invii
  in corso non si abbandona la schermata con lo stesso tasto.
- Verificato sul Samsung A52 `OWNER_DEVICE_SERIAL`: dettaglio orario → Meteo;
  Impostazioni aperte da Meteo → Meteo; Cerca → chiusura tastiera al primo
  Indietro, chiusura scheda al secondo, località invariata; dettaglio evento →
  lista Eventi → pagina Meteo precedente. Non attestati come collaudati sul
  dispositivo gli invii reali, i consensi, il player webcam o l'offline completo.
- Test frontend completi: 3139 superati, 6 saltati, 5 fallimenti già rilevati
  nell'audit precedente (AppRoutes, due test copy, EventsView, weatherForecastCss).
  Test mirati successivi per hook, cronologia e reset UV superati; 13 controlli
  build/API/pilota superati. Nessun errore lint nei file d'integrazione controllati;
  non è una dichiarazione di pulizia dell'intero lint del repository.
- APK ricompilato e installato con aggiornamento della sola pilota alle
  23:01:43: `1.0.1-local-pilot`, codice `300012`.
  SHA-256: `b2456a82eed9fee041ad92d0e81d8c0e4077992db2220e0956a1963b0aa5c306`.
  Percorso: `frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk`.
- Beta verificata dopo l'installazione: `com.meteofriul.app`, versione `1.0.1`,
  codice `300012`, ultimo aggiornamento ancora `2026-08-30 00:41:28`.
  Nessun deploy Play/web/sito, modifica backend/job o commit in questo intervento.

### Swipe sezioni Meteo — intervento del 7 settembre, ore 23:22

- [x] Rimosso il cambio sezione tramite swipe dalla sola pilota. La shell
  conserva layout e contenuti senza installare handler touch; Previsioni,
  Bollettino e Territorio restano accessibili dai tre pulsanti. Il blocco
  navigazione durante invio resta rispettato. Nessuna modifica alle gesture
  proprie di ore, mappe o player, né allo swipe del ramo non pilota.
- Motivo: le numerose aree interattive escluse rendevano lo swipe discontinuo;
  inoltre il selettore originale non esclude il tag `dialog` nativo, soltanto
  `[role=dialog]`, permettendo cambi pagina dal dettaglio orario.
- [x] 34 test mirati passati: composizione delle route, shell, pulsanti,
  cronologia, Indietro nativo e dettaglio orario. Nessun nuovo errore lint;
  restano i due errori preesistenti di AppRoutes (setRadius inutilizzato e
  setState in un effect) e il warning Fast Refresh preesistente della shell.
- [x] Samsung A52: swipe orizzontale non cambia nessuna delle tre sezioni;
  la striscia oraria scorre da 23:00 a 03:00; il popup orario resta aperto
  dopo swipe sui contenuti; Indietro lo chiude; i pulsanti aprono Bollettino
  e Territorio. Nessuna segnalazione o richiesta di consenso eseguita.
- Nuovo APK pilota installato alle `2026-09-07 23:22:28`, SHA-256
  `6c069b0122458567e5056e8b908a41fcf6ba0bbc401baad2a1e2363f4d82f5c0`.
  Beta ricontrollata: ultimo aggiornamento ancora `2026-08-30 00:41:28`.
  Nessun commit o deploy remoto.
- [ ] Verificare separatamente il pull-to-refresh dentro i dialoghi nativi:
  anche il suo selettore non include `dialog`. Questo potenziale conflitto
  verticale non è risolto dalla rimozione dello swipe orizzontale fra sezioni.

### Comuni rapidi — modifica del 7 settembre, ore 23:34

- [x] Nella pilota i collegamenti rapidi sono Udine, Trieste, Gorizia e
  Pordenone (al posto di Tarvisio), sempre visibili anche quando uno è attivo.
  Capoluoghi non duplicati nei Recenti, inclusi i record legacy senza ISTAT;
  frazioni distinte e dati salvati conservati. Ramo beta invariato.
- [x] Verifica visiva locale a 528 px con Pordenone attiva e ricerca Tarvisio
  ancora disponibile. 28 test mirati, lint e diff check superati.
- Modifica presente nel codice e nell'anteprima locale; non è stata ricompilata
  o reinstallata sul telefono in questo intervento. Entrerà nel prossimo APK.

## Home — proposta da confermare

- [ ] Rimuovere la fascia `Dati meteo locali` sotto la scheda principale, poiché
  duplica i dettagli disponibili nelle Previsioni. Conservare condizioni,
  temperatura e percepita; non rimuovere eventuali avvisi importanti.
  L'utente ha chiesto un parere: la fascia non è stata modificata in questo
  intervento. La riduzione di altezza non garantisce assenza di scorrimento
  su ogni telefono o dimensione dei caratteri.

### Allerta nella card Bollettino — verifica del 7 settembre

- [x] Verificati icona e messaggio con il percorso runtime completo della
  pilota locale, senza modifica al codice applicativo: una risposta simulata
  di `/weather/official-alerts` sostituisce la card Sintesi della Home con
  Allerta ufficiale, triangolo colorato, livello, testo, fonte e validità.
- [x] Il tocco apre il Bollettino all'ancora `official-alerts`: allerta completa
  prima della mappa. Nella Home il testo è sintetizzato su due righe, nel
  Bollettino è integrale. L'allerta è regionale FVG, non filtrata per comune.
- [x] Sette scenari nel browser isolato: gialla e arancione IT a 528 px,
  rossa FUR a 528 px, arancione IT a 360 px, arancione FUR in tema scuro,
  nessuna allerta e allerta scaduta. Nessuna sovrapposizione icona/testo né
  overflow orizzontale; livelli inattivo/scaduto non generano una falsa card.
  In FUR il testo ufficiale italiano conserva la nota di traduzione in revisione.
- [x] 96 test mirati superati su wiring, card, Home, icone, runtime, cache,
  contratto allerte e presentazione del Bollettino.
- Confine della prova: simulazione riconoscibile nel testo, risposta intercettata
  soltanto nel profilo browser temporaneo; richieste mutative bloccate.
  Nessun allarme reale, push, modifica al feed, APK, beta o profilo aperto
  dell'utente. Questo verifica rendering e navigazione, non certifica l'arrivo
  futuro di una vera allerta dal fornitore né la consegna delle notifiche.
- Screenshot e risultati salvati fra gli artefatti locali Codex nella cartella
  `official-alert-qa-20260907`; la prova non usa il vecchio Lab, il cui modello
  Home contiene soltanto il livello e non un messaggio completo.

## Icona launcher — requisito aggiunto dall'utente

- [x] Eliminare l'effetto di doppia cornice: la risorsa foreground precedente
  contiene il master quadrato al 54% dentro un ulteriore fondo azzurro opaco.
  La sagoma del launcher Android si aggiunge a questa composizione già presente.
- [x] Separare correttamente sfondo a piena superficie e marchio in primo piano,
  conservando testo, colori e leggibilità del marchio nella zona sicura.
- [x] Rispettare `android/launcher-assets/README.md` e il README del pacchetto
  `pilot-092026-text`: non sovrascrivere gli originali inventariati e non usare
  ingrandimenti arbitrari via XML come correzione della doppia cornice.
- [x] Preparare e verificare una nuova variante esclusivamente pilota, con
  provenienza e inventario propri, prima di adottarla nel runtime.
- [x] Collaudare la vera icona sulla home Samsung, incluse forma e leggibilità;
  una compilazione riuscita non basta. Beta, icona Play e altri asset approvati
  restano invariati.

  Chiuso l'8 settembre: variante `pilot-092026-launcher-r2`, estrazione tecnica
  dal master originale autorizzata dall'utente. Confronto reale prima/dopo sul
  Samsung A52, APK installata alle 21:58:12. Evidenze e hash nel rapporto
  `PILOT_ANDROID_LAUNCHER_INSTALL_2026-09-08.md`.

## Scopri — requisito aggiunto dall'utente

- [ ] Calendario/Santo del giorno, memorie secondarie e cultura devono avere
  schede e contenuti essenziali sempre visibili, senza contenitori apribili.
  Non basta impostare `open` lasciando la possibilità di richiudere la sezione.
- [ ] Dare una gerarchia coerente a rubrica, titolo della scheda, testo e fonte;
  evitare che il titolo del contenitore ripeta quello della sezione interna.
- [ ] Eliminare i duplicati fra calendario, memorie, proverbi e tradizioni.
  Usare le identità dei contenuti e le corrispondenze IT/FUR disponibili,
  non soltanto confronti letterali del testo tradotto.
- [ ] Non ripetere il santo principale fra gli altri santi, anche in friulano;
  non mostrare divisori o contenitori vuoti nei giorni privi di altri contenuti.
- [ ] Gli eventuali comandi per approfondire testi lunghi non devono nascondere
  un'intera rubrica o scheda; preservare la sintesi della lista degli altri santi.
- [ ] Verificare IT/FUR, date con e senza altri santi e memorie secondarie,
  cambio giorno e località. Tenere distinto il rendering legacy della beta.

## Webcam — requisito aggiunto dall'utente

- [ ] Rivedere fonte, località, pagina specifica e raggiungibilità di ogni voce;
  distinguere foto territoriale di anteprima da un fotogramma della webcam.
- [ ] Integrare il video dove esiste una sorgente ufficiale tecnicamente
  compatibile e con incorporamento consentito. La raggiungibilità di un URL
  non dimostra il diritto di incorporarlo né l'assenza di costi per il titolare.
- [ ] Distinguere diretta video, clip, panorama interattivo e immagine aggiornata:
  non chiamare video/live una foto o un panorama.
- [ ] Fonte e collegamento originale sempre riconoscibili; se il video non è
  incorporabile, mantenere l'accesso esterno e un'anteprima chiaramente indicata.
- [ ] Caricare il player solo su richiesta, senza autoplay, preload di flussi o
  addebiti impliciti al proprietario; interromperlo quando la vista si chiude.
- [ ] Verificare privacy, errori, fullscreen e ripresa dell'app sul telefono.
- [ ] Riutilizzare gli audit webcam esistenti e aggiornare le evidenze datate;
  non cambiare il catalogo/backend condiviso per una prova esclusivamente pilota.

### Riscontri del controllo in lettura del 7 settembre

- Catalogo locale: 19 voci, tre snapshot configurate, nessun video. Nella risposta
  API locale controllata risultavano snapshot solo Sacile e Cividale; Udine era
  in fallback. Non è una verifica del catalogo della beta installata.
- Il player esistente gestisce soltanto due iframe Panomax di prova, subordinati
  a `import.meta.env.DEV`; non è un player video già utilizzabile nell'APK pilota.
- Il controllo `health` delle webcam non certifica freschezza del flusso,
  identità dell'inquadratura o permesso di incorporamento.
- [Lignano/Punta Faro](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro)
  dichiara una diretta nella pagina ufficiale; non è stata trovata una concessione
  pubblica all'incorporamento e non è stato avviato il flusso durante il controllo.
- I riscontri su [WhatsUpCams](https://www.whatsupcams.com/it/terms-of-use/),
  [Panomax](https://www.panomax.com/en/imprint),
  [IPCamLive](https://www.ipcamlive.com/faqs) e
  [RTSP.me](https://rtsp.me/en/payment-terms.html) non hanno individuato nuove
  fonti che soddisfino già i vincoli registrati di incorporamento consentito,
  non a pagamento e senza possibili costi al titolare.
- Per il launcher è stata verificata la risorsa pilota effettiva, non solo il
  master. Il difetto di composizione è distinto dalla normale maschera Android:
  [specifica ufficiale dei livelli adattivi](https://developer.android.com/develop/ui/compose/system/icon_design_adaptive).

## Sequenza di lavoro

1. Affidabilità dati/UV e regressioni di navigazione.
2. Launcher e riorganizzazione Scopri; verifica fonti webcam in parallelo.
3. Incorporamento delle sole webcam ammissibili e test mirati.
4. Collaudo della pilota sul telefono: avvio, offline, riapertura, cambio lingua
   e località, dialoghi, contenuti e media.

L'eventuale sostituzione della beta è fuori da questo piano e richiederà una
decisione esplicita dopo la conclusione del test chiuso.
