# 0.1.15 — allineamento a main e preflight del bundle interno

> Verbale cronologico: le sezioni iniziali descrivono la preparazione.
> Stato attuale, verifica Play/Galaxy e rilievi aperti sono nel
> [riepilogo corrente](RELEASE_0.1.15_STATUS_20261021.md).

21 ottobre 2026. Il proprietario autorizza la generazione della AAB ufficiale,
non il caricamento su Play, installazioni, nuovi deploy o invii manuali.
Il canale previsto è il test interno riservato al proprietario; la restrizione
ai tester viene applicata in Play Console, non è una proprietà del file AAB.

## Sorgenti e identità

Ramo esistente `codex/release-0.1.15` allineato al main verificato
`c329217b5df540299dad69016848f47cf703a5d0` (CI 39619073997 verde).
I conflitti di documentazione sono risolti mantenendo le attestazioni più
recenti di main e le copie delle evidenze con la forma approvata dal controllo
privacy. La versione resta **0.1.15 / 300033**, package `com.meteofriul.app`.
Nessuna impostazione TEST viene trasferita nella variante ufficiale.

Rispetto a main, oltre alla preparazione della versione, sono conservate le
correzioni del preflight FVG già verificate sul ramo di deploy: contratto
writer `play-services-fvg-20261020.json` e controllo del digest esatto anche
quando una Cloud Build genera candidata e rollback. I test negativi continuano
a rifiutare digest mancante e archivio sorgente differente. Nessun job cambia.

Console Play riletta il 21 ottobre: massimo caricato **300031 / 0.1.14**,
in produzione e nei test interni. Nessuna release 0.1.15 caricata o creata.
Il registro locale viene verificato prima di riservare il nuovo codice.

Il builder richiede sorgenti pulite, salvate e allineate al ramo remoto:
il push tecnico del solo ramo release precede la generazione, senza promozione
su main, upload su Play o deploy. L'identità esatta del commit di compilazione
sarà fissata nella riserva e nel manifesto immutabile del bundle.

## Servizi e sponsor

API ufficiale invariata: tag `play-b6fbe4d`, revisione
`meteofriul-api-00251-jow`, sorgente originale attestata
`e180b87abe5dac022034881ea4eb1ca60a0d4e78`, equivalente dopo la pulizia Git
a `599aea2f8a3b1e7e65af2b43e77bb54e4637c96e` (prova descritta sotto).
Il builder verifica nuovamente binding live, digest, salute, TTL e attestazioni.

Community compatibile v2/v3 già attiva: vedere il
[verbale del deploy](COMMUNITY_0.1.15_DEPLOY_20261021.md).
ICON: nuova corsa, 215 lettori storici, 215 sidecar e campione nazionale
verificati nel [verbale](ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md).
Allerte FVG: acquisizione ripristinata, primo invio parziale e corse successive
deduplicate, come nel [verbale](FVG_ALERTS_DEPLOY_20261020.md).
Nessuno di questi servizi richiede un nuovo deploy per costruire la AAB.

**Sponsor disattivati**: catalogo API ufficiale del 21 ottobre ore 14:55 UTC,
`enabled=false`, zero campagne, revisione 117. Nessuna attivazione, modifica
al pannello o sincronizzazione dei dati sponsor. Il nuovo lettore del catalogo
resta compatibile ma non attiva campagne autonomamente.

Eventi: letture compatibili; gli aggiornamenti dei sei moduli backend su orari
rimangono separati e il catalogo non viene dichiarato integralmente fresco.
La distinzione FCM SenderIdMismatch/Unregistered nei runtime ancora precedenti
resta una correzione operativa separata. Costruire questa AAB non la distribuisce
né cambia sender, destinatari o configurazioni.

## Quattro aree Android e limiti

| Area | Controllo locale | Prova sul nuovo pacchetto |
| --- | --- | --- |
| Edge-to-edge e inset | 19 test in quattro suite UI/system bars passati; codice allineato a main | NON VERIFICATA su Android 15/16, gesti/tre tasti, temi, cutout, tastiera, ripresa |
| API system bar deprecate | Nessun setter deprecato reintrodotto nel codice applicativo; nessun cambio toolchain in questa preparazione | Avvisi delle dipendenze e rapporto Play del bundle esatto da leggere dopo upload autorizzato |
| Orientamento e schermi grandi | Telefoni portrait a schermo intero; nessun lock globale manifest; >=600 dp e multi-window adattivi | NON VERIFICATA la matrice del nuovo pacchetto, inclusi tablet e finestre multiple |
| R8 e risorse | Contratti PASS; minify e shrinkResources attivi, profilo ottimizzato, optimizedResourceShrinking=true, nessuna nuova keep rule | Mapping esterno e incluso nel bundle coincidenti, firma e bundle PASS; comportamento minificato ufficiale NON VERIFICATO fino al test |

