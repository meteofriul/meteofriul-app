# AAB 0.1.15 / 300037 — 24 ottobre 2026

> Aggiornamento del 24 ottobre sera: il proprietario ha aggiornato via Play; [collaudo della 300037 sul Galaxy](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md) completato nei percorsi osservati, con limiti Android e catalogo Eventi parziale espliciti. Lo stato di build/upload riportato sotto resta storico.

> Aggiornamento successivo del 24 ottobre, 18:52: AAB accettata e disponibile nel test interno, stessi due account e sponsor spenti. [Verbale di caricamento](ANDROID_0.1.15_300037_UPLOAD_20261024.md). Il testo seguente conserva lo stato al termine della build; runtime della 300037 non ancora verificato a quel momento.

## Esito e contenuto

**Generata, firmata, validata e archiviata; non caricata su Play.** Package
`com.meteofriul.app`, versione **0.1.15 / 300037**, sorgente
`d15edb10067b972c10e4989ebebfe6410a194f2c`, ramo `codex/release-0.1.15`.
Main incorporato `0841020a`; rispetto alla base già verificata cambia soltanto
il codice Android da 300036 a 300037. Sono incluse le correzioni approvate delle
PR 19/20: recupero e transitorio iniziale aria/pollini, contatore Eventi leggibile
in scuro, impaginazione GPS e traduzioni friulane. Conservati Tempo reale,
Posizione e gli altri interventi precedenti.

La Console letta il 24 ottobre conferma massimo caricato e test interno
**300036**, produzione **0.1.14 / 300031**. Questi canali non sono stati modificati.
Sponsor verificati prima e dopo: `enabled=false`, zero campagne, revisione 117.
Nessuna attivazione del pannello o allineamento dati sponsor; nessun upload,
installazione, emulatore, pubblicazione Web, deploy o invio manuale.

## Artefatto e conservazione

- AAB: `release-artifacts/android-play/meteofriul-300037-0.1.15.aab`, 73017579 byte.
- SHA-256: `81d3b1848ceb19c9095a46ca6b55bf8ce5bd00337c01fedf1d4d7582809d96cf`.
- Mapping: `meteofriul-300037-0.1.15.mapping.txt`, SHA-256 `1578fd6e78e3f27ea18a568673e571bf6e602f88a7d9bf349a1f34300307e6ff`.
- Firma upload: `338c051587d62cdad6f9bd38eaa1e793d3da2d6c30c4270f8450a93a6ecec3b4`, coincidente con la precedente accettazione Play.
- [Riserva](../../release-history/android-play/meteofriul-300037-0.1.15.reservation.json) e [manifesto immutabile](../../release-history/android-play/meteofriul-300037-0.1.15.release.json), stato `built-not-uploaded`.
- [Ricevuta dei controlli](evidence/release-0.1.15-300037-build-20261024/verification.json).

Copie con hash verificati nel worktree release e nella radice canonica.
Evidenze durevoli in `release-artifacts/android-play/evidence-300037/`;
log di lavoro in `.tmp/release-0.1.15-300037-build-20261024/`.
I **7928 file preesistenti protetti sono invariati**, inclusi
vecchi artefatti, registri e materiali locali. Non ricostruire o sovrascrivere
questa versione: per un futuro caricamento usare la AAB archiviata qui indicata.

## Controlli completati

Entrambe le guardie di versione e l'audit del registro sono passati prima della
riserva: massimo Play/locale 300036, nessuna riserva aperta che bloccasse il nome.
Dipendenze fisiche del checkout: 361 versioni conformi al lockfile, nessuna
installazione o copia. Configurazione Firebase ufficiale, Carto, JDK/SDK e hash
di bundletool 1.18.3 verificati. Nessuna modifica alla toolchain.

