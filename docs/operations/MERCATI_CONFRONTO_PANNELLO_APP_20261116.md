# Mercati: confronto archivio online e candidato app — 16 novembre 2026

## Ambito e metodo

Lettura **in sola lettura** dell'archivio Firestore `markets_archive` del progetto
`meteo-friul` con l'account amministrativo già configurato. La revisione privata
è **57**: 100 schede, di cui **80 selezionate**, 9 sospese e 11 bozze; 224 edizioni
complessive. La revisione pubblica resta **0**. Nessun salvataggio, job, deploy o
pubblicazione è stato eseguito.

Il confronto usa il commit candidato `03aa0783` e
`frontend/src/data/markets/catalogueCandidate2026.json` (SHA-256
`0de55893d1a1cd2bb283a8c1aa915d9ca1f679e7e5edea7c2efc8e120d56492a`).
Le schede selezionate sono state proiettate sui campi pubblici dello stesso
contratto del servizio; le edizioni sono state confrontate per ID e per tutti i
campi pubblici, inclusi data, stato, fonte, orario e sede specifica. Controllati
anche identità storiche, ritiri, alias delle edizioni e metadati del catalogo.
La verifica è di **corrispondenza dei dati**, non una nuova attestazione delle
fonti esterne o una prova dell'interfaccia su telefono.

## Risultato

| Controllo | Esito |
| --- | --- |
| Identità delle schede selezionate | 80/80 presenti in entrambi, nessuna mancante o aggiunta |
| Campi delle schede | 16 identici; 64 con almeno un campo diverso |
| Edizioni già presenti nel pannello per le schede selezionate | 202/202 identiche |
| Edizioni aggiuntive nel candidato app | 4, tutte con ID e fonte; nessuna edizione del pannello manca nell'app |
| Identità storiche | 89/89 presenti; 2 differiscono soltanto nell'elenco degli URL fonte |
| Ritiri | 13/13 identici |
| Alias edizioni | 217/217 esistenti identici; 4 nuovi alias accompagnano le 4 date aggiuntive |
| Metadati `checked`, `validThrough`, `timezone` | Identici |

Tra i campi diversi delle 64 schede: `scheduleNote` in 60, `cadence` in 41,
`hours` in 17, data `checked` in 7, URL principale in 2, sede in 1,
destinazione Indicazioni in 1 e autorità in 1. Le riscritture di cadenza e
nota eliminano perlopiù istruzioni di ricerca interne o ripetizioni. I fatti
da mantenere visibili sono conservati nei campi specifici o negli avvisi
generali: per esempio, la rotazione delle piazze di Gemona è nel campo sede;
il mercato feriale di Ronchi indica i giorni feriali nella cadenza; i mercatini
senza edizione futura mostrano «Prossima data non annunciata». Gli orari
diventati vuoti erano indicazioni generiche come «mattina» o valori non
confermati come orario di vendita. Le sette date `checked` più recenti del
candidato riflettono il controllo documentato del 12 novembre.

## Differenze che richiedono riallineamento

| Scheda | Nel candidato app, oltre alla revisione privata 57 | Riscontro precedente |
| --- | --- | --- |
| M025, AnticaMente ad Aviano | Edizione del **6 dicembre 2026** e relativo alias; controllo al 12 novembre | [Correzione ricorrenze](MERCATI_RICORRENZE_SENZA_DATA_20261112.md) |
| M038, Mercatino dell'antiquariato a San Daniele | Edizione del **29 novembre 2026**, sede **Piazza Vittorio Emanuele II**, Indicazioni e URL dell'agenda del mercatino; il pannello punta ancora alla pagina del mercato settimanale | [Agenda e verifica della sede](MERCATI_RICORRENZE_SENZA_DATA_20261112.md) |
| M042, Robis di une volte | Edizioni del **29 novembre e 13 dicembre 2026**, URL UNPLI e autorità aggiornata | [Date pubblicate da UNPLI](MERCATI_RICORRENZE_SENZA_DATA_20261112.md) |

Queste quattro edizioni spiegano per intero la differenza 202 → 206. Le
divergenze negli URL dell'indice storico riguardano M038 e M042 e seguono gli
stessi cambi di fonte. Nessuna delle quattro è stata ancora inserita nella
revisione privata online. I testi abbreviati del candidato sono proposte
editoriali già preparate nel ramo: **non** vanno sovrascritti automaticamente
con il testo più lungo del pannello.

## Passaggio successivo

1. Rileggere le quattro edizioni e le due fonti aggiornate, quindi salvarle
   nell'archivio privato tramite il pannello, **senza pubblicare**; riallineare
   nella stessa revisione i testi pubblici approvati e le sette date di
   controllo, conservando le note di ricerca interne dove servono.
2. Ripetere il confronto contro la nuova revisione privata fino a ottenere
   identità, campi pubblici, edizioni e registri coerenti. La revisione pubblica
   resta separata.
3. Solo dopo affrontare la prova reale Android e le verifiche Web/iPhone
   previste per un'eventuale release. Questo confronto non le sostituisce.

## Esito per ciascuna scheda selezionata

La tabella registra i **campi pubblici della scheda** che differiscono; le
edizioni sono verificate separatamente sopra. «Identica» significa che tutti
i campi pubblici della scheda coincidono esattamente.

