# Tolleranze nei job senza cambiare il formato delle app installate

Preparazione locale del 19 ottobre 2026, stesso ramo `codex/local-notice-icon2i-analysis`.
Questa revisione sostituisce il piano che aggiungeva `accumulation_quality` al
documento pubblico. Nessuna AAB, build Android, installazione, push, deploy,
acquisizione o invio reale. Sorgenti e piano aggiornato sono salvati insieme nel ramo dedicato.

## A cosa serve

I job possono distinguere una quantità entro tolleranza da un dato mancante,
senza obbligare gli utenti ad aggiornare l'app per continuare a leggere le
previsioni. La TEST e l'app ufficiale continuano a ricevere il formato v1 attuale.
Non cambia il significato dei valori visualizzati: i null pubblici restano null.

## Due documenti collegati

- Il percorso `weather/v1/icon2i/runs/<run>/municipalities/<istat>.json` conserva
  chiavi, misure, flag e righe a due ore del contratto precedente. Il publisher
  rimuove soltanto la nuova chiave oraria prima di calcolare hash e manifest.
- Il percorso aggiuntivo `weather/v1/icon2i/runs/<run>/accumulation-quality/<istat>.json`
  contiene la prova per i job, schema `icon-accumulation-sidecar.v1`, con corsa,
  comune, SHA-256 esatto del documento pubblico e associazione delle ore.
  Non è un archivio privato: è metadato meteo servito dallo stesso servizio HTTP,
  su un percorso separato, richiesto soltanto dal nuovo consumatore.
- Il checkpoint conserva l'input arricchito e la diagnostica. Il fingerprint
  dell'intento continua ad autenticare anche le prove; in recovery il publisher
  ricostruisce quell'input da previsione e metadato e ne verifica il fingerprint.
  Non si sostituisce l'hash dell'intento con quello del solo documento pubblico.

Tutti i metadati vengono scritti e riletti prima di pubblicare manifest e latest.
Oggetti preesistenti sono create-only; conflitti non vengono sovrascritti.
Il lettore HTTP usa la stessa autorizzazione per corsa attiva/precedente del
documento pubblico: un metadato in staging o revocato non diventa accessibile.
Un problema nel metadato non modifica la disponibilità della previsione pubblica.

## Consumatore e diagnostica

`LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED=true` abilita la lettura aggiuntiva
nel nuovo adattatore regionale; il default è `false` per preparare il passaggio
senza attivarlo implicitamente. Riepiloghi e avvisi condividono l'adattatore.
Il nazionale resta invariato. Il fetch aggiuntivo usa gli stessi timeout e
tentativi limitati, con al massimo un documento in più per fetch comunale.

Hash, corsa, comune, ore e prova devono coincidere; l'intero metadato viene
rifiutato se una verifica fallisce. Metadato assente, servizio non aggiornato,
errore HTTP o prova invalida non autorizzano la tolleranza. I mancanti rimangono
indisponibili per i fenomeni dipendenti; vento e caldo possono ancora essere valutati.
Nessun nuovo zero viene inserito nel documento o nei dati condivisi dei riepiloghi.
Le soglie e gli exit code restano quelli già preparati.

La diagnostica `data_quality.by_source_run[].accumulation_evidence` conta
`disabled`, `verified`, `unavailable`, `invalid` sui punti canonici, con il
denominatore esistente e senza moltiplicare i dispositivi. Restano i motivi
delle guardie e le valutazioni che usano la tolleranza, distinti dall'assenza
del file aggiuntivo. Non è stata creata una policy di allarme.

## Ordine futuro, ancora da autorizzare

1. Promuovere solo dopo revisione i nuovi sorgenti salvati nel ramo dedicato. Non distribuire
   isolatamente i vecchi commit tecnici come piano definitivo: non contengono
   questa separazione. Il kit locale aggiornato esporta tre fasi cumulative.
2. Fase 01: aggiornare il servizio HTTP per il nuovo percorso; predisporre
   publisher e lettore checkpoint compatibili come rollback. Acquisizione,
   derive e materializzatore restano quelli della baseline in questa fase.
   Il servizio HTTP, prima trasparente al nuovo campo, ora va aggiornato proprio
   per servire il percorso aggiuntivo. Monitor di freschezza invariato.
3. Fase 02: preparare un consumatore distinto senza invii con il flag sopra
   abilitato. Aggiornamenti di avvisi locali, mattutino e serale vanno coordinati;
   i riepiloghi continuano a rifiutare ore incomplete, senza dichiararle asciutte.
4. Fase 03: attivare il produttore su una nuova corsa, senza riscrivere corse
   storiche. Controllare separatamente previsione pubblica e prova per i job.
5. Verificare il candidato sulla nuova corsa e solo poi autorizzare gli invii.
   Conferma sul telefono utile a questo punto; non serve una nuova AAB per
   questa compatibilità. Una TEST locale da sola non prova l'integrazione cloud.

Rollback: usare la nuova fase 01 con sidecar e checkpoint 1/2, non il vecchio
commit `91913ad3` da solo. Nessuna eliminazione di dati o modifica degli oggetti
immutabili. Il consumatore può disabilitare l'uso dei metadati mantenendo i
mancanti indisponibili; non tornare al null trasformato in zero.

## Verifiche

- Lettore della release ufficiale `2f02c8ba` (0.1.14) e lettore `main`
  `8497e773`: ciascuno accetta tutti i **215 documenti**, manifest e latest
  proiettati; hash e dimensioni coincidono. Entrambi rifiutano il documento
  arricchito prima della separazione. Sono i validatori JavaScript originali
  eseguiti offline con Node; non una simulazione che allenta il vecchio schema.
- 101 test: nuovo percorso,
  publisher ICON/CAMS, integrità, revoche, staging invisibile, tentativi ripetuti,
  recovery, servizio HTTP con storage fittizio, worker e checkpoint.
- 75 test: lettore regionale/nazionale,
  guardia del file aggiuntivo, flag disabilitato anche con prove inline inattese,
  mancanti e riepiloghi mattutino/serale, con le regressioni di invio esistenti.
- 2 verifiche sulla fase 01
  isolata: recovery del fingerprint arricchito e checkpoint con 215 comuni.
- Kit: 3 patch, 42 file, applicazione ordinata e hash dei sorgenti verificati;
  acquisizione/derive/materializzatore ancora identici alla baseline nella fase 01.
  Sintassi Python, diff, JSON, link locali e canonical workspace cleanliness: OK.

Suite in parte sovrapposte: non sommare come casi unici. Socket bloccati;
storage, HTTP e mittenti fittizi. Nessuna acquisizione, esecuzione cloud o invio.
I log e i pacchetti locali sono sotto `.tmp/icon-sidecar-*` nel workspace canonico;
gli hash dei lettori e delle patch sono nel manifest operativo. Le prime
invocazioni con errori delle fixture/nome delle suite sono state corrette;
gli esiti sopra si riferiscono alle invocazioni completate con successo.

Restano da verificare dopo autorizzazione immagini distribuite, IAM, nuova
corsa reale e allarmi. La prova con il vecchio JavaScript non sostituisce
la conferma finale sul telefono contro i servizi aggiornati. Nessuna AAB
necessaria per il formato compatibile e nessuna percentuale del corpus
autunnale trasformata in soglia operativa.
