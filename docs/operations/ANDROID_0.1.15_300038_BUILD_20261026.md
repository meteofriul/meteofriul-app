# AAB 0.1.15 / 300038 — 26 ottobre 2026

## Stato prima della compilazione

Generazione autorizzata dal proprietario; **AAB non ancora generata né riservata**.
Ramo `codex/release-0.1.15`, main incorporato `c2b2cfe16c687f10bc4be87e50d26059a855b8b1`
con merge `072178cb`. Il solo codice versione passa da 300037 a 300038.
La lettura odierna di Play, panoramica release e bundle senza filtri, conferma
massimo 300037, test interno 0.1.15/300037 e produzione 0.1.14/300031.

Incluse antenna radar approvata e nuova leggibilità del testo secondario scuro.
Il contrasto resta sul ramo release, da verificare nella nuova AAB sul Galaxy;
non viene promosso automaticamente in main. Nessuna nuova funzione sponsor.

## Controlli prima di consumare il codice

Riutilizzati dopo confronto dell'albero frontend identico i controlli del
[26 ottobre](RELEASE_WEB_ALIGNMENT_20261026.md): 5.055 test, 13 esclusi, lint,
contratti nativi/R8/builder e build Web Android con binding API e CARTO.
361 dipendenze fisiche confrontate col lockfile, senza installare o aggiornare
pacchetti. Ripetuti firma upload, Firebase, SDK36, registro, guardie versione
e 16 guardie Node; tutti PASS. API/TTL e contratto Community PASS in lettura.
Sponsor `enabled=false`, zero campagne. Le evidenze storiche e i binari precedenti
sono protetti da inventario SHA-256.

Prima del builder occorrono commit sorgente pulito e allineato al remoto,
CI verde sul commit esatto e Web ricompilata dalla stessa sorgente.
Usare esclusivamente PowerShell 7 e `scripts/build-play-aab.ps1`, senza
android:sync manuale. L'attestazione TTL storica va ricontrollata: scade il
26 ottobre alle 21:48:36 UTC; non riscrivere attestazioni o aggirare il gate.

## Limiti operativi e verifiche successive

CAMS del 25 ottobre osservato scaduto alle 07:00 italiane; la prossima corsa
ordinaria è prevista alle 10:00. La build non rinnova quei dati: prima di
qualificare il test di aria e pollini serve una lettura corrente valida.
Eventi aggiornato separatamente; il recupero Barcolana resta da verificare
nella corsa del 27 ottobre alle 05:00, con il follow-up mantenuto.

| Area Android | Stato prima della nuova AAB |
| --- | --- |
| Edge-to-edge / inset | Contratti locali PASS; nuova AAB, Android 15/16 e gesti/cutout/tastiera NON VERIFICATI |
| API deprecate | Toolchain invariata; avvisi delle dipendenze e futuro report Play aperti |
| Orientamento / schermi grandi | Contratti PASS; nuova AAB, tablet e multi-window NON VERIFICATI |
| R8 / risorse | Contratti PASS; firma, mapping, configurazione e avvio della nuova AAB ancora da verificare; shrinking ottimizzato/AGP restano limiti |

Prova successiva sul Galaxy: Posizione prima/subito dopo aggiornamento Play,
Home, Previsioni (aria/pollini IT/FUR al carico/rientro), Bollettino, Tempo reale
(antenna e contrasto chiaro/scuro, mappa/dock/lista/webcam), Eventi, Scopri,
Impostazioni. Nessuna installazione o notifica di prova implicita.
Web pubblica e produzione Play invariate; Safari/iPhone/PWA NON VERIFICATI.
Generazione, upload interno e produzione restano azioni separate.

[Stato release](RELEASE_0.1.15_STATUS_20261021.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
