# Recupero delle modifiche approvate dalla TEST — 19 ottobre 2026

## Stato

Preparazione e verifica della TEST sul telefono completate sul ramo
`codex/forecast-themes-main`, esteso all'allineamento delle modifiche dell'app
approvate dal proprietario. Promozione locale a main autorizzata dopo i controlli
superati, mediante fast-forward dalla base
`6bd4216964ad81f7dcd20d478cde7b0db5ba442c`.
La sorgente TEST consultata è `e7c27181296bfed82f4c44f2d527d773963248b5`.
Il candidato applicativo integrato è `bbef86141066c2e34abf8ac7ebf838909ef36c20`.

Aggiornata soltanto la TEST sul Galaxy A52 a `0.1.14-full-test.6` / `300037`,
con dati preservati. Esito e identità dell'APK nel
[verbale sul telefono](APP_INTEGRATED_TEST_DEVICE_20261019.md).
Nessun push, AAB, deploy, esecuzione di job o invio reale. La configurazione
speciale della TEST resta fuori dalla promozione. Le approvazioni del proprietario
restano valide: il recupero non riapre le scelte UI.

## Cosa viene recuperato

| Ambito approvato | Provenienza TEST | Commit del candidato | Esito |
| --- | --- | --- | --- |
| Testi italiani/friulani, pill del bollettino uniformi e leggibili, Indietro Android fino all'uscita da Home | `a61563e8` | `2ec1a4b7` | Recuperato. In `App.jsx` trasferito soltanto il collegamento di Indietro; conservata la configurazione di main. |
| Conferma compatta No/Sì, icone del fenomeno, richiamo al 112, ricevuta centrata e autore Inviata da / Inviade di | Da `0b8f8230` a `58851b51`, comprese le correzioni della sovrapposizione in friulano | `c2b80e1c` | Recuperato il risultato finale. No conserva la scelta e non invia. |
| Aggiornamento FVG con cache piena e coordinamento del supplemento CAMS anticipato | `1b9dbad9` | `bbef8614` | Recuperato. Protegge bundle attivo, preferenze, puntatori e altri endpoint. |
| Previsioni chiare/scure, card uniformi, icone pioggia e selezione giorno/ora con contorno e sfumatura interna | `e7c27181` | `3b120ba6` | Già preparato nel ramo; conservato integralmente. |
| Catalogo Eventi reale | `c5dfef50` nella TEST | Nessun nuovo port necessario | Main usa già il catalogo pubblico. Il commit TEST cambia soltanto il suo instradamento e namespace della cache. |
| Lettura dei metadati opzionali delle tolleranze | `b25ddfe7` nella TEST | Nessun nuovo port necessario | Già presente in main. `iconAccumulationQuality.js` è identico; le differenze residue del client sono il fix FVG recuperato sopra. |

Il candidato contiene 47 file frontend diversi dalla base. Di questi, 44 hanno
contenuto identico alla TEST, confrontato normalizzando soltanto CRLF/LF.
Tre adattamenti intenzionali:

- `App.jsx`: solo il blocco Indietro, senza la configurazione nazionale specifica
  TEST e senza importare la modifica indipendente alla revoca delle push.
- `weatherV1Client.test.js`: regressione di quota su storage ordinario e isolato,
  senza dipendenza da `qa/full-test/storage.js`.
- `CommunityReportForm.submitLocation.test.jsx`: aggiornato il controllo rimasto
  alla vecchia conferma, con verifica No/Sì in entrambe le lingue.

## Cosa resta fuori

Nessuna importazione di profili/build script Full TEST, Firebase QA, fixture
Community, namespace Eventi TEST, marchio arancione, versioni/package TEST o
limitazioni TEST dei servizi in background e delle notifiche.
La configurazione normale di main resta invariata: questo lavoro non abilita o
disabilita invii e non cambia endpoint o servizi Community.

Restano invariati rispetto alla base i file Android, configurazioni e dipendenze,
script, workflow CI, backend e produttore meteo, asset pubblici, servizi Eventi,
branding e selezione del servizio Community. Non sono importati alla cieca gli
altri commit della storia TEST.

