# AAB 0.1.15 / 300037 — test interno del 24 ottobre 2026

> Aggiornamento del 24 ottobre sera: il proprietario ha aggiornato via Play; [collaudo della 300037 sul Galaxy](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md) completato nei percorsi osservati, con limiti Android e catalogo Eventi parziale espliciti. Lo stato di build/upload riportato sotto resta storico.

## Esito e perimetro

**Disponibile per i tester interni dalle 18:52 Europe/Rome.** Caricata la AAB
archiviata `meteofriul-300037-0.1.15.aab`, senza ricostruzione: 73017579 byte,
SHA-256 `81d3b1848ceb19c9095a46ca6b55bf8ce5bd00337c01fedf1d4d7582809d96cf`.
Package `com.meteofriul.app`, sorgente `d15edb10067b972c10e4989ebebfe6410a194f2c`,
base main `0841020a`, con le correzioni approvate delle PR 19/20.
[Identità e controlli di build](ANDROID_0.1.15_300037_BUILD_20261024.md).
CI del sorgente [40111204820](https://github.com/meteofriul/meteofriul-app/actions/runs/40111204820) verde;
registri di build già pubblicati sul ramo release in `34c3d973` prima dell'upload.

Il proprietario ha autorizzato il test interno mantenendo gli account esistenti.
La stessa unica lista con **due account** è selezionata prima e dopo; tabella
identica, nessuna modifica a membri o selezioni, indirizzi dei membri non letti.
Le altre liste restano escluse. Produzione riletta dopo l'upload:
**0.1.14 / 300031**, invariata. La 300037 sostituisce la 300036 soltanto nel test interno.

Sponsor verificati prima e dopo: `enabled=false`, zero campagne, revisione 117;
ultima lettura `2026-10-24T16:53:47.938312+00:00`. Pannello e sincronizzazione sponsor non attivati.
Nessuna installazione, emulatore, pubblicazione Web, deploy, invio manuale o
pubblicazione in produzione. Al termine dell'upload l’ultimo artefatto osservato sul Galaxy era la 300036;
**il runtime della 300037 era NON VERIFICATO**. Il successivo collaudo è collegato sopra.

## Convalida e quattro aree Android

Revisione Play: **zero errori bloccanti e un avviso**, relativo ai simboli nativi
di debug mancanti delle librerie transitive, già documentati. Mapping ReTrace
allegato automaticamente; nessuna nuova compilazione o modifica alla toolchain.

| Area | Riscontro per la 300037 e limite |
| --- | --- |
| Edge-to-edge / inset | Contratti di build PASS; Android 15/16, gesti, cutout e tastiera del nuovo pacchetto NON VERIFICATI |
| API system bar deprecate | Toolchain e codice nativo invariati salvo versionCode; nessun report pre-lancio utilizzabile. Avvisi storici delle dipendenze non dichiarati risolti |
| Orientamento / schermi grandi | 19.340 dispositivi supportati, nessun dispositivo perso rispetto alla precedente release; small/normal/large/xlarge. Tablet, multi-window e rotazione runtime NON VERIFICATI |
| R8 / risorse | Console: DEX 89%, offuscamento 91%, riduzione 91%, modalità completa e riduzione risorse ottimizzata. Raccomandazione repackaging/AGP 9.0 e simboli nativi ancora aperti; avvio minificato NON VERIFICATO |

Supporto statico pagine 16 kB, API minima 24 e target 36 confermati dalla Console.
Il supporto statico non certifica tutti i comportamenti runtime. La pagina
pre-lancio non offre risultati utilizzabili: nessuna prova cloud manuale avviata
e nessuna impostazione modificata. Le quattro raccomandazioni nella dashboard
di produzione sono esplicitamente associate alla **300031**, non alla 300037;
non costituiscono né un nuovo FAIL né un PASS di questa candidata.

## Note pubblicate

Italiano, **496 caratteri**, riletto nella release pubblicata:

• Aria e pollini: caricamento iniziale, rientro e recupero dati.
• Eventi: contatore leggibile in scuro, catalogo e testi migliorati.
• Tempo reale: mappa fino alla barra inferiore.
• Previsioni: nuovi temi e pioggia più leggibile.
• Bollettino: mappa e aggiornamento FVG corretti; menu fissi anche in Eventi.
• Community: conferma No/Sì, ricevuta «Inviata da» e layout GPS.
• Corretti Posizione, Indietro e ricerca; rivisti italiano e friulano, allerte «in FVG», compatibilità meteo e sicurezza.

La nota comprende le correzioni recenti e quelle precedenti della 0.1.15.
Il limite Play è 500 caratteri per lingua; italiano/friulano nell'app restano
quelli del bundle già firmato, senza modifiche durante l'upload.

## Registro e conservazione

- [Release nella Console](https://play.google.com/console/u/0/developers/7317561924451916933/app/4972150571875270846/tracks/4700755128382710882/releases/20/details).
- [Accettazione append-only](../../release-history/android-play/20261024T165300392Z-play-accepted-b03cfbd8248e44bca898926434a7f0eb.evidence.json). I 59 record precedenti sono invariati; totale 60.
- [Ricevuta strutturata](evidence/release-0.1.15-300037-upload-20261024/verification.json), con hash delle evidenze private.
- Prove locali in `release-artifacts/android-play/evidence-300037/play-upload-20261024/`; non pubblicare screenshot grezzi, mailing list o dati personali.

README, stato release, piano di parità e accettazione sono salvati nello stesso
ramo `codex/release-0.1.15` secondo il runbook. Nessuna promozione a main inclusa
in questa operazione; il sorgente AAB resta immutabile e la CI del codice è quella
indicata sopra. Verifica documentale e collegamenti prima del commit; audit
del ledger dal worktree pulito prima del push dei soli registri e verbali.

La Web da `d15edb10` è preparata e non pubblicata. Prima del prossimo passaggio
restano il collaudo della 300037 aggiornata via Play dal proprietario e i limiti
Android/Web elencati nel [verbale di build](ANDROID_0.1.15_300037_BUILD_20261024.md).
Registrare Posizione prima/subito dopo update e verificare separatamente tutte
le sezioni, aria/pollini IT/FUR al primo caricamento e rientro, Eventi in scuro,
Tempo reale, GPS e navigazione. Nessun PASS della 300036 sostituisce questa prova.
