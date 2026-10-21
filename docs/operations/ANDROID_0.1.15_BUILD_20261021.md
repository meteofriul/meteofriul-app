# 0.1.15 — allineamento a main e preflight del bundle interno

21 ottobre 2026. Il proprietario autorizza la generazione della AAB ufficiale,
non il caricamento su Play, installazioni, nuovi deploy o invii manuali.
Il canale previsto è il test interno riservato al proprietario; la restrizione
ai tester viene applicata in Play Console, non è una proprietà del file AAB.

## Sorgenti e identità

Ramo esistente `codex/release-0.1.15` allineato al main verificato
`c329217b5df540299dad69016848f47cf703a5d0` (CI 39619073997 verde).
I conflitti di documentazione sono risolti mantenendo le attestazioni più
recenti di main e le copie delle evidenze con la forma approvata dal controllo
privacy. La versione resta **0.1.15 / 300032**, package `com.meteofriul.app`.
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
`meteofriul-api-00251-jow`, sorgente attestata
`599aea2f8a3b1e7e65af2b43e77bb54e4637c96e`.
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
| R8 e risorse | Contratti PASS; minify e shrinkResources attivi, profilo ottimizzato, optimizedResourceShrinking=true, nessuna nuova keep rule | Mapping e bundle da verificare dopo build; comportamento minificato ufficiale NON VERIFICATO fino al test |

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
