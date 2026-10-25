# Pordenone Pensa: appuntamenti distinti — 25 ottobre 2026

Stato: correzione locale, non distribuita. Ramo `codex/events-pnpensa-barcolana`,
base main `0841020a42d836e44de306e9639b07b98fceaefc`.

## Problema e risultato

Il documento ABC 2026 contiene cinque sezioni con data, ora, sede e argomento.
L'adattatore precedente rifiutava tutto il post alla seconda data futura.
Ora quelle sezioni producono cinque eventi distinti: 27 ottobre e 3, 10, 17,
24 novembre 2026, tutti alle 19 a Pordenone. Sedi, immagini ed estratti provengono
da ciascuna sezione; le coordinate restano quelle del comune, senza fingere
una geolocalizzazione della sede. Nessun nuovo campo obbligatorio per i client.

Non si genera una serie presunta dalle parole «cinque incontri»: sono necessarie
le righe esplicite. Anni discordanti, giorno della settimana incoerente, data
aggiuntiva non associata, sessione incompleta o avviso di annullamento/rinvio
mantengono il post in revisione. Il controllo inventario API/sitemap e quello
sulla scomparsa di appuntamenti futuri restano invariati.

Il post Scienza 2026 resta in revisione: il titolo dichiara 2026 ma l'intestazione
interna dichiara «PordenonePensa Scienza 2025». Non è corretto spostare quegli
appuntamenti al 2026. È un'incoerenza della fonte distinta dal parser multi-data.

## Verifica

- Prima della modifica: 9 test mirati PASS.
- Dopo la modifica: 14 test mirati PASS, inclusi catalogo/query/deduplica di
  cinque schede, eliminazione delle sole date passate, revisione parziale della
  fonte e rifiuto dei casi incompleti/contraddittori.
- Suite `python -m unittest discover -s tests -p "test_pilot*.py"`: 770 test,
  PASS con 1 skip preesistente. Dopo l'ultima guardia sulla data priva di ora,
  e sulla struttura estranea/intervalli nel titolo, ripetuti i 14 test mirati: PASS.
- Replay offline dei due post WordPress già salvati: 6892 → 5 eventi; 6945 →
  revisione per anni discordanti. [Identità e risultati](evidence/events-pnpensa-20261025/verification.json).
- `git diff --check`: PASS.

Campioni grezzi e log restano locali: `.tmp/events-source-fixes-20261025` nella
radice canonica e log `events-pilot-pnpensa-20261025.log` nella cartella temporanea
Windows. Non è stata avviata una corsa cloud. Non sono stati modificati cataloghi
pubblicati, scheduler, sponsor, app o notifiche.

## Passaggio successivo

Revisione e promozione separate, quindi eventuale aggiornamento del solo job
Eventi e verifica di una corsa ordinaria. Le cinque nuove schede non sono ancora
pubblicate da questa correzione. Non serve una nuova AAB o un nuovo bundle Web
per leggere i dati prodotti con questo schema. Gestione generale fuori stagione
rinviata; nessun errore di trasporto viene classificato come fine stagione.