Target SDK 36, AGP 8.13.0 e Capacitor 8.5.1 invariati rispetto a main.
I test della TEST minificata su Galaxy Android 14 e della Web su Brave restano
prove precedenti; non certificano l'installazione di questo bundle tramite Play.
Non vengono avviati emulatori. La generazione per il test interno non equivale
all'approvazione della pubblicazione in produzione.

## Preparazione locale e seguito

Guardie release: 9 PASS; registro Play prima della build: 44 record, PASS;
contratti R8 e writer TTL multi-immagine PASS. Il controllo completo del builder,
inclusa la guardia Gradle, e gli esiti live vengono registrati nella chiusura.

Sono riutilizzate dipendenze già esistenti, copiate nel worktree per evitare che
Capacitor risolva il collegamento a un altro checkout nei file Gradle generati.
Nessuna modifica delle dipendenze dichiarate. Bundletool 1.18.3 recuperato dalla
release ufficiale Google e verificato contro l'hash già registrato nella 0.1.14.
File privati di firma, Firebase e mappe rimangono ignorati da Git.

La Web usa gli stessi sorgenti approvati. La candidata pubblica resta quella
documentata il 20 ottobre: preparare la 0.1.15 dallo stesso commit prima della
pubblicazione coordinata; nessun deploy Web qui. Safari/iPhone e Aggiungi a Home
restano NON VERIFICATI. [Piano Web/Android](WEB_ANDROID_RELEASE_PARITY.md).

Prossima fase, solo dopo ulteriore autorizzazione: caricare il bundle esatto sul
canale interno personale e provarlo tramite Play, conservando dati e preferenze.
App Check/Play Integrity, Community reale, notifiche/background e matrice Android
si verificano sul pacchetto distribuito dal canale, senza attribuire PASS alla
sola compilazione. Nessun upload o invio manuale fa parte di questa preparazione.

## Legame storico Community: correzione della provenienza

Il primo tentativo del builder si è fermato prima della riserva del codice:
`source_commit_not_backend_ancestor`. La prova TTL di settembre conserva il
commit originale; l'attestazione API del 20 ottobre usava il commit equivalente
dopo la pulizia della cronologia Git. I due identificativi appartengono a
percorsi di storia diversi, pur descrivendo gli stessi writer.

È stato recuperato il commit originale del backend
`e180b87abe5dac022034881ea4eb1ca60a0d4e78` dalla mappa locale di pulizia.
La sorgente della prova TTL `ca201f08` è sua antenata. Tutti i file copiati
nell'immagine, i percorsi, i modi Git, Dockerfile e requirements sono stati
confrontati byte per byte con `599aea2f`: identici. Il contratto dei writer è
identico anche a main. La nuova [attestazione di identità originale](../../release-history/android-preparation/0.1.15-20261021/api-original-source.json)
conserva digest immagine, Cloud Build e archivio già verificati; cambia soltanto
il riferimento al sorgente originale equivalente. Il secondo tentativo usa
questo riferimento, senza modificare alcuna guardia o prova TTL immutabile,
senza nuove scritture cloud e senza reintrodurre la vecchia storia nel ramo.

Il primo push tecnico era stato bloccato per vecchie rappresentazioni degli
hash nei commit documentali non pubblicati del ramo. La candidata è stata
consolidata direttamente su main, conservando un backup locale e verificando
l'identità dell'intero albero dei file. Il successivo push ha superato la
guardia privacy invariata. Nessun push forzato o promozione su main.

## Tentativo 300032 e nuova riserva prevista

Il secondo tentativo ha superato tutti i gate live e di provenienza, poi si è
fermato nella compilazione Web: la copia locale delle dipendenze aveva escluso
le directory `build`, omettendo anche il codice distribuito dal pacchetto `idb`
richiesto da Firebase Messaging. È un errore della preparazione locale, non un
cambiamento delle dipendenze o un difetto risolto nel codice applicativo.

Non è stata prodotta alcuna AAB. La riserva **300032** rimane immutabile con un
nuovo evento `abandoned`; non viene eliminata né riutilizzata. La candidata
resta 0.1.15 e passa al codice **300033**. La copia completa è stata ripristinata:
import `idb`, build Web Android in cartella temporanea, binding API e Carto PASS
prima della nuova riserva. Nessuna dipendenza dichiarata o toolchain aggiornata.


### Correzione del retry nel builder

