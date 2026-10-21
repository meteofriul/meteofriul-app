# Registro immutabile Android Google Play

**Stato del 21 ottobre:** 300032 è abbandonata senza bundle; 300033 / 0.1.15
è accettata nel test interno, con verifica del dispositivo e rilievi aperti.
I relativi record immutabili sono conservati sul
[ramo release](https://github.com/meteofriul/meteofriul-app/tree/codex/release-0.1.15/release-history/android-play)
finché la release non viene promossa. Prima di una nuova riserva considerarli
anche se il checkout di main non contiene ancora quei file.
[Stato e limiti](../../docs/operations/RELEASE_0.1.15_STATUS_20261021.md).

Questa directory e' il registro append-only della procedura protetta
`scripts/build-play-aab.ps1`. Contiene tre tipi di record, tutti immutabili:

- `*.reservation.json`: riserva `versionCode` e `versionName` prima della
  compilazione. Una build fallita non libera il codice;
- `*.release.json`: identifica l'AAB costruito, ancora nello stato
  `built-not-uploaded`. Non afferma che Play Console lo abbia visto o accettato;
- `*.evidence.json`: registra successivamente `play-accepted`, `abandoned` o
  una rotazione autorizzata della upload key.

Per la sequenza completa di preparazione, build, verifica e caricamento seguire
il [vademecum operativo](../../docs/operations/PLAY_AAB_RUNBOOK.md).

Ogni candidato deve avere un `versionCode` maggiore sia del massimo presente
in questo registro e nella cronologia privata, sia dell'ultimo valore osservato
in Play Console. Un codice riservato, costruito o abbandonato non viene mai
riutilizzato.

L'AAB firmato viene copiato senza sovrascrittura in
`release-artifacts/android-play/`, fuori da `frontend/android/app/build`. La
directory e' ignorata da Git ma deve essere conservata su storage durevole e
protetto; il nome del file e il suo SHA-256 sono registrati nel manifesto. Il
manifesto, la prenotazione e le evidenze vengono invece versionati nel
repository.

La prima build richiede il fingerprint SHA-256 della upload key come trust
anchor esplicito. Le build successive possono fidarsi soltanto dell'ultima
evidenza `play-accepted`; un semplice record `built-not-uploaded` non diventa
mai una fonte di fiducia. Una rotazione e' ammessa solo tramite una nuova
evidenza append-only che riporti vecchio fingerprint, nuovo fingerprint e
riferimento verificabile della Play Console.

Ogni worktree ha la propria configurazione locale ignorata da Git. Prima
di lanciare la build, assicurarsi che `VITE_TERRITORY_CARTO_API_KEY` sia
disponibile nel processo o in `frontend/.env.android.local` del worktree
corrente; non stampare la chiave. Lo script verifica Carto prima di creare
la reservation e ricontrolla la configurazione nel bundle Android.

Dopo la build:

1. committare e pushare prenotazione e manifesto, poi attendere la CI verde;
2. caricare esattamente l'AAB archiviato con lo SHA-256 registrato;
3. se Play lo accetta, eseguire `scripts/record-play-release-evidence.ps1` con
   evento `play-accepted` e un riferimento verificabile alla Console;
4. se non verra' caricato o usato, registrare invece `abandoned` con il motivo;
5. committare e pushare la nuova evidenza, senza modificare record precedenti.

Non eliminare, rinominare o correggere retroattivamente alcun record. Un errore
richiede una nuova evidenza o una nuova versione, mai la sovrascrittura della
cronologia.

Lo script protetto e la CI eseguono
`scripts/audit-play-release-ledger.ps1`: ogni JSON deve essere tracciato,
presente nel worktree, aggiunto da un solo commit e non deve comparire in alcun
commit successivo come modifica, rinomina, copia o cancellazione. In questo
modo anche una vecchia evidenza `play-accepted` non può essere riscritta per
sostituire silenziosamente il certificato upload fidato.


La modifica del builder che segue è sul ramo release, ancora da promuovere.
Un tentativo abbandonato **senza manifesto AAB** può essere ripetuto con lo stesso
nome visualizzato e un codice maggiore, conservando riserva ed evento precedenti.
La regola non permette mai di riutilizzare un codice né di cambiare un artefatto
esistente. Una riserva ancora aperta o una versione già costruita blocca il nome.
