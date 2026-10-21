# 0.1.15 / 300033 — verifica reale dopo aggiornamento Play

**Esito: promozione sospesa per configurazione nativa assente nel bundle.**
Le principali funzioni provate sul Galaxy funzionano, ma questo non chiude la
qualifica Android della release. Nessuna modifica al codice, nuova AAB,
installazione dell'agente, deploy, push, invio manuale o promozione a main.

## Identità e perimetro

- Data: 21 ottobre 2026, sessione sul telefono circa 18:00–18:16 Europe/Rome;
  successiva ispezione locale del bundle e delle sorgenti.
- App ufficiale `com.meteofriul.app`, **0.1.15 / 300033**, aggiornata dal
  proprietario via Play Store (`com.android.vending`), non APK debug/TEST.
- Sorgente compilata: `f82503e4daabc283a5caf77b49e7cf58439abf61`.
- SHA256 AAB: `cb461c8e5e6fddd05407214a507e151e02e8041f403d9346c364bbe0174ba019`.
- Samsung Galaxy A52 SM-A525F, Android 14 / API 34; target 36; 1080×2400,
  420 dpi, navigazione a tre pulsanti. WebView 155.0.8059.43 invariata.
- Tema di sistema scuro invariato; temi dell'app chiaro/scuro e italiano/friulano
  provati. Nessuna variazione di densità, orientamento, renderer o permessi OS.

La [ricevuta strutturata](../../release-history/android-preparation/0.1.15-20261021/device-verification.json)
lega controlli, hash degli APK installati, immagini, gerarchie e limiti.
Le precedenti ricevute di build e accettazione Play restano immutabili:
la presente integra il [verbale di preparazione](ANDROID_0.1.15_BUILD_20261021.md).

## Risultati funzionali

| Controllo | Esito e limite |
| --- | --- |
| Avvio, ritorno dal background, riapertura | PASS; selezione della previsione mantenuta. Nessun crash o ANR nei log acquisiti |
| Indietro Android | PASS: dettaglio Eventi torna alla lista; chiude i dialoghi; dalla Home esplicita esce al launcher |
| Previsioni FVG e nazionali | PASS: Pordenone e Roma caricate. A Roma UV/CAMS non disponibili nel contratto nazionale attuale; non classificati come regressione |
| Previsioni chiaro/scuro, IT/FUR | PASS nel campione: giorni uniformi, giorno/ora selezionati con contorno coerente, pioggia e quantità leggibili, nomi completi |
| Dettaglio orario | PASS: dialogo e grafici, ritorno alla previsione |
| Allerta FVG | PASS: dicitura «in FVG», livello arancione, validità e dettaglio delle zone; collegamento al bollettino |
| Community | PASS limitato a mappa, scelta, conferma IT/FUR, No/Sì e richiamo 112; No torna alla scelta, Indietro annulla. Nessun invio |
| Eventi | PASS: catalogo reale, immagine e fonte nel dettaglio, ritorno alla lista |
| Ricerca località | PASS: un comando di cancellazione nel campo, distinto dalla chiusura del dialogo; tastiera, selezione Roma e ripristino località |
| Aria, pollini, Sole/Luna, UV | PASS di visualizzazione FVG; dettagli caricati. Non equivale a una nuova attestazione dei job CAMS |
| Webcam e Scopri | PASS: catalogo e immagine Sacile con data/ora caricati, contenuti Scopri |
| Sponsor | DISATTIVATI: lettura configurazione `enabled=false`, zero campagne, revisione 117; nessuna attivazione di pannello o allineamento dati |
| Permessi e ambiente durante i test | PASS limitato alla sessione: 16 confronti invariati fra due letture entrambe successive all’aggiornamento. Non prova la conservazione delle preferenze attraverso l’aggiornamento Play |

La scelta temporanea di Roma disattiva la localizzazione automatica per progetto.
A fine prova sono ripristinati Pordenone, italiano, tema chiaro, localizzazione
attiva anche ad app chiusa e preferenze di notifiche originali. Nessuna
cancellazione di dati/cache, revoca di permessi o reinstallazione. App lasciata
sulla Home. Il controllo di preservazione confronta l'inizio e la fine di questa
sessione: non è una misura di ogni dato precedente all'aggiornamento Play.

## Segnalazione LOCATION-UPDATE-01 — posizione spenta dopo aggiornamento

Il proprietario ha precisato: **la posizione nell'app era disattivata subito
dopo l'aggiornamento Play e prima dei test dell'agente**. È una segnalazione
aperta sulla persistenza della preferenza durante l'aggiornamento; causa
non determinata. La successiva scelta di Roma durante i test non spiega
un'osservazione precedente alla sessione.

Distinguere tre stati: permesso Android di accesso alla posizione, servizio
Posizione del sistema e interruttore di localizzazione automatica dell'app.
Il permesso concesso non prova che gli altri due siano attivi. Le letture
`before.json` e `final.json` iniziano entrambe dopo l'aggiornamento Play:
il confronto dei permessi riguarda soltanto la sessione di test.

La prima gerarchia delle impostazioni acquisita dall'agente
(`settings-before.xml`) mostra già «Disattiva Posizione» e «Attiva anche ad app
chiusa»; quella finale mostra lo stesso. Questa rilevazione successiva non
confuta l'osservazione del proprietario subito dopo l'aggiornamento. Il passaggio
fra i due momenti non è documentato e non si presume una riattivazione da parte
del proprietario o dell'app.

