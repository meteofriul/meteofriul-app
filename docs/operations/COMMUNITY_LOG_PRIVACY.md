# Community Cloud: privacy dei log HTTP

La compatibilita Community con l'app 0.1.14 usa una verifica separata dei log
applicativi e dei log HTTP prodotti da Cloud Run. Rifiutare una query con
coordinate nell'applicazione non impedisce al provider di registrare l'URL.

## Controllo preparato

`scripts/prepare-community-log-privacy.py` produce una esclusione JSON per un
solo progetto e un solo servizio. Non chiama API, non modifica Cloud Logging
e non avvia deploy. Esempio con identificativi dimostrativi:

```powershell
python scripts/prepare-community-log-privacy.py --project isolated-community-qa --service community-compat-qa
python scripts/test-community-log-privacy.py
```

Il filtro esclude tutti i record `run.googleapis.com/requests` del servizio,
indipendentemente da codice HTTP, percorso o codifica della query. Cosi non si
affida a un elenco incompleto di nomi di parametri. Vengono omessi anche URL
senza query, IP remoti e user agent presenti in questi record. I log applicativi,
i log di avvio e le metriche native aggregate di Cloud Run restano disponibili.

La minore disponibilita della diagnostica per singola richiesta e una scelta
esplicita. Le metriche native non sostituiscono ogni analisi dei log: per esempio,
le richieste respinte prima di raggiungere un'istanza possono non essere incluse
nel contatore del container. Eventuali metriche aggiuntive devono usare solo
etichette aggregate; mai URL, coordinate, token o identificativi del client.

## Applicazione e verifica

1. Inventariare sink del progetto, eventuali sink degli antenati e destinazioni.
   Un'esclusione nel solo `_Default` non protegge copie instradate altrove.
2. Conservare la configurazione precedente. Aggiungere l'esclusione ai sink
   interessati senza sostituire esclusioni esistenti o disabilitare log di audit.
3. Attendere la propagazione, che puo richiedere minuti. La risposta positiva
   dell'API conferma il salvataggio, non l'immediata efficacia.
4. Eseguire campioni sintetici prima e dopo: query normali, codificate, parametri
   inattesi, percorsi e richieste 200/4xx; mantenere controlli di log applicativi
   e di un altro servizio. Verificare tutti i risultati paginati e un intervallo
   temporale esplicito; una pagina vuota con cursore non dimostra assenza.
5. Verificare che i record HTTP successivi non compaiano in alcuna destinazione
   pertinente, mentre controlli, log applicativi e metriche restano leggibili.
6. Ripetere il controllo quando cambiano sink, progetto, servizio o diagnostica.

L'esclusione impedisce la conservazione/instradamento attraverso il sink
configurato. Non annulla l'elaborazione iniziale del provider e non cancella
retroattivamente record gia conservati, compresi quelli arrivati durante la
propagazione. Accessi e retention dei log rimangono controlli distinti.

## Confini del collaudo

La policy e destinata inizialmente al QA isolato. La produzione richiede un
inventario aggiornato e una decisione separata prima di applicarla. Nessuna
modifica a main, deploy reale, build Android, AAB o Play e implicita.

La prova della scadenza usa un token App Check autentico a uso limitato,
conservato cifrato solo durante il test: viene accettato prima della scadenza,
poi rifiutato dopo la scadenza naturale, e confrontato con un nuovo token valido.
Il backend mantiene la normale verifica crittografica e temporale. Non vengono
alterati orologio o verifier; la prova non certifica consumo anti-replay,
Play Integrity o autenticazione dell'APK ufficiale.

## Esito QA del 17 ottobre 2026

Il [riepilogo verificato](evidence/community-cloud-qa-followup-2026-10-17.json)
registra il completamento dei due controlli. Il token autentico di 300 secondi
e stato accettato, poi respinto dopo scadenza naturale da entrambi i protocolli;
un token fresco e stato subito accettato. Il verificatore locale conferma
`ExpiredSignatureError`, senza alterazioni dell'orologio o della firma.

Dopo la propagazione, quattro campioni di log HTTP del servizio sono esclusi,
mentre i due controlli applicativo/altro servizio restano presenti. Le nove
richieste HTTP reali finali non risultano conservate nei log grezzi; log
applicativi e metriche native di conteggio/latenza sono ancora disponibili.
I primi campioni inviati durante la propagazione erano invece visibili e
restano documentati nelle evidenze private: l'effetto non e retroattivo.

La configurazione e i permessi reali sono invariati. Servizio e job QA rimossi,
account temporanei disabilitati, credenziali revocate e token locali eliminati.
La policy rimane nel QA. Nessuna modifica al runtime applicativo o nuova build
cloud e stata necessaria; l'immagine collaudata resta quella del commit
`81a2610d98ae967822a3b536d859de3645dbccdb`.

## Fonti

- [Cloud Logging: instradamento, esclusioni e propagazione](https://docs.cloud.google.com/logging/docs/export/configure_export_v2)
- [Cloud Run: metriche native](https://docs.cloud.google.com/run/docs/monitoring)
- [Firebase: scambio del debug token e opzione limitedUse](https://firebase.google.com/docs/reference/appcheck/rest/v1/projects.apps/exchangeDebugToken)
