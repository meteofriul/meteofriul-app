# Community 0.1.15: deploy e attivazione del 21 ottobre 2026

## Esito

Community v3 attiva su `meteofriul-community`, progetto `meteo-friul`, regione
`europe-west1`. Revisione `meteofriul-community-active0115-20261021`, 100% del traffico.
La revisione compatibile `meteofriul-community-compat0115-20261021` rimane Ready per il rollback.
Entrambe usano la stessa immagine:

`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/community@sha256:5a6b66ba8fc8f5861ac2fac57eee7c1dcf088a015479e56e291ea3d85a66a2d7`

Build `1dd3980b-eafc-4dcf-bff0-e7f9b2795f98` riuscita dal solo archivio approvato del commit
`05a4fcc69969c259163eaad9bca4a4f234384e81`, 35 file ammessi.
Nessun deploy di API generale, job, sponsor, pannello o Web. Nessuna AAB,
installazione, esecuzione di job, push Git, segnalazione o notifica manuale.

## Passaggio eseguito

1. Riletta la produzione e confermati digest, configurazione e traffico della
   baseline `meteofriul-community-00002-tt2`. Ripetuti hash e 33 test del
   pacchetto isolato: PASS. L'unica differenza di byte rispetto a main riguarda
   CRLF/LF nel file di test, verificato anche contro il commit fissato; il
   contenuto applicativo e l'hash dell'archivio non cambiano.
2. Costruita l'immagine approvata. Applicata al solo sink `_Default`
   l'esclusione `community-http-request-privacy`, conservando audit, altre
   impostazioni, log applicativi e metriche native.
3. Fissato esplicitamente il traffico alla vecchia revisione. Creati gli URL
   di controllo restituiti da Cloud Run e aggiunti all'allowlist host, insieme
   all'host pubblico. Distribuita la candidata senza traffico e v3 a 0.
4. Verificati letture, contratti, CORS Android/Web e controllo dei token sulla
   candidata. Dopo la prova di propagazione dei log, passata al 100% con v3 a 0
   e ripetute le verifiche pubbliche.
5. Creata la revisione attiva con lo stesso digest: unica differenza di
   configurazione applicativa, `COMMUNITY_V3_WRITES_ENABLED` da 0 a 1.
   Verificata prima tramite tag e poi con il 100% del traffico pubblico.

Sono preservati archivio, puntatore Firestore, prefisso snapshot, identità
runtime, App Check e allowlist Android/Web, accesso pubblico, CPU, memoria,
concorrenza, timeout e scaling. Nessuna migrazione, inizializzazione o copia
di dati TEST. Al controllo finale il puntatore snapshot è risultato
identico, contenuto compreso.

## Compatibilità e confini delle prove

- App già installata, per esempio 0.1.14: richieste senza header mantengono
  il contratto `community-pilot-national-safety-v2`. Letture e CORS passano.
- 0.1.15: header `X-Meteo-Community-Rules: community-reports-v3`, contratto v3
  leggibile e scritture abilitate nella configurazione distribuita.
- Le vecchie app leggono anche i gruppi v3, ma per interagire con un gruppo
  v3 devono aggiornarsi. La guardia contro il ritorno alle vecchie regole
  dopo un invio v3 resta presente, senza azzerare punti o identità.
- Le operazioni locali e i test nell'immagine coprono scritture e rollback;
  sulla produzione sono state eseguite solo letture, preflight e richieste
  a uno storico protetto respinte prima dell'elaborazione per token mancante
  o invalido. Nessun endpoint di invio, conferma o reputazione chiamato.
- Non è una prova end-to-end Play Integrity della futura AAB 0.1.15 né una
  prova visuale sul telefono. La creazione reale di una segnalazione resta
  al successivo test personale autorizzato.

Un health 500 è stato osservato prima delle modifiche cloud; la rilettura e
i controlli successivi hanno risposto 200. La causa non è stata dimostrata e
non viene attribuita al nuovo deploy. Nessun errore runtime osservato nel
controllo finale delle revisioni attivate.

## Privacy

