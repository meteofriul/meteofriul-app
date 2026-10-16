# TurismoFVG — primo avvio senza checkpoint, 7 ottobre 2026

Stato: **in corso sul ramo `codex/events-discovery-audit`**. Nessun catalogo e'
stato pubblicato. Questa prova riguarda l'avvio da catalogo vuoto; il
controllo annuale gia' completato e' documentato separatamente.

## Problema osservato

La scansione diretta dell'anno ha iniziato con 2.464 risultati dichiarati.
Alla pagina 66 il sito ne dichiarava 2.467. La raccolta ha rifiutato l'indice
senza creare schede parziali. Una scansione completa richiede centinaia di
pagine: un aggiornamento del sito mentre vengono lette rende instabile la
paginazione per offset.

## Controllo a finestre

I filtri ufficiali `start` e `end` restituiscono anche gli eventi che
attraversano due intervalli. I totali delle finestre **non** si sommano. La
prova in sola lettura ha confrontato gennaio e febbraio: 17 + 19 tessere,
con 7 sovrapposizioni, formano le stesse 29 tessere del periodo combinato.
Il confronto dell'1 e 2 ottobre ha dato 140 + 159 tessere, con 129
sovrapposizioni, e un'unione di 170: coincide con il periodo combinato.

Il lettore divide soltanto un intervallo troppo grande, controlla tutte le
pagine di ogni finestra e unisce le tessere per URL, giorno mostrato, titolo e
luogo. Rilegge l'indice annuale alla fine e richiede che il totale dell'unione
coincida con quello ufficiale. Un contenuto discordante tra finestre, un
totale mutato o una pagina incompleta ferma la fonte. Nella prima versione
la scansione annuale diretta, con al massimo 16 richieste simultanee, era
il primo tentativo; le finestre venivano usate solo dopo una variazione
del totale. Un errore di connessione aveva un ulteriore tentativo limitato
a questa fonte.

Una prova annuale a finestre ha verificato **2.478 tessere su 2.478** e
**1.513 URL distinti**. Con la soglia iniziale di 240 risultati per finestra
ha letto 901 pagine; il primo ciclo di 335 secondi ha registrato 2.439 URL
tra calendario e sitemap, controllato 384 dettagli e salvato un checkpoint
con 2.055 dettagli ancora da esaminare. La soglia rivista di 512 ha prodotto
lo stesso inventario in **143,59 secondi** e 488 letture di pagina nella
prova isolata. Questi conteggi sono prove dell'indice, non una certificazione
dei dettagli ancora pendenti.

Due riprese ravvicinate del ciclo locale sono state interrotte da reset e
timeout delle connessioni del sito. In quella fase il checkpoint restava
disponibile e la fonte falliva chiusa; le scansioni furono sospese per
limitare il carico sul sito.

## Esito successivo e verifica ancora necessaria

Il checkpoint e' stato completato. Il lettore usa ora direttamente le
finestre annuali per evitare di ripetere la scansione dopo un cambio del
totale. La [prova locale delle 15 fonti](EVENTI_CICLO_15_FONTI_2026-10-07.md)
e' `fresh` per tutte in 435,89 secondi, entro il budget comune di 875
secondi. Resta da verificare il primo ciclo distribuito da catalogo vuoto;
le prove sul telefono restano rinviate.

Una [nuova prova locale senza checkpoint l'8 ottobre](EVENTI_COLD_START_LOCALE_2026-10-08.md)
ha verificato il primo ciclo con il lettore a finestre: 2.433 URL,
960 dettagli controllati, 1.473 pendenti e checkpoint conservato in
319,28 secondi. Nessuna scheda TurismoFVG e' pubblicata finche' la fonte
resta incompleta.

La [ricerca ufficiale](https://www.turismofvg.it/eventi?hidehighlights=true&start=2026-01-01&end=2026-12-31)
e' la superficie usata per tutti i conteggi. Il job non legge PDF o locandine.
