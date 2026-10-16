# Audit scheda Google Play — 24 settembre 2026

Stato: descrizione estesa aggiornata dal proprietario nella Play Console e
pagine pubbliche allineate e distribuite su `meteofriul.it`; restano le
verifiche **obbligatorie prima del prossimo AAB e del cutover dall'ambiente
pilot**. La versione candidata è `0.1.2` (`300019`), successiva alla release
Play `0.1.0` (`300017`); `0.1.1` (`300018`) è stata abbandonata prima del
caricamento dopo una correzione al frontend.

## Testo pubblicitario approvato

Non usare la promessa assoluta «senza pubblicità».

Testo da inserire nella descrizione estesa di Google Play:

> **Gratuita, con possibili contenuti pubblicitari**
>
> Meteo Friûl è gratuita e può includere contenuti pubblicitari, promozionali
> o sponsorizzati.

La frase non vincola l'app a un formato specifico e resta adatta a card,
contenuti sponsorizzati, eventi in evidenza o altri formati futuri, senza
promettere l'assenza totale di pubblicità.

## Bozza descrizione estesa

Meteo Friûl mette il Friuli a portata di mano. Guarda che tempo fa, scopri cosa
succede vicino a te e lasciati guidare tra luoghi, storie e tradizioni del
territorio.

### Meteo e bollettini

Consulta le condizioni attuali, le previsioni orarie e l'andamento delle
prossime ore per la località che ti interessa. Trovi inoltre bollettini
regionali, allerte ufficiali e aggiornamenti meteo in tempo reale.

### Vivere e scoprire il Friuli

- Eventi: sagre, manifestazioni e appuntamenti vicino a te
- Scopri: luoghi, curiosità, storie e tradizioni del territorio
- Webcam: osserva il territorio in tempo reale
- Segnalazioni meteo: racconta le condizioni dal luogo in cui ti trovi
- Italiano e friulano: utilizza l'app nella lingua che preferisci

Il friulano affianca l'italiano ed è parte integrante dell'identità del
progetto.

### Gratuita, con possibili contenuti pubblicitari

Meteo Friûl è gratuita e può includere contenuti pubblicitari, promozionali o
sponsorizzati.

### Un progetto indipendente

Meteo Friûl è un progetto indipendente che raccoglie, organizza e confronta
dati meteo e informazioni sul territorio provenienti da più fonti regionali.
Non è un servizio ufficiale e non rappresenta enti pubblici, organizzazioni o
fornitori dei contenuti utilizzati.

## Gate prima dell'AAB

- [x] Completato l'audit dei link aperti dall'app, incluso il nuovo formato
  `https://meteofriul.it/?segnalazione=CODICE`; la compatibilità con il vecchio
  percorso `/evento/` non è richiesta per il cutover.
- [ ] Completare l'audit delle notifiche e del relativo cutover Play.
- [x] Creati e verificati i job `meteofriul-local-notice` e
  `meteofriul-official-alert-sync`, entrambi con Open-Meteo disabilitato; i
  relativi scheduler ufficiali hanno completato una prova reale e i vecchi
  scheduler con suffisso `pilot` sono stati messi in pausa.
- [x] Riscritte nel codice le promesse assolute «senza pubblicità» visibili
  nell'app, comprese le versioni italiana e friulana; resta la revisione
  linguistica finale durante l'audit dell'app.
- [x] Allineati README, privacy policy e pagine pubbliche al comportamento
  effettivo; la versione pubblicata di `meteofriul.it` non promette assenza di
  pubblicità e le fonti pubbliche riportano ICON-2I/CAMS senza Open-Meteo.
- [x] Verificata nella Play Console la dichiarazione Data safety: raccolta
  dichiarata per posizione, diagnostica, attività nell'app e ID dispositivo;
  dati cifrati in transito, nessun account e richiesta di cancellazione tramite
  la privacy policy. La dichiarazione «Annunci» è stata impostata su «Sì» e
  salvata nella Panoramica della pubblicazione: la scheda Play mostrerà
  «Contiene annunci» ed è già predisposta per future card promozionali o
  sponsorizzate, anche se questa build non integra AdMob.
- [x] Descrizione estesa aggiornata dal proprietario nella Play Console con la
  formulazione approvata.
- [x] Eseguiti test frontend completi (517 file, 4.614 test superati), lint e
  build; eseguiti inoltre 1.222 test backend e tutti i gate locali di release.
- [ ] Generare il nuovo AAB soltanto dopo la chiusura di tutti i punti sopra.
- [ ] Disattivare i servizi pilot solo dopo il rilascio e la verifica del nuovo
  client collegato ai servizi ufficiali.
