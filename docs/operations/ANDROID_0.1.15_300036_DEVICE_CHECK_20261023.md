# 0.1.15 / 300036 — verifica sul Galaxy dopo aggiornamento Play

**PASS dei percorsi osservati sul Galaxy; REALTIME-LAYOUT-01 risolto nel pacchetto ufficiale installato.**
Non è una qualifica completa di tutte le funzioni e piattaforme. La precedente
300035 resta documentata come FAIL: questa prova non ne riscrive l'esito.
Il proprietario ha aggiornato da Play e collegato il telefono. Nessuna nuova
installazione, build AAB, emulatore, push, merge, deploy, job o invio manuale.

## Identità ed evidenze

- Osservazioni: 23 ottobre 2026, circa 13:53–14:16 Europe/Rome.
- App ufficiale `com.meteofriul.app`, **0.1.15 / 300036**, installer
  `com.android.vending`; aggiornamento sul telefono alle 13:45:24.
- Sorgente AAB `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`, main incorporato
  `2d8b0c327204c5812bb67dbf203ed948812a445e`.
- AAB SHA256 `024212752b3af72f163d75849aa53c2b191ba0352e42423b11efccd2d7f8b51f`.
- Galaxy A52 SM-A525F, Android 14/API 34, target 36, 1080×2400, 420 dpi,
  navigazione a tre tasti; WebView 155.0.8059.43 invariata.
- Pacchetto minificato distribuito da Play, non APK debug/TEST o anteprima Web.

[Ricevuta e hash delle evidenze](evidence/release-0.1.15-300036-device-20261023/verification.json).
Screenshot, gerarchie, due registrazioni e log privati sono conservati nella
radice canonica, in `release-artifacts/android-play/evidence-300036/device-20261023/`,
ignorata da Git. La ricevuta non pubblica alias, token, identificativi del
telefono o coordinate. Il ramo release conserva separatamente il verbale
di [build](ANDROID_0.1.15_300036_BUILD_20261023.md) e quello di
[caricamento Play](ANDROID_0.1.15_300036_UPLOAD_20261023.md).

## Tempo reale

Mappa realmente visibile, con altezza utile e un piccolo distacco dalla barra
inferiore, in italiano/chiaro e friulano/scuro. Screenshot e gerarchia concordano:
i comandi Mappa/Segnalazioni/Webcam sono nell'area utile, non fuori schermo.
Il controllo è ripetuto dopo un avvio a freddo: il difetto della 300035 non ricompare.

- Mappa: tile e indicatore di località visibili, dock raggiungibile.
- Segnalazioni: lista vuota leggibile, coerente con il messaggio sulla mappa.
  Non essendoci segnalazioni nel campione, schede popolate e voti non sono verificati.
- Webcam: elenco e pin disponibili; apertura di Piancavallo – Panorama con
  immagine caricata; Indietro Android torna all'elenco.
- Radar: attivazione, legenda friulana e riproduzione verificati; l'orario passa
  da 14:00 live a 12:45 durante l'animazione. Nessuna precipitazione visualizzata
  nel campione: questo non verifica un caso con echi di pioggia né la loro accuratezza.
- Impostazioni: Indietro torna a Tempo reale senza uscire dall'app.

**REALTIME-LAYOUT-01 chiuso sulla 300036 nel Galaxy osservato.** Non equivale a
una verifica su tutte le dimensioni Android. Annotazione grafica separata:
il testo secondario «Nissune precipitazion rilevade» del radar scuro appare
molto attenuato; contrasto non misurato e nessuna modifica applicata in questa prova.

## Posizione e conservazione dello stato

Il proprietario conferma per la 300036: **«Sì, è rimasta attiva»**, riferendosi
allo stato subito dopo l'aggiornamento Play. È testimonianza del proprietario,
non una misura dell'agente eseguita prima dell'aggiornamento.

Preferenza Posizione attiva nell'app, servizio Android attivo e permessi
fine/coarse/background concessi sono verificati separatamente. Preferenza
conservata dopo 8 secondi in background e ripresa nello stesso processo, poi
avvio a freddo in un nuovo processo (tempo Activity dichiarato 2.181 ms).
Nessuna cancellazione di dati/cache o modifica dei permessi.

I **19 campi tecnici** prima/dopo sono invariati, inclusi versione, hash degli
APK installati, permessi, WebView e impostazioni di sistema. Italiano e tema
chiaro ripristinati; località predefinita, Posizione, Allerte e Avvisi invariati.
Telefono lasciato sulla mappa Tempo reale.

Il percorso ordinario supera la prova. Non sono indotti errori GPS temporanei,
timeout o errori di geocodifica; precisione e aggiornamento durante uno
spostamento non misurati. La causa dell'episodio storico della 300033 resta
distinta, come nell'[analisi Posizione](ANDROID_LOCATION_STARTUP_20261022.md).

## Aria e pollini

Card e dettagli reali leggibili in italiano e friulano, con unità e fonte CAMS.
Nel tema scuro/friulano sono leggibili anche le card completamente scorse.
Il cambio dell'ora durante la sessione cambia correttamente il campione:

