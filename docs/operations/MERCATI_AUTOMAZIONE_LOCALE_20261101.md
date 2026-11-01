# Mercati: automazione locale attivata — 1 novembre 2026

## Risultato operativo

Implementato ed eseguito il ricontrollo delle fonti censite. Il primo passaggio
con scrittura ha esaminato **100 mercati**, applicando **25 modifiche a 6 schede**.
Archivio amministrativo dalla revisione **4** alla **5**; **100 mercati, 219
edizioni e 59 pratiche**. Le sei nuove edizioni sono aggiunte ai 213 record
precedenti, senza cancellarne alcuno.

Una copia SQLite consistente della revisione 4 è stata salvata prima
dell'esecuzione. Il confronto successivo conferma: tutte le identità precedenti,
tutte le 59 pratiche, note pubbliche/interne, motivazioni delle edizioni e
precedente audit conservati. Snapshot pubblico identico, revisione pubblica **0**.
Il pannello e la sua API locale restano in modalità pubblicazione disattivata.

Il task Windows **`MeteoFriul-MarketsRefresh-Local`** è registrato e la sua prova
di esecuzione reale ha restituito **LastTaskResult=0**. Il rapporto del task è
`not_due`: i mercati già controllati oggi sono stati saltati, revisione 5
invariata. Prossimo avvio letto dal sistema: **2 novembre 2026, ore 08:20
italiane**. Trigger aggiuntivo all'accesso Windows, processo nascosto, utente
interattivo con privilegi limitati e divieto di sovrapposizione.

**Richiede questo PC acceso e la sessione Windows attiva. Non è un job cloud.**
L'attivazione online del servizio/catalogo resta separata e non è stata eseguita.

## Regola applicata ai dati

Il nuovo riscontro documentato può sostituire il vecchio valore, anche manuale.
Audit con prima/dopo, fonte, data di acquisizione, hash e prova testuale;
revisioni complete immutabili. Lo stesso fatto già osservato non annulla
una correzione manuale successiva; una modifica reale della fonte può farlo.
Questa è la precisazione del proprietario che sostituisce la precedente
proposta di precedenza assoluta dei campi manuali.

Le modifiche sono puntuali: non si sostituisce l'intera scheda con il risultato
di una ricerca. Note editoriali e considerazioni non vengono svuotate. Un
indirizzo meno specifico non elimina dettagli utili già presenti. Le avvertenze
nelle fonti sono conservate con prima/ultima osservazione e consultabili nel
pannello anche nei controlli successivi.

Le edizioni conservano il proprio ID quando una chiave stabile o una data
precedente esplicita documenta lo spostamento. Un'assenza nella fonte non
cancella date. Fonti discordanti bloccano l'intera edizione interessata,
evitando di combinare una data con la sede di un'altra ipotesi. Un conflitto
già registrato sulla scheda resta pertinente al controllo automatico.

Caso reale: **M024, Mercatino del Riuso**, conserva il conflitto già annotato
fra descrizione e lista automatica della fonte; il refresh non ha aggiunto
le date di quella lista. **M053, Lo Scrigno del Doge**, ha invece acquisito
il **6 gennaio 2027**, data esplicita nella fonte, e una sede più dettagliata.
La sua validità arriva a quel giorno, senza inventare la validità per tutto il 2027.

## Copertura e limiti

La lettura automatica copre attualmente:

- Eventi JSON-LD identificati per nome, comune e URL, con date singole,
  stato esplicito e sede dell'edizione.
- Pagine eventi Pro Loco FVG con titolo/comune verificati e sezioni etichettate
  Quando, Indirizzo e, se presente in forma riconoscibile, Orari.
- Calendario delimitato Pro Sacile, conservando le avvertenze ed evitando
  di confermare automaticamente la data indicata come provvisoria.

**Il controllo non verifica integralmente tutte le 100 schede.** Nel primo
passaggio 98 schede hanno almeno un limite o un'anomalia, anche quando altri
riscontri della stessa scheda hanno permesso un aggiornamento. Fra i codici:
85 schede con almeno una pagina non interpretabile, 33 con formato non supportato
(inclusi PDF), 6 con fonte non raggiungibile, 4 con pagina oltre il limite di
dimensione. Questi conteggi si sovrappongono e non equivalgono a mercati cessati.

