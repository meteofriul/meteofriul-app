# Segnalazioni: candidata TEST minificata del 15 ottobre 2026

## Ambito e identità

Preparazione e verifica della TEST, con autorizzazione esplicita all'aggiornamento
del Galaxy A52 tramite `adb install -r`. Promozione a main locale subordinata ai
controlli. GitHub, Play, AAB e distribuzioni cloud sono esclusi da questo lavoro.

- Ramo di integrazione: `codex/community-reports-simplification`.
- Main di partenza: `cab4871e8fe4f61014b0c9f8eb7d82b6b4b7ad0c`.
- Codice della candidata finale: `d72329509c1a423b887659086c67e15361364ccf`.
- APK: `build/android-test/2026-10-15/MeteoFriul-TEST-d7232950-R8.apk`.
- SHA-256: `181e526d88e683190387e7d05dec1fd651d2e85ba9b1e3cf431991a267a6a352`.
- Package `com.meteofriul.app.localpilot`, versione `0.1.14-local-pilot-r8`,
  versionCode 300031, min SDK 24, target SDK 36, firma debug di TEST.
- Minificazione e resource shrinking **attivi**, `debuggable=false`.
  Il debug della WebView rimane disponibile nella configurazione isolata TEST.
- L'APK riletta dal telefono ha lo stesso SHA-256. I package ufficiale e
  `com.meteofriul.app.tester` conservano versione e `lastUpdateTime` precedenti.

I documenti precedenti rimangono resoconti storici, non lo stato della candidata
attuale. Questo documento aggiorna
[il collaudo del 14 ottobre](COMMUNITY_EVENTS_ANDROID_TEST_2026-10-14.md).

## Modifiche e integrazione Eventi

La UX approvata resta compatta: «Recenti» espande il pannello, elenco con numero
di osservazioni, tempo trascorso e stato; riscontri «Conferme» e «Non c'è più» nel
dettaglio. Nel profilo la spiegazione di sentinelle, alias e punti è raccolta
nell'icona informativa, chiusa inizialmente. Corretto il tasto Android Indietro:
chiude l'informativa senza uscire anche dalle Impostazioni (`48fc1b5f`).

Le regole rimangono quelle approvate: 3 minuti fra invii, quote esistenti 4/ora
e 12/giorno, una osservazione attiva per installazione, 60 minuti di validità,
storico 48 ore. Un punto dopo validazione esterna; nessun tetto giornaliero ai
punti, attesa di 3 ore dall'ultimo premio per autore/fenomeno/Comune, nessun punto
per «tranquillo» o per il solo voto. GPS recente per entrambi i riscontri.
Voti precedenti non si trasferiscono al nuovo contenuto.

Main Eventi è stato integrato nel ramo prima della build (`73dcf15e`).
`backend/app/events` è identico a main: comprende Spazzapan e il recupero delle
quarantene già distribuiti e verificati nel
[ciclo Cloud Run](EVENTI_QUARANTENE_DEPLOY_2026-10-15.md).
Nessuna nuova distribuzione o esecuzione del job in questo collaudo Android.

La TEST usa Community SQLite locale su 8783 ed Eventi locale su 8784, entrambi
`published: false`, con `adb reverse`. Il catalogo Eventi è la copia del ciclo
verificato del 15 ottobre, snapshot `2026-10-15T17:07:52.543611+00:00`, SHA-256
`4cecfaeadc84d1a52fb614f143c7278a0e06c90ab6eae4ee45c21021ed0f27fc`.
Il collaudo non usa righe dimostrative QA. Sul telefono: 57 eventi del giorno e
dettaglio Giovanni Veronesi a Cinemazero, fonte TurismoFVG, leggibili.

Il meteo usa ancora la fixture locale del 4 settembre: «Meteo non disponibile»
non è un esito sul meteo corrente. Questa TEST richiede PC, servizi locali e
collegamento ADB; non è l'APK autonoma destinata alla distribuzione.

## Verifiche funzionali e conservazione dati

Le osservazioni e i voti sono reali nel database **TEST locale**. Nessuna scrittura
diretta nel database, manipolazione dell'orologio o sostituzione JavaScript del
GPS. Coordinate degli emulatori fornite attraverso la console Android; sul
telefono usato il GPS reale. Le letture SQLite di controllo omettono identificativi
delle installazioni e coordinate.