Il primo campione, durante la propagazione dell'esclusione, mostrava ancora
13 record HTTP. È conservato come esito intermedio, non come verifica riuscita.
Il controllo successivo mostra zero record HTTP Community nell'intervallo
esplicito, con paginazione completa, controllo precedente positivo, log
applicativi e di un altro servizio presenti e metriche native disponibili.
Nessun log storico cancellato. La prova non elimina l'elaborazione iniziale
del provider né garantisce il comportamento di future modifiche ai sink.

## Rollback compatibile pronto, non eseguito

Per fermare le nuove scritture v3, riportare il traffico alla revisione
`meteofriul-community-compat0115-20261021`. È lo stesso digest verificato, con il flag a 0.
Le letture restano disponibili; i nuovi client ricevono
`community_v3_rollout_pending` sulle scritture. Le operazioni degli utenti
non aggiornati rimangono disponibili secondo le regole di compatibilità.

```powershell
gcloud run services update-traffic meteofriul-community --to-revisions=meteofriul-community-compat0115-20261021=100 --project=meteo-friul --region=europe-west1 --account=meteofriul@gmail.com
```

Non ripristinare snapshot e non tornare alla vecchia immagine dopo scritture
v3. Il comando è documentato, non è stato eseguito. Conservare il servizio
compatibile prima di una successiva modifica del traffico.

## Sponsor: sospensione vincolante richiesta dal proprietario

Dal 21 ottobre le schede sponsor devono restare inattive fino a nuovo ordine
esplicito. Restano sospesi anche sviluppo del pannello e allineamento dei dati.
Il catalogo dell'API Play verificata risponde `enabled=false`, zero campagne.
Il percorso relativo del sito Web restituisce HTML, quindi non viene usato
come prova del catalogo. Il pacchetto Community non contiene il servizio
sponsor e questo intervento non cambia alcun dato, flag o deploy sponsor.
Il codice grafico già presente nella candidata non autorizza l'attivazione:
questo vincolo vale anche nella successiva preparazione della 0.1.15.

## Evidenze e stato Git

[Riepilogo e identità](../../release-history/community-deploy/0.1.15-20261021/deployment.json),
[verifica pubblica attiva](../../release-history/community-deploy/0.1.15-20261021/public-on-verification.json),
[audit finale](../../release-history/community-deploy/0.1.15-20261021/final-audit.json),
[prova privacy](../../release-history/community-deploy/0.1.15-20261021/privacy-proof.json).
Hash in `SHA256SUMS.txt` nella stessa directory. Log grezzi, configurazioni
complete e puntatori privati restano sotto `.tmp/community-deploy-20261021`
nella radice canonica e non sono versionati.

Verbale preparato sul ramo dedicato `codex/community-0.1.15-deploy`, dalla main
`ecb409d2`. Nessun push o promozione di questo verbale eseguiti con il deploy.
La [preparazione precedente](COMMUNITY_0.1.15_RELEASE_PREPARATION_20261020.md)
rimane evidenza storica del pacchetto, non descrive più lo stato distribuito.

## Salvataggio e promozione documentale del 21 ottobre

Il proprietario ha autorizzato commit e promozione su main del solo verbale
con le evidenze già raccolte. Questo passaggio non esegue nuove verifiche cloud:
gli orari nei file indicano i controlli effettuati durante il deploy.

Il controllo locale verifica JSON, riferimenti, coerenza degli esiti e hash dei
15 file elencati nel manifest, anche nei blob preparati per Git. La regola
`.gitattributes` limitata a questo archivio conserva i byte originali e impedisce
che la normalizzazione dei fine riga invalidi gli hash. I dati grezzi privati
restano fuori dal commit.

La promozione documentale avviene per fast-forward dalla main `ecb409d2`;
nessun file applicativo, configurazione runtime o servizio viene modificato.
Nessuna AAB, installazione, push, nuovo deploy o invio manuale. Resta vincolante
la sospensione di schede sponsor, sviluppo del pannello e allineamento dei dati
fino a nuovo ordine esplicito del proprietario.
