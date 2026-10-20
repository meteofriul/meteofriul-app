# Correzioni Web e riverifica Galaxy — 20 ottobre 2026

## Esito

Corretti i due riscontri della [prima verifica Galaxy](WEB_APP_GALAXY_VERIFICATION_20261020.md):
Indietro chiude il dettaglio Eventi mantenendo l'elenco aperto; la ricerca
mostra un solo comando di cancellazione, allineato anche con caricamento
e tastiera aperta. Entrambi verificati sul Galaxy A52 con Brave 1.97.59,
Android 14/API 34, in italiano/tema chiaro e friulano/tema scuro.

Lavoro locale sul ramo esistente `codex/web-android-parity`, base `a8bb5f1f`
(frontend approvato e main di partenza `bf304281`).
Il 20 ottobre, dopo il collaudo, il proprietario ha autorizzato il commit
delle correzioni e dei verbali e la promozione del lavoro verificato su main
locale. I cinque sorgenti coincidono con gli hash dell'artefatto collaudato;
non sono state introdotte altre modifiche funzionali dopo la prova sul Galaxy.
Controllo di pulizia della base: PASS. La consegna include anche il precedente
commit `a8bb5f1f` di preparazione e allineamento Web/Android.

Questa autorizzazione riguarda il salvataggio e l'integrazione del codice,
non la pubblicazione. Nessuna installazione, AAB, push, deploy o invio.

## Modifiche

- `useBrowserDialogBack`: una voce temporanea della cronologia mentre il
  dettaglio è aperto. Indietro la consuma e chiude il dettaglio; anche X,
  sfondo ed Escape, tramite lo smontaggio del dialogo, consumano la stessa
  voce. La registrazione evita duplicazioni in StrictMode e attende il
  ritorno asincrono prima di registrare una riapertura rapida. Preserva URL
  e stato precedente. Il comportamento resta circoscritto al dettaglio
  Eventi Web; non esteso a tutte le altre finestre dell'app.
- Runtime Capacitor esclusi dalla nuova gestione; il gestore Android
  esistente rimane quello utilizzato dall'app nativa.
- Ricerca: nascosto il controllo nativo Chromium/WebKit, mantenendo il
  pulsante accessibile dell'app e il tipo `search`. Spinner e cancellazione
  raggruppati nella stessa cella della griglia, senza andare a capo.

## Controlli

| Controllo | Risultato |
| --- | --- |
| Test locali | 56/56 in sette file, inclusi sei nuovi casi sulla cronologia; Vite/Vitest con config loader native |
| Lint mirato | PASS sui quattro file JavaScript/JSX coinvolti |
| Build Web e guardie | PASS; versione 0.1.14, endpoint e CARTO invariati; warning chunk preesistente non bloccante |
| Indietro reale IT | Tre cicli con apertura tramite touch e tasto Android Indietro: chiusura dettaglio, elenco/URL mantenuti, stato cronologia ripristinato |
| Chiusura X reale IT | Tre cicli tramite touch: voce temporanea rimossa. Un successivo Indietro raggiunge la pagina precedente in un solo passaggio |
| Indietro reale FUR/scuro | PASS: dettaglio chiuso, elenco in friulano mantenuto |
| Ricerca con tastiera IT/FUR | Un solo X visibile. Campo, spinner e X sulla stessa riga, alta 48 CSS px; pagina larga 411 px senza sforamento |
| Cancellazione | Testo svuotato tramite touch; X scompare, focus e tastiera rimangono sul campo |
| Telefono | Ufficiale, TEST, Brave e Chrome: versioni e date di installazione/aggiornamento identiche prima/dopo |
| Rete durante prova | 65 GET e 5 OPTIONS nel riepilogo delle 16:56:49 Europe/Rome; nessuna richiesta di scrittura e nessuna eccezione JS dell'app osservate |

Per mantenere visibile lo spinner è stata aggiunta temporaneamente una latenza
di 1.500 ms nella sola sessione DevTools del browser, poi rimossa. Risposte
dei servizi non simulate. I limiti CORS dell'origine locale rimangono:
questa prova riguarda il controllo di ricerca, non certifica il servizio
nazionale. La presenza di un solo X è verificata sulle immagini reali;
il valore `getComputedStyle` dello pseudo-elemento nativo non è usato come
prova della sua visibilità.

Il primo tentativo di touch remoto ha trovato Brave in background; dopo
averlo riportato in primo piano le prove sono state eseguite e registrate.
I test di cronologia attendono gli eventi effettivi, non un ritardo fisso.

## Artefatto ed evidenze

Nuova anteprima, senza sostituire l'archivio precedente:
`release-artifacts/web-candidates/20261020-web-navigation-fix/`.

- `web-preview.zip`, 503 file.
- SHA-256 `bc46313b9448aa4e987468d871d069a2ac4134bb2dba28f0e13a21b363e87cee`.
- Asset principali: `main-CJxLHnmY.js`, `main-BE0yK-t0.css`.
- `manifest.json`: hash di ogni asset e dei cinque sorgenti modificati,
  inclusi i test; stato `local-review-only-not-deploy-approved`.
- HTML e asset principali serviti sulla porta 5176 coincidono con il nuovo
  output archiviato. Nessuna nuova build nativa.
- [Evidenze selezionate](evidence/web-browser-fixes-2026-10-20/manifest.json):
  screenshot, misure, verifiche cronologia, pacchetti e traffico senza query.

La candidata aggiornata resta visibile nell'anteprima locale e su Brave
finché il collegamento USB e il server locale sono disponibili. Preferenze
della nuova origine locale ripristinate a Italiano/chiaro, Pordenone.
Notifiche non autorizzate (`default`), nessuna segnalazione inviata.

Restano aperti il binding API, i controlli dei servizi dall'origine pubblica,
Safari/iPhone e il passaggio dalla Web pubblica precedente. Questi risultati
non attestano Chrome, Safari, una nuova AAB o un rilascio pubblico.