| Ora del dato mostrata | PM2.5 | PM10 | O₃ | NO₂ | Graminacee |
| --- | --- | --- | --- | --- | --- |
| 13:00, dettagli IT | 7,5 | 11,1 | 60,5 | 9,9 | 0,26 |
| 14:00, rientro IT e card/dettagli FUR | 4,9 | 7,7 | 65,6 | 7,5 | 0,21 |

Inquinanti in µg/m³, pollini in grani/m³. Elaborazione mostrata 02:00; nel
dettaglio pollini sei specie, Artemisia 0,09 e le altre non dominanti <0,01.
Non si confrontano valori di ore diverse come se fossero lo stesso campione.
Questa è una verifica di lettura nell'app, non una nuova attestazione dei job CAMS.

Due registrazioni di rientro da Impostazioni, 12 secondi ciascuna, ispezionate
a 4 fotogrammi/s: nessuna falsa indisponibilità nei 48 campioni per lingua.
Con cache disponibile i valori arrivano subito. Il testo intermedio di
caricamento e i veri errori di rete non sono esercitati; nessun ritardo o
svuotamento cache imposto. Il campionamento non esclude un transitorio più breve
di 250 ms o in condizioni diverse. Restano le regressioni automatiche
[del transitorio CAMS](CAMS_REENTRY_LOADING_20261023.md).

## Sezioni e navigazione

| Sezione / percorso | Risultato osservato |
| --- | --- |
| Home | Meteo, Sintesi e anteprima Eventi visibili dopo avvio normale e a freddo |
| Previsioni | Card dei giorni uniformi, selezione giorno/ora coerente; scorrimento ordinario senza bloccare la barra delle previsioni; IT chiaro e FUR scuro |
| Bollettino | Entrata dalla Sintesi conserva località e menù; rimangono fissi nello scorrimento. Mappa con quote e località leggibili, senza precedente sovrapposizione |
| Tempo reale | Mappa, dock, lista segnalazioni, webcam e comandi radar come dettagliato sopra |
| Eventi | Catalogo reale, barra fissa durante lo scorrimento; dettaglio «PEOPLE, PLACES & THINGS» leggibile e Indietro torna alla lista |
| Scopri | Calendario, contenuto culturale e sezione del comune caricati e visibili |
| Impostazioni | Lingua/tema, stato delle preferenze e ritorno alla sezione precedente verificati; interruttori sensibili non modificati |

In Eventi un primo tentativo ha premuto una scheda già coperta dalla barra
fissa e ha selezionato Weekend: `event-detail`/`event-back` non provano il
dettaglio. La prova valida usa `event-detail-open`/`event-detail-back`, dopo
aver riaperto la lista e selezionato una scheda realmente visibile.
L'animazione radar non consentiva il dump UI inattivo: la riproduzione è
documentata con screenshot diretto, senza inventare una gerarchia concorde.

Non ripetuti su questa candidata: ricerca/località nazionale, form di conferma
Community e invio riuscito, voti, consegna notifiche, percorsi esterni dei link.
Le verifiche storiche restano distinte e non sono promosse a PASS della 300036.

## Nativo, log e quattro aree Android

Confrontati i **508 asset** dell'APK base installato con l'AAB: nessun file
mancante o diverso. Presenti configurazione Capacitor, registro plugin e
`res/xml/config.xml`; debug WebView spento e nessun server di sviluppo.
NATIVE-CONFIG-01 riconfermato chiuso per confezionamento e avvio sul Galaxy.

Nei due log raccolti (1.245 e 447 righe) nessun crash, ANR, errore JavaScript
non gestito o `net::ERR_`; assenti i precedenti errori di caricamento della
configurazione nativa. Le occorrenze `403` sono `res=0x403` del layout Android,
non risposte HTTP. Restano messaggi di Android/WebView su split senza dex,
media/Bluetooth, seed/feature flag e opt-in OnBackInvokedCallback: non risolti
né nascosti da questo verbale.

| Area obbligatoria | Prova e limite |
| --- | --- |
| Edge-to-edge / inset | Schermate portrait osservate senza sovrapposizioni con le barre di sistema su Android 14 a tre tasti; Android 15/16, gesti, cutout e tastiera non coperti |
| API system bar deprecate | Toolchain invariata; questa sessione non chiude gli avvisi delle dipendenze né sostituisce l'audit statico già nel verbale build |
| Orientamento / grandi schermi | Portrait osservato; rotazione fisica, tablet, multi-window e larghezze compatte non esercitati |
| R8 / risorse | Pacchetto ufficiale minificato verificato nei percorsi elencati, avvio a freddo e configurazioni presenti; non tutti i plugin e percorsi coperti |

Sponsor confermati `enabled=false`, zero campagne, revisione 117 prima/dopo.
Pannello e allineamento dati sponsor non attivati. Nessuna segnalazione o
notifica di prova inviata. Nessuna qualifica completa o pubblicazione in
produzione implicita: restano la matrice Android e i limiti sopra, la Web non
pubblicata e Safari/iPhone non verificato. Salvataggio locale nel ramo release;
commit, push e promozione restano azioni separate.
