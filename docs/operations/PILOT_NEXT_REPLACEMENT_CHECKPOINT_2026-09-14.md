# Prossima sostituzione della pilota — checkpoint obbligatorio

Data di registrazione: 14 settembre 2026  
Revisione frontend corrente: `9c72c6b`  
Stato: **codice locale verificato; distribuzione e collaudo sul Samsung ancora da eseguire**

## Stato da non confondere

- L'anteprima browser su `http://127.0.0.1:5174/` usa il frontend corrente e
  rende già visibili le correzioni del refresh/feedback e i successivi
  miglioramenti della pilota.
- La correzione del worker delle allerte ufficiali è presente nei sorgenti dal
  commit `aa4f58c`, ma a questo checkpoint **non risulta distribuita al worker
  cloud**.
- Le correzioni client per indipendenza degli esiti e feedback utente sono
  incluse nei commit `2defc84` e `62dc75a`, poi confluiti nella revisione
  corrente `9c72c6b`.
- La revisione corrente **non è stata ancora compilata e installata** come nuova
  APK `com.meteofriul.app.localpilot` sul Samsung A52.
- La beta ufficiale `com.meteofriul.app` resta fuori da questa distribuzione e
  deve rimanere invariata.

L'anteprima browser prova il comportamento Web locale. Non dimostra né la
revisione effettivamente attiva nel worker cloud né il codice contenuto
nell'APK già installata sul telefono.

## Gate prima della prossima installazione pilota

Non considerare completata la sostituzione finché non sono stati registrati
tutti i controlli seguenti.

1. **Identità dei sorgenti**
   - registrare commit esatto usato per il worker e commit esatto usato per
     l'APK;
   - verificare che la build includa `aa4f58c`, `2defc84`, `62dc75a` e le
     successive correzioni che si intendono collaudare;
   - controllare che il worktree sia nello stato previsto e che modifiche non
     committate non entrino accidentalmente nella build.

2. **Perimetro cloud**
   - verificare account, progetto e servizio target prima di qualunque deploy;
   - distribuire il worker allerte solo dopo autorizzazione separata;
   - verificare revisione attiva, health e risposta dell'endpoint allerte;
   - ricordare che un servizio condiviso non diventa isolato soltanto perché il
     client è la pilota.

3. **Build e installazione conservativa**
   - costruire la variante `localPilot` con gli script protetti del progetto;
   - registrare SHA-256 dell'APK, package, versionName/versionCode e revisione;
   - installare con aggiornamento in-place, senza disinstallazione e senza
     cancellare dati, cache, preferenze o permessi;
   - verificare SHA-256/identità della `base.apk` realmente installata e gli
     orari `firstInstallTime`/`lastUpdateTime`.

4. **Prova funzionale end-to-end sul Samsung**
   - avvio a freddo con cache preesistente e successiva riapertura offline;
   - refresh manuale con rete disponibile e con un singolo servizio in errore;
   - verificare separatamente allerte/avvisi, ICON, CAMS aria, CAMS pollini, UV,
     OSMER, radar, webcam, segnalazioni, eventi e Scopri;
   - un errore di un componente non deve annullare, bloccare o svuotare i dati
     validi degli altri componenti;
   - dati attivi già verificati devono restare visibili durante il download e
     in caso di fallimento; un candidato riuscito li sostituisce senza frame
     vuoti, anche dopo riapertura;
   - verificare cambio d'ora e cambio località senza contaminazione fra cache.

5. **Feedback utente e allerte**
   - `Aggiornato` deve comparire quando il refresh produce un risultato utile;
   - `Controlla la rete` deve essere riservato a un problema comprensibile di
     connettività, mentre codici, eccezioni e diagnostica restano nei log;
   - l'indisponibilità delle allerte non deve trasformare in fallimento ICON,
     CAMS, UV o gli altri servizi;
   - non mostrare all'utente diciture tecniche come `official_alerts_unavailable`
     o una card priva di utilità del tipo `Stato allerte non disponibile`;
   - verificare sia il caso con allerta ufficiale valida sia quello senza
     allerta valida.

6. **Controllo visivo della revisione corrente**
   - verificare le nuove card ambientali 2×2 e i pannelli di dettaglio;
   - controllare valori, unità, validità ed emissione di aria e pollini, senza
     AQI o classi sanitarie inventate;
   - verificare IT/FUR, tema chiaro/scuro, tasto Indietro Android, scroll e
     sovrapposizione con la barra inferiore.

7. **Beta ufficiale invariata**
   - registrare prima e dopo package, versione, `lastUpdateTime` e hash della
     beta ufficiale;
   - non aggiornare, avviare procedure Play o cancellare dati della beta durante
     il collaudo della pilota.

## Criterio di chiusura

Il checkpoint può essere marcato come completato soltanto dopo avere registrato
insieme:

- deploy effettivo e identità della revisione del worker allerte;
- build, hash e identità dell'APK pilota effettivamente installata;
- esito dei controlli end-to-end sul Samsung con cache conservata;
- conferma documentata che la beta ufficiale è rimasta invariata.

In assenza anche di uno solo di questi elementi, usare la formula: **corretto
nei sorgenti e/o nel browser, non ancora verificato nella nuova pilota completa**.

