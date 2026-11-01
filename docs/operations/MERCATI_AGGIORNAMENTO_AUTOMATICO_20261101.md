# Mercati: aggiornamento automatico — decisione del 1 novembre 2026

## Decisione del proprietario

Durante la revisione del pannello il proprietario ha confermato che le note
pubbliche standard vanno bene e ha richiesto che il controllo automatico
proceda senza conferma. Eventuali errori potranno essere corretti dal pannello,
anche a seguito di segnalazioni.

Questa decisione sostituisce la proposta conversazionale di far approvare
singolarmente gli aggiornamenti trovati online. Con la successiva istruzione
«Procediamo con l'automazione» il proprietario ha precisato che il nuovo dato
documentato deve sovrascrivere quello precedente, anche se inserito manualmente,
senza perdere informazioni o considerazioni. La precedenza assoluta delle
correzioni manuali proposta inizialmente è quindi superata.

Ownership: coordinatore per merge, servizio, job, script, pannello e documenti;
specialista `scopri` per acquisizione delle fonti e relativi test;
`build_verifica` per test indipendenti e verifica del contratto.

## Comportamento richiesto

- Recuperare periodicamente le fonti già censite e cercare nuovi riscontri.
  Per le variazioni documentate, applicare gli aggiornamenti senza domandare
  conferma a ogni esecuzione o per ogni scheda.
- Conservare fonte, data del controllo, differenze e identità stabili di
  mercato ed edizione. Il pannello resta lo strumento per correggere i dati.
- Un fatto documentato realmente cambiato sostituisce il valore precedente,
  anche manuale. La stessa evidenza già osservata non annulla invece una
  correzione manuale successiva. Il confronto avviene per singolo fatto, non
  sulla sola data di download o su una modifica irrilevante della pagina.
- Conservare valore precedente, nuovo valore, fonte e riscontro testuale
  nell'audit; ogni revisione completa rimane immutabile. Applicare modifiche
  puntuali: note pubbliche, annotazioni interne, limiti delle pratiche,
  fonti precedenti e altre edizioni non vengono cancellati dal refresh.
- Una fonte irraggiungibile, un risultato assente o un conflitto non sono
  una prova di cessazione, spostamento o nuova data. Registrare l'anomalia,
  mantenere i dati nei loro limiti di validità e ritentare; gli altri mercati
  continuano a essere controllati senza attendere approvazione.
- Non estendere la validità soltanto perché una pagina risponde o non cambia;
  non inventare nuove edizioni da ricorrenze non documentate e non riattivare
  mercati ritirati manualmente.
- Conservare le note pubbliche standard attuali. Non aggiungere all'interfaccia
  una lunga lista obbligatoria di proposte da accettare: esiti e anomalie
  dovranno essere consultabili in forma compatta.

## Cadenza implementata per l'archivio locale

Il launcher pianificabile controlla ogni giorno quali mercati sono dovuti:
fonti mensili (mese di calendario), appuntamenti nei prossimi 30 giorni e
validità in scadenza entro 30 giorni ogni sette giorni. Errori transitori
vengono ritentati il giorno successivo. Mercati sospesi o archiviati restano
esclusi. I mai controllati e i controlli più vecchi hanno precedenza.

Budget di acquisizione 30 minuti, con salvataggio del lavoro completato e
conteggio del residuo; il task Windows ha un limite di 45 minuti. La ricerca
territoriale trimestrale di nuovi mercati resta un'estensione da realizzare,
distinta dal ricontrollo delle fonti già censite.

## Stato effettivo e confini

Nel codice locale esistono ora `app.markets.refresh`, `refresh_job` e il metodo
interno `MarketsService.refresh`. Il processo raccoglie i riscontri, verifica
conflitti e provenienza e salva attraverso la stessa transazione con revisione
attesa usata dal pannello. Un salvataggio concorrente impedisce la sovrascrittura
silenziosa. Nessun nuovo endpoint HTTP di scrittura è esposto.

I metadati del controllo sono gestiti dal server e non possono essere alterati
dal payload di salvataggio del pannello. Nei conflitti fra fonti l'intera
edizione interessata resta invariata, evitando di combinare una data con la
sede di un'altra ipotesi. Le altre schede continuano il controllo.

In Fonti e verifica il pannello presenta un dettaglio richiudibile con una
modifica alla volta: prima, dopo e collegamento alla fonte. La fonte può essere
consultata insieme al riscontro conservato; l'apertura dello storico non
impone una nuova approvazione dell'aggiornamento.

La decisione elimina la richiesta di conferma per i singoli aggiornamenti
del futuro processo. L'attivazione online del servizio e del catalogo resta
il passaggio distinto sospeso nel [verbale del 30 ottobre](MERCATI_ATTIVAZIONE_ONLINE_20261030.md).
L'attuale avviso di pubblicazione disattivata nel pannello rimane veritiero.

La prima attivazione e la verifica sui dati reali sono registrate nel
[resoconto operativo](MERCATI_AUTOMAZIONE_LOCALE_20261101.md): automazione locale
attiva, revisione 5 e 25 modifiche su 6 schede. Non dedurre un job cloud attivo
dalla presenza del codice o degli script locali.
