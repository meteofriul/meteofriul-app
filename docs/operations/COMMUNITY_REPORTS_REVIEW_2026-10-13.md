# Segnalazioni e punti della Community

Analisi del 13 ottobre 2026 per il ramo `codex/community-reports-simplification`,
creato da `origin/main` al commit `d8a54e176409de25abfe5d77cd166e40099158b9`.
Il sistema distingue invii, episodi, conferme e punti. Due difetti riprodotti
localmente rendono i contatori del profilo incoerenti. La priorità proposta è
correggere i conteggi e rendere comprensibili le azioni, poi semplificare la
regola dei premi.

Questa analisi riguarda il codice del ramo, non una verifica del servizio
pubblico o dell'APK installato. Non modifica il funzionamento dell'app.

## Come vengono conteggiate le segnalazioni

| Voce | Comportamento attuale |
| --- | --- |
| Invio | Una nuova osservazione accettata dal server. Ripetere la stessa richiesta non crea un altro invio. |
| Episodio sulla mappa | Invii dello stesso fenomeno, nello stesso Comune e nella stessa fascia oraria di 60 minuti vengono raggruppati. Un simbolo può rappresentare più invii. |
| Segnalazioni attive | Il frontend somma gli invii contenuti nei gruppi disponibili; le conferme positive sono separate. Non è un totale storico di tutta la Community. |
| Totale personale | Dovrebbe contare gli invii accettati. Il servizio nazionale attuale non incrementa questo contatore, come riprodotto sotto. |
| Convalidate | Il registro personale conta gli episodi convalidati per autore quando passano anche il filtro dei premi. Per questo può non coincidere con tutti gli episodi già confermati. |
| In attesa | Episodi personali ancora attivi e non convalidati, senza conferme né segnalazioni di cessazione. Esclude “tranquillo”. |

La visibilità iniziale dura un'ora. La stessa installazione non può creare
un altro invio dello stesso fenomeno nello stesso Comune finché il precedente
è attivo. Può rinnovarlo, se ancora aggiornabile.

Il raggruppamento usa fasce orarie fisse: due persone che segnalano lo stesso
fenomeno alle 12:59:59 e alle 13:00:01 finiscono in episodi diversi. Questo è
il comportamento del codice, distinto dalla durata di un'ora di ogni invio.

Fonti: [servizio nazionale](../../backend/app/services/pilot_community.py),
[raggruppamento condiviso](../../backend/app/services/community.py),
[contatori del frontend](../../frontend/src/features/live/communitySocialPresentation.js).

## Come si guadagnano punti

- Un invio da solo vale zero punti. Un episodio viene convalidato quando
  un'altra installazione lo conferma, oppure quando almeno due installazioni
  hanno inviato osservazioni nello stesso gruppo. L'autoconferma è vietata.
- Ogni autore può ricevere un punto per episodio. La persona che preme
  “Conferma” non riceve punti per quel voto. Due autori indipendenti possono
  ricevere un punto ciascuno, se rispettano gli altri vincoli.
- Il massimo è tre punti al giorno, con cambio giorno a mezzanotte italiana.
  Il servizio nazionale applica inoltre 45 minuti tra due premi dello stesso
  autore. Le segnalazioni “tranquillo” non ricevono punti.
- Aggiornare o correggere non assegna un nuovo punto. Le protezioni sulla
  sequenza originale impediscono di usare sostituzioni per moltiplicare premi.
- Dire che il fenomeno è finito non revoca un punto già assegnato. La
  moderazione può revocarlo. Se la cessazione arriva prima della convalida,
  l'episodio può restare definitivamente senza premio.

| Punti | Rango |
| --- | --- |
| 0–4 | Osservadôr dal Cîl |
| 5–19 | Vuaite dal Timp |
| Da 20 | Sentinele dal Teritori |

L'identità dei conteggi è legata all'installazione, senza account personale.
Il cambio dell'alias è cosmetico. Perdere l'identificativo locale può impedire
di ritrovare i propri punti. Il riepilogo ha una scadenza di 365 giorni
rinnovata dalle scritture: non è un calcolo automatico dei soli punti
guadagnati negli ultimi 365 giorni.

Fonti: [validazione e registro dei premi](../../backend/app/repositories/community.py),
[filtro dei 45 minuti](../../backend/app/repositories/pilot_community.py),
[ranghi](../../backend/app/services/community.py),
[identità locale](../../frontend/src/services/liveApi.js).

## Problemi riprodotti

Le prove usano `PilotCommunityService`, memoria locale, orologio controllato e
geografia fittizia già presenti nei test. Lo stesso servizio è selezionato
dall'entrypoint pubblico nazionale, ma le prove non interrogano il cloud.

