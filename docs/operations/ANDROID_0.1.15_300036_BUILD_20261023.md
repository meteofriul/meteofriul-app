# AAB 0.1.15 / 300036 — 23 ottobre 2026

## Esito

**Generata, firmata e verificata.** Aggiornamento successivo: caricata nel test interno alle 13:37 del 23 ottobre; [verbale di accettazione](ANDROID_0.1.15_300036_UPLOAD_20261023.md). Package
`com.meteofriul.app`, versione **0.1.15 / 300036**, sorgente
`9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`, ramo `codex/release-0.1.15`.
Include main `2d8b0c32` e la correzione di Tempo reale: la mappa occupa lo spazio
fino alla navigazione inferiore, con il distacco richiesto. Conserva Posizione,
aria/pollini, configurazione nativa e le altre modifiche approvate.

Sponsor verificati prima e dopo: `enabled=false`, zero campagne, revisione 117.
Pannello e sincronizzazione sponsor sospesi. Nessuna installazione, emulatore,
pubblicazione Web, deploy o invio manuale. La lettura della Console prima della build confermava
300035 come massimo caricato e test interno corrente; produzione 300031.
Il caricamento successivo della 300036 è registrato nel verbale collegato sopra.

## Artefatto e conservazione

- AAB: `release-artifacts/android-play/meteofriul-300036-0.1.15.aab`, 73,017,302 byte.
- SHA256: `024212752b3af72f163d75849aa53c2b191ba0352e42423b11efccd2d7f8b51f`.
- Certificato upload: `338c051587d62cdad6f9bd38eaa1e793d3da2d6c30c4270f8450a93a6ecec3b4`, coincidente con l'ultima accettazione Play.
- Mapping: `meteofriul-300036-0.1.15.mapping.txt`, SHA256 `1578fd6e78e3f27ea18a568673e571bf6e602f88a7d9bf349a1f34300307e6ff`.
- [Riserva](../../release-history/android-play/meteofriul-300036-0.1.15.reservation.json) e [manifesto immutabile](../../release-history/android-play/meteofriul-300036-0.1.15.release.json).
- [Ricevuta dei controlli](evidence/release-0.1.15-300036-build-20261023/verification.json).

Copie verificate nel worktree release e nella radice canonica, sotto
`release-artifacts/android-play/`. Log privati, script di verifica e prove
durevoli in `release-artifacts/android-play/evidence-300036/` nella radice
canonica. 797 file precedenti invariati, inclusi registri, vecchi
artefatti e materiali locali. Non rigenerare o sovrascrivere questo codice.

## Verifiche completate

Entrambi i controlli di versione superati prima della riserva: massimo Play e
locale 300035; nome 0.1.15 riutilizzabile con un nuovo codice. Dipendenze fisiche,
361 versioni confrontate con lockfile; nessuna installazione di dipendenze.
Solo `versionCode` cambia rispetto a `22248c83`. I 5.047 test locali, lint e
contratti precedenti sono riutilizzati con questa distinzione; guardie di
release ripetute e CI sul commit esatto
[39944265214](https://github.com/meteofriul/meteofriul-app/actions/runs/39944265214)
completata: frontend, backend e contratti Windows PASS.

Build preliminari Web e Web Android PASS prima della riserva, con endpoint
ufficiali e controlli CARTO. Builder protetto PowerShell 7 completato con exit 0:
`2026-10-23T11:16:32.265496+00:00` → `2026-10-23T11:21:00.488300+00:00`.
Nessun `android:sync` manuale o Gradle alternativo al builder.

Bundletool 1.18.3 verificato per hash; identità, validazione bundle e firma di
tutti i payload PASS. Mapping esterno e incorporato coincidono. Configurazione
Capacitor e registro plugin corrispondono agli hash approvati; risorsa Cordova
`com.meteofriul.app:xml/config` presente e risolta. Debug WebView e mixed content
disattivati; nessun server di sviluppo. Verifica indipendente della copia
conferma identità, hash, mapping, configurazione e CSS del fix Tempo reale.

Preflight API e controlli TTL/sicurezza Community PASS prima/dopo la build.
API tagged `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, digest `5522b4cf…`,
provenienza originale `e180b87a`. Nessun aggiornamento backend necessario per
questa build secondo i gate eseguiti; questo non è un audit di tutti i job.

## Web dalla stessa sorgente

Web ricompilata in modalità `-BuildOnly` da `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`:
`release-artifacts/web-candidates/20261023-0.1.15-9d5ff2f4/`, 506 file Web e 505 asset Web Android.
Manifest SHA256 `42e81042e678be61091db42e401329f54353bddd8be28d4673eacbf898a75bc2`. Tutti i file ricontrollati;
il fix di Tempo reale è incluso in entrambi i bundle. Nessuna pubblicazione.
La candidata `16890b8c` resta conservata; sito pubblico nell'ultima lettura del
22 ottobre ancora 0.1.14. Safari/iPhone, PWA e aggiornamento cache NON VERIFICATI.

## Qualifica Android: limiti aperti

| Area | Stato della 300036 |
| --- | --- |
| Edge-to-edge / inset | Contratti automatici PASS; geometria della nuova AAB sul telefono, Android 15/16, gesti/cutout/tastiera NON VERIFICATI |
| API system bar deprecate | Toolchain e codice invariati rispetto alla base verificata; avvisi delle dipendenze e nuovo report Play ancora aperti |
| Orientamento / schermi grandi | Policy portrait telefoni e adattività conservate; rotazione, tablet e multi-window di questo pacchetto NON VERIFICATI |
| R8 / risorse | Minificazione, shrinking, firma, mapping e risorse native confezionate PASS; avvio e plugin sul pacchetto minificato NON VERIFICATI. Shrinking ottimizzato/AGP e simboli di quattro librerie transitive restano i limiti documentati |

**REALTIME-LAYOUT-01 resta aperto fino alla prova della nuova AAB installata.**
Le precedenti prove Brave/Galaxy del fix e quelle mirate della 300035 non sono
un PASS runtime della 300036. La 300035 mantiene il difetto riprodotto.
Home, Previsioni, Bollettino, Tempo reale, Eventi, Scopri e Impostazioni devono
essere registrati separatamente nel prossimo collaudo autorizzato. Conservare
lo stato di Posizione prima/dopo l'aggiornamento; verificare aria/pollini IT/FUR
al rientro, mappa/dock/lista/webcam e sezioni adiacenti senza invii manuali.

## Prossimo passaggio

Il caricamento successivo è stato autorizzato ed eseguito nel test interno.
Resta la prova sul telefono della 300036; non è qualificata per la produzione. PR 11 ancora
in bozza; main non modificato. Documenti e registri non cambiano il commit
sorgente dell'artefatto firmato.

[Stato release](RELEASE_0.1.15_STATUS_20261021.md) ·
[Runbook Play](PLAY_AAB_RUNBOOK.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
