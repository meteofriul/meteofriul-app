# Territorio - contratto funzionale

Data verifica: 2026-08-03

## Scopo

`Territorio` (`tab=live`) mostra osservazioni territoriali reali senza duplicare il Bollettino e senza trasformare dati community in informazioni ufficiali.

La pagina contiene due funzioni distinte:

1. mappa delle segnalazioni community geolocalizzate;
2. webcam regionali.

## Fonti e confini

### Webcam

- endpoint: `GET /api/live/webcams`;
- la UI usa il manifesto normalizzato del backend e non legge HTML OSMER;
- il Comune selezionato nell'app serve soltanto a ordinare il gruppo `Vicino`;
- vengono mostrati fotogrammi correnti, non un player HLS;
- un guasto della singola immagine non degrada tutte le webcam;
- dopo errore o 6,5 secondi senza risposta viene provata la webcam successiva dello stesso gruppo;
- il link fonte apre il pannello OSMER in una pagina esterna.

Radar, previsioni e allerte restano nel Bollettino e non vengono rappresentati nella mappa sociale.

### Community

- lettura: `GET /api/community/reports`;
- invio: `POST /api/community/reports`;
- conferma o smentita: `POST /api/community/reports/{group_id}/confirmation`;
- la mappa sociale e' la superficie principale delle segnalazioni in `Territorio`;
- i marker rappresentano `map_groups`, cioe' fenomeni attivi raggruppati per tipo, zona e finestra temporale;
- toccando un marker si vedono fenomeno, zona, ora, numero di segnalazioni e conferme;
- dopo un invio riuscito dati, mappa e lista vengono ricaricati immediatamente;
- l'invio richiede coordinate aggiornate del dispositivo;
- il GPS usato per la segnalazione non cambia il Comune selezionato nell'app;
- il nome della zona rilevata puo' essere corretto soltanto scegliendo una zona supportata entro 5 km dalle coordinate GPS;
- le coordinate originali restano nel comando di invio e il backend ripete il controllo di distanza: la correzione non consente di segnalare in una localita' lontana;
- se il GPS e' molto impreciso o non individua una zona supportata, l'utente puo' ripetere il rilevamento ma non sostituirlo con una localita' arbitraria;
- le coordinate precise non vengono mostrate nella pagina: il backend restituisce soltanto il centro della zona supportata;
- il backend applica durata, distanza massima e limite temporale tra invii;
- la UI dichiara sempre che le segnalazioni non sono verificate e non sostituiscono le comunicazioni ufficiali.
- la mappa si ingrandisce con gesto a due dita o doppio tocco; non mostra controlli `+` e `-`.

## Avvio, cache e assenza di rete

- webcam e community hanno cache indipendenti;
- la cache viene mostrata prima della richiesta di rete;
- il manifesto webcam viene riverificato dopo 10 minuti ed e' conservato al massimo 7 giorni;
- oltre 36 ore la webcam resta visibile ma viene dichiarata non aggiornata;
- la community viene riverificata dopo 1 minuto e conservata per 65 minuti;
- un errore di una fonte non cancella i dati ancora utilizzabili dell'altra;
- senza alcun dato disponibile viene mostrato lo stato vuoto della sola sezione interessata;
- lo svuotamento cache da Impostazioni comprende anche webcam e community.

## Stati utente

- gli stati regolari (`fonte attiva`, `dati salvati`) non occupano spazio nell'interfaccia;
- uno stato viene mostrato soltanto quando una fonte e' instabile, non disponibile o ancora in caricamento senza contenuto utile;
- non vengono mostrati percorsi locali del backend, dettagli diagnostici o endpoint tecnici;
- il contatore della mappa usa soltanto `X segnalazioni`, senza ripetere `attive`.

## Verifica completata

- dati reali e immagini effettivamente caricate;
- cambio categoria e cambio webcam;
- ordinamento per distanza da Pordenone;
- mappa sociale separata dal radar e visibile anche senza segnalazioni attive;
- marker zonali, dettaglio e contratto di conferma verificati con dati controllati;
- zoom tattile senza pulsanti `+` e `-`;
- correzione manuale della zona limitata a 5 km dal GPS e validata anche prima della richiesta;
- apertura e validazione del form community senza invio di segnalazioni di prova;
- cache presente con backend temporaneamente non raggiungibile;
- ripristino online;
- italiano e friulano;
- tema chiaro e scuro;
- nessun errore o warning nella console del browser.

## Fuori perimetro

- player video HLS nella WebView;
- invio di segnalazioni artificiali durante i test;
- uso di `/api/health/live-sources` nel flusso utente;
- notifiche o allerte generate dalle segnalazioni community.
