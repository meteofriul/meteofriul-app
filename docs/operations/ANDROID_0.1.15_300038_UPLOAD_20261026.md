# AAB 0.1.15 / 300038 — test interno del 26 ottobre 2026

## Esito e perimetro

**Disponibile per i tester interni dalle 13:28 Europe/Rome.** Play ha ricevuto
la AAB archiviata, senza ricostruzione, package `com.meteofriul.app`,
sorgente `7130c28ac4fdfde736498b84db28aaf738cb05db`, main incorporato `c2b2cfe1`.
File `meteofriul-300038-0.1.15.aab`, 73017701 byte,
SHA-256 `69be438d19a1e144d84227b78b9ff46bb205b4bf05465f13390abf36576c6f83`.
[Identità, firma e controlli della build](ANDROID_0.1.15_300038_BUILD_20261026.md).
L'identità è stata ricontrollata prima dell'upload e dopo la pubblicazione;
mapping esterno conforme al manifesto. Firma e configurazione indipendenti
già verificate sullo stesso identico file.
[CI della sorgente](https://github.com/meteofriul/meteofriul-app/actions/runs/40293565378): tre job PASS.

La 300038 sostituisce la 300037 soltanto nel test interno.
La stessa unica lista con **due account** è selezionata prima e dopo:
nessuna modifica alle liste o ai membri, indirizzi personali non letti.
La produzione è stata riletta dopo il rilascio: **0.1.14 / 300031**, invariata.
Sponsor letti prima e dopo: `enabled=false`, zero campagne, revisione 117.
Pannello e sincronizzazione sponsor restano disattivati.

Nessuna installazione, emulatore, nuova AAB, pubblicazione Web, deploy,
notifica manuale o pubblicazione in produzione.
**Runtime della 300038 NON VERIFICATO**: il collaudo sul Galaxy segue
l'aggiornamento via Play effettuato dal proprietario; la prova della 300037
non è un PASS della nuova versione.

## Controlli della Console e limiti Android

**Zero errori bloccanti, un avviso**: mancano i simboli di debug delle librerie
native transitive. Mapping ReTrace allegato automaticamente.
Supporto statico alle pagine 16 kB, API minima 24 e target 36 confermati.

| Area | Riscontro per la 300038 e limite |
| --- | --- |
| Edge-to-edge / inset | Contratti di build PASS; runtime nuovo, Android 15/16, gesti/cutout/tastiera NON VERIFICATI |
| API system bar deprecate | Nessun report pre-lancio utilizzabile; avvisi delle dipendenze ancora aperti. Le quattro raccomandazioni della dashboard di produzione sono associate alla 300031, non certificano la 300038 |
| Orientamento / grandi schermi | 19.414 dispositivi supportati; nessuna perdita rispetto alla precedente nella revisione Play. Small/normal/large/xlarge; tablet e multi-window NON VERIFICATI |
| R8 / risorse | DEX 89%, offuscamento 91%, riduzione 91%, modalità completa e shrinking risorse ottimizzato. Raccomandazione AGP 9/repackaging e simboli nativi aperti; avvio/bridge/plugin minificati da provare |

Nessuna prova cloud manuale avviata. Il report pre-lancio non offre risultati
utilizzabili; l'assenza di dati non viene presentata come successo.

## Note pubblicate

Italiano, **497 caratteri**, rilette nella release disponibile:

• Antenna radar e testi più leggibili in scuro.
• Aria e pollini: caricamento e recupero dati migliorati.
• Eventi: catalogo, testi e contatore scuro.
• Tempo reale: mappa fino alla barra inferiore.
• Previsioni: temi, card uniformi e pioggia visibile.
• Bollettino: mappa, aggiornamento FVG e menu fissi anche in Eventi.
• Community: No/Sì, ricevuta «Inviata da» e layout GPS.
• Corretti Posizione, Indietro e ricerca; testi italiani e friulani, allerte «in FVG», compatibilità meteo e sicurezza.

I testi IT/FUR nell'app sono quelli del bundle immutabile: nessuna modifica
durante l'upload. La nota riassume le correzioni della 0.1.15 e le novità
rispetto alla 300037, senza affermare la freschezza dei dati backend.

## Backend e Web: stato separato

Il deploy CAMS e della relativa policy è già attestato nel
[verbale del 26 ottobre](https://github.com/meteofriul/meteofriul-app/blob/4219581f17b35aa42bd346ff652058004d9cf5f0/docs/operations/CAMS_CONTINUITY_DEPLOY_20261026.md).
Letture correnti disponibili in quel controllo; il recupero su nuova famiglia
con continuità 36h resta da verificare. Nessuna nuova interrogazione dei job
durante questo upload. Il dato scaduto trovato nella prima preparazione
è un riscontro storico, non lo stato attuale assunto.

Barcolana resta una verifica operativa distinta; il follow-up del 27 ottobre
è stato **eliminato su richiesta del proprietario**, senza ricrearlo.
L'upload non dimostra il recupero delle fonti Eventi.

Web candidata `20261026-0.1.15-7130c28a` dalla stessa sorgente,
manifest SHA-256 `59cb9a4a4d79377313760569458b5b87d8c8086202e5c1e307f06feed97a047c`,
non pubblicata. Safari/iPhone e PWA restano NON VERIFICATI.
Ultima lettura pubblica disponibile: Web 0.1.14 del 23 ottobre.

## Registro, conservazione e prossimo passo

- [Release nella Console](https://play.google.com/console/u/0/developers/7317561924451916933/app/4972150571875270846/tracks/4700755128382710882/releases/21/details).
- [Accettazione append-only](../../release-history/android-play/20261026T122933197Z-play-accepted-a596d9fc52d44d698224a07bd5f5a4bd.evidence.json).
- [Ricevuta strutturata](evidence/release-0.1.15-300038-upload-20261026/verification.json).
- 62 record precedenti invariati (più il README del registro), totale 63 record.
- Evidenze private: `release-artifacts/android-play/evidence-300038/play-upload-20261026/`.
  Non pubblicare screenshot grezzi o dati delle mailing list.

README, stato release, parità Web e accettazione sono aggiornati nello stesso
ramo `codex/release-0.1.15`, con revisione del diff, collegamenti e audit ledger.
Il commit riguarda registri e documentazione; non modifica il codice firmato.
Nessuna promozione del ramo release in main inclusa in questa operazione.

Prossimo passo: aggiornamento del proprietario da Play e collaudo della 300038,
registrando Posizione prima/subito dopo, sezioni principali, aria/pollini
IT/FUR al primo carico e rientro, antenna/contrasto radar, Eventi e completezza.
Nessuna installazione o notifica di prova implicita. Prima della produzione
restano le verifiche effettive del nuovo pacchetto e l'autorizzazione distinta.