Il tentativo 300033 si è fermato prima della riserva: il builder bloccava anche
il nome 0.1.15 della riserva abbandonata senza bundle. La guardia è stata corretta
solo per questo caso: nome riutilizzabile dopo evento di abbandono validato e
assenza di manifesto AAB, codice sempre nuovo e maggiore. Sono mantenuti i
blocchi per codice riutilizzato, riserva aperta, bundle esistente e conflitti
nel ledger. La regola è documentata nel runbook e coperta da regressioni su
entrambi i controlli di versione e sulla lettura del ledger. Le guardie di
firma, TTL e provenienza non cambiano. 300033 non era stato ancora riservato.

## Chiusura della generazione

**AAB ufficiale 0.1.15 / 300033 generata**, stato `built-not-uploaded`.
Builder terminato con exit 0 il 21 ottobre alle 15:32:55 UTC. Sorgente esatto
`f82503e4daabc283a5caf77b49e7cf58439abf61`, allineato al main
`c329217b5df540299dad69016848f47cf703a5d0`; nessuna differenza nei sorgenti
runtime frontend, Android o backend rispetto a main.

- Bundle: `meteofriul-300033-0.1.15.aab`, 72.859.275 byte.
- SHA-256: `cb461c8e5e6fddd05407214a507e151e02e8041f403d9346c364bbe0174ba019`.
- Mapping: `meteofriul-300033-0.1.15.mapping.txt`, verificato anche dentro la AAB.
- Firma: un solo firmatario su tutte le voci; certificato upload coincidente con
  quello dell'ultima versione accettata su Play.
- Manifesto estratto dal bundle: `com.meteofriul.app`, min SDK 24, target 36,
  non debuggable, MainActivity ridimensionabile e senza blocco portrait globale.
  BuildConfig: DEBUG=false, LOCAL_WEATHER_PILOT=false.
- Quattro librerie native transitive DataStore: segmenti ELF con allineamento
  16.384 byte. Simboli nativi non disponibili nelle dipendenze: limite registrato,
  non dichiarato risolto. Questo controllo statico non è una prova runtime.
- Sponsor riletti alle 15:33:47 UTC: `enabled=false`, zero campagne, revisione 117.
  Nessuna attivazione del pannello o sincronizzazione dati.

AAB e mapping conservati nel worktree release e copiati senza sovrascrittura
nell'archivio `release-artifacts/android-play/` della radice canonica, con verifica
degli hash. Riserva e manifesto conservati nel registro immutabile. I nuovi
commit di documentazione successivi alla build non cambiano il file né il suo
commit sorgente.

I precedenti tentativi **non hanno prodotto alcuna AAB**. La riserva 300032
rimane abbandonata; 300033 è la sola AAB prodotta per questa preparazione.
L'eccezione sul nome non riutilizza né cancella un codice riservato.

Controlli locali completati: 9 guardie release, 19 test UI/inset/system bar,
49 test dei lettori sponsor; contratti R8, writer TTL, preflight API e builder
con regressioni del retry PASS. Build Web preliminare con binding e Carto PASS.
Rimangono gli avvisi noti su dimensione chunk, optimizedResourceShrinking
sperimentale, flatDir e deprecazioni Gradle: non sono stati soppressi o presentati
come risolti. Dettagli nella
[ricevuta di verifica](../../release-history/android-preparation/0.1.15-20261021/build-verification.json).

Play Console consultata in sola lettura: test interno attivo, una sola lista
selezionata con un utente; nessuna modifica a tester o release. L'AAB non è
caricata, installata o distribuita. Nessun nuovo deploy, invio manuale o emulatore.
La verifica reale attraverso Play resta da eseguire dopo autorizzazione distinta.

Le [regole obbligatorie di preparazione](ANDROID_BUILD_PREVENTION_RULES.md)
sono richiamate da README, AGENTS.md e runbook: dipendenze complete, assenza di
junction verso altri checkout, preflight prima della riserva, provenienza,
gestione degli errori e verifiche finali dell'artefatto.

## CI e salvataggio finale

