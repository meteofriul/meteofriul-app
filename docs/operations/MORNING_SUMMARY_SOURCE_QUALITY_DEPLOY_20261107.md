# Sintesi mattutina: dati orari incompleti — 7 novembre 2026

## Guasto e correzione

La corsa ordinaria del 7 novembre alle 07:30 CET ha letto 19 gruppi ICON ma li
ha tutti scartati nella costruzione del testo: 53 dispositivi idonei, 19
`source_failed`, zero tentativi FCM. Anche la corsa del 6 novembre è fallita;
per quel giorno la causa puntuale non è stata verificata. La sintesi serale del
6 novembre è riuscita con 53 accettazioni FCM; la ricezione sui singoli telefoni
non è stata verificata.

Nel campione pubblico di Udine della corsa ICON `20261107T000000Z`, 10 delle
16 ore residue avevano `precipitation_mm=null` e una aveva
`liquid_rain_mm=null`. I flag indicavano valori entro la risoluzione di codifica:
`null` significa misura non quantificabile, non pioggia pari a zero. La fonte
era pubblicata prima delle 07:30. I payload delle altre 18 località non sono
stati ispezionati singolarmente.

La [PR 44](https://github.com/meteofriul/meteofriul-app/pull/44), merge
`56e6b0017206c325fa9105ba6643bab37af0ab99`, conserva temperatura e massima
verificabili e aggiunge una sola breve nota sui dati delle precipitazioni quando
la serie oraria è incompleta. Non deduce assenza o orario della pioggia dai
valori mancanti. Il testo completo resta uguale con dati completi; i valori
malformati restano bloccanti. Tipo di notifica, deduplica e scheduler invariati.

Il collaudo owner può selezionare un solo hash SHA-256 d'installazione con
override temporaneo e gate singolo. Un hash non trovato blocca fonte e FCM.
L'override non è nella configurazione permanente. La [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/42357983461)
e la [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/42359433026)
hanno superato tutti e tre i job. La suite backend locale aveva due errori nel
test di sicurezza `lxml` perché l'interprete host usa 5.4.0 invece della 6.1.0
prescritta; la CI ha usato la dipendenza versionata.

## Immagine, collaudo e stato live

L'archivio Git del backend del commit `6d61770376c35e0c440e10e8304fbc4e3c4c3e1b`,
contenente solo `Dockerfile`, `requirements.txt` e `app`, ha SHA-256
`a8859fa20e58c91747a65609e81121e1d969b8eed2d8fc425e4b4125260f4c29`.
Cloud Build `e81244f9-028c-4db3-9520-a988f25275e9` è terminato con `SUCCESS`.
Il backend del merge `main` coincide con quello del commit candidato. Il digest
immutabile è `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:50f6eaebc18ba27890cffb540653adcef618c4df97a55118df81dd8a0f7db61b`.

Il job temporaneo `meteofriul-morning-forecast-qa-20261107` è stato creato
senza scheduler, con modalità permanente `off`, gate singolo e nessun hash
permanente. L'esecuzione `...-d57hh` in `dry_run` ha valutato un solo target e
una sola fonte, con zero errori e zero invii. L'esecuzione `...-2d4vv` ha
registrato `status=sent`, un target, un tentativo, una accettazione FCM e zero
errori; il proprietario ha confermato la ricezione di una notifica sul telefono.
Testo, tap e ricezione su altri telefoni non sono stati verificati sul dispositivo.
Dopo il readback `off` e l'assenza di scheduler, il job QA è stato eliminato.
Nessun identificatore del dispositivo è conservato in questo verbale.

Il 7 novembre è stata aggiornata **solo l'immagine** del job ordinario
`meteofriul-morning-forecast`, dal digest
`sha256:ab5ad97c5120d80fa1bdc4954ab9faca2d010d21aac842e1c3aba51ce327ea13`
al nuovo digest sopra. L'audit live restituisce `ready=true`: ambiente `send`,
account runtime e invoker corretti, scheduler `ENABLED` con `30 7 * * *` in
`Europe/Rome`, zero retry. Nessuna corsa ordinaria è stata forzata. La prima
corsa programmata con la nuova immagine è attesa l'8 novembre alle 07:30 CET;
esito e consegna ai destinatari restano da verificare. Nessuna AAB,
pubblicazione Web o versione dell'app è stata modificata.