Esito corretto: **permessi Android concessi durante i test; conservazione
dell'interruttore dell'app attraverso l'aggiornamento NON VERIFICATA**, con
segnalazione del proprietario da indagare. Non attribuire questo comportamento
al file Capacitor mancante senza una prova del collegamento.

La verifica futura richiede una lettura della preferenza prima di un
aggiornamento autorizzato e subito dopo, prima di interagire con ricerca o
localizzazione. Nessuna reinstallazione, modifica di preferenze o nuova prova
sul telefono effettuata per questa rettifica.

## Difetto bloccante NATIVE-CONFIG-01

Il log dell'app installata contiene `Unable to load capacitor.config.json`
con `FileNotFoundException`. Nell'AAB identificata sopra manca realmente
`base/assets/capacitor.config.json`; il registro `capacitor.plugins.json` esiste.
Il file sorgente `frontend/capacitor.config.json` è invece presente.

Il percorso di build in `scripts/build-play-aab.ps1` esegue `cap update android`
per il registro plugin e copia gli asset Web generati nella cartella `public`,
ma non materializza la configurazione Capacitor negli asset Android. MainActivity
non fornisce una configurazione alternativa. Il punto mancante è quindi nella
preparazione del pacchetto, non nell'installazione effettuata dal proprietario.

La differenza ha effetti funzionali: il sorgente chiede
`SystemBars.insetsHandling=disable`, mentre Capacitor senza configurazione usa
`css`; anche lo stile iniziale passa da `DARK` a `DEFAULT`. Il plugin proprietario
MeteoSystemBars gestisce già le variabili CSS delle safe area. Il rischio di
interferenza va chiuso; **non è stata osservata una rottura degli inset sul Galaxy
API 34**, e non si deduce una rottura certa sulle altre versioni Android.

Compare anche `res/xml/config.xml is missing!` nel parser Cordova. Il file
esiste nei sorgenti; il nome originale non appare nel bundle. Questo secondo
riscontro richiede una verifica dedicata delle risorse e dell'uso Cordova:
non si attribuisce senza prova la causa allo shrinking, né si dichiara innocuo.

Confronto locale limitato: l'AAB archiviata **0.1.11 / 300028** contiene entrambi
i file ai nomi originali. Non è un confronto con la versione Play immediatamente
precedente e non dimostra da sola quando sia nata la regressione.

Prima di un nuovo artefatto occorrono sincronizzazione della configurazione e
guardie sul contenuto finale, quindi ripetizione della verifica release.
Non nascondere gli errori nei log. **300033 non va sovrascritto o rigenerato:**
una nuova AAB richiede autorizzazione e un nuovo versionCode secondo il runbook.

## Rilievo grafico BULLETIN-MAP-01

Nella mappa del bollettino le gocce dell'icona in Carnia si sovrappongono
all'etichetta della temperatura a 1000 m. Visibile nelle prove chiara e scura.
È un difetto di disposizione grafica distinto dalla configurazione nativa.
Non corretto in questa sessione di verifica.

## Le quattro aree Android e ciò che resta aperto

| Area obbligatoria | Stato della prova corrente |
| --- | --- |
| Edge-to-edge / inset | UI leggibile su API 34 con tre pulsanti e tastiera, ma configurazione nativa FAIL; API 35/36 e gesti non verificati |
| API deprecate delle barre | Nessuna nuova attestazione: i rilievi statici e delle dipendenze del verbale build restano aperti; nessun crash non significa assenza di deprecazioni |
| Orientamento / ridimensionamento / schermi grandi | Attività richiede portrait sul Galaxy; rotazione fisica, tablet e multi-window non provati |
| R8 / ottimizzazione risorse | Provato il pacchetto release minificato distribuito da Play; percorsi esercitati funzionano, ma gli errori di configurazione/risorsa impediscono di considerare chiusa l'area |

Nessun emulatore, in accordo al vincolo del proprietario. La copertura Android
15/16 richiesta dal runbook resta **NON VERIFICATA**, non implicitamente derogata.

Non eseguiti: nuova consegna push e apertura da notifica, invii/ritiro/voti
Community, schermata di successo dopo scrittura reale, tracciamento prolungato
in background, rete assente o degradata, verifica completa Play Integrity/App
Check. Permessi e indicazioni UI attivi non dimostrano quei percorsi.

## Salvataggio e prossima azione

Immagini, gerarchie, log privati e ricevute grezze copiati senza rimuovere gli
originali in `release-artifacts/android-play/verification-300033-20261021/`
nella radice canonica, esclusa da Git. L'indice locale contiene hash e dimensioni;
la ricevuta versionabile conserva l'hash dell'indice. Non versionare log,
alias, identificativi di dispositivo o schermate private.

La sessione di test non ha eseguito commit o push. Il successivo salvataggio
e allineamento documentale è stato autorizzato separatamente dal proprietario;
README e GitHub devono conservare l'esito parziale e i tre rilievi aperti.
La base runtime main della prova è `c329217b5df540299dad69016848f47cf703a5d0`:
un successivo commit di soli documenti non promuove il codice della release.
La PR 11 resta in bozza. [Stato corrente](RELEASE_0.1.15_STATUS_20261021.md).
