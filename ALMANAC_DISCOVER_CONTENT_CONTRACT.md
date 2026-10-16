# Contratto contenuti Home, Almanacco e Scopri

Data: 2026-07-20

## Home

La Home mostra soltanto un'anteprima dell'Almanacco:

- data;
- santo del giorno;
- fase lunare;
- richiamo alle tradizioni.

Il testo completo del proverbio non viene mostrato in Home.

## Almanacco

L'Almanacco è la superficie quotidiana per:

1. data e stagione;
2. santo del giorno;
3. tradizione e un proverbio breve;
4. sole locale;
5. luna;
6. consigli della terra.

### Santo del giorno

Il calendario dei nomi resta separato dal catalogo editoriale dei profili. Un profilo può aggiungere:

- una descrizione fattuale di una o due frasi;
- ruolo o motivo della ricorrenza;
- epoca e luogo, soltanto quando sono significativi;
- fonte ufficiale e stato della revisione linguistica.

Nella card compaiono soltanto il nome e la breve descrizione. Fonte e metadati restano interni. La descrizione viene mostrata esclusivamente nella lingua con stato `curated`; se manca o attende revisione, la card mostra soltanto il nome e non genera testi riempitivi.

I proverbi selezionabili sono marcati `almanacEligible`. La priorità di selezione è:

1. data esatta;
2. regola mensile, stagionale, meteo o lunare;
3. rotazione generica controllata.

La rotazione generica evita una scheda vuota durante lo sviluppo, ma non completa il repertorio. Il requisito editoriale finale resta di 366 proverbi distinti, approvati in IT e FUR e assegnabili al calendario senza ripetizioni obbligate.

## Scopri

Scopri è la superficie culturale e territoriale per:

1. profilo del Comune selezionato;
2. Accadde oggi con eventuali voci secondarie ordinate per importanza e prossimita;
3. Riti e credenze popolari, soltanto quando una data, una festa mobile o un intervallo preciso lo giustificano;
4. Si diceva che..., con un detto spiegato e contestualizzato;
5. Archivio e tradizioni, con al massimo una scheda quotidiana di approfondimento.

Un testo Ostermann può alimentare sia Almanacco sia Scopri. L'Almanacco lo usa come proverbio breve quotidiano; Scopri lo ripropone come patrimonio culturale o approfondimento. La presenza nelle due superfici non è considerata un doppione, purché la fonte testuale resti unica e il riuso sia dichiarato nel catalogo.

La selezione temporale comune segue questa precedenza:

1. data esatta;
2. festa mobile;
3. intervallo tradizionale preciso;
4. mese;
5. stagione;
6. contenuto valido tutto l'anno.

Le ricorrenze certe non vengono spostate dalla rotazione. I candidati equivalenti di data esatta o festa mobile ruotano tra anni diversi; i candidati di uno stesso intervallo, mese o stagione ruotano giorno per giorno.

Le feste mobili di Scopri comprendono anche ricorrenze ordinali documentate, come la prima domenica di ottobre. Il campo opzionale `nthWeekdayDates` usa regole `{ month: 10, weekday: 0, ordinal: 1 }`: mese da 1 a 12, giorno da 0 (domenica) a 6, occorrenza da 1 a 5, tutti interi. Corrisponde soltanto al giorno effettivo; la quinta occorrenza può non esistere. Un campo esplicito vuoto, invalido o non corrispondente non diventa una rotazione mensile, stagionale o annuale. Restano valide eventuali altre date o finestre precise dichiarate nello stesso record. Questa estensione non modifica il calendario dell'Almanacco.

Riti e credenze non usa contenuti generici come riempitivo. Inoltre conserva l'ambito territoriale dichiarato dalla fonte: una pratica documentata in Carnia, nella Slavia friulana o in un singolo paese non viene presentata automaticamente come uniforme in tutta la regione.

## Fonti e lingue

- La fonte Ostermann resta visibile sulle schede culturali pertinenti.
- Le fonti generiche e i crediti fotografici restano nella sezione informativa dedicata.
- Un contenuto Scopri viene pubblicato soltanto dopo approvazione IT e FUR.
- I contenuti regionali non vengono attribuiti artificialmente al Comune selezionato.
- I nuovi filoni trovati in fonti istituzionali o archivistiche restano in staging finché non hanno copy IT/FUR, regola temporale e ambito geografico approvati.
