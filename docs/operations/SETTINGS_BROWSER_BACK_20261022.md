# Impostazioni: Indietro nel browser — 22 ottobre 2026

## Stato e perimetro

Correzione verificata sul ramo `codex/settings-browser-back`, nato da main
`afa5152aa0f7c439df1be174bb896ac0e850cc90`. Il proprietario ha autorizzato
il commit della correzione e del verbale e la promozione locale su main.
I sorgenti coincidono per SHA-256 con quelli provati sul Galaxy e nei test.
Le evidenze descrivono lo stato della verifica prima del commit; la
promozione avviene tramite fast-forward, senza modificare il codice provato.
Nessuna AAB, installazione, push, deploy o invio.

## Problema e correzione

Su Brave del Galaxy, aprire Impostazioni cambiava la schermata dell'app ma non
creava una voce nella cronologia Web. Il tasto Indietro di Android poteva quindi
lasciare Brave. La freccia interna disponeva già della sezione di provenienza.

L'app attiva ora il gestore Web esistente `useBrowserDialogBack` soltanto quando
Impostazioni è aperta. Indietro richiama lo stesso ritorno della freccia interna.
Chiudere con la freccia o passare a un'altra tab rimuove la voce aggiunta, senza
accumulare ritorni vuoti nelle aperture successive. Il gestore è escluso nei
runtime nativi Capacitor; la navigazione Android esistente non viene modificata.
Nessun cambiamento grafico, di testo, ai servizi o alle preferenze dell'utente.

## Verifica automatica

- 368 test passati, zero falliti, in 42 file: App, Impostazioni, Eventi e
  gestore Indietro nativo. Inclusi 12 nuovi casi di regressione sulla navigazione
  effettiva di App, con cronologia browser reale in jsdom e servizi isolati.
- Coperti Home, Previsioni, Bollettino, Eventi e Scopri, sia nell'esperienza
  definitiva sia in quella ordinaria; StrictMode, aperture ripetute, freccia
  interna e cambio tab mentre Impostazioni è aperta.
- ESLint sui file modificati: passato.
- Build frontend Vite 8.1.6: passata, output nella cartella temporanea del sistema.
  Restano il warning noto sui chunk e un avviso informativo sui tempi dei plugin.
  Non è una build Android o un artefatto pronto al deploy.
- Vitest e Vite avviati con `--configLoader native`; massimo due worker per i test.

## Verifica sul Galaxy

Galaxy A52 SM-A525F, Android 14, Brave 1.97.59. Anteprima sulla porta 5174,
launcher `scripts/start-local-weather-pilot.ps1 -NationalCloud -CheckOnly`,
USB reverse. Reader già pubblicati letti senza avviare job o acquisizioni.

| Percorso verificato | Esito |
| --- | --- |
| Bollettino → Impostazioni → Indietro Android | Torna al Bollettino, Brave aperto |
| Eventi → Impostazioni → Indietro Android | Torna a Eventi, Brave aperto |
| Previsioni → Impostazioni → Indietro Android | Torna a Previsioni, Brave aperto |
| Eventi → Impostazioni → freccia interna | Torna a Eventi |
| Dopo il ritorno: dettaglio Eventi → Indietro Android | Chiude il dettaglio e torna alla lista |

Riscontri da screenshot e gerarchia; ogni acquisizione verifica Brave in primo
piano. Tutti i percorsi mantengono lo stesso tab del browser. Località Pordenone,
italiano e tema chiaro conservati; posizione e notifiche non toccate. Anteprima
lasciata sulle Previsioni. Il pannello notifiche inizialmente aperto è stato
chiuso senza leggerne i contenuti o cambiarne le impostazioni.

## Evidenze e limiti

[Risultati, identità dei sorgenti e hash](evidence/settings-browser-back-2026-10-22/verification.json).
Screenshot dopo Indietro: [Bollettino](evidence/settings-browser-back-2026-10-22/bulletin-return.png),
[Eventi](evidence/settings-browser-back-2026-10-22/events-return.png),
[Previsioni](evidence/settings-browser-back-2026-10-22/weather-return.png).

Log e gerarchie grezze nella cartella ignorata `.tmp/settings-browser-back-20261022`
della radice canonica. Le schermate Impostazioni con l'alias locale restano lì,
escluse dalle evidenze destinate al repository.

Questa prova riguarda Brave su Android. Non certifica Safari/iPhone o una nuova
release nativa; non estende la cronologia Web a tutte le sezioni dell'app.