[CI del commit compilato](https://github.com/meteofriul/meteofriul-app/actions/runs/39626085533):
workflow concluso con successo. Frontend e hosting-preview-tool hanno conclusione
success; tutti i passi backend, inclusi test, compilazione e monitor PromQL,
sono conclusi con successo. Le API Actions e Checks mantengono però il metadato
del solo job backend in_progress senza conclusione: discrepanza conservata nella
[ricevuta CI](../../release-history/android-preparation/0.1.15-20261021/source-ci.json),
non trasformata in un risultato mancante o in un nuovo test. Nessuna esecuzione
duplicata avviata per aggirare questo stato. La generazione è conclusa; upload
e promozione restano fasi successive.

Le prove e il manifesto vengono salvati sul ramo release; main resta la base
verificata c329217b. La documentazione non dichiara eseguito il test runtime
della nuova AAB e non autorizza pubblicazione, installazione o altri invii.

## Test interno pubblicato — 21 ottobre, ore 17:52 Europe/Rome

Su autorizzazione esplicita del proprietario, caricato **lo stesso file AAB
0.1.15 / 300033**, senza ricompilazione; hash confrontato con il manifesto
immutabile prima dell'invio. Play ha accettato il bundle e la Console mostra
**Disponibile per i tester interni**. Il registro contiene un nuovo evento
`play-accepted`; riserva e manifesto precedenti rimangono immutati.

Il canale conserva la sola lista già selezionata dal proprietario, con **un
utente**; le altre due liste restano escluse. Nessuna modifica ai destinatari,
nessuna promozione in produzione, installazione da parte dell'agente, nuovo
deploy o invio manuale. Il proprietario ha poi confermato di vedere la release
di test nel Play Store e di stare aggiornando: conferma di accesso/disponibilità,
non ancora di funzionamento sul dispositivo.

Convalida Play della versione 300033:

- zero errori bloccanti; un solo avviso sui simboli di debug nativi mancanti
  delle dipendenze transitive, già noto e conservato come limite;
- supporto a pagine di memoria 16 kB, mapping ReTrace allegato, R8 completo,
  riduzione delle risorse ottimizzata;
- 19.325 dispositivi supportati, nessun dispositivo precedentemente supportato
  escluso. La feature portrait non è più obbligatoria nel manifest, in accordo
  con la policy adattiva per schermi grandi; il comportamento sul telefono
  resta da verificare nella nuova installazione;
- raccomandazione di aggiornamento ad AGP 9.0 nel dettaglio R8: nessun
  aggiornamento toolchain effettuato. Non è un errore bloccante dell'upload.

Le prove runtime delle quattro aree Android e un rapporto pre-lancio del nuovo
bundle non sono dichiarati superati. Gli sponsor sono stati riletti dopo il
rilascio: `enabled=false`, zero campagne, revisione 117; pannello e allineamento
dati non attivati.

**Promozione Git separata:** aperta la [PR 11](https://github.com/meteofriul/meteofriul-app/pull/11).
Tutti e tre i controlli della [CI PR](https://github.com/meteofriul/meteofriul-app/actions/runs/39628516862)
sono conclusi con successo. Il tentativo di merge, condizionato ai controlli,
è stato rifiutato dalla revisione automatica delle autorizzazioni perché la
nuova AAB non era ancora stata provata su dispositivo. Il comando non è stato
eseguito; nessun tentativo alternativo o merge indiretto. Main rimane
`c329217b5df540299dad69016848f47cf703a5d0` e la PR è stata convertita in bozza.

Il passaggio su main previsto dal runbook è quindi **ancora da completare**.
È stato eseguito soltanto il caricamento interno richiesto, che consente al
proprietario di provare il nuovo pacchetto via Play. La disponibilità nel test
non costituisce una deroga ai controlli richiesti per promuovere il codice.

Dettagli nella [ricevuta del test interno](../../release-history/android-preparation/0.1.15-20261021/play-internal-verification.json).
Screenshot e letture complete restano nelle evidenze locali ignorate.

## Verifica della nuova installazione Play — 21 ottobre, ore 18

Il proprietario ha aggiornato dal Play Store. La verifica sul Galaxy A52 con
Android 14 ha esercitato il vero pacchetto release 300033: previsioni FVG e
nazionali, temi/lingue, Eventi, conferma Community senza invio, allerta,
ricerca, Indietro e ritorno dal background. Nessun crash rilevato; sponsor
disattivati e preferenze ripristinate.

**La promozione resta sospesa:** il bundle non contiene `capacitor.config.json`
e l'app segnala l'assenza a runtime, usando valori predefiniti diversi da quelli
del progetto. È presente anche un errore di lettura della risorsa Cordova
`config.xml`, da approfondire. Le prove API 34 riuscite non risolvono questi
difetti né sostituiscono Android 15/16, gesti e schermi grandi.

Esiti, prove e rilievo grafico sulla mappa sono nel
[verbale dispositivo](ANDROID_0.1.15_DEVICE_CHECK_20261021.md) e nella
[ricevuta](../../release-history/android-preparation/0.1.15-20261021/device-verification.json).
Nessuna nuova build, installazione, invio, pubblicazione o promozione Git.

### Rettifica sulla conservazione della posizione

Il proprietario segnala che l'interruttore Posizione dell'app risultava spento
subito dopo l'aggiornamento, prima dei test dell'agente. La conservazione dei
permessi Android misurata durante la sessione non dimostra la conservazione
della preferenza dell'app nel passaggio di versione. Il rilievo
`LOCATION-UPDATE-01` resta aperto nel [verbale dispositivo](ANDROID_0.1.15_DEVICE_CHECK_20261021.md),
con causa non determinata; non è spiegato dalla successiva scelta di Roma
durante i test. Nessuna nuova azione sul telefono per questa rettifica.
