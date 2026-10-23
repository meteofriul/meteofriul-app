# AAB 0.1.15 / 300035 — 23 ottobre 2026

## Esito

**Generata e verificata; non caricata su Play.** Package `com.meteofriul.app`,
versionName `0.1.15`, versionCode **300035**. Sorgente
`5e9bc7dcdc6183a2fc43ada2dea3dfb22f2a3dc1`, ramo `codex/release-0.1.15`.
Il proprietario ha autorizzato esplicitamente questa generazione dopo
l'abbandono del tentativo 300034. Nessuna installazione, prova browser,
emulatore, deploy o invio manuale. Main non promosso.

Sponsor verificati prima e dopo: `enabled=false`, zero campagne, revisione 117.
Pannello e sincronizzazione dei dati sponsor non attivati.

## Artefatto e sorgenti

- AAB: `release-artifacts/android-play/meteofriul-300035-0.1.15.aab`, 73.017.265 byte.
- SHA256: `1bcf6a32348eee0f098f475c179523a309d962a86c3faf8736a0bd29a1622762`.
- Certificato upload: `338c051587d62cdad6f9bd38eaa1e793d3da2d6c30c4270f8450a93a6ecec3b4`, uguale all'ultima accettazione Play.
- Mapping: `meteofriul-300035-0.1.15.mapping.txt`, SHA256 `1578fd6e78e3f27ea18a568673e571bf6e602f88a7d9bf349a1f34300307e6ff`.
- [Riserva](../../release-history/android-play/meteofriul-300035-0.1.15.reservation.json) e [manifesto immutabile](../../release-history/android-play/meteofriul-300035-0.1.15.release.json).
- [Ricevuta di verifica](evidence/release-0.1.15-300035-build-20261023/verification.json).

Copie verificate nel worktree release e nella radice canonica, sotto
`release-artifacts/android-play/`. Log e prove durevoli nella radice canonica:
`release-artifacts/android-play/evidence-300035/`. AAB, mapping, log privati e
chiavi restano ignorati da Git; sorgenti, documenti, riserva e manifesto sono
versionati. 58 file precedentemente protetti con hash invariati, incluse le
vecchie release. Non rigenerare né sovrascrivere il 300035.

## Verifiche completate

CI del commit compilato [39917176816](https://github.com/meteofriul/meteofriul-app/actions/runs/39917176816):
frontend, backend e contratti Windows PASS. Regressioni locali del controllo
nativo: 43 asserzioni PASS; contratti builder e nove guardie frontend PASS.

Builder protetto completato con codice 0, dalle 07:25:27 alle 07:30:37 UTC.
Gradle: 294 task, 1m15s, BUILD SUCCESSFUL. Bundletool 1.18.3 validato per hash;
validazione bundle, identità, binding API/Community e firma di tutti i payload
PASS. Mapping esterno e incorporato coincidono. Configurazione Capacitor e
registro plugin coincidono con i sorgenti approvati; risorsa
`com.meteofriul.app:xml/config` risolta in `base/res/xml/config.xml`.
Debug WebView e mixed content disattivati, nessun server di sviluppo nel JSON.
Una verifica indipendente della copia durevole riconferma hash e contenuto.

Preflight API prima/dopo PASS, immagine `5522b4cf…`, tag `play-b6fbe4d`,
revisione `meteofriul-api-00251-jow`. Provenienza originale `e180b87a`, equivalente
a `599aea2f` e compatibile con l'ancestry della prova TTL storica. Push TTL,
Community TTL e sicurezza dei contenuti Community PASS. Il set dei writer
include il job avvisi già distribuito il 21 ottobre. Nessun aggiornamento
backend o nuovo deploy necessario per questa build.

La [diagnosi del 300034](ANDROID_0.1.15_300034_BUILD_20261023.md) rimane distinta:
il filtro bundletool errato è corretto e provato con output reale e casi
negativi; riserva e abbandono non sono riscritti.

## Web dalla stessa sorgente

Build Web protetta `-BuildOnly` dal medesimo commit `5e9bc7dc`, versione 0.1.15,
506 file; guardie API, CARTO e service worker PASS. Archivio canonico:
`release-artifacts/web-candidates/20261023-0.1.15-5e9bc7dc/`.
Manifest SHA256 `b864977656515bb1f651026df17d42d95d4c4eda90cc7062998c5f9a24add8ff`;
hash di tutti gli asset ricontrollati. Sostituisce la candidata `c30cfe33`, che
resta conservata. Nessuna pubblicazione; ultima verifica del sito pubblico
22 ottobre: 0.1.14. Nessuna nuova prova browser per scelta del proprietario.
Safari/iPhone, PWA e aggiornamento cache rimangono NON VERIFICATI.

## Controlli runtime ancora aperti

| Area | Esito e limite |
| --- | --- |
| Edge-to-edge / inset | Regressioni automatiche incluse nella CI; Android 15/16, gesti/tre tasti, cutout, tastiera e ripresa della nuova AAB NON VERIFICATI |
| API system bar deprecate | Nessuna modifica applicativa o toolchain in questa build; rimangono avvisi di dipendenze e Gradle, da non dichiarare risolti |
| Orientamento / schermi grandi | Policy telefono portrait e layout adattivo invariati; tablet e multi-window della nuova AAB NON VERIFICATI |
| R8 / risorse | Minificazione, shrinking, firma, configurazione nativa e mapping PASS sul bundle reale; funzionamento sul dispositivo NON VERIFICATO; quattro librerie native transitive senza simboli forniti |

NATIVE-CONFIG-01 è risolto nel confezionamento, resta da verificare l'avvio
minificato. LOCATION-UPDATE-01 e transitorio CAMS sono inclusi e coperti dalle
regressioni, ma attendono il nuovo pacchetto sul telefono. Acquisire preferenza
Posizione prima e subito dopo l'aggiornamento, prima di interazioni che la
cambino. Il difetto riprodotto non dimostra la causa dell'episodio Play precedente.

## Prossimo passaggio

Dopo il salvataggio su GitHub e la CI dei record di build, chiedere una distinta
autorizzazione per caricare **questo file esatto** nel test interno personale.
Nessuna pubblicazione in produzione. Non promuovere la release su main prima
dei controlli runtime pertinenti. [Stato](RELEASE_0.1.15_STATUS_20261021.md) ·
[Runbook](PLAY_AAB_RUNBOOK.md) · [Regole di prevenzione](ANDROID_BUILD_PREVENTION_RULES.md).
