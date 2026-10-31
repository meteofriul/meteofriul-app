# Stato conservato e copertura dei report — 31 ottobre 2026

Ricognizione del profilo `controllo_job` sulle prove già raccolte, senza nuove
chiamate cloud. Copre sei servizi HTTP, quattordici istanze di job, undici
Scheduler abilitati e le dipendenze dell'app. Non è un nuovo controllo in
tempo reale: configurazione, esecuzione, freschezza del dato e corretto
funzionamento nell'app sono prove distinte.

## Decisione

Conservare questo indice datato e riutilizzare gli stati già presenti.
ICON, CAMS, Eventi, allerte, notifiche, monitor e Community possiedono già
JSON persistenti, checkpoint o registrazioni transazionali. Non serve un
nuovo job solo per duplicarli. Un'eventuale panoramica del pannello dovrebbe
leggere sintesi degli stati esistenti, senza avviare acquisizioni.

L'[audit dei costi](JOBS_COST_AUDIT_20261031.md) ha già portato al
[riuso della verifica FVG](ICON_VERIFICATION_REUSE_20261031.md). Le altre
ottimizzazioni qui indicate richiedono prima una misura del problema.

## Dati e stato già disponibili

| Servizio | Stato già conservato | Controllo o intervento utile |
| --- | --- | --- |
| ICON FVG e nazionale | Puntatori, manifest, hash, generazioni, validità, claim e checkpoint | Riutilizzare la verifica della stessa generazione; distinguere nuovo dato da esecuzione senza aggiornamento |
| CAMS | Famiglia atomica, UV, richieste, checkpoint ed esiti per componente | Misurare letture ripetute e ripristino del checkpoint; conservare separati gli esiti dei componenti |
| Eventi | Catalogo persistente, revisione, data/esito/errori per fonte e checkpoint | Verificare riuso per singola fonte e recupero delle quattro fonti arretrate rilevate il 31 ottobre |
| Allerte ufficiali | Snapshot Firestore FVG e nazionale, acquisizione, revisione e validità | Verificare copertura e conservazione correnti; lo stato di base esiste già |
| Notifiche | Outbox, deduplica, claim e ricevute transazionali private | Eventuale riepilogo aggregato di tentativo/esito; accettazione FCM e ricezione sul dispositivo restano distinte |
| Monitor ICON | Stato JSON FVG/nazionale con età, cause, esito e storia | Riutilizzarlo e verificare lo stato dopo il recupero; non creare un secondo monitor |
| Community | Snapshot privati immutabili, puntatore condizionale, hash e ricevute | Verificare conservazione fisica degli snapshot superati e funzionamento corrente, senza copiare dati privati nel report |
| OSMER | Emissione, hash e versione parser nel payload; cache di processo di 30 minuti nel percorso esaminato | Non è dimostrato uno snapshot condiviso durevole tra istanze/riavvii: verificare fonte e comportamento effettivi prima di progettarlo |
| Radar | Timestamp dei prodotti; cache di processo di 4 minuti, ripiego su dati precedenti fino a 30 minuti | Valutare riuso dei soli metadati se il consumo lo giustifica; nessun archivio delle immagini proposto |
| Webcam | Cataloghi JSON versionati, controlli amministrativi e cache | Catalogo e risposta HTTP non provano freschezza dell'immagine; verificare l'updater prima di aggiungere uno stato dell'ultimo controllo per webcam |

La mappa dettagliata, con responsabilità, percorsi, prove e limiti, è nel
[JSON di ricognizione](evidence/APP_SERVICE_REPORT_COVERAGE_20261031.json).
Le indicazioni sul codice non attestano automaticamente la configurazione
distribuita. Una cache in memoria non equivale a un archivio durevole.

## Prove operative da aggiornare

| Priorità | Ambito e responsabile | Prova mancante o incompleta |
| --- | --- | --- |
| Prima | API generale — `meteo` | Emissione e completezza OSMER IT/FUR, timestamp radar e freschezza delle webcam correnti; le metriche HTTP non coprono queste funzioni |
| Prima | Eventi — `eventi` | Stato delle fonti CSS Udine, Teatro Verdi Trieste, Galleria Spazzapan e Barcolana dopo gli errori osservati; nessun recupero eseguito da questa ricognizione |
| Prima | Community e persistenza — coordinatore | Ultima prova funzionale completa trovata del 21 ottobre; il 31 sono state lette configurazioni e metriche. Aggiornare prove di contratto, App Check, conservazione e privacy dei log |
| Prima | Hosting/parità — coordinatore e `build_verifica` | Associare artefatto pubblico, hash e sorgente; controllare cache/redirect e qualifiche Safari/iPhone. Il successo dell'anteprima 5174 non dimostra parità online |
| Successiva | Storage, Firestore e immagini — proprietari dei dati | Conservazione, TTL effettivo, versioni superate e possibilità di ripristino; dimensioni e scadenza logica non provano cancellazione fisica |
| Successiva | Costi — coordinatore | Fattura, crediti, franchigie condivise, rete, build e hosting: il modello disponibile è parziale |
| Successiva | Mappe/località, identità e servizi esterni — coordinatore | Disponibilità e quote dei fornitori, cache, IAM e attestazione sul dispositivo non coperti dall'audit dei job |
| Editoriale | Scopri/Almanacco — `scopri` | Copertura delle date, revisione FUR e associazione al pacchetto distribuito; non richiede di per sé un job ricorrente |

Mercati e pannello mantengono il loro percorso di preparazione e revisione.
La loro pubblicazione resta disattivata; non sono un settimo servizio di
produzione mancante dall'inventario. Sponsor, landing e pannello sono progetti
collegati: le loro configurazioni e i loro costi attuali non sono stati
verificati da questa ricognizione.

## Come conservare i prossimi esiti

Per una sintesi operativa bastano servizio, ora del controllo, ultimo
tentativo, ultimo successo, ciclo/revisione, pubblicazione, validità, esito,
causa e riferimento alla prova. I campi non verificati restano sconosciuti:
non vanno ricavati dall'età del documento. La sintesi non deve contenere
token, destinatari push, identificativi personali o snapshot Community.

Se in futuro uno stato JSON sarà usato per saltare lavoro, deve identificare
la versione verificata e la sua scadenza, con aggiornamenti condizionali e
invalidazione quando cambiano dati o regole. Un semplice `ultimo_controllo`
non dimostra che il dato sia ancora valido.

L'inventario UI3 del 10 agosto e i verbali di singoli deploy rimangono prove
datate. Alcune descrizioni sono superate da aggiornamenti successivi: questo
indice ne esplicita i limiti senza riscriverne la storia.

## Provenienza e limiti

Sono stati verificati 64 riferimenti locali nella radice canonica. Alcuni
rapporti del 31 ottobre sono ancora nel lavoro locale Mercati e non vengono
incorporati in questa PR. Il JSON distingue i riferimenti disponibili in
questo candidato da quelli solo locali; i percorsi `.tmp/` sono prove locali,
non allegati pubblicati. La ricognizione conservata contiene le conclusioni
e i limiti anche quando tali allegati non sono disponibili a un lettore remoto.

Nessun job eseguito o modificato, nuova pianificazione, deploy, invio push,
cancellazione di dati o verifica su dispositivo effettuati per questo indice.