| Prova | Riscontro |
| --- | --- |
| Invio Pioggia dal telefono, build R8 intermedia `a403ed9f` | Ricevuta e scadenza 60 minuti; inviate 2 → 3, punti ancora 2 |
| Conferma da API 36, stessa build R8 intermedia | Conferme 0 → 1; autore 3 inviate / 3 confermate / 3 punti; confermante invariato a 2 punti |
| Aggiornamento alla finale `d7232950` | Alias Cjampane dal Cîl, contatori 3/3/3 e storico conservati |
| «Non c'è più» da API 35 sulla finale | Riscontri 0 → 1, conferme ancora 1; autore ancora 3 punti. Il marcatore scompare solo al votante, non viene ritirato globalmente sotto la soglia di 3 |
| GPS mancante/non disponibile | Il voto è rifiutato senza cambiare i contatori; ripetuto con fix fresco nativo (5 m) e riuscito |
| Storico reale sul telefono | Righe di 24 e 46 ore con conteggio; dettaglio scaduto con conferme e riscontri, nessun comando di voto |
| Informativa e Indietro | Apre, chiude solo l'informativa e lascia le Impostazioni; test di regressione automatizzato e prova nativa |
| Background, reload e avvio a freddo sul telefono | Profilo e tema conservati; avvio finale con UI pronta in circa 2,3 secondi |
| Tastiera sul telefono | Campo Comune utilizzabile; inset inferiore 48 → 0 con tastiera, poi ripristinato a 48; nessuna località modificata |

La candidata finale differisce dall'intermedia solo per la chiusura
dell'informativa e il contrasto nativo Android 15: logica delle regole, bridge GPS,
invio e assegnazione punti sono identici. La nuova build minificata è comunque
installata e provata sui dispositivi indicati, con ulteriori voti e letture reali.
Le durate limite, i conteggi raggruppati maggiori di 1, gli invii concorrenti e
la paginazione sono coperti dai test automatici; non sono simulati come attese
manuali di ore sul telefono.

## Quattro aree Android

### Edge-to-edge e barre

La combinazione problematica API 35/sistema chiaro è riprodotta prima della
correzione: tasti scuri sul fondo blu. Nel ramo dedicato
`codex/android-test-bar-contrast`, commit `efc10ba7`, Android 15 in modalità
diurna usa una superficie nativa chiara con richiesta esplicita di icone scure.
La barra di stato resta blu. Le altre versioni mantengono le superfici precedenti.
I richiami di configurazione vengono applicati dopo quelli di Capacitor.

Su API 35 le sei combinazioni dei tre tasti passano: contrasto osservato circa
8,76:1 in modalità diurna e almeno 8,94:1 in modalità notturna. Verificati anche i
gesti nei due temi sistema e tre temi app. Su API 36 verificate le stesse 12
combinazioni; sul Galaxy A52 le sei combinazioni con i tre tasti. I rapporti
pixel sono un supporto alle schermate native, non una prova isolata di tutta
l'accessibilità. Nessun overflow orizzontale nei casi registrati.

### API deprecate

Nessun setter deprecato dei colori delle barre nel codice applicativo e nessun
opt-out edge-to-edge. L'analisi DEX dell'APK finale trova **due chiamate residue**:
`setStatusBarColor` e `setNavigationBarColor`. Il mapping R8 le attribuisce al
metodo `androidx.core.view.WindowCompat.enableEdgeToEdge` di Core **1.17.0**,
fuso in `j3.a.r`. Il nome della classe contenitore offuscata, da solo, sarebbe
fuorviante. Non risultano chiamate a `setNavigationBarDividerColor`.

Le chiamate di compatibilità della dipendenza sono mantenute; non si sostituisce
alla cieca la funzione AndroidX. Activity 1.11.0, AppCompat 1.7.1. L'eventuale
avviso Play del prossimo bundle rimane **NON VERIFICATO**, perché nessun bundle
è stato generato o caricato.

### Orientamento e geometria

Telefono a schermo intero verticale, nessuna impostazione di rotazione aggiunta.
Manifest senza blocco portrait globale, Activity ridimensionabile. Verificati
320/360 dp, tablet 800 × 1280 e 1280 × 800, cutout laterale nei due versi e
Home/Meteo/Eventi/Scopri/Impostazioni. I risultati specifici e le schermate sono
conservati nelle evidenze; dimensioni simulate non equivalgono a un pieghevole
fisico.

Su API 35 eseguito vero schermo diviso con Impostazioni Android, confermato da
`mLastReportedMultiWindowMode=true`; rotazione e ridimensionamento della finestra
con lista selezionata conservata. A finestra bassa il contenuto scorre nel
contenitore `main`: verificato che «Segnala meteo» possa arrivare sopra la barra
di navigazione. Un semplice `window.scrollTo` non verifica questo scorrimento.

Le simulazioni che cambiano **densità** riavviano la WebView prima di misurare:
la WebView vecchia può conservare temporaneamente le metriche precedenti.
Le rotazioni e il ridimensionamento multi-window sono invece eseguiti durante
l'uso, senza alterare gli inset CSS manualmente. La rotazione dei telefoni è
stimolata via ADB sul dispositivo reale e sugli emulatori, non tramite una
rotazione fisica effettuata dal proprietario. La Activity resta verticale.

Matrice numerica finale API 36: **53 casi**, tutti con pagina e navigazione
entro gli inset; API 35: **22 casi compatti/rotazione** conservati nel JSON,
oltre alle schermate tablet e alle prove native di schermo diviso. Su API 36
verificati anche selezione Pioggia con GPS e pagina «Controlla e invia» nei due
orizzontali, senza eseguire un ulteriore invio. Tastiera, background e reload
finali su API 36 preservano profilo e inset. Non viene dichiarata una prova di
ogni combinazione cartesiana possibile su ogni modello fisico.