In particolare restano separati, fuori dai quattro gruppi richiesti:

- le modifiche precedenti al calendario/caricamento del bollettino contenute nel
  commit misto `2bd731e5` (distinte dal fix dell'aggiornamento ICON/FVG);
- la revoca nativa delle push dello stesso commit, da valutare come lavoro autonomo;
- la superficie opaca di Impostazioni `431ec71e`, la cui efficacia sul problema
  originale non è stata dimostrata dopo l'interruzione delle prove dell'emulatore.

## Verifiche locali

- 46 file Vitest, **808 test distinti superati**, con configurazione nativa e un
  solo worker. Copertura: lettore/contratto meteo, runtime FVG e CAMS, refresh,
  navigazione, testi, Community, Eventi, Impostazioni e previsioni nei due temi.
- Prima esecuzione: 806 passaggi e un'aspettativa obsoleta nella conferma Community.
  Il controllo chiedeva ancora la frase ripetuta rimossa su richiesta e cercava
  il vecchio pulsante nel corpo. Aggiornato al footer No/Sì, mantenendo i controlli
  GPS e di mancato invio; rieseguito soltanto quel file, 6 test superati.
  Il totale finale combina i 802 test degli altri 45 file con questi 6.
- ESLint su tutti i JavaScript/JSX modificati: superato. Controllato nuovamente
  il solo test Community dopo la correzione.
- `git diff --check`: superato. Cleanliness del workspace canonico: superata.
- Confronto degli ambiti esclusi con main e corrispondenza dei sorgenti TEST:
  superati. Nessuna dipendenza runtime dai file Full TEST introdotta.
- Nessuna installazione di dipendenze; riutilizzate quelle locali esistenti.
  Node `22.17.1`, Vitest `4.1.12`. Test con servizi simulati, nessun invio reale.
- Avvisi di doppia registrazione del plugin Capacitor nel test delle revoche
  CAMS osservati nel log; i relativi 15 test passano. Non sono una verifica nativa.

Riepilogo riproducibile, elenco dei test e identità del codice:
[local-checks.json](evidence/app-approved-alignment-2026-10-19/local-checks.json).

Le precedenti verifiche visive della TEST in italiano/friulano restano evidenze
di quella sorgente. La build Full TEST.5 già controllata sul Galaxy A52 includeva
il fix FVG, ma non i nuovi temi delle previsioni. Non è una prova del candidato
integrato in questo ramo. Nel primo intervento di preparazione non erano state
ripetute prove browser o telefono. La verifica successiva autorizzata del candidato
integrato è ora completata nel [verbale sul telefono](APP_INTEGRATED_TEST_DEVICE_20261019.md),
con una nuova TEST.6; non sono stati avviati emulatori o test cloud.

## Ordine del prossimo passaggio

1. Completato: candidato identificato, nuova TEST.6 installata con autorizzazione,
   Indietro/uscita, No/Sì e ricevuta simulata, previsioni IT/FUR nei due temi,
   aggiornamento FVG, nazionale ed Eventi verificati sul Galaxy.
2. Controlli pertinenti superati: promozione locale del ramo a main autorizzata
   tramite fast-forward. Verificare pulizia e discendenza immediatamente prima
   del passaggio; le configurazioni speciali TEST sono escluse.
3. Push, build di rilascio/AAB e pubblicazione restano azioni successive distinte.
   Per un rilascio valgono [AGENTS.md](../../AGENTS.md) e il
   [runbook Android](PLAY_AAB_RUNBOOK.md#controlli-android-obbligatori-per-ogni-release).
   I casi Android non provati non diventano risolti grazie a questi test frontend.

Il controllo della nuova corsa del produttore previsto per il 20 ottobre è
separato dal recupero dell'app: vedere il
[piano delle tolleranze](ICON2I_COORDINATED_ROLLOUT_20261019.md) e il
[verbale della fase 3](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).
Questo ramo non cambia quel piano e non attiva gli invii.
