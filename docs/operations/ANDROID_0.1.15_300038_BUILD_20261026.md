# AAB 0.1.15 / 300038 — 26 ottobre 2026

## Esito e contenuto

**Generata, firmata, validata e archiviata; non caricata su Play.**
Package `com.meteofriul.app`, versione **0.1.15 / 300038**,
sorgente `7130c28ac4fdfde736498b84db28aaf738cb05db`, ramo `codex/release-0.1.15`.
Main incorporato `c2b2cfe16c687f10bc4be87e50d26059a855b8b1`. Incluse antenna radar approvata e leggibilità
del testo secondario in scuro; conservate correzioni di Posizione, aria/pollini,
contatore Eventi, Tempo reale, Bollettino, Community e testi IT/FUR.
Il contrasto aggiuntivo resta sul ramo release, da provare nella nuova AAB;
non viene promosso in main sulla sola compilazione.

Play letto oggi senza filtri: massimo/test interno **300037**, produzione
**0.1.14 / 300031**. Nessuno di questi canali è stato modificato.
Sponsor verificati prima/dopo: `enabled=false`, revisione 117, zero campagne.
Nessun upload, installazione, emulatore, nuovo deploy o invio manuale.
Controllo Eventi del 27 ottobre alle 05:00 italiane mantenuto.

## Artefatto e conservazione

- AAB: `release-artifacts/android-play/meteofriul-300038-0.1.15.aab`, 73017701 byte.
- SHA-256: `69be438d19a1e144d84227b78b9ff46bb205b4bf05465f13390abf36576c6f83`.
- Mapping: `meteofriul-300038-0.1.15.mapping.txt`, SHA-256 `1578fd6e78e3f27ea18a568673e571bf6e602f88a7d9bf349a1f34300307e6ff`.
- Certificato upload: `338c051587d62cdad6f9bd38eaa1e793d3da2d6c30c4270f8450a93a6ecec3b4`, identico alla precedente accettazione Play.
- [Riserva](../../release-history/android-play/meteofriul-300038-0.1.15.reservation.json) e [manifesto immutabile](../../release-history/android-play/meteofriul-300038-0.1.15.release.json), stato `built-not-uploaded`.
- [Ricevuta dei controlli](evidence/release-0.1.15-300038-build-20261026/verification.json).

Copie con hash verificati nel worktree release e nella radice canonica.
Evidenze private durevoli in `release-artifacts/android-play/evidence-300038/`;
log in `.tmp/release-0.1.15-300038-build-20261026/`.
**10323 file preesistenti protetti invariati**.
Non rigenerare né sovrascrivere il codice 300038; usare questo artefatto per
un eventuale successivo upload autorizzato.

## Controlli eseguiti

Prima della riserva: dipendenze fisiche complete, 361 versioni conformi al
lockfile; Firebase ufficiale, SDK36, JDK, bundletool 1.18.3 e certificato upload
verificati. Build Web Android preliminare con binding API/CARTO PASS.
Nessun aggiornamento della toolchain. Entrambe le guardie versione, audit
ledger e 16 guardie Node PASS. Dopo confronto dell'identità frontend,
riutilizzati i 5.055 test locali (13 esclusi), lint e contratti nativi/R8/builder
del [26 ottobre](RELEASE_WEB_ALIGNMENT_20261026.md).

[CI 40293565378](https://github.com/meteofriul/meteofriul-app/actions/runs/40293565378) sul commit esatto: tutti e tre
i job PASS (frontend, backend, controlli Windows). Builder protetto PowerShell7
fuori sandbox: `2026-10-26T08:41:34.919924+00:00` → `2026-10-26T08:45:56.549844+00:00`,
exit0. Nessun android:sync manuale o comando Gradle alternativo.
API `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, digest `5522b4cf…`,
sorgente originale `e180b87a`; preflight prima/dopo e gate Community/TTL PASS.

Verifica indipendente sul file firmato: identità bundletool, firma di tutti
i payload, mapping esterno/incorporato, JSON Capacitor, registro plugin e
risorsa Cordova `com.meteofriul.app:xml/config` PASS. Configurazione senza
server locale, debug WebView o mixed content. Controllata presenza dei CSS
Tempo reale/contatore scuro/contrasto radar, antenna e testi IT/FUR; harness assente.

Il primo push era stato fermato dal controllo privacy: cinque hash di
evidenza, associati a chiavi con il nome API, erano interpretati come segreti.
Le due ricevute ora usano campi espliciti `file`/`sha256`, con gli stessi valori.
Normalizzati soltanto sei commit non pubblicati, preservando uno snapshot locale;
cronologia remota, frontend, regole privacy e baseline invariati. Nuova scansione
senza rilievi e push normale riuscito. Nessuna riserva era stata consumata;
gli archivi Web preliminari restano conservati con la loro identità originale.

## Web dalla stessa sorgente

Archivio `release-artifacts/web-candidates/20261026-0.1.15-7130c28a`;
manifest SHA-256 `59cb9a4a4d79377313760569458b5b87d8c8086202e5c1e307f06feed97a047c`.
506 file Web e 505 asset Web Android dalla stessa sorgente `7130c28ac4fdfde736498b84db28aaf738cb05db`,
con hash verificati e binding API/Community/CARTO corretti; non pubblicati.
L'archivio è stato prodotto prima della AAB: i suoi campi temporali
`aab_generated=false` e CI pending descrivono quel momento, non lo stato finale.
La presente ricevuta collega i due artefatti e la CI completata.
Ultima lettura pubblica disponibile: Web0.1.14 del 23 ottobre.
Safari/iPhone/PWA e servizi/cache dall'origine pubblica della candidata
restano NON VERIFICATI.

## Limiti e prossimo collaudo

Il controllo finale delle 2026-10-26T08:47:37.300217+00:00 ha trovato CAMS del 25 ottobre scaduto alle
07:00 italiane; prossima corsa prevista alle 10:00. **La AAB non risolve
la freschezza dei dati**. Occorre verificarne il recupero prima di attestare
aria e pollini nella nuova versione. Non sono state avviate acquisizioni.
Barcolana è un lavoro backend distinto: aggiornamento distribuito, recupero
da verificare nella corsa ordinaria del 27 ottobre, follow-up mantenuto.

| Area | Esito della 300038 |
| --- | --- |
| Edge-to-edge / inset | Contratti PASS; nuova AAB su telefono, Android15/16, gesti/cutout/tastiera NON VERIFICATI |
| API deprecate | Toolchain invariata; restano gli avvisi delle dipendenze e il riesame del futuro report Play |
| Orientamento / grandi schermi | Contratti PASS; nuova AAB, tablet e multi-window NON VERIFICATI |
| R8 / risorse | Firma, mapping, minificazione, shrinking e configurazione PASS; avvio/bridge/plugin del nuovo bundle NON VERIFICATI; shrinking ottimizzato/AGP e simboli transitivi restano limiti |

Non è una qualifica completa né una pubblicazione in produzione.
Dopo upload separatamente autorizzato e aggiornamento del proprietario via Play,
registrare Posizione prima/subito dopo, Home, Previsioni (aria/pollini IT/FUR
al primo carico e rientro), Bollettino, Tempo reale (antenna/contrasto,
mappa/dock/lista/webcam), Eventi e completezza, Scopri, Impostazioni.
Nessuna notifica di prova implicita. La prova Galaxy della 300037 non viene
riutilizzata come PASS del nuovo pacchetto.

[Stato release](RELEASE_0.1.15_STATUS_20261021.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