Restano da ampliare i lettori per fonti comunali, PDF e altri formati; non sono
stati inventati dati per ottenere una copertura apparente. La ricerca
territoriale generale/trimestrale di nuovi mercati non è ancora implementata.
Il calendario non genera date per ricorrenza implicita o per ogni giorno di
un intervallo di manifestazione. Fonti vecchie, identità ambigue, date non
confermate e conflitti rimangono segnalati.

## Pianificazione, persistenza e interfaccia

Il task si avvia ogni giorno ma controlla le singole fonti mensilmente;
appuntamenti nei successivi 30 giorni e verifiche in scadenza entro 30 giorni
sono ricontrollati ogni sette giorni. Errori transitori sono ritentati il
giorno successivo. Budget di acquisizione 30 minuti, salvataggio del lotto
completato e conteggio residuo; massimo 45 minuti per il task Windows.
Priorità ai mercati mai controllati e ai controlli più vecchi.

Le richieste sono HTTPS, con destinazioni pubbliche validate e connessione
all'indirizzo verificato, senza credenziali/cookie/proxy, redirect sullo stesso
host, al massimo quattro URL per mercato e 2 MiB per risposta. Il limite di
quattro fonti è segnalato quando interviene; non attesta copertura delle fonti
aggiuntive. Nessuna nuova dipendenza installata.

`MarketsService.refresh` usa la transazione con revisione attesa e ricevuta
idempotente. Una modifica nel pannello durante l'acquisizione genera conflitto,
senza sovrascrivere silenziosamente il salvataggio concorrente. Ledger e chiavi
delle edizioni sono gestiti dal server e protetti dal PUT del pannello.
Il job non invoca la pubblicazione e non estende la verifica globale della
scheda per effetto di un semplice HTTP 200.

In **Fonti e verifica → Controlli automatici**, lo storico si apre a richiesta:
una modifica o avvertenza alla volta, con confronto prima/dopo e fonte. Moduli
aggiornati serviti su 5182 con HTTP 200; API 8003 riavviata dopo verifica del
processo e riletta autenticata: revisione 5, metadati del refresh disponibili,
pubblicazione disattivata. Verifica visiva della nuova sezione ancora aperta.

## Verifiche ed evidenze

- **92 test backend PASS:** 27 contratto indipendente, 11 job, 18 lettori fonti,
  36 regressioni archivio/API/Firestore simulato/servizio cloud. Ultima piccola
  correzione del controllo indirizzi verificata nuovamente sui 27 test di contratto.
- `compileall` e diff check PASS. Sintassi dei launcher/task PowerShell valida.
- **30 test mirati pannello PASS**, lint senza nuovi avvisi, build PASS con
  1953 moduli; consueto avviso di dimensione chunk non bloccante. Il primo lint
  aveva rilevato un export utility incompatibile con Fast Refresh, poi corretto.
- Copie nel pannello esterno verificate con SHA-256 e confronto preventivo
  delle modifiche concorrenti; originali conservati in `.tmp/`.
- Prima prova su due fonti in sola lettura, poi anteprima dei 100 mercati,
  infine applicazione reale e confronto integrale dei campi da preservare.
- Prova del task registrato: esecuzione riuscita e nessuna seconda revisione
  quando le schede non sono ancora dovute.

Evidenze locali ignorate: `.tmp/markets-refresh-baseline-20261101.json`,
`.tmp/markets-refresh-preservation-20261101.json`, manifest di consegna pannello
`markets-refresh-panel-delivery-20261101.json` e `markets-refresh-notes-delivery-20261101.json`,
percorso build `.tmp/markets-refresh-panel-build-20261101.txt`.
Rapporto applicato `.dev-logs/markets/refresh/refresh-20261101T104601438Z.json`;
prova task `.dev-logs/markets/refresh/refresh-20261101T105156430Z.json`.

Lavoro nel ramo Mercati corrente, non committato o promosso. Nessuna modifica
alle credenziali, nessun deploy, nuova build Android, artefatto Web di release,
notifica o pubblicazione applicativa. L'archivio locale è stato aggiornato
come autorizzato; non va descritto come invariato.