| ID | Scheda | Campi diversi |
| --- | --- | --- |
| M001 | Mercato cittadino di Pordenone | cadenza, nota |
| M002 | Mercato settimanale di Sacile | Identica |
| M003 | Mercato settimanale di Codroipo | orario |
| M004 | Mercato settimanale | Identica |
| M005 | Mercato settimanale di Palmanova | Identica |
| M006 | Mercato settimanale | Identica |
| M007 | Mercato settimanale | Identica |
| M008 | Mercato settimanale | nota |
| M009 | Mercato settimanale | nota |
| M010 | Mercato settimanale di Cividale del Friuli | nota |
| M011 | Mercato settimanale di Gemona del Friuli | cadenza, nota |
| M012 | Mercato settimanale di Pasiano | nota |
| M016 | Mercato settimanale di Muggia | nota |
| M017 | Mercato contadino di San Daniele | cadenza, nota |
| M018 | Mercato Agrizero di Sacile | cadenza, orario, nota |
| M019 | Mercato agricolo di Pasiano | Identica |
| M020 | Mercato Contadino di Aviano | cadenza, orario, nota |
| M021 | Campagna Amica – piazza Vittorio Veneto | nota |
| M022 | Mercato coperto | Identica |
| M023 | Mercato ortofrutticolo – accesso al pubblico | Identica |
| M025 | AnticaMente ad Aviano | cadenza, verifica, orario, nota |
| M027 | Mercatino dell'Usato | cadenza, verifica, orario, nota |
| M028 | Mercanti in Giardino | Identica |
| M030 | Mercatino dell'antiquariato | cadenza, nota |
| M032 | Mercatino dell'Antica Contea Fortezza di Gradisca | cadenza, verifica, orario, nota |
| M033 | Mercatino dell'Antiquariato e dell'Usato | cadenza |
| M034 | Mercatino delle pulci e del libro usato | cadenza, orario, nota |
| M035 | La Soffitta in Piazza | cadenza, nota |
| M037 | Sacellum – La piazza delle antichità | cadenza, nota |
| M038 | Mercatino dell'antiquariato | cadenza, verifica, Indicazioni, sede, nota, URL fonte |
| M039 | Il Baule del Diavolo | cadenza, nota |
| M040 | Udine Antiqua | cadenza, verifica, nota |
| M041 | Vecchi Ricordi | cadenza, verifica, nota |
| M042 | Robis di une volte | autorità, cadenza, verifica, nota, URL fonte |
| M043 | Tesori del Tempo — Campagnola | cadenza, nota |
| M044 | CREATTIVAMENTE | cadenza, nota |
| M045 | META | cadenza, nota |
| M047 | Mercatino al tram | cadenza, nota |
| M048 | Mercatino di Cavana | cadenza, nota |
| M049 | Mercatino di Porto Vecchio | cadenza |
| M050 | Mercatino di Ponterosso | cadenza, nota |
| M051 | Un pozzo di occasioni | Identica |
| M052 | I sabati di Arti in Piazza | nota |
| M053 | Lo Scrigno del Doge | cadenza, nota |
| M055 | Barbacan Produce | cadenza |
| M058 | Magia di Natale | Identica |
| R-GTS-M005 | Mis Mas de tut un poc | cadenza, nota |
| R-PN-M002 | Mercato del capoluogo di Casarsa | nota |
| R-PN-M004 | Mercato settimanale di Cordenons | nota |
| R-PN-M007 | Mercato agricolo di Torre | cadenza, orario, nota |
| R-PN-M008 | Mercato agricolo del Sacro Cuore | cadenza, orario, nota |
| R-PN-M009 | Mercatino degli hobbisti e della creatività - Festa di Santa Lucia | Identica |
| R-PN-M012 | Mercato settimanale di Budoia | Identica |
| R-PN-M013 | Mercato settimanale di Maron | orario, nota |
| R-PN-M014 | Mercato settimanale di Caneva | orario, nota |
| R-PN-M016 | Mercato settimanale di Coltura | orario, nota |
| R-PN-M031 | Voglia di Natale | cadenza, nota |
| R-PN-M032 | Dal Campat alla Piazza - mercatini | orario, nota |
| R-PN-M034 | Mercatino di Natale a Villanova | cadenza, nota |
| R-PN-M054 | Mercato settimanale ordinario di Aviano | nota |
| R-PN-M055 | Mercato settimanale di Maniago | nota |
| R-PN-M062 | Mercato settimanale di Roveredo in Piano | Identica |
| R-PN-M063 | Mercato settimanale di Spilimbergo | nota |
| R-PN-M066 | Mercato settimanale di San Vito al Tagliamento | nota |
| R-UDA-M012 | Mercato settimanale di Basiliano | orario, nota |
| R-UDA-M020 | Mercato di Campagna Amica di Codroipo | cadenza, nota |
| R-UDA-M052 | Mercato settimanale di Cervignano del Friuli | orario, nota |
| R-UDA-M054 | Mercato invernale di Lignano Sabbiadoro | nota |
| R-UDA-M057 | Mercato agroalimentare Naturalmente Lavariano | cadenza, orario, nota |
| R-UDA-M060 | Mercato settimanale di Latisana capoluogo | nota |
| R-UDB-M006 | Campagna Amica di Passons | cadenza, nota |
| R-UDB-M010 | Advento Nassfeld – Pramollo | cadenza, nota |
| R-UDB-M015 | Mercatini di Natale di Ragogna | Identica |
| R-UDB-M016 | Sapori di Carnia – mostra mercato gastronomica 2026 | cadenza, orario, nota |
| R-UDB-M021 | Profumo di Natale nell'aria | Identica |
| R-UDB-M025 | 22ª Mostra Mercato – Gesti antichi per un nuovo Natale | cadenza, nota |
| R-UDB-M027 | Mercatini di Natale a Sauris di Sopra | nota |
| R-UDB-M040 | Campagna Amica Piazza XX Settembre | cadenza, nota |
| R-UDB-M041 | Mercato coperto Campagna Amica di Udine | cadenza, nota |
| R-UDB-M042 | Campagna Amica Villaggio del Sole | cadenza, nota |