19 test di layout/barre/inset, 16 guardie frontend, 43 asserzioni di
configurazione nativa e contratti R8 PASS. La
[CI 40111204820](https://github.com/meteofriul/meteofriul-app/actions/runs/40111204820)
è verde sul commit esatto: frontend, backend e controlli Windows.
Le prove Galaxy IT/FUR delle PR 19/20 restano riferite ai rispettivi sorgenti;
non sono una prova runtime della nuova AAB.

Build Web e asset Web Android preliminari PASS prima della riserva, con endpoint
ufficiali e guardie API/CARTO. Il lettore locale dell'archivio aveva interpretato
il carattere ellissi con cp1252: corretto usando UTF-8 esplicito. I testi IT/FUR
nei bundle erano corretti; verificati e archiviati senza ricompilazioni o
modifiche agli asset. Nessun codice era stato riservato in quella fase.

Builder protetto PowerShell 7, fuori sandbox, completato con exit 0:
`2026-10-24T16:26:27.746591+00:00` → `2026-10-24T16:33:28.923024+00:00`.
Nessun `android:sync` manuale o Gradle alternativo. Preflight API e gate
TTL/sicurezza Community PASS prima/dopo. API `play-b6fbe4d`, revisione
`meteofriul-api-00251-jow`, digest `5522b4cf…`, origine `e180b87a`.
Nessun aggiornamento backend necessario secondo questi gate; non è un audit
aggiuntivo di tutti i job.

Verifica indipendente della AAB: identità e bundletool PASS; firma di tutti i
payload e mapping esterno/incorporato coincidenti. JSON Capacitor e registro
plugin con hash approvati; risorsa Cordova `com.meteofriul.app:xml/config`
presente e risolta. Nessun server locale, debug WebView o mixed content.
Nel bundle firmato sono presenti CSS Tempo reale/contatore scuro, testi IT/FUR
e ciclo di caricamento CAMS; harness di prova assente.

## Web dalla stessa sorgente

Candidata Web compilata con `-BuildOnly` da `d15edb10067b972c10e4989ebebfe6410a194f2c`:
`release-artifacts/web-candidates/20261024-0.1.15-d15edb10/`.
Manifest SHA-256 `1bc0ab3316aab8ec6d879e754a23ca38ee956a9498c3aa9602f4f9a2236dff2b`.
506 file Web e 505 asset Web Android, hash ricontrollati; 1892 sorgenti
verificati. Sponsor spenti; nessuna pubblicazione. Le candidate precedenti restano
conservate. Ultima lettura pubblica del 23 ottobre: Web 0.1.14.
Servizi/cache da origine autorizzata, Safari/iPhone e PWA restano NON VERIFICATI.

## Qualifica Android ancora aperta

| Area | Esito della 300037 |
| --- | --- |
| Edge-to-edge / inset | Contratti locali PASS; geometria e interazioni della nuova AAB su telefono, Android 15/16, gesti/cutout/tastiera NON VERIFICATE |
| API deprecate | Codice nativo e toolchain invariati salvo versionCode; restano avvisi delle dipendenze e riesame del report Play del nuovo bundle |
| Orientamento / grandi schermi | Policy precedente conservata e contratti PASS; rotazione, tablet e multi-window della nuova AAB NON VERIFICATI |
| R8 / risorse | Minificazione, shrinking, firma, mapping e configurazione confezionata PASS; avvio/bridge/plugin della nuova AAB NON VERIFICATI. Shrinking ottimizzato/AGP e simboli assenti per quattro librerie transitive restano limiti aperti |

**Non è una qualifica completa né una pubblicazione in produzione.** Il prossimo
collaudo autorizzato deve registrare separatamente Home, Previsioni, Bollettino,
Tempo reale, Eventi, Scopri e Impostazioni; Posizione prima/subito dopo update,
aria/pollini IT/FUR anche al primo caricamento/rientro ed errore, contatore Eventi
in scuro, mappa/dock/lista/webcam. Screenshot e gerarchia devono concordare.
Nessuna prova con invii automatici o manuali avviata in questa preparazione.

## Salvataggio e prossimo passaggio

Il commit sorgente è pubblicato sul ramo release e la CI è completata prima
della build. Riserva, manifesto, ricevuta e documenti sono salvati nello stesso
ramo, separati dagli archivi binari ignorati. Main resta `0841020a`.
Il caricamento nel test interno richiede l'autorizzazione distinta del proprietario;
né l'upload né una promozione in produzione sono stati eseguiti.

[Stato release](RELEASE_0.1.15_STATUS_20261021.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