| Caso | Risultato osservato |
| --- | --- |
| Nuovo invio accettato | Un'osservazione memorizzata e una in attesa, ma `total_reports = 0`. |
| Ripetizione della stessa richiesta | Ancora una sola osservazione: la protezione dai doppioni funziona. |
| Conferma da un'altra installazione | Un punto e una convalidata, ma ancora zero invii totali. |
| Secondo fenomeno dello stesso autore dopo due minuti, confermato da un'altra installazione | L'episodio risulta convalidato, ma il profilo resta a una convalidata e un punto per il filtro dei 45 minuti. |
| Trascorrono altri 45 minuti | Il secondo premio non arriva automaticamente. Un'ulteriore conferma sul secondo episodio ancora attivo lo fa salire a due punti e due convalidate. |
| Stesso fenomeno, autori diversi, due secondi a cavallo dell'ora | Gruppi diversi; entrambi restano in attesa. |

**Totale personale:** `PilotCommunityService.create_report` non chiama
`record_report_submission_memory`, mentre il servizio condiviso lo fa.
Il profilo legge il totale restituito dal server. Non basta quindi cambiare
l'etichetta nell'interfaccia.

**Convalidate e premi:** il filtro dei 45 minuti viene applicato prima di
registrare anche la convalida personale. La validità dell'episodio e il
conteggio personale possono così divergere. La convalida va registrata
indipendentemente dal diritto a ricevere un punto.

**Significato di “Smentisci”:** il codice tratta il voto negativo come cessazione
del fenomeno; alcune etichette lo presentano invece come smentita. Una
segnalazione può essere stata corretta e ora essere terminata. Con tre voti
negativi il gruppo viene ritirato dalla mappa per tutti; il votante lo può
nascondere subito dalla propria mappa.

Fonti: [servizio pubblico nazionale](../../backend/app/pilot_community_cloud.py),
[selezione frontend del servizio nazionale](../../frontend/src/services/localCommunityPilot.js),
[profilo](../../frontend/src/features/settings/SettingsView.jsx),
[testi delle azioni](../../frontend/src/copy/liveViewCopy.js).

## Semplificazione proposta

1. **Conteggi affidabili e visibili.** Presentare “Inviate”, “Confermate” e
   “Punti”, con una spiegazione breve: “Un punto quando altri confermano,
   massimo tre al giorno”. Contare la convalida anche se non produce un premio.
   Le modifiche a un invio conservano il conteggio; una sostituzione che crea
   davvero un altro invio segue una regola esplicita e coerente con le quote.
2. **Un solo percorso per modificare.** Mostrare “È ancora così”, “Modifica” e
   “Ritira”. Dentro “Modifica”, il sistema applica la correzione disponibile o
   propone un nuovo invio, spiegando l'effetto prima dell'invio. Le differenze
   tecniche tra rinnovo, correzione e sostituzione non devono diventare tre
   procedure da imparare. Per gli altri usare “Lo vedo anch'io” e “Non c'è più”;
   mantenere separata la segnalazione di un abuso.
3. **Una regola dei premi comprensibile.** Mantenere un punto per episodio
   confermato e massimo tre al giorno; proporre la rimozione del vincolo
   aggiuntivo dei 45 minuti. Restano unicità, limiti agli invii, protezione
   dall'autoconferma e dalle sostituzioni ripetute. Questa è una modifica di
   prodotto da valutare, non già applicata.

I limiti attuali agli invii sono distinti dai punti: almeno due minuti tra nuove
osservazioni, massimo quattro negli ultimi 60 minuti e dodici nelle ultime
24 ore. Correzione entro cinque minuti; rinnovo della stessa osservazione per
un'ora senza nuovi punti. Si possono mantenere questi controlli e mostrarne
la spiegazione solo quando servono.

La correzione futura del totale non ricostruisce da sola gli invii storici
mancanti. Prima di promettere un recupero occorre verificare quali dati
persistenti siano ancora disponibili. Anche un eventuale cambio del
raggruppamento orario richiede una scelta distinta e prove dedicate.

## Verifiche eseguite

- Backend: 68 test superati con
  `python -m unittest tests.test_community_reputation tests.test_pilot_community tests.test_pilot_community_rule_boundaries -q`.
- Frontend: 79 test superati nei quattro file `communityReputation.test.js`,
  `SettingsView.test.jsx`, `communitySocialPresentation.test.js` e
  `localCommunityPilot.test.js`, tramite `npm run test -- ...`, che usa
  il caricamento nativo della configurazione.
- Riproduzioni aggiuntive in memoria dei casi della tabella. I due difetti
  dei contatori non sono coperti dalle asserzioni delle suite eseguite.

Il ramo contiene solo questa analisi. Nessuna modifica a `main`, servizi
pubblici, Play, APK o telefono.