### R8 e risorse

Ramo dedicato `codex/android-test-minified`, integrato nella candidata. Aggiunta
la modalità facoltativa `-Minified` al builder isolato TEST e verifica Gradle
del package, firma, debuggabilità e shrinking. Usati profilo ottimizzato e keep
rule della release. AGP **8.13.0** con
`android.r8.optimizedResourceShrinking=true`: pipeline ottimizzata disponibile
ufficialmente già su AGP 8.12/8.13
([guida Android](https://developer.android.com/topic/performance/app-optimization/enable-app-optimization)).
Nessun aggiornamento di toolchain in questo
collaudo; il lavoro AGP 9 rimane sul ramo separato già esistente.

Configurazione, mapping, simboli, assenza di keep troppo ampie, metadati permessi
Capacitor e stack trace: PASS. Mapping, configurazione, risorse, seeds e usage
associati al SHA dell'APK sono archiviati. Build e compilazione dei test nativi
PASS; i test Android strumentati sono **compilati, non eseguiti**. Le prove
runtime qui registrate operano invece sull'APK minificata effettiva.

Bridge App, Geolocation, SystemBars e controllo permesso notifiche rispondono
sulla TEST. Su API 36 verificato anche il dialogo nativo delle notifiche e il
passaggio `prompt` → `granted` dopo «Allow». La consegna push Firebase di produzione, App Check, worker e
pubblicazione Play non sono certificati da questa identità locale: rimangono
controlli della candidata di distribuzione prima di una futura AAB autorizzata.
Il controllo sul permesso notifiche non viene presentato come consegna push.

## Ambienti, limiti e prove automatiche

| Ambiente | Identità |
| --- | --- |
| Telefono | Galaxy A52 SM-A525F, Android 14/API 34, WebView 155.0.8059.43, 1080 × 2400, densità 420 |
| Android 15 | AVD MeteoFriul_R8_Opt_API35, google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys, WebView 124.0.6367.219 |
| Android 16 | AVD MeteoFriul_Community_API36, google/sdk_gphone64_x86_64/emu64xa:16/BE2A.250530.026.D1/13818094:user/release-keys, WebView 133.0.6943.137 |

Durante l'avvio iniziale dell'emulatore API 36, con forte carico e aggiornamenti
delle app Google, sono presenti ANR della TEST **e di Google Foto**. Non sono
cancellati dai risultati. Dopo assestamento e arresto di Play Store nel solo
emulatore, nuovo avvio a freddo riuscito (Activity circa 10,5 s, UI pronta dopo
altri 7,2 s). Usato un solo emulatore alla volta e arrestato il daemon Gradle
dopo la compilazione. Le prove successive e i log finali vanno valutati insieme
a questo limite dell'ambiente, senza dichiarare «zero ANR nella sessione».
Nel controllo successivo dalle 18:37:42 UTC, 27.385 righe di log conservate
non contengono nuovi ANR o errori fatali. Questo è un controllo delimitato,
non una garanzia di assenza di problemi in ogni condizione di carico.

- Backend regole, confini, SQLite, reputazione e API: 82 test + 27 subtest PASS.
- Frontend integrazione Community/profilo/layout: 103 test in 11 file PASS.
- Correzione Back e regressioni collegate: 23 test PASS.
- Controlli finali nativeSystemBars/shell/inset/layout/informativa: 20 test PASS.
- Release guard: 9 PASS; guard Android localPilot: 7 PASS.
- Contratto R8, compilazione nativa, build finale e pulizia workspace: PASS.

I gruppi di test possono sovrapporsi: non se ne sommano i conteggi come test
unici. Nessuna CI remota richiesta: GitHub escluso esplicitamente dal proprietario.

## Evidenze e stato della promozione

Evidenze versionate in [evidence/community-final-2026-10-15](evidence/community-final-2026-10-15),
con inventario e SHA-256. APK e mapping completo sono conservati anche nella
directory locale ignorata `build/android-test/2026-10-15/`. Nella stessa directory,
`runtime-evidence.zip` conserva tutte le schermate per caso; il suo hash è in
`candidate.json`. Una selezione rappresentativa è anche versionata direttamente.
I file testuali versionati sono normalizzati a LF; i log originali sono
conservati nell'archivio completo, separatamente dai checksum delle copie leggibili.

**Esito: PASS per la promozione dei sorgenti a main locale nell'ambito richiesto.**
Controlli applicabili della TEST completati, con limiti e differenze dalla futura
candidata di distribuzione dichiarati sopra. L'allineamento locale deve essere
un avanzamento da `cab4871e` al commit che contiene questo resoconto, senza
checkout del runtime canonico, push o modifica degli asset privati ignorati.

Questa promozione non certifica la scomparsa degli avvisi Play, non promuove il
ramo AGP 9 e non autorizza AAB, pubblicazione, deploy Community o installazione
dell'app ufficiale. I controlli della distribuzione restano un passaggio separato.
