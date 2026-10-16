# Runtime IAM notifiche — preparazione 30 settembre 2026

## Scopo

Questo workstream prepara un'identita' runtime minima per i processi che leggono
e scrivono lo stato notifiche in Firestore e consegnano messaggi con FCM:

- service account:
  `meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`;
- ruolo predefinito: `roles/datastore.user`;
- ruolo custom: `projects/meteo-friul/roles/meteofriulFcmSender`;
- unica permission del ruolo custom: `cloudmessaging.messages.create`.

Non modifica il Compute default, non rimuove ruoli e non cambia API, Cloud Run
Job, servizi, scheduler, immagini o modalita' di consegna. In particolare non
attiva la notifica serale.

## Esito applicazione

Applicazione autorizzata ed eseguita il 30 settembre 2026 sull'account
`meteofriul@gmail.com` e sul progetto `meteo-friul`:

- service account creato e attivo;
- ruolo custom creato in stage `GA` con la sola permission
  `cloudmessaging.messages.create`;
- binding `roles/datastore.user` presente;
- binding del ruolo custom FCM presente;
- nessun altro ruolo di progetto assegnato al nuovo runtime.

Il readback autorevole finale ha restituito `ready=true`, zero finding e zero
blocker. Non sono stati creati o modificati job, scheduler o servizi Cloud Run.

## Gate

Lo script `scripts/prepare-notification-runtime-iam.ps1` parte in `Audit`. La
modalita' `Apply` puo' soltanto colmare quattro assenze note: service account,
ruolo custom e i due binding minimi. Si arresta se trova un account/progetto
diverso, un'identita' disabilitata, permission aggiuntive o qualsiasi ruolo di
progetto inatteso assegnato al runtime.

```powershell
.\scripts\notification-runtime-iam.contract.tests.ps1
.\scripts\prepare-notification-runtime-iam.ps1 -Mode Audit

# Solo dopo audit e approvazione esplicita della mutazione IAM:
.\scripts\prepare-notification-runtime-iam.ps1 -Mode Apply
.\scripts\prepare-notification-runtime-iam.ps1 -Mode Audit
```

La procedura e' idempotente. Un errore parziale non avvia workload: l'identita'
resta inutilizzata e il readback successivo indica esattamente quale requisito
manca. Non viene eseguita una cancellazione automatica, per evitare di eliminare
una risorsa che potrebbe essere diventata condivisa durante un esito ambiguo.

## Passo successivo separato

Dopo un audit verde, il ramo della notifica serale deve sostituire nello script
di deploy il Compute default con questa identita', poi ripetere test, build per
commit, deploy iniziale in `off`, `dry_run` e prova sul telefono proprietario.
La migrazione degli altri workload esistenti resta un change distinto.
