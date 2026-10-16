# Meteo Friul UI 3.0.0 - Audit Checklist

Data: 2026-06-21
Stato: checklist operativa iniziale

## Scopo

Questa checklist serve a verificare ogni passaggio della UI 3.0.0 senza rompere la app attuale.

Va usata:

- prima di promuovere una schermata dal laboratorio;
- prima di fare commit;
- prima di push/deploy/APK quando coinvolti;
- quando si importa logica dalla app attuale;
- quando si sposta un'informazione da una tab a un'altra.

Regola base:

```text
non perdere dati, cambiare solo gerarchia e presentazione
```

## 1. Controllo generale

- [ ] La modifica e' dietro flag/laboratorio se non ancora approvata.
- [ ] Non cambia API o backend senza motivo esplicito.
- [ ] Non cambia cache o policy dati dentro un intervento solo UI.
- [ ] Non aggiunge nuove regole meteo.
- [ ] Non aggiunge nuove interpretazioni OSMER.
- [ ] Non sposta testo/copy dentro JSX quando dovrebbe stare in modulo copy.
- [ ] Non aggiunge CSS definitivo in fondo a un file legacy senza motivo.
- [ ] Non usa `!important` come soluzione ordinaria.
- [ ] Non introduce card dentro card senza necessita reale.
- [ ] Non peggiora leggibilita su telefono.

## 2. Home

Obiettivo Home UI 3.0.0:

```text
sintesi immediata, utile, leggibile
```

La Home non deve diventare una dashboard tecnica.

### Dati da tenere in Home

Da valutare come principali:

- [ ] meteo corrente;
- [ ] temperatura;
- [ ] percepita se utile;
- [ ] condizione meteo;
- [ ] localita;
- [ ] min/max;
- [ ] vento sintetico;
- [ ] probabilita pioggia;
- [ ] pollini se disponibili;
- [ ] umidita se utile;
- [ ] alba/tramonto se rimangono leggibili;
- [ ] sintesi giornata;
- [ ] almanacco teaser;
- [ ] evento consigliato.

### Dati candidati a Bollettino/dettaglio

Da spostare o ridurre in Home se creano rumore:

- [ ] pressione;
- [ ] visibilita;
- [ ] nuvolosita percentuale;
- [ ] andamento orario;
- [ ] sparkline/grafici;
- [ ] vento dettagliato;
- [ ] probabilita pioggia estesa;
- [ ] evoluzioni 4/12/20;
- [ ] dettagli tecnici secondari.

Regola:

```text
la Home puo mostrare meno dati, ma nessun dato deve sparire dal sistema
```

### Check Home

- [ ] Localita chiara e ben allineata.
- [ ] Cambio localita non rompe dati Home.
- [ ] Temperatura leggibile su scene chiare e scure.
- [ ] Condizione meteo leggibile.
- [ ] Scenetta non copre testo.
- [ ] Scenetta non influenza logica app.
- [ ] Dettagli meteo non sembrano rumore grafico.
- [ ] Card sintesi leggibile.
- [ ] Icona sintesi visibile.
- [ ] Almanacco leggibile.
- [ ] Eventi teaser mostra totale coerente.
- [ ] IT/FUR entrambi corretti.
- [ ] Nessun testo troppo piccolo.
- [ ] Nessun oro su bianco poco leggibile.

## 3. Bollettino

Obiettivo Bollettino UI 3.0.0:

```text
lettura ufficiale e approfondita del meteo regionale
```

Qui possono vivere i dettagli tecnici che appesantiscono la Home.

### Dati Bollettino da proteggere

- [ ] A1-A9 ufficiali quando disponibili.
- [ ] Evoluzioni F/Z quando disponibili.
- [ ] Overlay vento ufficiale.
- [ ] Overlay fulmini ufficiale.
- [ ] Testo ufficiale OSMER.
- [ ] Fonte ARPA FVG OSMER chiara.
- [ ] Emissione bollettino.
- [ ] Stato dato non disponibile se manca fonte ufficiale.

### Dettagli che possono essere spostati qui dalla Home

- [ ] pressione;
- [ ] visibilita;
- [ ] nuvolosita;
- [ ] andamento giornata;
- [ ] vento dettagliato;
- [ ] pioggia/probabilita;
- [ ] temperatura per fasce;
- [ ] evoluzione 4/12/20;
- [ ] legenda chiara.

### Check Bollettino

- [ ] La mappa non interpreta liberamente il testo.
- [ ] Se A1-A9 ci sono, comandano loro.
- [ ] Se A1-A9 mancano, non si inventano marker.
- [ ] Vento non diventa marker primario.
- [ ] Fulmini non coprono label importanti.
- [ ] Province/label non coprono marker.
- [ ] Link esterno riconoscibile.
- [ ] FUR non maschera testo ufficiale IT.
- [ ] Traduzione FUR marcata come Meteo Friul quando presente.
- [ ] Testo leggibile senza scroll interni inutili.

## 4. Eventi

Obiettivo Eventi UI 3.0.0:

```text
eventi locali leggibili, aggiornati e coerenti fra web e APK
```

### Check dati

- [x] Pagina Eventi importata come view reale, non piu laboratorio.
- [x] `EventsView.jsx` non contiene fetch, localStorage o chiamate `/local/events`.
- [x] Controller Eventi legge cache full/home prima della rete e non scrive payload `refreshing`/`partial`.
- [x] `Oggi`, `Weekend`, `Prossimi` funzionano nel browser integrato.
- [x] Stato `refreshing`/`partial` mantiene cache visibile quando esiste.
- [ ] Conteggio Home coerente con tab Eventi in tutte le localita.
- [ ] Cache non nasconde eventi nuovi oltre scadenza.
- [ ] Localita diversa produce eventi coerenti.
- [ ] Coordinate vicine non rompono cache.
- [ ] Fonti completate visibili in diagnostica se serve.
- [ ] Immagini caricano lazy e non bloccano lista.
- [ ] Fallback immagine dignitoso.
- [ ] Distanza/ranking geografico prudente.
- [ ] Categorie non confondono sagre, teatro, turismo, ecc.

### Check UI

- [x] Card leggibili con immagine lazy e fallback visuale.
- [x] Data chiara.
- [x] Luogo chiaro.
- [x] Fonte chiara.
- [x] Stato vuoto/loading separato dalla lista reale.
- [x] Cambio localita apre il bottom sheet.
- [ ] Testo non tagliato male su tutti i casi reali.
- [ ] IT/FUR microcopy corretta su pagina completa.

## 5. Vedi

Obiettivo Vedi UI 3.0.0:

```text
webcam, territorio e segnalazioni in modo pulito e affidabile
```

### Webcam

- [x] Le card non promettono video se viene mostrato solo il fotogramma corrente.
- [x] Fonte/stato discreto ma chiaro.
- [x] Immagini aggiornate quando la fonte cambia.
- [x] Manifest remoto supportato tramite `/api/live/webcams`.
- [x] Fallback immagine non rotto e passaggio controllato alla webcam successiva.
- [x] Nota fonti esterne leggibile.

### Mappa e segnalazioni

- [x] La mappa di Vedi mostra esclusivamente segnalazioni community, non radar o previsioni.
- [x] I marker usano i gruppi zonali del backend e non espongono il punto GPS preciso.
- [x] Tocco del marker apre fenomeno, zona, orario, conteggio e conferme.
- [x] Invio riuscito ricarica immediatamente mappa e lista.
- [x] Mappa presente anche nello stato senza segnalazioni attive.
- [x] Disclaimer completo.
- [x] Disclaimer non appare in modo molesto.
- [x] Coordinate precise non esposte inutilmente.
- [x] Counter sintetico `X segnalazioni`, separato dall'azione.
- [x] Bottone segnala chiaro.
- [x] Zoom mappa affidato a gesto tattile/doppio tocco, senza controlli `+` e `-`.
- [x] Stati regolari della fonte rimossi; restano visibili soltanto problemi utili all'utente.
- [x] Correzione zona consentita soltanto tra localita' supportate entro 5 km dal GPS.
- [x] Coordinate GPS originali mantenute nell'invio e ricontrollate dal backend.
- [x] Azioni di conferma, correzione e nuovo rilevamento allineate come pulsanti icona.
- [x] TTL previsto lato Firestore quando configurato.
- [x] Rate limit presente.
- [x] Nessuna segnalazione community mascherata da dato certificato.

Contratto verificato: [LIVE_VIEW_FUNCTIONAL_CONTRACT.md](LIVE_VIEW_FUNCTIONAL_CONTRACT.md).

## 6. Scopri e Almanacco

Obiettivo:

```text
contenuti locali curati, leggibili e non improvvisati
```

### Check contenuto

- [ ] Fonte indicata quando serve.
- [ ] Testi lunghi non entrano senza revisione.
- [ ] FUR approvato solo quando controllato.
- [ ] Stato `in revisione` visibile solo dove serve.
- [ ] Nessun testo storico trattato come microcopy.
- [ ] Nessun blocco troppo lungo senza gerarchia.

### Check UI

- [ ] Card editoriali leggibili.
- [ ] Oro usato con contrasto sufficiente.
- [ ] Titoli chiari.
- [ ] Proverbi/compiti non sembrano elementi tecnici.
- [ ] CTA coerenti.

## 7. GPS e localita

- [ ] Posizione automatica e localita all'avvio non sono in conflitto.
- [ ] Cambio Comune aggiorna Home.
- [ ] Cambio Comune aggiorna Eventi.
- [ ] Cambio Comune aggiorna Scopri se dipendente da localita.
- [ ] Cache usa localita/coordinate in modo coerente.
- [ ] Se GPS non disponibile, localita manuale resta possibile.
- [ ] Permessi Android gestiti senza bloccare app.
- [ ] Nessun dato preciso mostrato inutilmente.

## 8. Notifiche e toast

- [ ] Push registrate su APK.
- [ ] Permesso notifiche gestito correttamente.
- [ ] Toast in app leggibile.
- [ ] Toast chiudibile.
- [ ] Colore toast coerente con gravita.
- [ ] Durata toast sufficiente.
- [ ] Testi push brevi e chiari.
- [ ] Avvisi Meteo Friul distinti da allerte ufficiali.
- [ ] Promemoria ripetuti solo secondo policy definita.
- [ ] Freddo, neve, ghiaccio, grandine, caldo, Bora, vento, pioggia e temporali coperti se previsti dalla policy.

## 9. Traduzioni IT/FUR

- [ ] Copy UI in moduli dedicati.
- [ ] Nessun fallback IT involontario in FUR.
- [ ] Cambio lingua visibile ma non invasivo.
- [ ] Titolo bi-color preservato.
- [ ] Microcopy FUR controllata.
- [ ] Testi ufficiali esterni non tradotti come se fossero ufficiali FUR.
- [ ] Bollettino FUR marcato come traduzione Meteo Friul quando presente.
- [ ] Dizionario/correttore usato come QA lessicale, non motore automatico cieco.

## 10. Regressioni visive da bloccare

Bloccare la modifica se compare uno di questi problemi:

- [ ] bianco abbagliante dominante;
- [ ] testo piccolo difficile da leggere;
- [ ] oro su bianco poco leggibile;
- [ ] card dentro card senza motivo;
- [ ] badge/pill fluttuanti senza gerarchia;
- [ ] pulsanti isolati o lontani dal contesto;
- [ ] scenetta che copre testo;
- [ ] mappa troppo decorativa;
- [ ] UI tutta di un solo colore;
- [ ] effetto dashboard pesante;
- [ ] effetto app meteo generica;
- [ ] cambio FUR invisibile;
- [ ] icone incoerenti col testo.

## 11. Test minimi prima di commit

Frontend:

- [ ] test mirati del modulo modificato;
- [ ] `npm run build`;
- [ ] browser locale;
- [ ] IT/FUR;
- [ ] mobile stretto;
- [ ] stati loading/vuoti/errori.

Backend, se coinvolto:

- [ ] test backend mirati;
- [ ] health locale;
- [ ] endpoint interessati.

Eventi, se coinvolti:

- [ ] Pordenone city-only;
- [ ] Pordenone con coordinate;
- [ ] altra localita;
- [ ] cache fresh/stale;
- [ ] immagini.

Bollettino, se coinvolto:

- [ ] giorno corrente;
- [ ] giorno proiettato;
- [ ] A1-A9;
- [ ] vento;
- [ ] fulmini;
- [ ] FUR/IT.

APK, solo se richiesto o necessario:

- [ ] preflight owner: `npm run android:sync` e `assembleDebug` eseguiti
      direttamente fuori dal sandbox con lo stesso endpoint tagged;
- [ ] endpoint verificato sia nel bundle WebView sia nel worker nativo;
- [ ] package, `versionCode`, `versionName`, permessi e SHA-256;
- [ ] firma APK;
- [ ] installazione su telefono;
- [ ] API produzione;
- [ ] notifiche se coinvolte.

AAB Play, solo dopo autorizzazione esplicita:

- [ ] nessun `android:sync` manuale precedente;
- [ ] esclusivamente `scripts/build-play-aab.ps1` eseguito fuori dal sandbox;
- [ ] ledger, bundletool, upload certificate, endpoint e archivio verificati.

## 12. Prima di deploy

- [ ] Repo pulito o modifiche note.
- [ ] Commit chiaro.
- [ ] Push riuscito.
- [ ] Cloud Run se backend cambiato.
- [ ] Cloudflare Pages se il frontend pubblico è cambiato.
- [ ] Health produzione letto correttamente.
- [ ] Degraded Protezione Civile FVG valutato come problema noto, non confuso con OSMER.
- [ ] APK rifatto solo se serve.

## 13. Domanda finale prima di promuovere una UI

Prima di promuovere una schermata UI 3.0.0 chiedere:

```text
E' piu bella, piu leggibile e piu ordinata senza cambiare il comportamento della app?
```

Se la risposta non e' chiaramente si, resta in laboratorio.

## 14. Audit Home laboratorio 2026-06-21

Esito ridisegno Home tranche 10:

- [x] Modifica ancora in laboratorio.
- [x] Nessuna API, cache o policy dati cambiata.
- [x] Nessuna nuova regola meteo o interpretazione OSMER.
- [x] Home ridotta a dati primari: meteo, temperatura, localita, percepita, pioggia, vento, umidita, Eventi teaser.
- [x] Pressione, visibilita e copertura non sono piu dati primari della Home.
- [x] CSS Home isolato in `frontend/src/features/home/home.css`.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Palette blu/oro usata come identita, non come tema monocolore.
- [x] Preview mobile `390x844` verificata.
- [x] Preview desktop `1280x900` verificata.
- [x] Console browser pulita dopo aggiunta favicon.
- [x] Bottom nav verificata con click su Eventi.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] stati runtime loading/error con dati reali;
- [ ] scenetta meteo definitiva;
- [ ] IT/FUR in browser su tutte le label Home;
- [ ] telefono reale o APK quando richiesto;
- [ ] collegamento controllato a `homeDataController`.

## 15. Audit personalita Home 2026-06-21

Esito passata visuale tranche 11:

- [x] La Home non usa piu solo card generiche e colore blu/oro.
- [x] Il marchio header non e' piu un placeholder testuale.
- [x] La hero comunica territorio e meteo con asset dedicato.
- [x] Testi e dati restano nativi, non incorporati nell'immagine.
- [x] Gli asset serviti sono ottimizzati in WebP.
- [x] I dettagli meteo restano limitati ai quattro dati primari.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun asset pesante PNG viene referenziato dalla UI finale.
- [x] Preview mobile `390x844` verificata.
- [x] Preview desktop `1280x900` verificata.
- [x] Console browser pulita.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] varianti meteo diverse da sereno;
- [ ] tema scuro;
- [ ] telefono reale/APK;
- [ ] eventuale asset night/rain/snow;
- [ ] collegamento live a dati reali.

## 16. Audit gerarchia Home 2026-06-21

Esito passata informativa tranche 12:

- [x] La hero non mostra piu `Dati da cache` in stato normale.
- [x] La formulazione generica dell'aggiornamento e' stata rimossa dalla hero normale e rifinita in tranche 16 come tempo relativo.
- [x] La Home include una sezione `Sintesi bollettino`.
- [x] La Home include una sezione `Almanacco`.
- [x] I nuovi componenti ricevono testo dal view model, non da logica nel JSX.
- [x] La sintesi bollettino non interpreta OSMER e resta fixture laboratorio.
- [x] La lingua IT/FUR arriva alla Home laboratorio.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] CSS nuovo limitato a `frontend/src/features/home/home.css`.
- [x] Header mobile corretto in `frontend/src/ui/layout/layout.css` per evitare overflow a 390px.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint e build passati.
- [x] Browser integrato: Home reload pulita, console pulita, click Eventi funzionante.
- [x] Browser integrato 390px: nessun overflow orizzontale.
- [x] Preview screenshot Edge: mobile compatto `500x844` e desktop `1280x900`.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] collegamento reale a bollettino quando disponibile;
- [ ] collegamento reale ad Almanacco quando disponibile;
- [ ] CTA Home con navigazione reale;
- [ ] stati loading/error/vuoto delle due sezioni;
- [ ] telefono reale/APK quando richiesto.

## 17. Audit maturita Home 2026-06-21

Esito passata strutturale tranche 13:

- [x] Il titolo visuale `Home` non ruba piu spazio nel primo viewport.
- [x] L'H1 resta presente per accessibilita.
- [x] Hero ridotta da circa 304px mobile a 244px nel viewport `390x844`.
- [x] Hero piu meteo/brand e meno cartolina grazie a overlay piu controllato.
- [x] Marchio aquila alleggerito via CSS.
- [x] Quattro dati meteo primari ancora subito visibili sotto la hero.
- [x] Eventi visibile nel primo viewport con prima card sopra la bottom nav.
- [x] Bottom nav leggermente piu compatta, senza scendere sotto target touch accettabile.
- [x] Bollettino e Almanacco restano presenti nella Home.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint e build passati.
- [x] Browser integrato: Home reload pulita, console pulita, click Eventi funzionante.
- [x] Browser integrato `390x844`: nessun overflow orizzontale.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] varianti meteo diverse da sereno;
- [ ] tema scuro;
- [ ] mark/logo semplificato come asset dedicato, se confermato;
- [ ] CTA reali di Eventi/Bollettino/Almanacco;
- [ ] telefono reale/APK quando richiesto.

## 18. Audit Eventi e avvisi Home 2026-06-21

Esito passata mirata tranche 14:

- [x] Eventi in Home e' una singola anteprima, non una mini-lista tagliata.
- [x] Il totale eventi resta visibile nel sottotitolo.
- [x] Il CTA verso la tab Eventi resta disponibile.
- [x] La card Eventi usa una variante CSS dedicata, senza sovrascritture globali.
- [x] Il testo avvisi non usa piu la forma tecnica `Avvisi ufficiali: 1`.
- [x] Singolare e plurale del testo avvisi sono coperti da test.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e guardrail passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] comportamento con eventi reali molto lunghi;
- [ ] CTA reali di Eventi/Bollettino/Almanacco;
- [ ] telefono reale/APK quando richiesto.

## 19. Audit header laboratorio 2026-06-21

Esito passata mirata tranche 15:

- [x] Il badge `Lab UI 3` non e' piu visibile nell'header.
- [x] Il concetto laboratorio resta interno alla shell.
- [x] Header piu pulito: brand, lingua, impostazioni.
- [x] Copy `labLabel` rimossa per evitare testo morto.
- [x] Regola CSS mobile del badge header rimossa.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e guardrail passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] stato/indicatore interno laboratorio in strumenti sviluppatore, se servira';
- [ ] telefono reale/APK quando richiesto.

## 20. Audit microtesto aggiornamento Home 2026-06-21

Esito passata mirata tranche 16:

- [x] `Aggiornamento recente` non compare piu nella Home.
- [x] L'aggiornamento mostra `Aggiornato 5 minuti fa` nella preview.
- [x] Il testo aggiornamento non ha background, bordo o radius da pill.
- [x] L'avviso meteo resta l'unica pill nella hero.
- [x] Il formato relativo vive nel view model, non nel JSX.
- [x] La preview usa `updatedAgoMinutes: 5` senza modificare servizi o cache.
- [x] Singolare/plurale del tempo relativo coperti da test deterministico.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] aggiornamento relativo con dati live reali;
- [ ] stati oltre 24 ore, se si decide una formula diversa;
- [ ] telefono reale/APK quando richiesto.

## 21. Audit microtesto allerta Home 2026-06-21

Esito passata mirata tranche 17:

- [x] `Avviso meteo` non compare piu nella Home.
- [x] La hero mostra `Allerta ufficiale` come testo semplice.
- [x] Il testo allerta non ha background, bordo o radius da pill.
- [x] L'allerta usa un'icona inline solo come richiamo visivo, senza tornare a pill.
- [x] Il view model supporta label specifiche come `Caldo intenso`.
- [x] Le vecchie classi `mf-home-insight` sono state rimosse dal CSS Home.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e guardrail passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] testo allerta con dati ufficiali reali;
- [ ] comportamento con label molto lunga;
- [ ] telefono reale/APK quando richiesto.

## 22. Audit allerta ufficiale azionabile 2026-06-21

Esito passata mirata tranche 18:

- [x] `Allerta ufficiale` e' `button` solo quando arriva da `officialAlerts`.
- [x] Il click apre il tab `Bollettino`.
- [x] Avvisi informativi non ufficiali restano non azionabili.
- [x] La policy vive nel view model tramite `alertSummary`, non in CSS o stringhe sparse.
- [x] Il testo resta trasparente, senza background, bordo o radius da pill.
- [x] Il focus keyboard e' visibile solo sul controllo azionabile.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build, guardrail e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] sezione/ancora reale `official-alerts` nel Bollettino definitivo;
- [ ] stato senza allerte ufficiali reali;
- [ ] telefono reale/APK quando richiesto.

## 23. Audit label brevi allerte Home 2026-06-21

Esito passata mirata tranche 19:

- [x] Home preferisce `Allerta gialla`, `Allerta arancione`, `Allerta rossa` quando il livello colore e' disponibile.
- [x] Con piu' allerte vince il livello colore piu' alto.
- [x] Se manca il colore, Home usa fenomeni corti come `Allerta temporali`.
- [x] Headline prolisse tipo `Allerta ufficiale: temporali forti...` non vengono mostrate nella Home.
- [x] Il dettaglio rimane destinato al Bollettino.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build, guardrail e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] payload reali Protezione Civile/allerte ufficiali con campi colore diversi;
- [ ] copy FUR specifica per livelli colore, da tradurre con audit dedicato;
- [ ] telefono reale/APK quando richiesto.

## 24. Audit tono colore allerte Home 2026-06-21

Esito passata mirata tranche 20:

- [x] `alertSummary` espone `level` e `tone`.
- [x] La UI accetta solo toni controllati: `yellow`, `orange`, `red`, `neutral`.
- [x] `Allerta gialla` usa la classe `mf-home-alert-text--yellow`.
- [x] Le allerte senza livello colore restano `neutral`, quindi non sembrano automaticamente gialle.
- [x] Il triangolo distingue il richiamo ufficiale; il colore distingue solo il livello.
- [x] Nessuna pill reintrodotta.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build, guardrail e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] resa visiva reale di `Allerta arancione` e `Allerta rossa` su device fisico;
- [ ] payload reali Protezione Civile con mapping colore;
- [ ] telefono reale/APK quando richiesto.

## 25. Audit hero immagine pulita 2026-06-21

Esito passata mirata tranche 21:

- [x] Rimossi i nodi decorativi `mf-home-hero__landscape`, `mf-home-hero__ridge`, `mf-home-hero__river`.
- [x] Rimossa texture diagonale dalla hero.
- [x] Rimossi bagliori/effetti radiali dalla hero.
- [x] La foto e' background diretto della hero.
- [x] Resta solo uno scrim leggero per leggibilita' del testo.
- [x] Temperatura, aggiornamento e allerta restano leggibili.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] resa della foto pulita su device fisico e display molto luminoso;
- [ ] eventuale regolazione dello scrim quando saranno introdotte varianti meteo;
- [ ] telefono reale/APK quando richiesto.

## 26. Audit varianti meteo Home 2026-06-21

Esito passata mirata tranche 22:

- [x] `weatherVariant` esposto dal view model.
- [x] Supportate varianti `clear`, `partly`, `cloud`, `rain`, `storm`, `snow`, `fog`, `night`.
- [x] La hero usa `data-weather-variant`, non logica meteo nel JSX.
- [x] Le icone hero seguono `weather.icon.type`.
- [x] Varianti CSS costruite con variabili di atmosfera, non sovrascritture sparse.
- [x] Nessuna texture o effetto pesante reintrodotto.
- [x] Dark mode annotata come fase progettuale successiva.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] QA visiva manuale di `rain`, `storm`, `snow`, `fog`, `night` con dati reali o fixture navigabili;
- [ ] eventuale set immagini dedicate per famiglie meteo, solo dopo stabilizzazione base;
- [ ] progettazione dark mode con token light/dark;
- [ ] telefono reale/APK quando richiesto.

## 27. Audit preview laboratorio varianti meteo 2026-06-21

Esito passata mirata tranche 23:

- [x] La preview e' confinata in `features/lab`.
- [x] La Home riceve un modello statico demo tramite prop `model`.
- [x] Nessun servizio dati, cache, GPS, notifiche o OSMER viene chiamato.
- [x] Il controllo permette di vedere `clear`, `partly`, `cloud`, `rain`, `storm`, `snow`, `fog`, `night`.
- [x] Ogni variante demo aggiorna condizione, icona, temperatura e dettagli principali.
- [x] CSS del controllo isolato in `lab.css`.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e browser QA interattiva passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] rimozione o flag esplicito del controllo preview prima di una UI finale;
- [ ] confronto manuale delle varianti su telefono reale;
- [ ] eventuali asset dedicati per famiglie meteo solo dopo approvazione della base.

## 28. Audit background meteo hero Home 2026-06-21

Esito passata mirata tranche 24:

- [x] Gli asset meteo sono usati in WebP, non PNG pesanti.
- [x] `clear` e `partly` restano sulla foto base pulita.
- [x] `cloud`, `rain`, `storm`, `snow`, `fog`, `night` usano background dedicati.
- [x] Aggiunte varianti combinate `cloud-night`, `rain-night`, `storm-night`, `snow-night`.
- [x] `snow-night` usa `notte_e_neve.webp`.
- [x] Le icone meteo specifiche hanno priorita su luna generica per pioggia/neve/temporale notturni.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint, build e browser QA interattiva passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] resa su telefono reale, soprattutto neve/nebbia molto chiare;
- [ ] eventuale regolazione fine degli scrim per testo su sole/poco nuvoloso;
- [ ] scelta definitiva se tenere tutte le varianti notte nella preview laboratorio.

## 29. Audit scrim leggero hero Home 2026-06-21

Esito passata mirata tranche 25:

- [x] Lo scrim globale e' stato ridotto su tutte le varianti meteo.
- [x] La protezione resta concentrata su lato testo e fondo hero.
- [x] Le immagini meteo risultano piu' visibili.
- [x] Nessuna `mask-image` introdotta.
- [x] Nessun filtro blur/grayscale introdotto.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Build e browser QA passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] controllo su telefono reale con luminosita' alta;
- [ ] eventuale taratura specifica per sole/poco nuvoloso dopo approvazione visuale.

## 30. Audit header brand UI 3 2026-06-21

Esito passata mirata tranche 26:

- [x] Titolo brand aggiornato a `Meteo Friûl`.
- [x] Sottotitolo in header letto dalla copy ufficiale gia' importata.
- [x] Aquila resa piu' presente e non chiusa in una tessera.
- [x] Pulsanti lingua e impostazioni lasciati invariati.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test mirato, lint, build e browser QA desktop/mobile passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] eventuale revisione finale del rapporto dimensionale aquila/titolo dopo test su telefono reale;
- [ ] scelta definitiva se mantenere sempre il sottotitolo o nasconderlo su viewport estremamente stretti.

## 31. Audit separazione Home normale / laboratorio 2026-06-22

Esito passata mirata tranche 27:

- [x] La Home normale non mostra piu' `Varianti meteo`.
- [x] La Home normale parte da header + hero meteo.
- [x] La preview varianti resta accessibile con flag lab esplicito.
- [x] Il flag lab e' disattivato di default.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test mirati, lint, build e browser QA desktop/mobile passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] decidere se mantenere storage `uiV3Lab` o lasciare solo query param per strumenti lab;
- [ ] QA su telefono reale della prima schermata senza pannello preview.

## 32. Audit card meteo Home sobrie 2026-06-22

Esito passata mirata tranche 28:

- [x] Rimosse le varianti colore per singola card meteo.
- [x] Tutte le card usano lo stesso accento blu/fiume.
- [x] Tutte le icone usano lo stesso trattamento cromatico.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA mirata passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] controllo su telefono reale della leggibilita' delle icone monocromatiche.

## 33. Audit contrasto allerta hero Home 2026-06-22

Esito passata mirata tranche 29:

- [x] Aggiunto mini-background traslucido alla riga allerta.
- [x] Mantenuta label compatta senza pill pesante.
- [x] Severity `yellow/orange/red/neutral` ancora gestita da CSS/view model esistente.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA mirata passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] controllo su varianti pioggia/neve/notte per evitare fondo troppo scuro o troppo evidente.
- [ ] debito progettuale: rifinire la leggibilita' della hero su immagini molto luminose con una passata dedicata
      (protezione locale per testi/allerta/metriche, non patch improvvisate o scurimento uniforme della foto).

## 34. Audit palette light e dark tokens 2026-06-22

Esito passata mirata tranche 30:

- [x] Palette light resa meno fredda tramite token.
- [x] Dark mode introdotta tramite `html[data-theme="dark"]`.
- [x] Default tema ancora light.
- [x] Preview dark disponibile con `?theme=dark`.
- [x] Bottom nav e superfici Home leggono token, non override sparsi.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test mirati, lint, build e browser QA light/dark passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] decidere se usare tema `system` come default finale o mantenere light;
- [ ] aggiungere controllo utente in Impostazioni quando la schermata esistera';
- [ ] QA su telefono reale in ambiente luminoso e buio.

## 35. Audit micro-accento FUR titoli pagina 2026-06-22

Esito passata mirata tranche 31:

- [x] Titoli pagina FUR con iniziale oro.
- [x] Bottom nav lasciata senza accenti lettera per lettera.
- [x] Copy non modificata per ottenere l'effetto visivo.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA dark/FUR passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] applicare lo stesso trattamento ai titoli reali quando le viste non saranno piu' placeholder/lab.

## 36. Audit colore titoli pagina per tema/lingua 2026-06-22

Esito passata mirata tranche 32:

- [x] Light IT: titolo pagina blu Friul.
- [x] Light FUR: titolo pagina blu Friul con iniziale oro.
- [x] Dark IT: titolo pagina chiaro.
- [x] Dark FUR: titolo pagina chiaro con iniziale oro.
- [x] Bottom nav non modificata.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA light/dark IT/FUR passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] controllo cromatico sugli altri titoli reali quando le schermate verranno completate.

## 37. Audit accento bottom nav light/dark 2026-06-22

Esito passata mirata tranche 33:

- [x] Bottom nav attiva con accento oro controllato in light mode.
- [x] Bottom nav attiva con accento oro leggibile in dark mode.
- [x] Stato attivo basato su token `--mf-nav-active-*`, non su override sparsi.
- [x] Nessun ritorno a pulsanti pieni oro.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA light/dark su navbar passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] QA su telefono reale per leggibilita' con pollice/nav vicina al bordo basso.

## 38. Audit oro identitario unico 2026-06-22

Esito passata mirata tranche 34:

- [x] Brand `Friul` usa `--mf-gold`.
- [x] Iniziale titoli pagina FUR usa `--mf-gold`.
- [x] Accento bottom nav attiva usa `--mf-gold`.
- [x] Alpha/bordi oro derivano da `--mf-gold-rgb`.
- [x] `--mf-gold-700` non e' usato per brand/titoli/accenti principali.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA light/dark passati.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] controllo finale palette su telefono reale in luce naturale.

## 39. Audit prima pagina Bollettino 2026-06-22

Esito passata mirata tranche 35:

- [x] Bollettino separato dalla Home e orientato alla consultazione ARPA/OSMER.
- [x] Mappa previsionale basata su SVG interno Meteo Friul con geometria Openpolis/ISTAT semplificata.
- [x] Confine FVG e confini interni PN/UD/GO/TS presenti nella mappa.
- [x] Tile OpenStreetMap rimossi dalla pagina Bollettino.
- [x] Layer immagine OSMER `_t` rimossi dalla pagina Bollettino.
- [x] Overlay dati proprietario con icone e badge Meteo Friul.
- [x] Lista testuale A1-A9 rimossa dalla pagina: le zone restano rappresentate dalla mappa.
- [x] Sezione `Dati utili` aggiunta con alba, tramonto, umidita, pollini, UV e vento.
- [x] Didascalia sotto mappa rimossa: firma `Mappa Meteo Friul` dentro l'area azzurra della mappa.
- [x] Riferimenti ARPA/OSMER mantenuti nella card fonte, non duplicati sotto la mappa.
- [x] Card fonte separata rimossa: `OSMER ARPA FVG`, aggiornamento e link sono metadati della sintesi bollettino sotto titolo/data.
- [x] Card `Testo ARPA` rimossa: il testo descrittivo resta una sola volta nella sintesi bollettino.
- [x] Scala visuale della mappa aumentata nel viewport mobile senza cambiare geometria o marker.
- [x] Fallback per dati overlay mancanti con avviso sopra la mappa.
- [x] Fonte `OSMER ARPA FVG` e link `www.meteo.fvg.it` visibili dentro la sintesi bollettino.
- [x] Google Maps non introdotto nella pagina Bollettino.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Lint, build e browser QA mobile light/dark passati.
- [x] Browser QA fallback maschera mancante passato tramite preview dev.

Resta da verificare prima di promozione fuori laboratorio:

- [ ] collegare i testi reali del bollettino quando il data controller sara' pronto;
- [ ] sostituire le coordinate fixture con mapping A1-A9 derivato dal data controller reale;
- [ ] validare in review finale la resa cartografica su telefono reale;
- [ ] decidere gestione ufficiale allerta/CFD con fonte ARPA senza duplicare il bollettino;
- [ ] collegare la mappa al data controller reale senza usare fixture.

## 40. Promemoria progettuale Almanacco

- [ ] Valutare rubrica `Astro Friul` / `Consiglio lunare` come contenuto leggero e locale.
- [ ] Non presentarla come oroscopo serio: deve restare ironica, pratica e dichiaratamente editoriale.
- [ ] Combinare, solo dopo audit, data, segno zodiacale del periodo, fase lunare e meteo del giorno.
- [ ] Evitare predizioni assolute o tono esoterico; usare consigli quotidiani legati a caffè, ombrello, orto, camminate, vento e caldo.
- [ ] Tenere la rubrica in Almanacco, non in Bollettino.
- [ ] Valutare rubrica `Accadde oggi` / `Pillole di Friuli` come contenuto culturale prioritario per `Scopri`.
- [ ] Preparare archivio controllato, non scraping automatico, con campi `date`, `title`, `body`, `area`, `source`, `tags`.
- [ ] Curare 50-100 pillole iniziali con rotazione giornaliera quando manca una data esatta.
- [ ] Tenere i testi brevi, 1-2 righe, su storia locale, lingua, tradizioni, stagioni e territorio.
- [ ] Posizionare `Accadde oggi` in `Scopri`; usare al massimo un teaser in Almanacco se utile.

## 41. Audit chiusura Bollettino e avvio Almanacco 2026-06-23

Esito passata Bollettino:

- [x] La card fonte separata non e' presente.
- [x] Fonte, aggiornamento e link `www.meteo.fvg.it` restano dentro la sintesi bollettino.
- [x] La card `Testo ARPA` non e' duplicata.
- [x] La lista testuale `Zone del bollettino` non e' duplicata sotto la mappa.
- [x] I tab mostrano i giorni del bollettino.
- [x] La mappa mantiene scala `330px` e nessun overflow orizzontale a `390x844`.
- [x] `Dati utili` resta leggibile sopra la bottom nav a fine scroll.
- [x] Light e dark mode verificate su Bollettino.

Avvio pagina Almanacco:

- [x] Route interna `almanac` aggiunta senza inserire un sesto item nella bottom nav.
- [x] CTA Home `Almanacco` apre la nuova pagina.
- [x] La bottom nav resta a 5 voci e, dentro Almanacco, mantiene Home come area madre.
- [x] Lo scroll della shell torna in alto quando cambia route.
- [x] Pagina Almanacco separata in `frontend/src/features/almanac`.
- [x] CSS Almanacco dedicato in `almanac.css`, importato nel layer `features`.
- [x] Santo del giorno visibile come sezione primaria.
- [x] Sole, luna, consigli della terra e tradizione/proverbio presenti; ponte a Scopri rimosso per evitare contenuti segnaposto.
- [x] Tradizione e proverbio raggruppati in un unico blocco culturale.
- [x] Blocco `Tradizione del giorno` spostato subito dopo il Santo, prima di Sole/Luna.
- [x] `Santo del giorno` e `Tradizione del giorno` usano header editoriale: icona blu, label oro, titolo principale nero.
- [x] Header `Santo del giorno` usa icona chiesetta, piu' semantica del calendario.
- [x] Blocchi pratici/naturali tenuti consecutivi: sole/luna prima, consigli della terra subito dopo.
- [x] Linee decorative sfumate inferiori rimosse dalle card Almanacco principali.
- [x] Hero editoriale Almanacco rimossa: resta solo riga data/stagione/giorno.
- [x] Sole e Luna restano in colonna, con Sole prima e Luna dopo.
- [x] Titoli `SOLE` e `LUNA` ripristinati come label rubrica compatte: icone blu e testo nero per leggibilita' su card chiara.
- [x] Token Almanacco allineati: rimosso `--mf-blue-600` non definito e usato `--mf-blue`.
- [x] Luna riallineata allo schema storico: orb, fase, barra, illuminazione, ciclo lunare, prossima fase.
- [x] Box duplicati Luna `Illuminazione`/`Ciclo lunare` rimossi: resta la sintesi unica sotto la barra.
- [x] Sole ridisegnato come schema informativo allineato alla Luna: orb solare, durata luce, barra e alba/tramonto.
- [x] Rimosso lo schema ad arco per evitare tagli visivi, marker ambigui e ingombro decorativo.
- [x] Dati Sole mantenuti nella card senza reintrodurre i tre riquadri separati sotto il disegno.
- [x] Microdato Sole reso comprensibile come frase `Sole alto - 67 gradi sopra l'orizzonte`, alimentata dal controller locale Almanacco.
- [x] Barra Sole e barra Luna ricevono percentuali dal modello dati: Sole calcolato da alba/tramonto, Luna da ciclo sinodico.
- [x] Orb Sole ripulito: rimosso il `conic-gradient` che creava una striscia/raggio giallo ambiguo.
- [x] Orb Luna ripulito: rimosso il dettaglio radiale/cratere che sporcava il simbolo in piccolo.
- [x] Riga data Almanacco resa neutra: rimosso oro non semantico per evitare effetto patchwork cromatico.
- [x] Riga data Almanacco resa piu' intenzionale: `Inizio estate` sostituito da `Estate, giorno 3`.
- [x] Accenti IT fixture corretti per `Martedi`, `Eta lunare` e `umidita`.
- [x] Blocco `Pillole di Friuli` rimosso dall'Almanacco finche' `Scopri` non avra' contenuti propri curati.
- [x] `Consigli della terra` alleggeriti visivamente: righe meno piene e piu' coerenti con una lista pratica.
- [x] `Consigli della terra` rifiniti come lista editoriale numerata, non come mini-card tecniche.
- [x] `frontend/src/domain/almanac` creato come dominio puro per santi, sole, luna, tradizione, proverbi e consigli.
- [x] Archivi controllati importati: santi, proverbi, consigli mensili, schedule e record Ostermann `section: almanacco`.
- [x] `almanacFixture.js` rimossa: la vista usa `buildAlmanacViewModel`, non fixture statiche.
- [x] Route Almanacco caricata in lazy loading per non appesantire il bundle principale della Home.
- [x] Home riallineata alla nuova gerarchia: hero, sintesi bollettino, almanacco, eventi.
- [x] `Percepita` spostata sotto la temperatura principale nella hero Home.
- [x] Griglia tecnica Home rimossa: vento, umidita' e pioggia non sono piu' mostrati come bento sotto la hero.
- [x] `Pioggia` aggiunta ai `Dati utili` del Bollettino, insieme a vento e umidita'.
- [x] `Accadde oggi` resta destinato a `Scopri`, non al Bollettino.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Nessun `App.css` introdotto.
- [x] Nessun `!important`.
- [x] Test, lint e build passati.
- [x] Browser QA `390x844` light: nessun overflow, console pulita, screenshot acquisito, schema Sole senza arco residuo.

Resta da verificare prima di promozione fuori laboratorio:

- [x] audit/import controllato del data controller Almanacco reale;
- [x] archivio santorale/editoriale controllato importato come dati locali testati;
- [ ] revisione FUR umana dei testi Almanacco;
- [ ] valutare se Almanacco resta pagina Home-linked o diventa sezione di Scopri;
- [ ] screenshot QA quando il canale browser torna a catturare immagini senza timeout;
- [ ] telefono reale/APK quando richiesto.

## 42. Audit copertura proverbi Ostermann 2026-06-24

Esito passata dati:

- [x] Ostermann resta fonte primaria per la parte culturale di `Scopri`; l'Almanacco usa solo una selezione giornaliera/teaser.
- [x] Archivio culturale Ostermann gia' importato: 59 record, di cui 49 `section: almanacco`.
- [x] Proverbi separati dall'archivio culturale: 48 record importati, non sufficienti per un proverbio al giorno.
- [x] Slot data-specifici attuali: 6 date piu' fallback, quindi non esiste ancora un calendario completo 365/366.
- [x] Aggiunto piano sorgenti `ostermannProverbSources.json` con pagine Ostermann prioritarie da estrarre.
- [x] Aggiunta staging area `proverbCandidates.json` per non mischiare candidati e dati pubblicabili.
- [x] Aggiunto guardrail `getProverbArchiveReadiness` per misurare copertura, slot mancanti e readiness del calendario quotidiano.
- [x] Aggiunto controllo `isPromotionReadyCandidate`: un candidato non passa se manca fonte/pagina, testo pulito o stato `ready`.
- [x] Prima tranche candidati estratta da Ostermann pagine 103, 105, 190 e 193.
- [x] Candidati segnati come `source_checked`, non `ready`, quindi non pubblicabili automaticamente.
- [x] Prima review editoriale separata in `proverbCandidateReview.json`.
- [x] Distinti candidati forti, sostituzioni, varianti, testi da contesto, archivio-only e hold.
- [x] Corretto guardrail mojibake: la lettera `â` corretta non viene piu' trattata come errore.
- [x] I candidati futuri restano fuori da `proverbs.json` finche' non sono verificati, normalizzati e tradotti.
- [x] Prima promozione controllata: 8 record Ostermann inseriti in `proverbs.json` con stato `lab_ready`, fonte pagina e `humanReviewRequired: true`.
- [x] Aggiunto slot `03-19` per `San Josef biel, buine anade`, coerente con il santo di San Giuseppe.
- [x] Guardrail aggiornato: conta record `lab_ready`, record con revisione umana richiesta e riferimenti schedule mancanti.
- [x] Nessun proverbio grezzo o solo `source_checked` e' stato promosso nella UI.
- [x] Seconda tranche candidati: estratte pagine Ostermann 49 e 54, con 13 nuovi candidati su luna, pioggia, freddo e santi invernali.
- [x] Pagine sorgente con candidati estratti: 49, 54, 103, 105, 190 e 193.
- [x] Candidati totali in `proverbCandidates.json`: 44, tutti fuori dalla UI finche' non vengono promossi manualmente.
- [x] Creato backlog Scopri `ostermannDiscoverBacklog.json`: 28 record, 28 pagine sorgente, uso primario `discover`, nessun record pronto UI.
- [x] Le 22 pagine non ancora proverbiali sono segnate `discover_backlog_extracted`, non piu' `to_extract`.
- [x] Aggiunto guardrail `getOstermannDiscoverBacklogSummary`: Scopri e Almanacco restano separati nei dati.
- [x] Creato catalogo sorgenti granulare `frontend/src/data/ostermann/sourceCatalog.json`: 27 pagine prioritarie Ostermann, incluse pagine P1 derivate dall'indice e dal piano sorgenti.
- [x] Creato archivio estratti `frontend/src/data/ostermann/extracts.json`: 26 estratti, 24 pagine sorgente coperte, uso primario `discover`.
- [x] Ogni estratto conserva pagina PDF, pagina testo, path normalizzato, path clean da verificare, tag, stagioni, aree, date anchor e stato review.
- [x] Le traduzioni IT sono marcate come `it_draft`, non come copy finale.
- [x] Tutti i record FUR restano `pending_review`; nessuna traduzione FUR e' stata dichiarata approvata.
- [x] Gli estratti superstiziosi/delicati sono marcati `archive_context`, non contenuto leggero per Home/Almanacco.
- [x] Aggiunto guardrail `getOstermannArchiveSummary` / `getOstermannArchiveIssues` per bloccare duplicati, pagine sconosciute e record pronti UI senza review.
- [x] Nessun nuovo estratto Ostermann e' letto dalla UI.
- [x] Prima source-check su pagine clean completata per 6 estratti marcati `needs_source_check`.
- [x] Cinque estratti sono stati sbloccati come `translated_it_draft` con `sourceCheck: clean_page_checked_partial`.
- [x] `ost-extract-044-luna-lavori-campi` e' stato sbloccato dopo controllo immagine `ocr-pages/page-044.png` e OCR alternativo `page-044-psm4.txt`, senza usare nuovi strumenti.
- [x] Il guardrail Ostermann ora conta `cleanPageCheckedExtracts`, `inconclusiveSourceChecks` e `remainingNeedsSourceCheck`.
- [x] Seconda tranche estratti granulari completata senza usare Unlimited-OCR e senza promozione UI.
- [x] Nuove pagine catalogate: 40, 43, 57, 58, 59, 68, 87, 96, 119, 121, 122, 129, 141, 146, 189, 192, 234, 608, 609 e 674.
- [x] Catalogo Ostermann portato a 47 pagine prioritarie.
- [x] Archivio estratti portato a 46 estratti granulari su 44 pagine sorgente coperte.
- [x] Nuovi filoni coperti: luna e lavori, durata delle giornate, Candelora/Pasqua/Ascensione, fumo del Midili, Garbin, campane e grandine, fulmini/piante, arcobaleno, aloni lunari, vigna/santi, erbe, Sant'Ermacora, giochi di neve.
- [x] Pagina 122 trattata solo con cautela: normalizzato rumoroso, OCR alternativo locale controllato parzialmente e record marcato `archive_context`.
- [x] Contenuti superstiziosi, rituali o medico-erboristici marcati `archive_context` e non trasformati in consigli pratici.
- [x] Tutte le nuove traduzioni IT restano `it_draft`; tutto il FUR resta `pending_review`.
- [x] Nessun nuovo estratto Ostermann e' letto dalla UI.
- [x] Recuperato il lavoro curato precedente gia presente in `ostermannCulturalDiscover.json`: 59 record, 54 pagine sorgente, 58 record FUR approvati e 1 record `short_ready`.
- [x] Confronto vecchia app/nuovo progetto: nessun ID mancante tra i 59 record curati, ma il nuovo progetto contiene FUR piu avanzato rispetto al JSON sorgente vecchio ispezionato.
- [x] Catalogate come `curated_recovered` le 16 pagine curatoriali non ancora presenti nel catalogo: 28, 45, 46, 67, 69, 70, 98, 106, 111, 145, 227, 233, 299, 541, 545 e 604.
- [x] Collegate anche le pagine 190 e 193 ai record curati recuperati, mantenendo lo stato candidati gia esistente.
- [x] Catalogo Ostermann portato a 63 pagine sorgente; tutte le 54 pagine del lavoro curato precedente risultano ora catalogate.
- [x] Guardrail aggiornato: conta record curati recuperati, FUR approvati, pagine curate mancanti dal catalogo e pagine curate ancora senza estratto granulare.
- [x] Le 18 pagine curate senza estratto granulare sono state trasformate in record `extracts.json` collegati con `curatedRecordId`.
- [x] `extracts.json` passa a 64 estratti granulari, 62 pagine sorgente coperte e 18 estratti `curated_recovered`.
- [x] Le 54 pagine del corpus curato precedente hanno ora copertura nel catalogo e nel livello granulare.
- [x] I record recuperati non duplicano il FUR approvato: puntano a `ostermannCulturalDiscover.json` come fonte curata.
- [x] Un solo estratto recuperato richiede ancora review FUR perche' il record sorgente e' `short_ready`.
- [x] Guardrail aggiunti per `catalogExtractIdsMissing` e `recoveredExtractsMissingCuratedRecord`.
- [x] Nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.
- [x] Creata mappa `curatedLinks.json` per collegare 38 estratti granulari non recuperati a record gia curati.
- [x] La mappa contiene 43 riferimenti verso `ostermannCulturalDiscover.json`, senza duplicare il FUR approvato.
- [x] I collegamenti servono a evitare doppioni futuri tra archivio granulare e corpus curato precedente.
- [x] Guardrail aggiunti per estratti collegati duplicati, estratti mancanti e record curati mancanti.
- [x] Nessun record di collegamento Ostermann e' letto dalla UI.

Resta da fare:

- [x] estrarre prima tranche candidati dalle pagine prioritarie Ostermann senza inserirli subito nella UI;
- [ ] correggere mojibake e grafie sospette nei proverbi legacy rimasti in `normalizationStatus: draft`;
- [ ] revisione FUR/IT umana della prima tranche in `proverbs.json` e `proverbCandidates.json`;
- [x] promuovere solo una shortlist P1 in stato laboratorio, senza dichiararla definitiva;
- [ ] verificare ogni proverbio contro pagina clean/PDF;
- [ ] review editoriale della seconda tranche pagine 49/54;
- [ ] verificare contro pagina clean/PDF gli estratti granulari rimasti non controllati prima di qualunque promozione;
- [x] trasformare le 18 pagine `curated_recovered` mancanti in estratti granulari collegati al record curato originale;
- [x] verificare su immagine `ost-extract-044-luna-lavori-campi`, perche' la pagina clean era inconcludente;
- [ ] normalizzare FUR dei 46 estratti non recuperati dal corpus curato e revisionare il singolo recupero `short_ready`;
- [ ] spezzare le pagine molto ricche come 104 e 60 in micro-estratti dopo controllo clean;
- [ ] trasformare il backlog Scopri in sezioni/card reali solo dopo disegno UX dedicato;
- [ ] scegliere quali record Scopri possono diventare teaser Almanacco;
- [ ] usare `curatedLinks.json` durante il disegno di Scopri per non creare card duplicate su temi gia curati;
- [ ] arrivare ad almeno 366 slot datati curati, meglio 500+ record per rotazione futura;
- [ ] promuovere in `proverbs.json` solo i record con fonte, pagina, stato revisione e traduzione IT/FUR controllata.

## 43. Audit dorsale dati Bollettino OSMER 2026-06-24

Esito passata dati:

- [x] Creata policy condivisa per allerte ufficiali in `domain/alerts/officialAlerts.js`.
- [x] Stato verde/green/non attivo escluso da banner, click e notificabilita UI.
- [x] Livelli giallo, arancione e rosso normalizzati in label brevi.
- [x] La Home non mantiene piu' un parser allerta duplicato.
- [x] Il dettaglio lungo dell'allerta resta destinato al Bollettino.
- [x] Creato `bulletinDataController`: fetch/stato dati separati dalla vista.
- [x] Creato `bulletinViewModel`: interpretazione payload separata dal rendering.
- [x] `BulletinView.jsx` riceve un modello e non decide fetch/cache.
- [x] `forecast.osmer_structured.days[*].areas9` guida i marker A1-A9 quando presente.
- [x] Se A1-A9 mancano, la UI non inventa marker e mostra lo stato non disponibile.
- [x] Il testo ufficiale OSMER viene mantenuto come testo ufficiale, senza traduzione mascherata.
- [x] La fonte `OSMER ARPA FVG` e il link `www.meteo.fvg.it` restano nella pagina Bollettino.
- [x] La sezione allerta usa ancora `official-alerts` come ancora semantica.
- [x] Le notifiche push non sono state importate o attivate: restano tema backend/APK dedicato.
- [x] Le previsioni FUR restano fuori da questa tranche: mappatura e revisione verranno fatte dopo.
- [x] Localita laboratorio `Udine` documentata come temporanea.
- [x] Bollettino collegato allo store/cache bootstrap condiviso con Home (`weatherBootstrapCache:v2`).
- [x] Apertura Bollettino: ultimo OSMER valido letto subito dalla cache, refresh eseguito dopo senza stato visibile di caricamento.
- [x] Se il refresh fallisce e la cache OSMER ufficiale esiste, il Bollettino resta leggibile come dato cache/stale invece di cadere in falso non disponibile.
- [x] Rimossa dalla route Bollettino la UI transitoria `Caricamento bollettino`.
- [x] Test mirati, lint e build passati.
- [x] Browser locale verificato: payload Udine con A1-A9 e mappa con 9 marker.

Resta da fare:

- [ ] sostituire la localita laboratorio con la sorgente reale localita/GPS della shell UI 3.
- [ ] decidere il flusso notifiche ufficiali senza mettere logica push nella vista.
- [ ] prima di qualunque collegamento live, eseguire `backend_dryrun_staging/backend_live_bridge_readiness.py`.
- [ ] risolvere i blocker del gate secondo `BACKEND_LIVE_BRIDGE_PLAN.md`.
- [ ] validare payload reali di allerta gialla/arancione/rossa quando disponibili.
- [ ] dedicare una passata separata alle previsioni FUR gia mappate nella vecchia app.
- [ ] verificare se l'attendibilita va mediata dalle aree A1-A9 o letta da un campo regionale ufficiale.

## 44. Audit parita runtime vecchia app -> UI 3 2026-06-28

Obiettivo:

- evitare di rifare da zero flussi gia risolti nella vecchia app solo per ottenere una UX piu bella;
- importare in modo controllato la dorsale runtime: cache, refresh, eventi, GPS, notifiche, stati offline/stale;
- mantenere i componenti UI come presentazione, senza fetch/cache/notifiche dentro le card.

Fonte vecchia app verificata:

- `frontend/src/App.jsx` vecchia app contiene bootstrap meteo con `weatherBootstrapCache:v2`;
- `fetchWeather` legge subito cache fresca/stale e aggiorna dopo;
- `fetchRegionalBulletin` usa cache OSMER ufficiale e non svuota la vista se la rete fallisce;
- `handleRefreshNow` coordina meteo, eventi, bollettino regionale e posizione automatica;
- `handlePullRefreshTouchStart/Move/End/Cancel` implementa pull-to-refresh con soglia e feedback;
- `refreshAfterForeground` aggiorna su `visibilitychange`, `focus` e `online`;
- Eventi mantiene cache e refresh separati, senza svuotare la lista visibile in caso di errore;
- GPS/autolocalizzazione e notifiche restano orchestrazione runtime, non UI.

Stato UI 3:

- [x] Home usa `homeDataController` con cache fresca prima della rete e fallback stale.
- [x] Bollettino ora usa `weatherBootstrapCache:v2`, ultimo OSMER valido immediato e refresh silenzioso.
- [x] Componenti Home/Bollettino non decidono fetch/cache direttamente.
- [ ] Pull-to-refresh non ancora migrato in UI 3.
- [x] Refresh foreground/online migrato come `runtimeRefreshToken` per Home/Bollettino, con soglia anti-rumore.
- [ ] Timer retry Eventi non ancora migrato in UI 3.
- [x] Localita attiva letta dalla chiave legacy `defaultLocation` e passata a Home/Bollettino/Opzioni.
- [ ] Bridge GPS/reverse geocoding non ancora migrato in UI 3.
- [ ] Reset cache da impostazioni non ancora migrato in UI 3.
- [ ] Notifiche push da auditare/importare solo in tranche dedicata.

Gate prima di considerare la app reattiva/completa:

- [x] aprire Home con cache presente: nessun loading visibile, dati immediati;
- [x] aprire Bollettino con cache OSMER presente: nessun loading visibile, dati immediati;
- [ ] forzare rete fallita con cache valida: dati restano visibili, stato errore non svuota UI;
- [ ] pull-to-refresh aggiorna meteo, Eventi e Bollettino senza doppie fetch inutili;
- [ ] pull-to-refresh non parte dentro modali, menu, bottom sheet o scroll interni;
- [ ] ritorno foreground/online aggiorna in background senza bloccare l'utente;
- [x] avvio con localita salvata non usa fixture Udine come se fosse dato della localita salvata;
- [x] cambio localita manuale non riusa lo stato route della localita precedente;
- [ ] cambio GPS/reverse geocoding non mescola dati vecchia localita con nuova localita;
- [ ] Eventi conserva cache/lista visibile durante refresh e stati parziali;
- [ ] notifiche restano scollegate dalla UI finche' non esiste policy/test dedicato.

## 45. Audit Bollettino giorno per giorno 2026-06-28

Controllo eseguito nel browser locale su `http://127.0.0.1:5173/?tab=bulletin&probe=day-audit`.

Esito IT:

- [x] `Oggi 28/06`: testo ufficiale presente, mappa presente, attendibilita `73%`, nessun loading, nessun pending.
- [x] `Lunedi 29/06`: testo ufficiale presente, mappa presente, attendibilita `64%`, nessun loading, nessun pending.
- [x] `Martedi 30/06`: testo ufficiale presente, mappa presente, attendibilita `69%`, nessun loading, nessun pending.
- [x] `Mercoledi 01/07`: testo ufficiale presente, mappa presente, attendibilita `64%`, nessun loading, nessun pending.
- [x] `Giovedi 02/07`: testo ufficiale presente, mappa presente, attendibilita `64%`, nessun loading, nessun pending.

Esito FUR:

- [x] Le tab restano allineate allo stesso calendario IT: `Vue 28/06`, `Lunis 29/06`, `Martars 30/06`, `Miercus 01/07`, `Joibe 02/07`.
- [x] Le sintesi FUR sono mostrate come seconda faccia del giorno corrispondente, non come calendario autonomo.
- [x] Nessun stato `Dati OSMER non disponibili`, `Caricamento bollettino` o `Non ancora emesso` sulle cinque tab attualmente emesse.
- [x] Il payload FUR espone campi `date` arretrati di un giorno, ma `date_label` e testo corrispondono al giorno IT corretto: mantenere il calendario IT come asse del Bollettino.

Note:

- Il quinto giorno risulta ora emesso da OSMER; quindi la UI deve mostrare `Giovedi 02/07` con testo, mappa e attendibilita, non `Non ancora emesso`.
- La regola `Non ancora emesso` resta valida solo quando il quinto slot esiste nel calendario ma manca davvero il testo/mappa ufficiale.

## 46. Audit Opzioni 2026-06-28

Esito:

- [x] L'ingranaggio della testata apre la route `settings`.
- [x] La pagina Opzioni resta fuori dalla bottom nav; la navigazione principale mantiene Home, Bollettino, Vedi, Eventi e Scopri.
- [x] Lingua IT/FUR selezionabile da pagina Opzioni e sincronizzata con la shell.
- [x] Tema `Chiaro`, `Scuro`, `Sistema` selezionabile e salvato come preferenza.
- [x] Rimossa la card introduttiva ridondante: il primo viewport mostra subito le preferenze.
- [x] Copy interna di cantiere sostituita con stati leggibili per utente (`Non attiva`, `Dati salvati`, `Regole definite`, ecc.).
- [x] Browser verificato: apertura Opzioni, cambio FUR, cambio tema scuro/chiaro e ritorno Home.
- [x] Console browser pulita.
- [x] Test mirati, lint e build passati.

Resta da fare:

- [ ] collegare localita reale/GPS solo dopo audit vecchia app;
- [ ] collegare pull-to-refresh e refresh foreground/online solo dopo audit runtime;
- [ ] collegare notifiche e permessi solo dopo audit policy e backend;
- [ ] decidere se la sezione Fonti dovra aprire pagine esterne, privacy o un dettaglio interno.

## 47. Policy cache vecchia e fonte non raggiungibile 2026-06-28

Decisione:

- [x] Cache recente: puo essere mostrata subito per rendere l'app reattiva.
- [x] Cache troppo vecchia: non deve essere presentata come bollettino corrente all'avvio.
- [x] Se il refresh fallisce e rimane solo cache stale, il view model del Bollettino mostra `Dati non raggiungibili`.
- [x] In questo stato non vengono mostrati testo, mappa, attendibilita o focus vecchi.
- [x] La Home eredita la stessa semantica dalla sintesi Bollettino: niente vecchio bollettino travestito da dato valido.

Verifiche:

- [x] Test `bulletinViewModel`: payload stale con forecast vecchio + errore rete produce `source_unreachable`.
- [x] Test `homeDataController`: snapshot meteo troppo vecchio non viene idratato come dato iniziale.
- [x] Test `bulletinDataController`: snapshot bollettino troppo vecchio non viene idratato all'avvio.
- [x] Browser caso sano: Bollettino aggiornato `28/06 - 12:41`, nessun loading e nessun warning.

Resta da fare:

- [ ] Traduzione FUR dedicata per il messaggio `Dati non raggiungibili`, senza toccare alla cieca il blocco FUR gia fragile.

## 48. Inventario runtime e sorgenti UI 3 2026-06-28

Documento di riferimento:

```text
UI3_RUNTIME_DATA_INVENTORY.md
```

Decisioni:

- [x] Distinti dati reali, cache, fallback controllati, dati locali curati, fixture/lab e UI only.
- [x] Chiarito che Home e Bollettino hanno gia dorsale reale/cache via `/api/weather/bootstrap`.
- [x] Chiarito che la ricerca localita usa lista FVG locale piu endpoint `/api/location/search`, ma non e' ancora registry comuni definitivo.
- [x] Chiarito che Vedi e Scopri restano viste laboratorio nella UI 3.0.0.
- [x] Chiarito che Eventi pagina ora ha dorsale reale/cache e non deve piu passare da `EventsLabView`.
- [x] Chiarito che Almanacco usa dati locali curati, non fonte live.
- [x] Chiarito che GPS, pull-to-refresh completo, reset cache e notifiche push sono ancora tranche dedicate.
- [x] Rimossa dalla Home la sintesi bollettino statica come fallback produttivo.

Gate da rispettare prima di altro redesign:

- [ ] ogni card Home deve dichiarare se legge dato reale, teaser locale o fallback neutro;
- [ ] nessuna fixture deve comparire come dato ufficiale;
- [x] Eventi pagina importa cache, filtri e stati base della vecchia app senza fetch dentro la view;
- [ ] Opzioni non deve promettere funzioni non collegate senza copy utente chiara;
- [ ] Bollettino resta la priorita meteo: data, testo, mappa, attendibilita, FUR/IT e stati fonte.

## 49. Audit/import Eventi runtime 2026-06-28

Obiettivo:

- portare la pagina Eventi fuori dal laboratorio senza copiare alla cieca la vecchia app;
- mantenere view, cache, API e view model separati;
- evitare lista vuota durante refresh o stati parziali.

Decisioni:

- [x] `EventsView` e' presentazionale: non fa fetch, non legge/scrive localStorage, non chiama `/local/events`.
- [x] `eventsDataController` gestisce cache full/home, fetch full, stati `refreshing`/`partial` e fallback stale.
- [x] `eventsViewModel` normalizza filtri tempo, categorie, date, immagini e copy.
- [x] `AppRoutes` collega la tab Eventi al controller, non alla vecchia `EventsLabView`.
- [x] La pagina usa `eventsCache:v10` e mantiene preferenza per raccolta full quando disponibile.

Verifica:

- [x] Test mirati: 7 file, 48 test passati.
- [x] `npm run lint` passato.
- [x] `npm run build` passato.
- [x] Browser integrato su `/?tab=events&probe=events-audit`: pagina non vuota, 20 eventi, tab Oggi/Weekend/Prossimi, categorie, immagini e zero errori console.
- [x] Browser integrato: click Weekend -> 5 eventi; click Prossimi -> 16 eventi visibili e `Mostra altri`; click Cambia -> bottom sheet localita.
- [x] Audit comuni rapidi: Udine, Pordenone, Trieste, Tarvisio e Lignano mostrano eventi reali e tab attive.
- [x] Bug trovato e corretto: una cache vuota recente poteva bloccare il refresh Eventi e mostrare 0 eventi anche se l'endpoint aveva dati.
- [x] Caso Gorizia verificato dopo correzione: 18 eventi, Oggi 7, Weekend 6, Prossimi 9+, console pulita.

Restano fuori:

- [ ] audit ranking geografico/event-weather fit;
- [ ] confronto puntuale Home count vs pagina per piu localita;
- [ ] database comuni/coordinate definitivo;
- [ ] pull-to-refresh completo e reset cache da Opzioni.

## 50. Audit qualita Eventi rapidi 2026-06-28

Controlli eseguiti:

- [x] API `/api/local/events` per Udine, Pordenone, Trieste, Gorizia, Tarvisio e Lignano Sabbiadoro.
- [x] Tutti i comuni rapidi auditati rispondono con `cache.status = fresh`.
- [x] Nessuna fonte pending nei payload auditati.
- [x] Nessun evento oltre 30 km nei record con distanza esplicita.
- [x] Browser Gorizia: immagini visibili caricate, 0 fallback sui primi 7 eventi.
- [x] Home Gorizia coerente con pagina Eventi: `18 eventi`.
- [x] Home Eventi ora usa la stessa normalizzazione della pagina Eventi per luogo e data compatta.
- [x] Home Eventi applica un ranking editoriale leggero: eventi puntuali di oggi/prossimi prima delle mostre o degli intervalli molto lunghi, senza nasconderli se sono gli unici disponibili.
- [x] Browser Home Gorizia dopo ranking: teaser `Piccolo Opera Festival -Da Ponte Cafe: Vienna`, data `28 GIU`, non piu mostra lunga iniziata ad aprile.

Risultati sintetici:

- Udine: 46 eventi, fonti TurismoFVG / Anteprima Sagre / SagreFVG.
- Pordenone: 49 eventi, fonti TurismoFVG / Paesi in Festa / Anteprima Sagre.
- Trieste: 30 eventi, fonti TurismoFVG / Anteprima Sagre / Pro Loco FVG.
- Gorizia: 18 eventi, fonti TurismoFVG / Anteprima Sagre.
- Tarvisio: 13 eventi, fonte TurismoFVG.
- Lignano Sabbiadoro: 20 eventi, fonte TurismoFVG.

Debiti emersi:

- [x] `eventWeatherFit` riprogettato come modulo puro di ranking nascosto Home, senza copy meteo visibile nella card Evento.
- [ ] audit titoli lunghi/troncati provenienti dalle fonti.

## 51. Audit eventWeatherFit 2026-06-28

Decisione:

- [x] Non copiato il vecchio `frontend/src/utils/eventWeatherFit.js` alla cieca.
- [x] Recuperato il criterio utile: sensibilita evento, indoor/outdoor, meteo delicato, pioggia, temporale, neve, vento/Bora, caldo e freddo.
- [x] Creato `frontend/src/features/events/eventWeatherFit.js` come modulo puro, senza JSX, fetch, cache o localStorage.
- [x] La Home usa il fit solo come score di ranking del teaser Eventi.
- [x] La pagina Eventi resta neutra: nessuna pill, consiglio o notifica meteo aggiunta.
- [x] Il fit non espone copy utente: restituisce `level`, `reasonCode`, `score` e metadati tecnici.
- [x] Testato che pioggia/temporale favoriscono eventi riparati a parita di data.
- [x] Testato che vento/Bora resta overlay di attenzione e non diventa una notifica Evento.

Restano fuori:

- [ ] usare `eventWeatherFit` per notifiche Eventi: richiede policy dedicata.
- [ ] usare `eventWeatherFit` nella pagina Eventi: da decidere solo se serve davvero.
- [ ] calibrare il peso dello score su payload reali di piu comuni.

## 52. Audit localita manuale e recenti 2026-06-28

Decisione:

- [x] Il cambio localita manuale passa dalla shell e resta separato da GPS/reverse geocoding.
- [x] La route attiva usa `getLocationCacheKey(activeLocation)` nella `key`, quindi Home, Bollettino ed Eventi vengono rimontati quando cambia comune.
- [x] La ricerca localita combina lista FVG locale ed endpoint `/api/location/search`, filtrando risultati fuori regione.
- [x] I recenti restano nel contratto legacy `recentLocations`, deduplicati e limitati a 6 voci.
- [x] La rimozione recenti non cambia la localita attiva: toglie solo la voce dalla lista recenti.
- [x] Il bottom sheet rilegge i recenti a ogni apertura, evitando stato interno vecchio se la lista cambia fuori dal pannello.
- [x] Copy del bottom sheet normalizzata in ASCII per evitare fragilita di encoding nel file FUR/IT.

Verifica:

- [x] Test mirati `appLocation` e `locationSearch`: 2 file, 10 test passati.
- [x] Server locale `http://127.0.0.1:5173/` raggiungibile con HTTP 200.

Restano fuori:

- [ ] registry comuni FVG definitivo con tutte le coordinate affidabili;
- [ ] GPS/reverse geocoding e policy auto-location dalla vecchia app;
- [ ] pull-to-refresh completo e refresh foreground/online;
- [ ] verifica browser automatica: il browser integrato si e' bloccato durante reload/snapshot in questa tranche.

## 53. Registry comuni FVG 2026-06-29

Fonte e metodo:

- [x] Elenco comuni/codici preso da ISTAT `Elenco-comuni-italiani.xlsx`, foglio `CODICI al 21_02_2026`.
- [x] Estratti 215 comuni FVG.
- [x] Coordinate prodotte da geocoding operativo via endpoint locale `/api/location/search`.
- [x] 202 comuni risolti con match geocoding diretto.
- [x] 13 comuni fusi/non risolti dal nome ISTAT esatto risolti con alias o componenti annotati nel record.
- [x] Nessuna coordinata inventata senza `coordinateSource` e, dove serve, `coordinateNote`.

Implementazione:

- [x] `frontend/src/data/fvgPlaces.js` ora contiene registry completo da 215 voci.
- [x] `LocationSearchSheet` usa il registry anche per i comuni rapidi, evitando coordinate duplicate scritte a mano.
- [x] Test aggiunti su conteggio, coordinate finite, comuni fusi e anti-mojibake.
- [x] Test search aggiornati: con registry completo una query puo restituire piu comuni coerenti, non un solo risultato.

Restano fuori:

- [ ] Verifica visuale browser del bottom sheet con molti risultati, bloccata se il browser integrato non torna stabile.
- [ ] GPS/reverse geocoding: usa policy e flusso vecchia app in tranche dedicata.
- [ ] Pull-to-refresh/cache runtime: tranche successiva dopo GPS/coordinate.

## 54. Audit GPS/reverse geocoding 2026-06-29

Fonte auditata:

- [x] Vecchia app `frontend/src/App.jsx`: chiavi `autoLocationEnabled`, `defaultLocation`, cache `locationReverseCache:v1`.
- [x] Vecchia app `autoLocationPolicy`: regole su failure, foreground recheck e confronto comune risolto.
- [x] Vecchia app backend `/api/location/reverse`: contratto `{ city, region, lat, lon }`.
- [x] Vecchia app Android/native bridge: soglie fast/confirm estratte, ma non collegato il bridge in UI 3.

Implementazione controllata:

- [x] `autoLocationPolicy` UI 3 mantiene la policy gia importata e aggiunge `getGpsLocationQualityDecision()`.
- [x] Soglie importate: fast entro 15 minuti e 5000 m, confirm entro 60 minuti e 10000 m.
- [x] `appLocation` espone la chiave legacy `autoLocationEnabled` con read/write testati.
- [x] `reverseLocation` costruisce URL `/api/location/reverse`, usa cache 7 giorni e normalizza `insideFvg`.
- [x] Fallimento reverse esplicito: non finge un comune FVG, ritorna `ok: false` e `Posizione attuale`.
- [x] Nessun permesso GPS chiesto dalla UI in questa tranche.
- [x] Nessun cambio automatico localita collegato alla shell in questa tranche.

Restano fuori:

- [x] UX consenso GPS in Opzioni con azione esplicita.
- [x] Collegamento `navigator.geolocation` browser dietro tap utente.
- [x] Strategia iniziale fuori FVG: non cambiare localita attiva.
- [ ] Android bridge.
- [ ] Reverse geocoding live verificato in browser dopo collegamento UI.
- [ ] Pull-to-refresh/cache runtime.

Verifica:

- [x] Test mirati GPS/reverse/app location: 3 file, 21 test passati.

## 55. UX consenso GPS e reverse live 2026-06-29

Decisione:

- [x] Il consenso GPS passa da Opzioni, sezione Localita.
- [x] La Home non chiede permessi posizione automaticamente.
- [x] L'azione visibile e' `Usa posizione` / `Aggiorna`, con stato di caricamento.
- [x] Se il browser non supporta GPS, il permesso e' negato o il reverse fallisce, la localita attiva non cambia.
- [x] Se il reverse risolve una posizione fuori FVG, la localita attiva non cambia.
- [x] Se il reverse risolve un comune FVG, la localita viene salvata in `defaultLocation` con source `browser_geolocation`, `autoLocationEnabled` diventa `true` e si forza refresh runtime.

Implementazione controllata:

- [x] `deviceLocation` legge solo coordinate browser, senza decidere il comune.
- [x] `App` orchestra `deviceLocation` + `reverseLocation` solo dopo tap esplicito.
- [x] `SettingsView` mostra stati GPS: non attiva, ricerca, aggiornata, permesso negato, fuori FVG, non disponibile.
- [x] Nessun Android bridge importato in questa tranche.

Restano fuori:

- [ ] Test browser con geolocation reale o mock browser.
- [ ] Stato/copy FUR da rifinire in passata dedicata encoding.
- [ ] Auto-check foreground della posizione automatica.
- [ ] UX privacy/permessi piu estesa.

Verifica:

- [x] Test mirati device/reverse/app location: 3 file, 18 test passati.
- [x] Lint frontend passato.
- [x] Browser Opzioni: riga `Posizione dispositivo / Non attiva / Usa posizione` visibile.
- [x] Reverse via Vite proxy con backend locale: Gorizia risolta da coordinate note.
- [ ] Permesso GPS reale non accettato nel browser: richiede consenso esplicito utente.

## 56. Separazione localita visualizzata e GPS dispositivo 2026-06-29

Decisione:

- [x] `Comune visualizzato` indica cosa l'utente sta guardando nell'app.
- [x] `Posizione dispositivo` indica dove si trova il telefono.
- [x] La scelta manuale di un comune non deve essere sovrascritta dal GPS.
- [x] Il GPS puo restare disponibile come dato dispositivo per funzioni future.
- [x] Il cambio manuale spegne solo il legame `meteo segue GPS`, senza cancellare lo stato GPS gia rilevato.

Restano fuori:

- [ ] UX avanzata per decidere se usare GPS solo per Eventi vicino a me.
- [ ] Storage persistente separato dell'ultima posizione dispositivo.
- [ ] Android bridge.

Verifica:

- [x] Test mirati device/reverse/app location: 3 file, 18 test passati.
- [x] Lint frontend passato.

## 57. Audit permessi GPS/notifiche vecchia app 2026-06-29

Decisione corretta:

- [x] Per APK/Android questa decisione supera il precedente flusso laboratorio `Usa posizione` da Opzioni come gate iniziale.
- [x] In Android il primo permesso da chiedere all'apertura e' posizione nativa.
- [x] Solo dopo accettazione/rifiuto posizione e localita risolta/scelta si chiede il permesso notifiche nativo.
- [x] Nessuna finestra/card/pannello custom per sostituire i prompt nativi Android.
- [x] Browser `Usa posizione` in UI3 resta flusso laboratorio/web, non gate Android definitivo.

Audit completato:

- [x] Vecchia app `frontend/src/App.jsx`: startup GPS, fallback, richiesta notifiche.
- [x] Vecchia app `frontend/src/utils/autoLocationPolicy.js`: fallimenti temporanei vs negazione.
- [x] Vecchia app `MainActivity.java`: bridge `MeteoAndroid` e Fused Location Provider.
- [x] Vecchia app `pushNotifications.js`: richiesta/registrazione native push.
- [x] Vecchio backend `devices/register` e `devices/unregister`.
- [x] Documento dedicato `PERMISSIONS_GPS_PUSH_AUDIT.md`.

Restano fuori:

- [ ] Collegamento push reale.
- [ ] Import modulo push UI3.
- [ ] Android bridge UI3.
- [ ] Test APK/emulatore.

## 58. Contratto startup Android GPS/notifiche 2026-06-29

Implementato:

- [x] Modulo puro `frontend/src/domain/startup/androidPermissionGate.js`.
- [x] Stati espliciti: GPS pending, GPS resolving, GPS denied, GPS unavailable, GPS temporary failure, manual location, notifications pending, ready.
- [x] Azioni esplicite: richiedere posizione nativa, risolvere localita da posizione, richiedere localita manuale, richiedere notifiche native.
- [x] Primo avvio Android: posizione nativa prima delle notifiche anche se esiste gia una localita manuale precedente.
- [x] Notifiche native solo dopo localita da posizione risolta o localita manuale scelta.
- [x] Fallimenti temporanei GPS separati da negazione/unsupported.

Restano fuori:

- [ ] Collegamento con Capacitor/Android reale.
- [ ] Prompt posizione reale.
- [ ] Prompt notifiche reale.
- [ ] Registrazione FCM/backend.
- [ ] Test APK/emulatore.

Verifica:

- [x] Test mirati Android gate + policy GPS/reverse/app location: 5 file, 37 test passati.

## 59. Audit runtime cache/refresh vecchia app 2026-06-29

Decisione:

- [x] L'app deve idratarsi subito da cache valida quando disponibile.
- [x] Il refresh deve lavorare dietro senza svuotare Home, Bollettino o Eventi.
- [x] Se la fonte non e' raggiungibile e non esiste cache utile, mostrare stato chiaro `Dati non raggiungibili`.
- [x] Se la fonte non e' raggiungibile ma esiste cache utile, il dato resta visibile con stato prudente/stale.
- [x] Pull-to-refresh e reset cache restano fuori finche non esiste un orchestratore testato.

Audit completato:

- [x] Vecchia app `App.jsx`: cache meteo, eventi, bollettino, refresh manuale, foreground, pull-to-refresh.
- [x] UI3 `homeDataController`: cache fresca, fallback stale, Eventi visibili durante errori.
- [x] UI3 `bulletinDataController`: solo cache con testo ufficiale OSMER.
- [x] UI3 `eventsDataController`: cache durante `refreshing`/`partial` e failure.
- [x] Documento dedicato `RUNTIME_REFRESH_CACHE_AUDIT.md`.

Restano fuori:

- [ ] Modulo puro `runtimeRefreshPolicy`.
- [ ] Collegamento shell UI3.
- [ ] Pull-to-refresh visuale.
- [ ] Reset cache da Opzioni.
- [ ] Foreground GPS Android-safe.

## 60. Contratto runtime refresh/cache 2026-06-29

Implementato:

- [x] Modulo puro `frontend/src/domain/runtime/runtimeRefreshPolicy.js`.
- [x] Stati espliciti: hydrated, refreshing, fresh, unchanged, stale visible, unreachable empty, ignored stale location.
- [x] Decisione idratazione cache prima della rete.
- [x] Decisione refresh fallito: mantenere dato visibile se esiste, altrimenti stato non raggiungibile.
- [x] Decisione anti-risposta localita vecchia.
- [x] Decisione Eventi: non scrivere cache per payload `refreshing`/`partial`, retry entro budget.
- [x] Throttle foreground refresh con stato pagina visibile.

Restano fuori:

- [ ] Collegamento a `App.jsx`.
- [ ] Pull-to-refresh visuale.
- [ ] Reset cache da Opzioni.
- [ ] Feedback UI definitivo.
- [ ] Foreground GPS Android-safe.

Verifica:

- [x] Test mirati runtime policy + controller Home/Bollettino/Eventi: 4 file, 33 test passati.

## 61. Collegamento shell runtime refresh/cache 2026-06-29

Implementato:

- [x] `App.jsx` usa `runtimeRefreshPolicy` per decidere se emettere un refresh token.
- [x] Timer verifica meteo centralizzato su `RUNTIME_WEATHER_VERIFY_INTERVAL_MS`.
- [x] Foreground/focus/online passano da `shouldRunRuntimeRefresh()`.
- [x] Cambio localita e GPS continuano a forzare refresh senza passare dal throttle.
- [x] La shell non svuota dati: le route continuano a usare controller/cache gia testati.

Restano fuori:

- [ ] Pull-to-refresh visuale.
- [ ] Reset cache da Opzioni.
- [ ] Feedback UI definitivo per refresh riuscito/non cambiato.
- [ ] Foreground GPS Android-safe.
- [ ] Orchestratore unico con esito `{ ok, changed, source }`.

Verifica:

- [x] Test mirato runtime policy: 1 file, 11 test passati.
- [x] Lint frontend passato.

## 62. Pull-to-refresh controllato 2026-06-29

Implementato:

- [x] Modulo puro `frontend/src/domain/runtime/pullRefreshPolicy.js`.
- [x] Soglie vecchia app recuperate: lock verticale 28px, trigger 172px, max 224px, tracking 0.58, feedback minimo 900ms.
- [x] Gesture collegata solo allo scroll principale `mf-app-main`.
- [x] Target esclusi: header, bottom nav, bottoni, input, tab, mappa bollettino, location sheet.
- [x] Swipe orizzontali cancellati per non interferire con tab/carousel.
- [x] Il rilascio oltre soglia emette solo refresh forzato via shell; non svuota dati visibili.

Restano fuori:

- [ ] Esito refresh `{ ok, changed, source }` visibile all'utente.
- [ ] Reset cache da Opzioni.
- [ ] Pull-to-refresh APK/emulatore.
- [ ] Eventuale affinamento microcopy FUR.

Verifica:

- [x] Test mirati pull/runtime/copy: 3 file, 19 test passati.
- [x] Lint frontend passato.

## 63. Feedback pull-to-refresh leggibile 2026-06-29

Corretto:

- [x] Icona refresh classica (`RefreshCw`) al posto dello spinner generico.
- [x] Copy IT `Sto aggiornando`.
- [x] Copy FUR `O soi daûr a inzornâ`.
- [x] Dopo rilascio oltre soglia l'indicatore resta visibile mentre la route attiva completa il refresh.
- [x] Tempo minimo visibile aumentato a 1400ms per evitare scomparsa immediata.
- [x] Route senza refresh dati chiudono subito la promise, rispettando comunque il tempo minimo.
- [x] Timeout guardrail 8000ms per non lasciare l'indicatore bloccato.

Restano fuori:

- [x] Stato finale esplicito: gestito nella tranche 64 con `Caricamento` / `Aggiornato` / `Fallito`.
- [ ] Verifica APK/emulatore touch reale.

Verifica:

- [x] Test mirati pull/runtime/copy: 3 file, 19 test passati.
- [x] Browser: markup pull-to-refresh presente con icona refresh e copy a riposo.
- [x] Lint frontend passato.

## 64. Esito pull-to-refresh esplicito 2026-06-29

Implementato:

- [x] Copy IT finale: `Caricamento`, `Aggiornato`, `Fallito`.
- [x] Copy FUR finale: `Cjariament`, `Inzornât`, `Falît`.
- [x] Il refresh mostra prima lo stato di caricamento, poi un risultato persistente prima del rientro.
- [x] `Aggiornato` viene mostrato solo quando la route attiva chiude il refresh con esito positivo.
- [x] `Fallito` viene mostrato in caso di errore route, timeout o promise respinta.
- [x] La rotazione dell'icona resta limitata allo stato di caricamento.
- [x] Correzione tranche 117: un errore di rete non diventa `Fallito` se resta visibile un dato utile non `isStale`.
- [x] Correzione tranche 117: un bollettino passato/scaduto (`isStale`) non viene considerato dato buono.

Restano fuori:

- [ ] Distinzione futura `Aggiornato` / `Gia aggiornato` con esito `changed`.
- [ ] Verifica APK/emulatore touch reale.

Verifica:

- [x] Test mirati pull/runtime/copy.
- [x] Test frontend completo: 59 file, 409 test.
- [x] Lint frontend.
- [x] Build frontend.
- [x] Browser integrato: pagina montata, nessun warning/error console, indicatore a riposo presente.
- [ ] Gesto touch reale su APK/emulatore: non riproducibile col drag desktop del browser integrato.

## 65. Localita globale e ingresso Cambia contestuale 2026-06-30

Implementato:

- [x] La localita resta globale: `defaultLocation` continua a governare Home, Eventi, Scopri e caricamenti dati.
- [x] Home mostra `Cambia` accanto alla localita nella hero meteo.
- [x] Eventi mantiene `Vicino a {comune}` e il suo `Cambia`.
- [x] Scopri e' predisposto con `A {comune}` + `Cambia`.
- [x] La lente generica in header e' stata rimossa per evitare doppio ingresso alla stessa funzione.
- [x] Il click `Cambia` apre sempre lo stesso bottom sheet localita globale.
- [x] Bollettino non mostra ancora la localita, per non confondere OSMER ufficiale FVG con una sezione localizzata non ancora progettata.

Restano fuori:

- [ ] decidere se/dove mostrare la localita nel Bollettino dopo OSMER, in una sezione localizzata separata;
- [ ] eventuale sorgente evoluzione locale, con Open-Meteo lasciato fuori per ora;
- [ ] verifica visuale finale su mobile reale/APK.

Verifica:

- [x] Browser integrato: Home/Eventi/Scopri aprono il bottom sheet `Cambia localita`.
- [x] Browser integrato: Bollettino non mostra il contesto localita.
- [x] Lint frontend passato.
- [x] Test frontend completo: 59 file, 411 test.

## 66. Ripresa audit permessi Android GPS/notifiche 2026-06-30

Verificato:

- [x] `PERMISSIONS_GPS_PUSH_AUDIT.md` aggiornato con stato UI3 corrente.
- [x] UI3 non ha ancora Capacitor/Android project nel `frontend/package.json`.
- [x] UI3 non ha ancora bridge Android `MeteoAndroid`.
- [x] UI3 usa oggi solo il flusso web/laboratorio `Usa posizione` in Opzioni.
- [x] `androidPermissionGate` resta modulo puro: nessun prompt reale, nessun token, nessun backend.
- [x] Vecchia app riletta: Manifest, `MainActivity.java`, `App.jsx`, `autoLocationPolicy.js`, `pushNotifications.js`, `capacitor.config.json`, `package.json`.
- [x] Confermato che il prompt posizione della vecchia app non e' generato direttamente dal bridge, ma dal flusso WebView/geolocation dopo il controllo nativo.
- [x] Confermato che le notifiche native passano da Capacitor Push Notifications.

Decisione:

- [x] Nessun collegamento push reale in questa tranche.
- [x] Nessun token FCM registrato.
- [x] Nessuna modifica a backend, workflow, scheduler o APK.
- [x] Prossima tranche tecnica: adapter nativi separati per location e push, poi orchestratore startup Android.

Restano fuori:

- [ ] Android project/Capacitor in UI3.
- [ ] Prompt posizione reale.
- [ ] Prompt notifiche reale.
- [ ] Registrazione device backend.
- [ ] Test APK/emulatore dell'ordine GPS -> notifiche.

## 67. Adapter posizione nativo esplicito 2026-06-30

Implementato:

- [x] Creato `frontend/src/services/nativeLocationAdapter.js`.
- [x] Creato `frontend/src/services/nativeLocationAdapter.test.js`.
- [x] Il contratto usa evento pulito `meteo-native-location`, non il legacy `meteo-fast-location`.
- [x] Il contratto prevede metodo esplicito futuro `requestLocationPermission(requestId)`.
- [x] Le richieste native usano `requestId` e ignorano eventi di altre richieste.
- [x] Timeout nativo normalizzato in `native_location_timeout`.
- [x] Payload nativo normalizzato prima della policy posizione.

Guardrail:

- [x] Nessun collegamento ad avvio app.
- [x] Nessuna modifica ad `App.jsx`.
- [x] Nessun Android project aggiunto.
- [x] Nessun permesso posizione reale chiesto.
- [x] Nessuna notifica/push/token/backend toccati.

Verifica:

- [x] Test mirati adapter + gate startup + policy posizione: 3 file, 26 test passati.

Restano fuori:

- [ ] Implementare bridge Android UI3 con `requestLocationPermission`.
- [ ] Collegare adapter a orchestratore startup Android.
- [ ] Test APK/emulatore del prompt posizione nativo.

## 68. Adapter notifiche native esplicito 2026-06-30

Implementato:

- [x] Creato `frontend/src/services/nativePushAdapter.js`.
- [x] Creato `frontend/src/services/nativePushAdapter.test.js`.
- [x] Il permesso notifiche viene normalizzato in `granted`, `denied`, `prompt`, `unsupported`, `unknown`.
- [x] `requestNativePushPermission()` chiama il prompt solo quando `checkPermissions()` restituisce `prompt`.
- [x] Il canale Android `weather_alerts` viene preparato solo per piattaforma Android.
- [x] `registerNativePush()` e `unregisterNativePush()` chiamano solo il plugin nativo.
- [x] I listener token/errori inoltrano solo a callback esplicite.

Guardrail:

- [x] Nessun token salvato.
- [x] Nessun `installation_id` generato.
- [x] Nessun backend `/devices/register` o `/devices/unregister` chiamato.
- [x] Nessun collegamento ad avvio app.
- [x] Nessun invio push reale.
- [x] Nessun Android project aggiunto.

Verifica:

- [x] Test mirati adapter push + gate startup: 2 file, 19 test passati.

Restano fuori:

- [ ] Collegare Capacitor reale in UI3.
- [ ] Collegare adapter push all'orchestratore startup Android.
- [ ] Registrazione device backend, solo dopo decisione esplicita.
- [ ] Test APK/emulatore del prompt notifiche nativo.

## 69. Terminologia posizione dispositivo 2026-07-01

Decisione:

- [x] In UI si usa `Usa posizione`, non `Usa GPS`.
- [x] `Posizione dispositivo` indica la posizione stimata da Android/browser, non solo il GPS satellitare.
- [x] La posizione puo arrivare da GPS, rete mobile, Wi-Fi, celle o ultima posizione nota se Android la considera valida.
- [x] Se i servizi posizione sono spenti o il permesso e' negato, resta valida la localita manuale.

Implementato:

- [x] `SettingsView` aggiornata con azione `Usa posizione` e stato `Ricerca posizione`.
- [x] Copy FUR della riga posizione completata per caricamento, errore, permesso negato, fuori FVG e successo.
- [x] `PERMISSIONS_GPS_PUSH_AUDIT.md` aggiornato con terminologia e provider Android.

Guardrail:

- [x] Nessun prompt reale collegato.
- [x] Nessun Android project aggiunto.
- [x] Nessun push, token, backend o meteo modificato.

## 70. Orchestratore startup Android GPS/notifiche 2026-07-02

Implementato:

- [x] Creato `frontend/src/domain/startup/androidStartupPromptFlow.js`.
- [x] Creato `frontend/src/domain/startup/androidStartupPromptFlow.test.js`.
- [x] Sequenza Android formalizzata: posizione dispositivo -> localita risolta/scelta -> notifiche.
- [x] GPS richiesto prima delle notifiche quando `autoLocationEnabled` e' attivo, anche se esiste una localita manuale precedente.
- [x] Notifiche richieste solo dopo localita risolta o manuale disponibile.
- [x] Rifiuto GPS senza localita utile porta a `manualLocationRequired`, senza prompt notifiche.
- [x] Rifiuto GPS con localita manuale disponibile consente il prompt notifiche.
- [x] Fallimento temporaneo GPS resta retryable e non apre notifiche.
- [x] `startupNotificationsAsked:v1` e `weatherAlertsEnabled` bloccano prompt notifiche ripetuti.

Guardrail:

- [x] Nessun prompt reale aperto.
- [x] Nessun collegamento a Capacitor reale.
- [x] Nessun token FCM salvato.
- [x] Nessuna chiamata backend device.
- [x] Nessun Android project aggiunto.

Verifica:

- [x] Test mirati startup/push/location: 4 file, 35 test passati.

Restano fuori:

- [x] Collegare orchestratore ad `App.jsx` nella tranche 71.
- [ ] Persistere i patch storage restituiti dal flow.
- [ ] Collegare plugin push reale.
- [ ] Test APK/emulatore dell'ordine prompt GPS -> notifiche.

## 71. Collegamento startup Android in App 2026-07-02

Implementato:

- [x] Creato `frontend/src/app/androidStartupRuntime.js`.
- [x] Creato `frontend/src/app/androidStartupRuntime.test.js`.
- [x] `App.jsx` esegue l'orchestratore solo su runtime Android nativo.
- [x] Browser escluso dal flusso startup: nessun prompt web automatico.
- [x] La risoluzione posizione di startup riusa il percorso di `Usa posizione`.
- [x] Storage startup letto con default Android corretto: primo avvio puo chiedere posizione.
- [x] Patch notifiche persistite solo se arrivera una decisione nativa reale, non su dry-run `unsupported`.

Guardrail:

- [x] Nessun prompt notifiche reale collegato.
- [x] Nessun token FCM salvato.
- [x] Nessuna chiamata backend device.
- [x] Nessun Android project aggiunto.
- [x] Nessuna modifica a meteo, OSMER, Eventi, Home o cache runtime.

Verifica:

- [x] Test mirati startup/runtime/location: 4 file, 34 test passati con `--configLoader native`.
- [x] Suite completa: 66 file, 475 test passati con `--configLoader native`.
- [x] Lint passato.
- [x] Build passato.

Restano fuori:

- [ ] Collegare plugin push reale.
- [ ] Test APK/emulatore dell'ordine prompt Android.
- [ ] Registrazione device/backend.

## 72. Audit localita e ricerca comuni 2026-07-03

Implementato/verificato:

- [x] Registro comuni FVG: 215 record come fonte auditata.
- [x] Nessun nome comune duplicato.
- [x] Nessuna coordinata mancante o non numerica.
- [x] Capoluoghi `Udine`, `Pordenone`, `Gorizia`, `Trieste` presenti e agganciati alla provincia corretta.
- [x] Ricerca locale immediata durante la digitazione.
- [x] Ricerca backend mantenuta dopo debounce, come arricchimento e non come prerequisito.
- [x] Sigle provincia `UD`, `PN`, `GO`, `TS` con capoluogo in prima posizione.
- [x] Localita attiva esclusa dalle liste visibili per evitare ripetizioni.
- [x] Recenti e comuni rapidi deduplicati.
- [x] Rimozione recenti verificata in UI.

Verifica:

- [x] Test mirati localita: 4 file, 26 test passati.
- [x] Suite completa: 66 file, 478 test passati.
- [x] Lint passato.
- [x] Build passato.
- [x] Browser: `Cambia` -> ricerca `gori` -> risultato immediato `Gorizia`.
- [x] Browser: ricerca `pord` con Pordenone attiva -> Pordenone non ripetuta.
- [x] Browser: rimozione recente -> voce rimossa da recenti e visibile nei rapidi.

Restano fuori:

- [ ] Reverse geocoding live completo.
- [ ] Health meteo locale per tutte le localita.
- [ ] Test Android/APK della ricerca localita.

## 73. Audit copertura Almanacco 365 2026-07-03

Implementato/verificato:

- [x] Creato `ALMANAC_365_COVERAGE_AUDIT.md`.
- [x] Confermata copertura santi: 366/366 giorni + default.
- [x] Confermata copertura consigli terra: 12/12 mesi, 2 consigli per mese + default.
- [x] Confermati proverbi: 52 record, 43 `homeEligible`, 6 date fisse + default.
- [x] Confermate tradizioni Ostermann eleggibili Almanacco: 49 record.
- [x] Confermate tradizioni con data esatta: 9 giorni.
- [x] Confermati record con intervalli: 8.
- [x] Confermato che il backlog Ostermann non e UI-ready.
- [x] Creato `frontend/src/domain/almanac/almanacCoverageAudit.test.js`.

Decisione:

- [x] Almanacco puo mostrare contenuti tutti i giorni grazie a fallback controllati.
- [x] Non esistono ancora 365 proverbi/tradizioni uniche.
- [x] Scopri resta archivio/rubrica, non motore giornaliero.
- [x] Prossimo passo progettuale: contratto `dailyEditorialCalendar`.

Restano fuori:

- [ ] Popolare una matrice editoriale 366 giorni.
- [ ] Decidere regole editoriali definitive per proverbio/tradizione/pillola.
- [ ] Certificare FUR campo per campo.

## 74. Audit reperimento proverbi giornalieri 2026-07-03

Implementato/verificato:

- [x] Creato `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Confermati proverbi pubblicati: 48.
- [x] Confermati proverbi `homeEligible`: 39.
- [x] Confermati candidati proverbiali: 44.
- [x] Confermati candidati recensiti: 31.
- [x] Confermati candidati consigliati per promozione: 13.
- [x] Confermate pagine fonte Ostermann candidate: 28.
- [x] Confermate pagine gia estratte come candidati: 6.
- [x] Confermate pagine backlog da lavorare: 22.
- [x] Creato `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js`.

Decisione:

- [x] Prima fonte dei mancanti: Ostermann gia mappato.
- [x] Fonti esterne solo dopo esaurimento/valutazione del bacino Ostermann.
- [x] Nessun proverbio senza fonte o senza stato editoriale.

Restano fuori:

- [ ] Promuovere i 13 candidati dopo review FUR/IT.
- [ ] Estrarre nuovi candidati dalle 22 pagine backlog.
- [ ] Costruire il calendario `dailyEditorialCalendar`.

## 75. Primo batch estrazione candidati proverbi Ostermann 2026-07-03

Implementato/verificato:

- [x] Letta pagina 97 in versione normalizzata e clean.
- [x] Letta pagina 102 in versione normalizzata e clean.
- [x] Escluso materiale OCR rovinato dalla pagina 97.
- [x] Aggiunti 6 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 97 e 102 come `candidate_extracted`.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornato guardrail `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js`.

Decisione:

- [x] I candidati FUR leggibili restano `source_checked`, ma non pubblicati.
- [x] I pronostici lunari in italiano restano `candidate` e senza `fur`.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.

Restano fuori:

- [ ] Revisione linguistica FUR dei nuovi candidati.
- [ ] Decisione editoriale sui due pronostici lunari italiani.
- [ ] Prossimo batch sulle 20 pagine backlog residue.

## 76. Secondo batch estrazione candidati proverbi Ostermann 2026-07-03

Implementato/verificato:

- [x] Letta pagina 99 in versione normalizzata e clean.
- [x] Letta pagina 104 in versione normalizzata e clean.
- [x] Esclusa la nota diaristica di Del Negro dalla pagina 99.
- [x] Escluso materiale OCR rovinato dalla pagina 104.
- [x] Aggiunti 8 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 99 e 104 come `candidate_extracted`.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornati guardrail `proverbDailyRepertoireAudit.test.js` e `proverbArchiveReadiness.test.js`.

Decisione:

- [x] I nuovi candidati restano materiale di lavoro.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.
- [x] I riferimenti locali come `Ambruset` restano candidati finche non viene chiarito il contesto geografico.

Restano fuori:

- [ ] Revisione linguistica FUR dei nuovi candidati.
- [ ] Decisione editoriale sui proverbi troppo locali o poco immediati.
- [ ] Prossimo batch sulle 18 pagine backlog residue.

## 77. Batch calendario santi Ostermann 2026-07-03

Implementato/verificato:

- [x] Letta pagina 59 in versione normalizzata e clean.
- [x] Letta pagina 60 in versione normalizzata e clean.
- [x] Letta pagina 61 in versione normalizzata e clean.
- [x] Letta pagina 63 in versione normalizzata e clean.
- [x] Candelora non duplicata perche gia presente in `proverbs.json`.
- [x] San Blas non duplicato perche gia candidato.
- [x] Aggiunti 14 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 59, 60, 61 e 63 come `candidate_extracted`.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornati guardrail `proverbDailyRepertoireAudit.test.js` e `proverbArchiveReadiness.test.js`.

Decisione:

- [x] I nuovi candidati restano materiale di lavoro.
- [x] I proverbi contraddittori su Venerdi Santo restano con nota di cautela.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.

Restano fuori:

- [ ] Revisione linguistica FUR dei nuovi candidati.
- [ ] Decisione editoriale su proverbi mobili come Venerdi Santo e Ascensione.
- [ ] Prossimo batch sulle 14 pagine backlog residue.

## 78. Batch meteo vento e temporali Ostermann 2026-07-03

Implementato/verificato:

- [x] Letta pagina 94 in versione normalizzata e clean.
- [x] Letta pagina 96 in versione normalizzata e clean.
- [x] Riletta pagina 101 come fonte gia parzialmente coperta da Scopri/proverbi esistenti.
- [x] Letta pagina 126 in versione normalizzata e clean.
- [x] Aggiunti 10 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 94, 96, 101 e 126 come `candidate_extracted`.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornati guardrail `proverbDailyRepertoireAudit.test.js` e `proverbArchiveReadiness.test.js`.

Decisione:

- [x] Pagina 94 usata con parsimonia perche soprattutto lessico dei venti.
- [x] Pagina 101 non duplica i proverbi gia presenti su sole rosso/nebbia.
- [x] Le credenze narrative su lampi/demoni/grandine restano fuori dai candidati proverbiali.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.

Restano fuori:

- [ ] Revisione linguistica FUR dei nuovi candidati.
- [ ] Decisione editoriale su detti troppo culturali per Almanacco breve.
- [ ] Prossimo batch sulle 10 pagine backlog residue.

## 79. Batch neve e arcobaleno Ostermann 2026-07-03

Implementato/verificato:

- [x] Rilette le pagine 130, 131, 132, 140 e 141 come batch neve/arcobaleno.
- [x] Aggiunti 10 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 130, 131, 132, 140 e 141 come `candidate_extracted`.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornati guardrail `proverbDailyRepertoireAudit.test.js` e `proverbArchiveReadiness.test.js`.

Decisione:

- [x] I nuovi candidati restano materiale di lavoro.
- [x] Il pronostico dell'arcobaleno di pagina 140 resta candidato Scopri, non proverbio FUR pronto.
- [x] I testi incerti su calendario mobile, neve e traduzione restano con nota di cautela.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.

Restano fuori:

- [ ] Revisione linguistica FUR dei nuovi candidati.
- [ ] Decisione editoriale su proverbi con traduzione incerta.
- [ ] Prossimo batch sulle 5 pagine backlog residue.

## 80. Chiusura backlog Ostermann P1/P2 2026-07-03

Implementato/verificato:

- [x] Lavorate le pagine 189, 192, 608, 609 e 674.
- [x] Aggiunti 8 record in `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 189, 192, 608, 609 e 674 come `candidate_extracted`.
- [x] Pagina 608 tracciata senza duplicare il nucleo San Barnaba gia estratto da pagina 192.
- [x] Aggiornati conteggi in `PROVERB_DAILY_REPERTOIRE_AUDIT.md`.
- [x] Aggiornati guardrail `proverbDailyRepertoireAudit.test.js` e `proverbArchiveReadiness.test.js`.

Decisione:

- [x] Backlog P1/P2 Ostermann gia individuato portato a zero.
- [x] I nuovi record restano candidati di lavoro.
- [x] I record in prosa culturale restano `candidate`, non pronti per proverbio quotidiano.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.

Restano fuori:

- [ ] Revisione linguistica FUR/IT dei 100 candidati.
- [ ] Selezione editoriale dei candidati promuovibili.
- [ ] Assegnazione calendario/rotazione dopo revisione, non prima.

## 81. Promozione candidati Ostermann gia revisionati 2026-07-03

Implementato/verificato:

- [x] Recuperata la review precedente: 31 candidati gia recensiti.
- [x] Confermati 13 candidati consigliati per promozione o sostituzione controllata.
- [x] Verificato che 8 dei 13 erano gia stati promossi in una tranche precedente.
- [x] Promossi i 5 candidati residui gia recensiti in `frontend/src/data/almanac/proverbs.json`.
- [x] Sostituito il record sporco `ostermann-umiltat-glace` con `ostermann-103-umiditat-glazze`.
- [x] Tutti i 13 record promossi restano `normalizationStatus: lab_ready` e `humanReviewRequired: true`.
- [x] Nessuna modifica a `schedule.json`: i nuovi record non sono date puntuali.
- [x] Nessun candidato non revisionato e stato pubblicato.

Conteggi:

- [x] Proverbi pubblicati: 48 -> 52.
- [x] Proverbi `homeEligible`: 39 -> 43.
- [x] Proverbi `lab_ready`: 8 -> 13.
- [x] Proverbi con review umana richiesta: 8 -> 13.

Decisione:

- [x] Non serve rifare da zero la review dei 100 candidati: la review gia fatta viene rispettata.
- [x] Il prossimo lavoro e classificare i candidati rimanenti non revisionati.

Restano fuori:

- [ ] Revisione linguistica finale dei 13 record `lab_ready`.
- [ ] Review FUR/IT dei candidati rimanenti instradati.
- [ ] Disegno dati Scopri/archivio per i record non proverbiali.
- [ ] Calendario giornaliero 366 slot.

## 82. Routing candidati Ostermann rimanenti 2026-07-03

Implementato/verificato:

- [x] Creato `frontend/src/domain/almanac/proverbCandidateRouting.js`.
- [x] Creato `frontend/src/domain/almanac/proverbCandidateRouting.test.js`.
- [x] Classificati i 69 candidati non coperti dalla review precedente.
- [x] Separati 55 record `source_checked` dai 14 record ancora `candidate`.
- [x] Nessun record e stato promosso in `proverbs.json`.
- [x] Nessun record e diventato `homeEligible`.

Code operative:

- [x] Review Almanacco: 23 record.
- [x] Contesto o sospensione: 32 record.
- [x] Scopri/archivio: 14 record.

Decisione:

- [x] La classificazione e un routing di lavoro, non una review linguistica finale.
- [x] Almanacco usa solo record che passano poi da review FUR/IT.
- [x] Scopri resta destinazione primaria per prosa, curiosita, contesto locale e materiale non proverbiale.

Restano fuori:

- [ ] Review FUR/IT della coda Almanacco da 23 record.
- [ ] Disegno dati Scopri/archivio per i 14 record non proverbiali.
- [ ] Eventuale assegnazione calendario solo dopo review, non durante il routing.

## 83. Review FUR/IT candidati Almanacco pagina 54 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 54 in versione normalizzata.
- [x] Riletta pagina Ostermann 54 in versione clean.
- [x] Registrata review per `ostermann-054-epifanie-fred`.
- [x] Registrata review per `ostermann-054-febrar-soreli`.
- [x] Registrata review per `ostermann-054-san-blas-fred`.
- [x] Registrata review per `ostermann-054-san-valantin-fin-inviar`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 23 a 19 record.

Decisione:

- [x] I quattro record sono promuovibili solo dopo review finale FUR/IT.
- [x] Nessun record pagina 54 entra ora in `proverbs.json`.
- [x] Nessun record pagina 54 diventa `homeEligible`.

Restano fuori:

- [ ] Promozione controllata dei quattro record in `proverbs.json`.
- [ ] Aggancio a `schedule.json` per 06/01, 03/02 e 14/02 solo dopo promozione.
- [ ] Validazione finale delle forme `frêt`, `Blâs`, `nâs`, `pâs`, `invier`, `agâr`.

## 84. Review FUR/IT candidati Almanacco pagina 60 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 60 in versione normalizzata.
- [x] Riletta pagina Ostermann 60 in versione clean.
- [x] Registrata review per `ostermann-060-sant-ane-furmiar`.
- [x] Registrata review per `ostermann-060-san-lurinz-seren`.
- [x] Registrata review per `ostermann-060-san-bortolomio-bon-timp`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 19 a 16 record.

Decisione:

- [x] I tre record sono promuovibili solo dopo review finale FUR/IT.
- [x] `ostermann-060-avost-monz-fumin` resta in contesto/sospensione.
- [x] Nessun record pagina 60 entra ora in `proverbs.json`.
- [x] Nessun record pagina 60 diventa `homeEligible`.

Restano fuori:

- [ ] Promozione controllata dei tre record in `proverbs.json`.
- [ ] Aggancio a `schedule.json` per 26/07, 10/08 e 24/08 solo dopo promozione.
- [ ] Validazione finale di `furmiâr`, `denote/dinote`, `Lurinz`, `deliziôs`, `Bortolomio`, `vendemis`.

## 85. Review FUR/IT candidati Almanacco pagina 61 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 61 in versione normalizzata.
- [x] Riletta pagina Ostermann 61 in versione clean.
- [x] Registrata review per `ostermann-061-san-maurizi-seren`.
- [x] Registrata review per `ostermann-061-san-simon-unviar`.
- [x] Registrata review per `ostermann-061-fueis-tardis`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 16 a 13 record.

Decisione:

- [x] San Maurizio e San Simone sono promuovibili solo dopo review finale FUR/IT come record datati.
- [x] `ostermann-061-fueis-tardis` e promuovibile solo come contenuto autunnale/stagionale, non come slot calendario.
- [x] Nessun record pagina 61 entra ora in `proverbs.json`.
- [x] Nessun record pagina 61 diventa `homeEligible`.

Restano fuori:

- [ ] Promozione controllata dei tre record in `proverbs.json`.
- [ ] Aggancio a `schedule.json` per 22/09 e 28/10 solo dopo promozione.
- [ ] Validazione finale di `Maurizi`, `vintôs`, `Simon`, `unviâr`, `cjâdi`, `temê`, `crût`.

## 86. Review FUR/IT candidati Almanacco pagina 192 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 192 in versione normalizzata.
- [x] Riletta pagina Ostermann 192 in versione clean.
- [x] Registrata review per `ostermann-192-san-barnaba-vin`.
- [x] Registrata review per `ostermann-192-assunte-vin`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 13 a 11 record.

Decisione:

- [x] I due record sono promuovibili solo dopo review finale FUR/IT.
- [x] Il record San Barnaba mantiene cautela sulla lettura OCR della data nella fonte.
- [x] Nessun record pagina 192 entra ora in `proverbs.json`.
- [x] Nessun record pagina 192 diventa `homeEligible`.

Restano fuori:

- [ ] Promozione controllata dei due record in `proverbs.json`.
- [ ] Aggancio a `schedule.json` per 11/06 e 15/08 solo dopo promozione.
- [ ] Validazione finale di `Barnaba`, `Assunte`, `bondance` e dell'ancora calendario San Barnaba.

## 87. Review FUR/IT candidati Almanacco pagina 126 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 126 in versione normalizzata.
- [x] Riletta pagina Ostermann 126 in versione clean.
- [x] Registrata review per `ostermann-126-tone-ploe-tempieste`.
- [x] Registrata review per `ostermann-126-mai-tempieste`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 11 a 9 record.

Decisione:

- [x] `ostermann-126-tone-ploe-tempieste` e promuovibile come contenuto stagionale temporalesco.
- [x] `ostermann-126-mai-tempieste` e promuovibile come contenuto mensile di maggio.
- [x] Nessun record pagina 126 entra ora in `proverbs.json`.
- [x] Nessun record pagina 126 diventa `homeEligible`.
- [x] Gli altri record pagina 126 restano fuori per contesto, tono o cautela editoriale.

Restano fuori:

- [ ] Promozione controllata dei due record in `proverbs.json`.
- [ ] Validazione finale di `tone`, `ploe`, `tempieste`, `Mai`, `nuie nus reste`.
- [ ] Disegno regola calendario/mese per i contenuti non datati.

## 88. Review FUR/IT candidati Almanacco pagina 130 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 130 in versione normalizzata.
- [x] Riletta pagina Ostermann 130 in versione clean.
- [x] Registrata review per `ostermann-130-sot-nev-pan`.
- [x] Il record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 9 a 8 record.

Decisione:

- [x] Il record e promuovibile come contenuto stagionale invernale.
- [x] Non e uno slot calendario.
- [x] Nessun record pagina 130 entra ora in `proverbs.json`.
- [x] Nessun record pagina 130 diventa `homeEligible`.

Restano fuori:

- [ ] Promozione controllata del record in `proverbs.json`.
- [ ] Validazione finale di `nef`, `ploe`, `fan`.
- [ ] Disegno regola stagionale per i contenuti invernali non datati.

## 89. Review FUR/IT candidati Almanacco pagina 104 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 104 in versione normalizzata.
- [x] Riletta pagina Ostermann 104 in versione clean.
- [x] Registrata review per `ostermann-104-monts-chapiel`.
- [x] Registrata review per `ostermann-104-cil-lane`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 8 a 6 record.

Decisione:

- [x] I due record sono promuovibili come segni meteo visuali/quotidiani.
- [x] Nessuno dei due e uno slot calendario.
- [x] Nessun record pagina 104 entra ora in `proverbs.json`.
- [x] Nessun record pagina 104 diventa `homeEligible`.
- [x] I record pagina 104 con riferimento locale specifico o resa meno stabile restano fuori.

Restano fuori:

- [ ] Promozione controllata dei due record in `proverbs.json`.
- [ ] Validazione finale di `cjapiel`, `falç`, `rischjel`, `cîl`, `a lane`.
- [ ] Disegno regola per i segni meteo non datati.

## 90. Review FUR/IT candidati Almanacco pagina 49 2026-07-03

Implementato/verificato:

- [x] Riletta pagina Ostermann 49 in versione normalizzata.
- [x] Riletta pagina Ostermann 49 in versione clean.
- [x] Registrata review per `ostermann-049-prin-martars-lune-pluv`.
- [x] Registrata review per `ostermann-049-lune-brume`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 6 a 4 record.

Decisione:

- [x] Il record `prin martars di lune` e promuovibile come contenuto lunare/ciclo lunare.
- [x] `Lune di Brume` e promuovibile come contenuto mensile di novembre.
- [x] Nessun record pagina 49 entra ora in `proverbs.json`.
- [x] Nessun record pagina 49 diventa `homeEligible`.
- [x] Gli altri record lunari pagina 49 restano fuori per tono, spiegazione o oscurita editoriale.

Restano fuori:

- [ ] Promozione controllata dei due record in `proverbs.json`.
- [ ] Validazione finale di `prin martars di lune`, `sec/sech`, `Brume`.
- [ ] Disegno regola per contenuti lunari/mensili non datati.

## 91. Chiusura coda Review Almanacco Ostermann 2026-07-04

Implementato/verificato:

- [x] Riletta pagina Ostermann 96 in versione clean.
- [x] Riletta pagina Ostermann 97 in versione clean.
- [x] Riletta pagina Ostermann 99 in versione clean.
- [x] Riletta pagina Ostermann 102 in versione clean.
- [x] Registrata review per `ostermann-096-garbin-timp`.
- [x] Registrata review per `ostermann-097-rosadis-marz-bueris-avril`.
- [x] Registrata review per `ostermann-099-tre-fumatis-ploe`.
- [x] Registrata review per `ostermann-102-cuch-ploe-sut`.
- [x] Ogni record ha `recommendedFur`, `recommendedIt`, fonte pagina e motivazione.
- [x] La coda Review Almanacco residua passa da 4 a 0 record.

Decisione:

- [x] I quattro record sono promuovibili solo dopo review finale FUR/IT.
- [x] Nessuno dei quattro e uno slot calendario giornaliero.
- [x] Nessun record entra ora in `proverbs.json`.
- [x] Nessun record diventa `homeEligible`.
- [x] La coda Review Almanacco preliminare e chiusa.

Restano fuori:

- [ ] Promozione controllata dei record promuovibili in `proverbs.json`.
- [ ] Validazione finale di `garbin`, `bueris`, `fumatis`, `cuc/cuch`, `sût`.
- [ ] Disegno regola per contenuti mensili, stagionali, lunari e segni meteo non datati.
- [ ] Trattamento separato delle code `Contesto o sospensione` e `Scopri/archivio`.

## 92. Piano promozione controllata Almanacco 2026-07-04

Implementato/verificato:

- [x] Creato `frontend/src/domain/almanac/proverbPromotionPlan.js`.
- [x] Creato `frontend/src/domain/almanac/proverbPromotionPlan.test.js`.
- [x] I 36 candidati promuovibili sono separati in 13 gia pubblicati e 23 pendenti.
- [x] I 23 pendenti sono classificati per uso: 10 datati, 4 mensili, 4 stagionali, 4 segni meteo, 1 ciclo lunare.
- [x] I 10 candidati datati sono gli unici candidati con slot potenziale in `schedule.json`.
- [x] I 13 candidati gia pubblicati risultano presenti in `proverbs.json`.
- [x] Nessun record e stato pubblicato in questa tranche.
- [x] Nessun record e stato agganciato a `schedule.json`.

Decisione:

- [x] Il piano e una matrice di lavoro, non una promozione dati.
- [x] La pubblicazione resta manuale e richiede review finale FUR/IT.
- [x] I proverbi non datati non devono entrare nello schedule giornaliero.

Restano fuori:

- [ ] Promozione controllata dei 23 record pendenti in `proverbs.json`.
- [ ] Aggancio dei 10 record datati a `schedule.json` solo dopo promozione.
- [ ] Regole runtime per rotazioni mensili, stagionali, lunari e segni meteo.
- [ ] Trattamento separato delle code `Contesto o sospensione` e `Scopri/archivio`.

## 93. Promozione controllata proverbi datati 2026-07-04

Implementato/verificato:

- [x] Promossi in `proverbs.json` solo i 10 candidati `almanac_dated`.
- [x] Ogni record promosso mantiene `normalizationStatus: lab_ready`.
- [x] Ogni record promosso mantiene `humanReviewRequired: true`.
- [x] Ogni record promosso ha fonte Ostermann 1894 e `sourceDetail` tracciato.
- [x] Aggiornato `schedule.json` solo per le 10 date fisse.
- [x] Nessun candidato mensile, stagionale, lunare o segno meteo e stato agganciato allo schedule.
- [x] Aggiunto test di selezione reale con `pickDailyProverb`.
- [x] Aggiornati i guardrail su copertura, archivio e piano promozione.

Risultati:

- [x] `proverbs.json`: 52 -> 62 record.
- [x] `homeEligible`: 43 -> 53 record.
- [x] `lab_ready`: 13 -> 23 record.
- [x] `humanReviewRequired`: 13 -> 23 record.
- [x] Date fisse in `schedule.json`: 6 -> 16.

Decisione:

- [x] La promozione e controllata e limitata alle date fisse.
- [x] I record restano in stato laboratorio, non approvati definitivamente.
- [x] La review linguistica finale resta necessaria prima di considerarli copy definitivo.

Restano fuori:

- [ ] Promozione dei 13 record non datati pendenti.
- [ ] Regole runtime per rotazioni mensili, stagionali, lunari e segni meteo.
- [ ] Trattamento separato delle code `Contesto o sospensione` e `Scopri/archivio`.

## 94. Promozione controllata proverbi non datati 2026-07-04

Implementato/verificato:

- [x] Promossi in `proverbs.json` i 13 candidati non datati gia revisionati.
- [x] Nessun record non datato e stato aggiunto a `schedule.json`.
- [x] Ogni record promosso mantiene `normalizationStatus: lab_ready`.
- [x] Ogni record promosso mantiene `humanReviewRequired: true`.
- [x] Ogni record promosso ha fonte Ostermann 1894 e `sourceDetail` tracciato.
- [x] Aggiunti metadati editoriali `almanacTargetUse`, `months`, `seasons`, `weatherTags` o `lunarRule` dove servono.
- [x] Aggiunte regole runtime per rotazioni mensili, stagionali, segni meteo e ciclo lunare.
- [x] Aggiunti test di selezione reale con `pickDailyProverb`.
- [x] Aggiornati i guardrail su copertura, archivio e piano promozione.
- [x] Audit visivo 2026-07-04: `ostermann-126-tone-ploe-tempieste` riclassificato da stagionale a segno meteo temporalesco.
- [x] Audit visivo 2026-07-04: esclusi i proverbi mensili/stagionali/meteorologici dal fallback generico.

Risultati:

- [x] `proverbs.json`: 62 -> 75 record.
- [x] `homeEligible`: 53 -> 66 record.
- [x] `lab_ready`: 23 -> 36 record.
- [x] `humanReviewRequired`: 23 -> 36 record.
- [x] Candidati promuovibili pendenti: 13 -> 0.
- [x] Date fisse in `schedule.json`: restano 16.

Decisione:

- [x] I proverbi mensili compaiono solo nei mesi dichiarati.
- [x] I proverbi stagionali compaiono solo nelle stagioni dichiarate.
- [x] I segni meteo compaiono solo se il meteo corrente fornisce un tag coerente.
- [x] Il proverbio lunare richiede martedi entro i primi 7 giorni della lunazione e tag pioggia.
- [x] I record restano materiale laboratorio: pubblicati tecnicamente, ma non approvati come copy definitivo.

Restano fuori:

- [ ] Revisione linguistica finale dei 36 record `lab_ready`.
- [ ] Trattamento separato delle code `Contesto o sospensione` e `Scopri/archivio`.

## 95. Matrice repertorio proverbi 2026-07-04

Implementato/verificato:

- [x] Creato `frontend/src/domain/almanac/proverbRepertoireMatrix.js`.
- [x] Creato `frontend/src/domain/almanac/proverbRepertoireMatrix.test.js`.
- [x] Separati conteggi pubblicati, candidati, date fisse, date note, sorgenti e gap.
- [x] Aggiornati `PROVERB_DAILY_REPERTOIRE_AUDIT.md` e `ALMANAC_365_COVERAGE_AUDIT.md` con fotografia 2026-07-04.

Risultati:

- [x] Proverbi pubblicati: 75.
- [x] Proverbi `homeEligible`: 66.
- [x] Candidati grezzi: 111.
- [x] Repertorio di lavoro totale: 186.
- [x] Date fisse in `schedule.json`: 16.
- [x] Date note contando anche candidati: 34.
- [x] Gap verso 366 date note: 332.
- [x] Gap verso archivio 500 contando anche candidati: 314.

Decisione:

- [x] Non basta promuovere i candidati esistenti: serve continuare estrazione/revisione fonte o accettare una rotazione non giornaliera.
- [x] I candidati restano fuori dalla UI finche non sono verificati, normalizzati e classificati.

Restano fuori:

- [ ] Nuovo giro fonte Ostermann oltre le 28 pagine gia estratte.
- [ ] Scelta editoriale fra calendario 365 rigido e rotazione giornaliera da repertorio ampio.
- [ ] Estensione futura verso 366 slot unici, senza usare fonti non controllate.

## 96. Nuovo giro fonte Ostermann proverbi 2026-07-04

Implementato/verificato:

- [x] Ispezionato il report `normalized-theme-index` sulle pagine Ostermann normalizzate.
- [x] Confermate 751 pagine normalizzate disponibili localmente.
- [x] Confermato che il primo piano fonte usava 28 pagine.
- [x] Aggiunte 12 nuove pagine `to_extract` in `frontend/src/data/almanac/ostermannProverbSources.json`.
- [x] Le nuove pagine sono ordinate per `pdfPage`.
- [x] Aggiornati i test della matrice repertorio e del daily repertoire audit.
- [x] Aggiornati `PROVERB_DAILY_REPERTOIRE_AUDIT.md` e `ALMANAC_365_COVERAGE_AUDIT.md`.

Pagine aggiunte:

- [x] P1: 29, 31, 43, 58, 68, 100, 146.
- [x] P2: 44, 46, 83, 87, 111.

Decisione:

- [x] Le nuove pagine sono coda fonte, non nuovi proverbi.
- [x] Nessun record nuovo entra in `proverbCandidates.json`.
- [x] Nessun record nuovo entra in `proverbs.json`.
- [x] Nessun record nuovo diventa `homeEligible`.
- [x] Le pagine narrative o delicate vanno valutate anche per Scopri, non forzate nell'Almanacco.

Restano fuori:

- [x] Avviata l'estrazione dei proverbi candidati dalle 12 pagine, con primo batch tracciato nella sezione 97.
- [x] Separare testi brevi per Almanacco e testi lunghi/esplicativi per Scopri, senza buttare materiale utile.
- [ ] Normalizzare FUR e scrivere IT solo dopo verifica pagina fonte.
- [x] Chiudere le 3 pagine residue senza forzare candidati proverbio, come tracciato nella sezione 99.

## 97. Prima estrazione nuovo giro Ostermann proverbi 2026-07-04

Implementato/verificato:

- [x] Rilette le pagine Ostermann 29, 31, 58 e 146 in versione clean/normalizzata.
- [x] Aggiunti 4 candidati a `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 29, 31, 58 e 146 come `candidate_extracted`.
- [x] Aggiornata la coda fonte: 32 pagine estratte su 40, 8 pagine ancora `to_extract`.
- [x] Aggiornati test repertorio, audit giornaliero e readiness archivio.
- [x] Aggiornati `PROVERB_DAILY_REPERTOIRE_AUDIT.md` e `ALMANAC_365_COVERAGE_AUDIT.md`.

Candidati aggiunti:

- [x] `ostermann-029-canicule-bagnat-sut` - Canicola e andamento stagionale.
- [x] `ostermann-031-macis-zenar` - stelle di gennaio / Macis.
- [x] `ostermann-058-san-pauli-scur` - San Paolo, 10 gennaio.
- [x] `ostermann-146-cercli-lune-ploe` - aloni lunari e pioggia.

Decisione:

- [x] Nessun nuovo record entra in `proverbs.json`.
- [x] Nessun nuovo record diventa `homeEligible`.
- [x] I testi lunghi o esplicativi restano materiale da trattare in Scopri come spiegazione editoriale, non come proverbio grezzo in Almanacco.
- [x] Le varianti contraddittorie, oscure o troppo rovinate non sono state importate.

Restano fuori:

- [x] Estrarre o chiudere le 8 pagine residue: 43, 44, 46, 68, 83, 87, 100, 111.
- [ ] Review FUR/IT dei 4 nuovi candidati prima di qualsiasi promozione.
- [ ] Eventuale collegamento Scopri tra proverbi brevi e spiegazioni culturali lunghe.

## 98. Seconda estrazione nuovo giro Ostermann proverbi 2026-07-04

Implementato/verificato:

- [x] Verificato che molte pagine residue erano gia presenti come estratti Scopri, non come proverbi candidati.
- [x] Rilette le pagine 43, 68, 83, 87 e 100 in versione clean/normalizzata.
- [x] Aggiunti 7 candidati a `frontend/src/data/almanac/proverbCandidates.json`.
- [x] Marcate le pagine 43, 68, 83, 87 e 100 come `candidate_extracted`.
- [x] Lasciate `to_extract` le pagine 44, 46 e 111, perche' piu' adatte a Scopri/contesto o ancora delicate.

Candidati aggiunti:

- [x] `ostermann-043-lune-setembar-siet` - luna di settembre.
- [x] `ostermann-068-fum-traviers-bez` - fumo del Midili.
- [x] `ostermann-068-fum-riviel-biel` - fumo del Midili, seconda formula.
- [x] `ostermann-083-joibe-setemane` - detto del giovedi.
- [x] `ostermann-087-sante-luzie-nadal` - Santa Lucia/Natale.
- [x] `ostermann-087-nadal-une-volte` - Natale una volta all'anno.
- [x] `ostermann-100-nul-plovi` - nubi e pioggia.

Decisione:

- [x] Nessun nuovo record entra in `proverbs.json`.
- [x] Nessun nuovo record diventa `homeEligible`.
- [x] Le pagine gia presenti in Scopri vengono riusate come contesto, non duplicate come testi lunghi in Almanacco.
- [x] I candidati locali/rituali restano con note di cautela e review FUR/IT obbligatoria.

Stato dopo la tranche:

- [x] Candidati grezzi: 111.
- [x] Pagine fonte estratte: 37/40.
- [x] Pagine residue: 44, 46, 111.
- [x] Date note contando candidati: 34.
- [x] Gap archivio 500 contando candidati: 314.

Restano fuori:

- [x] Decidere se 44 e 46 restano solo Scopri/consigli della terra o se producono candidati brevi.
- [x] Trattare pagina 111 con cautela: pioggia/nozze/grandine, credenze delicate.
- [ ] Review FUR/IT dei nuovi 7 candidati prima di qualsiasi promozione.

## 99. Chiusura coda Ostermann Scopri/contesto 2026-07-04

Implementato/verificato:

- [x] Verificato che la pagina 44 era gia recuperata come `ost-extract-044-luna-lavori-campi`.
- [x] Verificato che la pagina 46 era gia recuperata come `ost-extract-046-luna-uccelli-bucato`, con record curato e FUR breve.
- [x] Verificato che la pagina 111 era gia recuperata come `ost-extract-111-uccelli-marini-pioggia`, con record curato e FUR approvato.
- [x] Marcate le pagine 44, 46 e 111 come `discover_backlog_extracted`, non come `candidate_extracted`.
- [x] Esteso l'audit dati per distinguere pagine candidate proverbio, pagine Scopri/contesto e pagine ancora aperte.

Decisione:

- [x] Nessun nuovo candidato proverbio viene creato da 44, 46 o 111.
- [x] Pagina 44 resta materiale Scopri/consigli della terra: FUR non pronto, testo agricolo-lunare pratico.
- [x] Pagina 46 resta archivio/Scopri: FUR breve gia recuperato, ma contenuto troppo narrativo/domestico per proverbio quotidiano.
- [x] Pagina 111 resta ponte Scopri/meteo popolare: FUR approvato nel record curato, ma materiale pioggia/nozze/grandine delicato.

Stato dopo la tranche:

- [x] Candidati grezzi: 111.
- [x] Pagine fonte candidate proverbio: 37.
- [x] Pagine fonte chiuse come Scopri/contesto: 3.
- [x] Pagine fonte ancora `to_extract`: 0.
- [x] Piano fonte Ostermann P1/P2: 40/40 chiuso.

## 100. Contratto Scopri - Memoria del giorno 2026-07-05

Implementato/verificato:

- [x] Creato archivio `frontend/src/data/discover/localMemory.json` per `Accadde oggi` / `Pillole di Friuli`.
- [x] Le bozze storiche sono marcate `source_needed` e `readyForUi: false`.
- [x] Creato dominio puro `frontend/src/domain/discover/localMemory.js`.
- [x] `Scopri` mostra la sezione `Memoria del giorno` solo con record `ready_for_discover` e fonte verificata/nota editoriale.
- [x] Almanacco resta pulito: nessuna pillola storica viene mostrata li' finche' `Scopri` non ha un archivio curato.

Restano fuori:

- [ ] Reperire e verificare fonti per le prime 50-100 pillole.
- [ ] Preparare copy IT/FUR definitivo per i record approvati.
- [ ] Decidere se mostrare un teaser Almanacco solo dopo almeno una prima tranche UI-ready.

## 101. Prima tranche fonti Memoria del giorno 2026-07-05

Implementato/verificato:

- [x] Esteso `frontend/src/data/discover/localMemory.json` con stati distinti `source_candidate` e `source_verified`.
- [x] Separati i temi con sola traccia utile dai temi con fonte controllata.
- [x] Promosse a `source_verified` solo fonti controllate su Aquileia: UNESCO, Museo Archeologico Nazionale e portale territoriale Aquileia.
- [x] Lasciati Gorizia/Transalpina, Pirona e Perdon di Barbana come `source_candidate`, quindi non pubblicabili.
- [x] Aggiornato il dominio `localMemory` con contatori audit per candidati e fonti verificate.
- [x] Nessun record entra in Scopri: tutti restano `readyForUi: false`.

Decisione:

- [x] `source_verified` non significa contenuto pronto: serve ancora copy IT/FUR approvata.
- [x] Wikipedia puo restare traccia di lavoro, ma non fonte finale per pubblicazione.
- [x] La prima tranche serve a costruire base e metodo, non a riempire la UI con contenuti incerti.

Restano fuori:

- [ ] Cercare fonti migliori per Gorizia/Transalpina, Pirona e Perdon di Barbana.
- [ ] Trasformare le fonti Aquileia in pillole brevi IT/FUR revisionate.
- [ ] Definire un obiettivo minimo di copertura: prime 50, poi 100, poi calendario piu ampio.

## 102. Prima copy draft Memoria del giorno - Aquileia 2026-07-05

Implementato/verificato:

- [x] Trasformate le 4 fonti Aquileia `source_verified` in copy brevi IT/FUR.
- [x] Marcate le copy IT come `copy_draft`.
- [x] Marcate le copy FUR come `copy_draft_pending_review`.
- [x] Aggiunti contatori audit `copyDraftItRecords` e `copyDraftFurRecords`.
- [x] Tutti i record restano `readyForUi: false`, quindi non compaiono in Scopri.

Decisione:

- [x] La fonte verificata non basta per pubblicare: serve revisione editoriale e linguistica.
- [x] Le copy sono brevi e adatte a Scopri, non schede enciclopediche.
- [x] La parte FUR resta proposta da controllare, non testo approvato.

Restano fuori:

- [ ] Revisione FUR vera delle 4 copy Aquileia.
- [ ] Decisione su quale record Aquileia promuovere per primo a `ready_for_discover`.
- [ ] Ricerca fonti migliori per i 3 record ancora `source_candidate`.

## 103. Revisione copy Aquileia IT/FUR 2026-07-05

Implementato/verificato:

- [x] Rilette le 4 copy Aquileia gia agganciate a fonti verificate.
- [x] Rifinite le frasi IT per tono breve da Scopri.
- [x] Marcate le copy IT come `approved`.
- [x] Ripulite le copy FUR in coerenza con lessico gia presente nel progetto.
- [x] Marcate le copy FUR come `human_review_needed`, non `approved`.
- [x] Aggiunti contatori audit `approvedItRecords` e `furHumanReviewNeededRecords`.
- [x] Nessun record diventa visibile: `readyForUi` resta `false`.

Decisione:

- [x] La revisione automatica/supportata non basta per approvare definitivamente il FUR.
- [x] Prima promozione UI solo dopo revisione umana o controllo linguistico dedicato.
- [x] IT puo essere usato come base approvata per la prima uscita Scopri, se il record viene promosso.

Restano fuori:

- [ ] Validazione FUR finale delle 4 copy Aquileia.
- [ ] Scelta del primo record Aquileia da rendere `ready_for_discover`.
- [ ] Eventuale controllo visivo in Scopri dopo promozione di un solo record.

## 104. Contratto FUR completo per Scopri 2026-07-05

Implementato/verificato:

- [x] Aggiunto guardrail `frontend/src/domain/discover/discoverFurReadiness.js`.
- [x] Misurata la copertura reale di Scopri: 59 record curati visibili in IT, 58 con FUR `approved`, 1 con FUR `short_ready`.
- [x] Identificato il blocco preciso: `ost-0013-luna-uccelli-bucato`, pagina Ostermann 46, testo FUR lungo ancora `pending_review`.
- [x] La vista Scopri in lingua FUR ora filtra i record non approvati in FUR invece di mostrare fallback IT.
- [x] La sezione `Memoria del giorno` segue la stessa regola: se un record futuro e' pronto in IT ma non in FUR, resta fuori dalla vista FUR.
- [x] Le 7 Memorie locali restano invisibili: 0 record `ready_for_discover`, 4 copy FUR `human_review_needed`.
- [x] Il backlog Ostermann resta fuori UI: 28 record, 28 con FUR `pending_review`, 0 record pronti UI.

Decisione:

- [x] Scopri FUR non deve contenere fallback IT involontari.
- [x] Un record con FUR `short_ready` non e' considerato approvato per la vista FUR completa.
- [x] I dati restano conservati: il record non approvato resta disponibile in IT e in archivio dati, ma non viene pubblicato in FUR.

Restano fuori:

- [x] Revisione FUR vera del record `ost-0013-luna-uccelli-bucato`.
- [ ] Validazione FUR finale delle 4 copy Aquileia prima di qualsiasi promozione in `Scopri`.
- [ ] Controllo visivo Scopri IT/FUR dopo eventuale promozione di nuovi record.

## 105. Chiusura FUR record Scopri pagina 46 2026-07-05

Implementato/verificato:

- [x] Riletta pagina Ostermann 46 in versione clean e normalizzata.
- [x] Confrontato il record con il lavoro precedente: era l'unico record curato Scopri ancora `short_ready`.
- [x] Approvata copy FUR lunga per `ost-0013-luna-uccelli-bucato`, senza tradurre letteralmente il passo storico.
- [x] Aggiornato `languageStatus.fur` da `short_ready` ad `approved`.
- [x] Allineato l'estratto `ost-extract-046-luna-uccelli-bucato`: `furReviewRequired: false`.
- [x] Il guardrail Scopri ora misura 59/59 record curati con FUR approvato.

Decisione:

- [x] Il testo resta scheda di contesto secondaria: utile per Scopri, non proverbio giornaliero.
- [x] La copy FUR e' editoriale Meteo Friul, derivata dalla fonte Ostermann ma non citazione storica letterale.
- [x] Le Memorie locali restano ancora escluse finche' non hanno FUR validato.

Restano fuori:

- [ ] Validazione FUR finale delle 4 copy Aquileia prima di qualsiasi promozione in `Scopri`.
- [ ] Controllo visivo Scopri IT/FUR dopo eventuale promozione di nuovi record.

## 106. Prima Memoria locale pubblicata in Scopri 2026-07-05

Implementato/verificato:

- [x] Validata la copy FUR delle 4 Memorie Aquileia gia agganciate a fonti verificate.
- [x] Aggiunto contatore audit `approvedFurRecords` per distinguere FUR approvato da FUR ancora in revisione.
- [x] Promossa solo `memory-source-aquileia-crocevia-popoli` a `ready_for_discover`.
- [x] Mantenuti nascosti gli altri 3 record Aquileia: fonte e FUR sono pronti, ma non sono ancora scelti per la UI.
- [x] Aggiornato il guardrail FUR di Scopri: 1 Memoria locale visibile, 1/1 con FUR approvato.

Decisione:

- [x] La prima uscita in Scopri deve essere una pillola rotante generale, non un blocco di 4 record pubblicati insieme.
- [x] Il record exact-date del 3 luglio resta nascosto finche' non decidiamo esplicitamente di usarlo in calendario.
- [x] Nessuna fonte candidata viene promossa senza fonte migliore.

Restano fuori:

- [ ] Controllo visivo Scopri IT/FUR della nuova Memoria locale.
- [ ] Scelta editoriale dei prossimi record Aquileia da pubblicare.
- [ ] Ricerca fonti migliori per Gorizia/Transalpina, Pirona e Perdon di Barbana.

## 107. Chiusura Memorie Aquileia e blocco candidate deboli 2026-07-05

Implementato/verificato:

- [x] Promosse in Scopri tutte le 4 Memorie Aquileia gia verificate e con FUR approvato.
- [x] Il record Basilica resta exact-date sul 3 luglio.
- [x] Gli altri 3 record Aquileia entrano nella rotazione Scopri.
- [x] Mantenute fuori le 3 candidate non solide: Gorizia/Transalpina, Pirona, Perdon di Barbana.
- [x] Aggiunta nota editoriale di blocco sulle 3 candidate, con fonte mancante esplicitata.
- [x] Aggiornati i guardrail: 4 Memorie locali visibili, 4/4 con FUR approvato.

Decisione:

- [x] Pubblicare subito tutto cio' che ha fonte verificata e FUR approvato.
- [x] Non pubblicare record candidati solo per accelerare: restano fuori finche' non hanno fonte migliore.
- [x] Le candidate non sono perse: sono backlog editoriale con motivo di blocco scritto nel dato.

Restano fuori:

- [ ] Recuperare fonte ferroviaria/locale solida per Gorizia/Transalpina.
- [ ] Recuperare fonte DBF/ARLeF/Societa Filologica o bibliografia controllata per Pirona.
- [ ] Recuperare fonte ufficiale locale, santuario o ICCD per Barbana.

## 108. Strategia Scopri giornaliera e copertura annuale 2026-07-05

Implementato/verificato:

- [x] Misurata la copertura reale di Scopri e Almanacco con `getDiscoverCoverageSummary`.
- [x] Scopri ora usa una logica giornaliera selettiva: un focus principale piu' una Memoria locale, un rito/credenza e una scheda Ostermann di contesto.
- [x] Le sezioni non pubblicano piu' blocchi da 4-6 card solo per riempire la pagina.
- [x] Le Memorie locali distinguono `exact_date` da `rotation`: le date esatte possono essere presentate come "Accadde oggi".
- [x] Copertura attuale Scopri: 59 record Ostermann curati, 4 Memorie locali pronte, 28 record Ostermann in backlog non UI-ready.
- [x] Copertura attuale proverbi: 96 pubblicati, 87 eleggibili per Almanacco/Home, 22 date fisse, default di rotazione presente.
- [x] Santo del giorno e consigli della terra hanno copertura base annuale; proverbi e Accadde oggi non sono ancora un calendario 365/366 completo.

Decisione:

- [x] Scopri deve essere una pagina del giorno, non un archivio lungo.
- [x] Massimo un contenuto per tipo al giorno, oltre al focus principale; niente riempitivi casuali.
- [x] Se una memoria ha data esatta verificata, puo' diventare "Accadde oggi"; altrimenti resta "Memoria del giorno".
- [x] Ostermann resta soprattutto tradizione/meteo popolare/FVG, senza forzare una localita' quando il contenuto non e' locale.
- [x] Per coprire davvero tutto l'anno servono promozione editoriale dei candidati, nuovi record locali verificati e review FUR/IT controllata.

Restano fuori:

- [ ] Costruire un calendario "Accadde oggi" con almeno 1 contenuto verificato per molte date, senza usare fonti deboli.
- [ ] Promuovere i candidati proverbiali uno per volta in `proverbs.json` e `schedule.json`.
- [ ] Definire ranking localita'/provincia per le Memorie locali quando il dataset contiene piu' aree.
- [ ] Verifica visiva Scopri IT/FUR dopo la riduzione a una card per tipo.

## 109. Correzione e promozione proverbio San Gregorio 2026-07-05

Implementato/verificato:

- [x] Riletto il candidato `ostermann-097-san-grivor-vint` contro pagina Ostermann 1894 p. 97.
- [x] Trovato e corretto errore di data: il candidato era stato indicato come `03-12`, ma la vecchia estrazione ordinata scioglie l'OCR sporco come `26/3`.
- [x] Aggiornati `proverbCandidates.json` e `proverbCandidateReview.json` a `03-26`.
- [x] Promosso il proverbio in `proverbs.json` come record `almanac_dated`, `homeEligible`, `lab_ready`, con `humanReviewRequired: true`.
- [x] Agganciato il proverbio al calendario del 26 marzo in `schedule.json`.

Decisione:

- [x] Non usare il 12 marzo: era un errore derivato dalla lettura precedente.
- [x] La data del 26 marzo viene dalla fonte Ostermann/estrazione ordinata, non dal santorale interno.
- [x] La grafia `San Grivor/Grivôr` resta tracciata come punto di review FUR, ma non blocca la pubblicazione controllata perche' la fonte e il significato sono chiari.

Restano fuori:

- [ ] Promuovere i 4 candidati rimasti nella review solo dopo controllo FUR/IT dedicato.
- [ ] Continuare l'estrazione di nuovi proverbi datati per aumentare la copertura annuale.

## 110. Promozione segni meteo Ostermann 2026-07-05

Implementato/verificato:

- [x] Riletti i 4 candidati rimasti nella matrice di promozione.
- [x] Promossi 3 segni meteo brevi e leggibili: rane/pioggia, arie rosse/pioggia-vento, gallo dopo mezzogiorno.
- [x] I tre record sono entrati in `proverbs.json` come `almanac_weather_sign`, `homeEligible`, `lab_ready`, con `humanReviewRequired: true`.
- [x] Nessuna nuova data fissa e' stata aggiunta: restano 22 slot calendario.
- [x] Il candidato lunare `ostermann-146-cercli-lune-ploe` e' stato lasciato fuori in questa tranche: la pagina fonte legge `plse` nella seconda riga e serviva review FUR prima di normalizzarlo a `ploe`.

Decisione:

- [x] I segni meteo brevi possono alimentare rotazioni Almanacco/Scopri senza fingere copertura giornaliera esatta.
- [x] Non promuovere il proverbio lunare in questa tranche finche' la grafia non e' risolta in modo pulito.
- [x] Il repertorio migliora, ma il calendario 365/366 resta incompleto.

Restano fuori:

- [x] Review FUR del proverbio lunare sugli aloni: `Cercli vizin...`, risolta nella sezione 111.
- [ ] Nuove estrazioni Ostermann mirate a proverbi con data o mese esplicito.

## 111. Risoluzione proverbio lunare sugli aloni 2026-07-05

Implementato/verificato:

- [x] Riletto `ostermann-146-cercli-lune-ploe` contro la pagina Ostermann normalizzata e la vecchia estrazione ordinata.
- [x] Confermato che la pagina OCR contiene `plse`, ma la vecchia estrazione ordinata scioglie la riga come `ploe vizine`.
- [x] Aggiornata la review: il proverbio non entra nel ciclo lunare automatico, ma nei segni meteo popolari.
- [x] Pubblicato in `proverbs.json` come `almanac_weather_sign`, `homeEligible`, `lab_ready`, con `humanReviewRequired: true`.
- [x] Nessuna nuova data fissa e' stata aggiunta: restano 22 slot calendario.

Decisione:

- [x] Usarlo come proverbio sugli aloni lunari e la pioggia, non come regola automatica basata sulla fase lunare.
- [x] Mantenere nel dato la traccia `fur_original` con `plse` e la fonte della normalizzazione a `ploe`.
- [x] La coda promozione precedente e' chiusa: il prossimo lavoro deve cercare nuovi proverbi con data o mese esplicito.

Restano fuori:

- [x] Ripartire dall'estrazione Ostermann cercando prioritariamente date, santi, mesi e segnali stagionali espliciti.

## 112. Estrazione Ostermann pagina 57 - giornate e santi 2026-07-05

Implementato/verificato:

- [x] Riletta pagina Ostermann 57 contro testo normalizzato e vecchia estrazione gia preparata in `ostermann/extracts.json`.
- [x] Aggiunta pagina 57 alla matrice fonte dei proverbi come `candidate_extracted`.
- [x] Estratti 5 nuovi candidati con data esplicita o range databile:
  - `ostermann-057-san-tomas-zornade-curte` - 21 dicembre.
  - `ostermann-057-san-tomas-nadal-di-gial` - 21/25 dicembre.
  - `ostermann-057-san-lucio-nadal-gial` - 24/25 dicembre.
  - `ostermann-057-nadal-pascute-orute` - Natale/Epifania.
  - `ostermann-057-san-luigi-zornade-lunge` - 21 giugno.
- [x] Tutti i record restano `source_checked`, `homeEligible: false`: estrazione controllata, non pubblicazione.
- [x] Aggiornati i test di repertorio: 116 candidati, 41 pagine fonte, 38 pagine candidate estratte, 32 date candidate.
- [x] Aggiunta review editoriale per tutti e 5 i candidati pagina 57:
  - 2 candidati datati promuovibili dopo review FUR finale e aggiornamento controllato dello schedule.
  - 3 varianti da scegliere, non da pubblicare insieme.
- [x] Routing automatico pulito: nessun candidato pagina 57 resta in coda non decisa.

Decisione:

- [x] Trattare questi record come coda editoriale di calendario/luce, non come contenuto gia pronto per la Home.
- [x] La review FUR resta necessaria: alcuni testi usano forme storiche o varianti da normalizzare con calma.
- [x] Non promuovere varianti troppo vicine sull'Epifania finche' non scegliamo una gerarchia editoriale.

Restano fuori:

- [x] Review editoriale FUR/IT dei 5 candidati pagina 57.
- [x] Review FUR finale operativa e pubblicazione controllata dei 2 candidati datati, risolta nella sezione 114.
- [x] Decidere se pubblicarli come proverbi giornalieri o come schede Scopri sul ciclo della luce: entrano come proverbi datati Almanacco con `humanReviewRequired: true`.
- [x] Continuare l'estrazione mirata su pagine 62-63 per San Macari, San Ruperto, San Zorz, San Zuan e Sant'Egidio.

## 113. Estrazione Ostermann pagina 62 - mesi e santi 2026-07-05

Implementato/verificato:

- [x] Riletta pagina Ostermann 62 contro testo normalizzato e pagina clean.
- [x] Verificato che pagina 63 era gia' estratta e revisionata: San Zuan, Sant'Egidio e ottobre/febbraio non sono stati duplicati.
- [x] Aggiunta pagina 62 alla matrice fonte dei proverbi come `candidate_extracted`.
- [x] Estratti 6 nuovi candidati con mese/data esplicita:
  - `ostermann-062-sis-dis-an-mesais` - ultimi 6 giorni dell'anno e primi 6.
  - `ostermann-062-zenar-ploe-avril` - gennaio/aprile.
  - `ostermann-062-san-macari-setembar` - 2 gennaio/settembre.
  - `ostermann-062-febrar-curt-amar` - febbraio.
  - `ostermann-062-febrar-senze-criure` - febbraio/marzo.
  - `ostermann-062-san-ruperto-lui` - 27 marzo/luglio.
- [x] Aggiunta review editoriale per tutti e 6:
  - 3 candidati mensili promuovibili dopo review FUR finale.
  - 2 candidati datati da spiegare prima in Scopri/nota.
  - 1 candidato in hold per interpretazione `nui` e incertezza della fonte.
- [x] Aggiornati i test di repertorio: 122 candidati, 42 pagine fonte, 39 pagine candidate estratte, 35 date candidate.
- [x] Routing automatico pulito: nessun candidato pagina 62 resta in coda non decisa.

Decisione:

- [x] I mensili brevi possono ampliare le rotazioni di Almanacco dopo review finale.
- [x] San Macari e San Ruperto non vanno pubblicati come proverbi giornalieri senza contesto.
- [x] Pagina 63 resta valida ma gia' lavorata: non fare doppioni.

Restano fuori:

- [x] Review FUR finale operativa dei 3 candidati mensili pagina 62, risolta nella sezione 114.
- [ ] Decidere se San Macari/San Ruperto sono contenuto Scopri o solo archivio.
- [ ] Continuare con prossime pagine non ancora censite nel piano fonte, evitando pagine gia' chiuse.

## 114. Promozione controllata candidati Ostermann luce e mesi 2026-07-05

Implementato/verificato:

- [x] Pubblicati in `proverbs.json` 5 record gia' revisionati, tutti `homeEligible`, `lab_ready`, `humanReviewRequired: true`:
  - `ostermann-057-san-tomas-zornade-curte` - proverbio datato 21 dicembre.
  - `ostermann-057-san-luigi-zornade-lunge` - proverbio datato 21 giugno.
  - `ostermann-062-zenar-ploe-avril` - rotazione mensile gennaio/aprile.
  - `ostermann-062-febrar-curt-amar` - rotazione mensile febbraio.
  - `ostermann-062-febrar-senze-criure` - rotazione mensile febbraio/marzo.
- [x] Aggiornato `schedule.dailyProverbs` con:
  - `06-21` -> `ostermann-057-san-luigi-zornade-lunge`.
  - `12-21` -> `ostermann-057-san-tomas-zornade-curte`.
- [x] Aggiunto test funzionale: 21 giugno e 21 dicembre selezionano i nuovi proverbi esatti.
- [x] Aggiunto test sul pool mensile: i tre nuovi mensili sono pubblicati come `almanac_monthly`.
- [x] Aggiornati i contatori: 101 proverbi pubblicati, 92 `homeEligible`, 24 date schedulate, 62 record `lab_ready` con review umana richiesta.
- [x] La coda promozione torna a zero: nessun candidato promuovibile rimane pendente.

Decisione:

- [x] Consolidare prima un pacchetto piccolo e verificato, invece di continuare solo a estrarre nuovi candidati.
- [x] I 5 record sono usabili in app, ma restano marcati come contenuti da review umana: non sono "definitivi editoriali".
- [x] San Macari e San Ruperto non entrano nello schedule in questa tranche.

Restano fuori:

- [ ] Decidere il destino editoriale di San Macari e San Ruperto: Scopri con nota, archivio, o futura scheda spiegata.
- [ ] Continuare estrazioni solo dopo aver scelto il prossimo gruppo fonte non gia' chiuso.

## 115. Promozione controllata proverbi datati San Zuan, San Gorgon e I Muarts 2026-07-05

Implementato/verificato:

- [x] Riletti contro pagina normalizzata i candidati gia' estratti:
  - pagina 63: `ostermann-063-san-zuan-timp`, data 24 giugno.
  - pagina 61: `ostermann-061-san-gorgon-ploe`, data 9 settembre.
  - pagina 103: `ostermann-103-muarz-novembre`, data 2 novembre.
- [x] Pubblicati in `proverbs.json` 3 record datati, tutti `homeEligible`, `lab_ready`, `humanReviewRequired: true`.
- [x] Aggiornato `schedule.dailyProverbs` con:
  - `06-24` -> `ostermann-063-san-zuan-timp`.
  - `09-09` -> `ostermann-061-san-gorgon-ploe`.
  - `11-02` -> `ostermann-103-muarz-novembre`.
- [x] Aggiornata `proverbCandidateReview.json`: i tre record passano a `promote_after_fur_review`, con fonte, data e copy FUR/IT consigliata.
- [x] Aggiunto test funzionale: 24 giugno, 9 settembre e 2 novembre selezionano i nuovi proverbi esatti.
- [x] Aggiornati i contatori: 104 proverbi pubblicati, 95 `homeEligible`, 27 date schedulate, 65 record `lab_ready` con review umana richiesta.

Decisione:

- [x] San Zuan entra come proverbio datato dell'Almanacco; il materiale narrativo/tradizionale su San Zuan resta in Scopri.
- [x] San Gorgon entra come proverbio meteo datato, ma resta marcato `humanReviewRequired` per la resa di `montanis/montanon`.
- [x] I Muarts entra come proverbio datato del 2 novembre, con resa italiana esplicativa per evitare oscurita' in UI.

Restano fuori:

- [ ] San Vizenz/San Lorenz resta sospeso: doppia data e possibile conflitto con lo slot San Lurinz gia' schedulato.
- [ ] San Macari e San Ruperto restano fuori: servono nota o contesto Scopri prima di usarli.

## 116. Analisi San Macari e San Ruperto da Ostermann pagina 62 2026-07-05

Implementato/verificato:

- [x] Riletta pagina Ostermann 62 contro testo normalizzato e pagina clean.
- [x] Verificato `ostermann-062-san-macari-setembar`:
  - fonte: `Tal il dì di San Macari (2 gennaio) - e tal il mês di setembar. (?)`.
  - aggancio: 2 gennaio come giorno osservato, settembre come mese pronosticato.
  - problema: Ostermann marca il detto con `(?)`, quindi la fonte stessa segnala incertezza.
- [x] Verificato `ostermann-062-san-ruperto-lui`:
  - fonte: `Se San Ruperto no l'ha nui (27 marzo) No ju varà nanche il mês di lui. (?)`.
  - aggancio: 27 marzo come giorno osservato, luglio come mese pronosticato.
  - problema: Ostermann marca il detto con `(?)`; inoltre `nui/nûi` va confermato linguisticamente prima della pubblicazione.

Decisione:

- [x] Nessuno dei due entra ora in `schedule.json`.
- [x] Nessuno dei due entra ora in `proverbs.json`.
- [x] Entrambi sono piu' adatti a una futura scheda Scopri con nota editoriale, non a un proverbio secco dell'Almanacco.

Restano fuori:

- [x] Rubrica Scopri decisa: `Si diceva che...`.
- [x] Scrivere copy IT/FUR breve per San Macari e San Ruperto dentro `Si diceva che...`, senza presentarli come previsione certa.

## 117. Rubrica Scopri - Si diceva che 2026-07-05

Implementato/verificato:

- [x] Creato archivio dedicato `frontend/src/data/discover/traditionalSayings.json`.
- [x] Pubblicati solo due record pronti per Scopri:
  - `saying-ostermann-san-macari-setembar`, da `ostermann-062-san-macari-setembar`.
  - `saying-ostermann-san-ruperto-lui`, da `ostermann-062-san-ruperto-lui`.
- [x] Aggiunto dominio puro `frontend/src/domain/discover/traditionalSayings.js`.
- [x] La rubrica mostra al massimo un detto al giorno: data esatta se presente, altrimenti rotazione.
- [x] Aggiunta sezione `Si diceva che...` / `Si diseve che...` in Scopri.
- [x] Aggiornati guardrail FUR e copertura Scopri.

Decisione:

- [x] I due record restano materiale Scopri/Ostermann, non proverbi dell'Almanacco.
- [x] La copy li presenta come voce di tradizione popolare, non come previsione certa.
- [x] Il titolo non usa formule di cautela burocratiche: `Si diceva che...` e' la rubrica approvata.

Restano fuori:

- [ ] Eventuale affinamento FUR umano della microcopy, se emergono correzioni linguistiche.
- [ ] Aggiungere nuovi record alla rubrica solo dopo la stessa regola: fonte verificata, copy IT/FUR approvata, niente schedule automatico.

## 118. Routing backlog Ostermann per Scopri 2026-07-06

Implementato/verificato:

- [x] Creato `frontend/src/domain/discover/ostermannDiscoverRouting.js`.
- [x] Creato `frontend/src/domain/discover/ostermannDiscoverRouting.test.js`.
- [x] Classificati i 28 record `ostermannDiscoverBacklog` senza pubblicarli in UI:
  - 4 candidati `Si diceva che...`.
  - 2 candidati `Memoria del giorno`.
  - 22 candidati archivio/contesto Scopri.
- [x] Nessun record backlog entra in `ostermannCulturalDiscover.json`.
- [x] Nessun record backlog entra in `localMemory.json`.
- [x] Nessun record backlog entra in `traditionalSayings.json`.

Decisione:

- [x] `Si diceva che...` accetta solo estratti brevi e isolabili, non pagine multi-detto.
- [x] `Memoria del giorno` accetta solo contenuti territoriali con data esplicita e fonte/copy da rifinire.
- [x] Archivio Scopri resta la destinazione dei temi ampi: lessico, raccolte di proverbi, calendario agricolo multi-data, meteo popolare complesso.

Prossimi candidati lavorabili:

- [x] `Si diceva che...`: neve/pane promosso nella sezione 119.
- [x] `Si diceva che...`: arcobaleno/annata, arcobaleno/tempo, Pasqua/fieno promossi nella sezione 120.
- [ ] `Memoria del giorno`: San Barnaba e viti, Sant'Ermacora e settimana delle disgrazie auditati nella sezione 121 ma non ancora pubblicabili.
- [ ] Archivio Scopri: scegliere una sola scheda alla volta, con copy IT/FUR breve e non citazione grezza.

## 119. Prima promozione backlog in Si diceva che 2026-07-06

Implementato/verificato:

- [x] Riletta pagina Ostermann 130 in versione clean e normalizzata.
- [x] Verificato il detto `Sot nêv pàn, sot ploe fan` dentro il contesto neve/pioggia/raccolti.
- [x] Aggiunto `saying-ostermann-neve-pane-pioggia` a `frontend/src/data/discover/traditionalSayings.json`.
- [x] Copy IT/FUR breve: tradizione dei campi, non regola meteo.
- [x] Routing backlog aggiornato: `ost-discover-130-neve-pane-pioggia-fame` risulta `published_in_scopri`.

Decisione:

- [x] Il detto entra in `Si diceva che...`, non in `proverbs.json` e non nello schedule Almanacco.
- [x] La fonte resta Ostermann 1894, pagina 130 / pagina testo 105.

Restano fuori:

- [ ] Verifica umana fine della resa FUR `Sot nêf/sot nêv` se vogliamo normalizzare ulteriormente la grafia.
- [x] Prossimi candidati `Si diceva che...`: arcobaleno/annata, arcobaleno/tempo, Pasqua/fieno, promossi nella sezione 120.

## 120. Chiusura candidati Si diceva che da backlog 2026-07-06

Implementato/verificato:

- [x] Rilette le pagine Ostermann 140, 141 e 193 in versione clean/normalizzata.
- [x] Aggiunto `saying-ostermann-arcobaleno-annata` da `ost-discover-140-arcobaleno-annata`.
- [x] Aggiunto `saying-ostermann-arcobaleno-tempo` da `ost-discover-141-arcobaleno-tempo`.
- [x] Aggiunto `saying-ostermann-pasqua-fieno` da `ost-discover-193-pasqua-fieno`.
- [x] Copy IT/FUR breve e senza formule di allarme/cautela dentro il testo visibile.
- [x] `Pasqua/fieno` mantiene `movableDates: ["easter"]` come dato editoriale e `dateAnchors: ["07-15"]` per Sant'Anacleto.
- [x] Aggiornati i guardrail: `Si diceva che...` passa da 3 a 6 record pronti, con 3 record a data esplicita.
- [x] Routing backlog aggiornato: i 4 candidati `traditional_saying_candidate` risultano tutti `published_in_scopri`.

Decisione:

- [x] I tre record entrano solo in Scopri, non in Almanacco e non nello schedule dei proverbi.
- [x] Per pagina 140 la copy non usa il riferimento al giallo/granoturco: il testo OCR disponibile si interrompe dopo `se il giallo,`.
- [x] Per pagina 141 la copy isola i versi brevi su arcobaleno del mattino/pioggia, senza portare in UI la pagina ampia.
- [x] Per pagina 193 la copy usa Pasqua/fieno come detto breve e conserva Sant'Anacleto come ancora datata.

Restano fuori:

- [ ] Eventuale revisione FUR fine su `forazs`, `bon marcjat` e sulle grafie storiche degli originali.
- [ ] Dopo questa chiusura, i prossimi lavori Scopri sono `Memoria del giorno` o archivio spiegato, non altri record `Si diceva che...` gia' in coda.

## 121. Audit Memoria del giorno da backlog Ostermann 2026-07-06

Implementato/verificato:

- [x] Rilette le pagine Ostermann 608 e 609 in versione clean/normalizzata.
- [x] Aggiunto `memory-ostermann-san-barnaba-viti` da `ost-discover-608-san-barnaba-viti`, ma non pubblicato.
- [x] Aggiunto `memory-ostermann-sant-ermacora-bufere` da `ost-discover-609-sant-ermacora-bufere`, ma non pubblicato.
- [x] Entrambi i record entrano in `frontend/src/data/discover/localMemory.json` come `source_verified`.
- [x] Entrambi restano `readyForUi: false`: fonte buona, copy non ancora abbastanza chiara per la lettura rapida.
- [x] Aggiornato `ostermannDiscoverRouting.js`: il routing considera pubblicati solo i `candidateId` di record davvero `ready_for_discover` e `readyForUi: true`.
- [x] Guardrail aggiornati:
  - `localMemoryReady`: resta 4.
  - `localMemoryExactDateDays`: resta 1.
  - `localMemory` ha 2 record `source_verified` non visibili.
  - `publishedInScopriRecords` nel backlog: resta 4.
  - `pendingCopyRecords` nel backlog: resta 24.

Decisione:

- [x] San Barnaba e Sant'Ermacora non entrano ora in `Memoria del giorno`: non sono abbastanza immediati/capibili per l'utente.
- [x] I due record restano materiale Scopri/Ostermann da riscrivere, non proverbi Almanacco, non notifiche meteo e non allerte.
- [x] Regola corretta: data esplicita + fonte verificata non bastano; serve anche una copy che si capisca senza contesto.

Restano fuori:

- [ ] Riscrivere San Barnaba e Sant'Ermacora come schede comprensibili, oppure spostarli in archivio spiegato.
- [ ] Eventuale revisione FUR fine di `vendeme`, `vîts`, `tampiestis/tampieris` solo dopo copy IT definitiva.
- [ ] Prossimo lavoro Scopri: archivio spiegato, scegliendo un solo tema alla volta.

## 122. Prima scheda Archivio Scopri da Ostermann 2026-07-06

Implementato/verificato:

- [x] Riletto il record culturale gia esistente `ost-0051-san-barnaba-vite`.
- [x] Evitato il duplicato con `memory-ostermann-san-barnaba-viti`, che resta non visibile in `Memoria del giorno`.
- [x] Spostato `ost-0051-san-barnaba-vite` in `section: archivio_tradizioni`.
- [x] Riscritta la copy come racconto breve: `Ostermann raccontava San Barnaba`.
- [x] La scheda resta visibile in Scopri IT/FUR, ma come archivio narrativo e non come card giornaliera esatta.
- [x] Aggiunto guardrail in `ostermannArchive.test.js` per bloccare ritorni a testo catalografico o sezione sbagliata.

Decisione:

- [x] Archivio Scopri puo usare contenuti Ostermann piu spiegati, con tono umano.
- [x] `Memoria del giorno` resta riservata a contenuti immediatamente capibili come "oggi successe..." o "oggi si faceva...".
- [x] San Barnaba e la vite non entra in `Memoria del giorno`: la fonte e valida, ma il contenuto richiede contesto.

Restano fuori:

- [x] Applicare lo stesso trattamento a Sant'Ermacora solo dopo una copy breve e comprensibile: completato nella sezione 123.
- [ ] Definire progressivamente altri temi archivio, uno alla volta, senza riempire Scopri con piu card dello stesso tipo nello stesso giorno.

## 123. Seconda scheda Archivio Scopri da Ostermann 2026-07-06

Implementato/verificato:

- [x] Riletto il record culturale gia esistente `ost-0052-sant-ermacora-grandini-bufere`.
- [x] Evitato il duplicato con `memory-ostermann-sant-ermacora-bufere`, che resta non visibile in `Memoria del giorno`.
- [x] Spostato `ost-0052-sant-ermacora-grandini-bufere` in `section: archivio_tradizioni`.
- [x] Riscritta la copy come racconto breve: `Sant'Ermacora e il cielo di luglio`.
- [x] Eliminato dal testo visibile il tono troppo cupo/rigido di `settimana delle disgrazie`.
- [x] Aggiunto `candidateId` ai record San Barnaba e Sant'Ermacora per chiudere il routing backlog come pubblicato in Scopri.
- [x] Aggiornato `ostermannDiscoverRouting.js`: ora considera anche i record culturali pronti di Scopri, non solo `Si diceva che...` e `Memoria del giorno`.
- [x] Guardrail aggiornati:
  - backlog Scopri pubblicato: 4 -> 6;
  - backlog pendente: 24 -> 22;
  - Almanacco culturale rapido: 48 -> 47 record;
  - giorni esatti nel pool culturale Almanacco: 8 -> 7.

Decisione:

- [x] Sant'Ermacora resta materiale storico-popolare per Archivio Scopri, non memoria del giorno e non avviso meteo.
- [x] Il testo deve raccontare il rapporto tra luglio, grandini e calendario dei santi, senza sembrare una previsione o un allarme.
- [x] I candidati `santi_e_territorio` possono essere risolti fuori da `Memoria del giorno` quando hanno bisogno di contesto.

Restano fuori:

- [ ] Continuare l'Archivio Scopri con un solo tema alla volta.
- [ ] Scegliere il prossimo candidato tra temi gia estratti ma non adatti a card giornaliera.

## 124. Terza scheda Archivio Scopri da Ostermann 2026-07-06

Implementato/verificato:

- [x] Scelto `ost-0021-segni-animali-vento` come terzo tema Archivio Scopri.
- [x] Motivazione: contenuto gia estratto e curato, ma senza data precisa e troppo ampio per una card giornaliera.
- [x] Spostato il record in `section: archivio_tradizioni`.
- [x] Riscritta la copy come racconto breve: `Animali, vento e cielo`.
- [x] Il testo chiarisce che non sono previsioni, ma osservazioni popolari del tempo.
- [x] Aggiornato il guardrail: Almanacco culturale rapido 47 -> 46 record; giorni esatti invariati a 7.

Decisione:

- [x] I contenuti generalisti di osservazione popolare possono vivere in Archivio Scopri.
- [x] Non vanno usati per riempire Almanacco quando non hanno un aggancio giornaliero chiaro.
- [x] La copy deve distinguere sempre tradizione/lettura popolare da previsione meteo.

Restano fuori:

- [ ] Scegliere il prossimo tema tra record gia curati ma troppo ampi per `Memoria del giorno` o Almanacco quotidiano.

## 125. Quarta scheda Archivio Scopri da Ostermann 2026-07-06

Implementato/verificato:

- [x] Scelto `ost-0024-monti-col-cappello` come quarto tema Archivio Scopri.
- [x] Motivazione: contenuto territoriale, gia curato, senza data precisa e piu adatto a racconto che ad Almanacco giornaliero.
- [x] Spostato il record in `section: archivio_tradizioni`.
- [x] Riscritta la copy come racconto breve: `Quando i monti mettono il cappello`.
- [x] Il testo chiarisce che non e una previsione, ma una lettura popolare del paesaggio.
- [x] Aggiornato il guardrail: Almanacco culturale rapido 46 -> 45 record; giorni esatti invariati a 7.

Decisione:

- [x] I segnali del paesaggio montano sono perfetti per Archivio Scopri quando non hanno una data.
- [x] Il tono deve restare narrativo e territoriale, non operativo tipo "preparati alla pioggia".
- [x] La scheda valorizza il Friuli montano senza trasformare Ostermann in fonte previsionale.

Restano fuori:

- [ ] Prossimo tema possibile: `Rane, vacche e pioggia`, se vogliamo continuare il filone animali/meteo popolare.

## 126. Regola data/fallback Scopri 2026-07-06

Decisione:

- [x] La data comanda solo le rubriche giornaliere: `Accadde oggi` / `Memoria del giorno` e `Si diceva che...`.
- [x] `Accadde oggi` si usa solo quando esiste una memoria con data esatta.
- [x] Se non esiste una memoria esatta, la card non deve fingere di essere "del giorno": viene mostrata come `Storie del territorio`.
- [x] `Si diceva che...` cerca prima un detto con data esatta; se manca, ruota solo tra detti senza data precisa.
- [x] I detti datati non devono uscire a caso fuori giorno.
- [x] `Archivio e tradizioni` e `Riti e credenze popolari` restano rotazioni editoriali, non contenuti "accadde oggi".

Implementato/verificato:

- [x] Aggiunta copy IT/FUR per il fallback `Storie del territorio` / `Storiis dal teritori`.
- [x] Aggiornato il view model Scopri per titolare correttamente la memoria non datata.
- [x] Aggiornata la rotazione dei detti per escludere contenuti con `dateAnchors` o `dateRanges` quando non corrispondono alla data.
- [x] Aggiunti test per memoria non datata e rotazione detti senza data.

Restano fuori:

- [ ] Costruire progressivamente un calendario `Accadde oggi` vero, con fonti solide, senza usare rotazioni generiche come ricorrenze.
- [ ] Aumentare i proverbi/detti con data esplicita, mantenendo separati i detti generici.

## 127. Obiettivo calendario Scopri 365/366 2026-07-06

Decisione:

- [x] `Memoria del giorno` deve puntare a una copertura completa: 1 memoria verificata per ogni giorno dell'anno.
- [x] `Si diceva che...` / proverbio del giorno deve puntare a una copertura completa: 1 detto/proverbio per ogni giorno dell'anno.
- [x] Riti, storie e archivio non vanno forzati a 365: si calendarizzano solo se hanno una data o un periodo reale.
- [x] Le schede senza data restano rotazione editoriale o archivio, non sostituti mascherati di `Accadde oggi`.

Fotografia attuale:

- [x] Memoria del giorno: 1 giorno coperto su 366; 365 mancanti.
- [x] `Si diceva che...`: 3 giorni coperti su 366; 363 mancanti.
- [x] Proverbi Almanacco schedulati: 27 giorni coperti su 366; 339 mancanti.
- [x] Proverbi pubblicati disponibili: 104, di cui 95 eleggibili per Home/Almanacco.

Implementato/verificato:

- [x] Esteso l'audit dati Scopri con liste giorni mancanti per memoria, detti e proverbi schedulati.
- [x] Aggiunti guardrail testati per non perdere di vista il divario reale rispetto al calendario completo.

Prossimo lavoro dati:

- [ ] Creare una tabella di lavorazione `MM-DD -> memoria/proverbio/fonte/stato`.
- [ ] Promuovere prima i contenuti gia verificati e databili.
- [ ] Estrarre nuovi proverbi Ostermann con data/mese esplicito.
- [ ] Reperire fonti storiche locali per `Accadde oggi`, evitando riempitivi generici.

## 128. Tabella lavoro calendario Scopri 2026-07-06

Implementato/verificato:

- [x] Creato `discoverDailyCalendarPlan`, generato da fonti reali e non scritto a mano.
- [x] La tabella produce 366 righe `MM-DD`.
- [x] Ogni riga contiene:
  - `memory`: memoria locale esatta o `missing_memory`;
  - `saying`: detto/proverbio Scopri esatto o `missing_saying`;
  - `proverb`: proverbio Almanacco schedulato, mancante o schedulato senza record.
- [x] Aggiunto summary operativo con:
  - giorni pronti/mancanti per memoria;
  - giorni pronti/mancanti per `Si diceva che...`;
  - giorni schedulati/mancanti per proverbi Almanacco;
  - vista gennaio come primo mese di lavoro.
- [x] Testato che `01-02` agganci San Macario nei detti.
- [x] Testato che `01-06` agganci il proverbio Epifania nello schedule Almanacco.

Fotografia attuale confermata:

- [x] Memoria: 1/366.
- [x] `Si diceva che...`: 3/366.
- [x] Proverbi Almanacco schedulati: 31/366.
- [x] Schedule proverbi senza record rotto: 0.

Prossimo passo:

- [ ] Usare gennaio come primo mese operativo: riempire prima i giorni con fonti gia presenti, poi cercare fonti mancanti.

## 129. Primo riempimento gennaio proverbi 2026-07-06

Decisione:

- [x] Gennaio si riempie prima con proverbi gia pubblicati e con fonte controllata.
- [x] Gli slot aggiunti non sono `Accadde oggi`: sono proverbi editorialmente collocati nel mese/stagione.
- [x] Per questa prima passata sono esclusi proverbi con sola `grafia normalizzata preliminare`.

Inseriti nello schedule:

- [x] `01-01` -> `ostermann-189-sut-zenar-granar`, gennaio/asciutto/granaio.
- [x] `01-02` -> `ostermann-062-zenar-ploe-avril`, gennaio/aprile/pioggia.
- [x] `01-03` -> `ostermann-130-sot-nev-pan`, neve/pane/pioggia.
- [x] `01-04` -> `ostermann-103-umiditat-glazze`, umidita/ghiaccio/freddo.

Effetto copertura:

- [x] Proverbi Almanacco schedulati: 27 -> 31.
- [x] Giorni mancanti: 339 -> 335.
- [x] Gennaio ora ha 7 slot coperti: 01, 02, 03, 04, 06, 10, 17.

Restano fuori:

- [ ] `01-05`, `01-07`, `01-08`, `01-09`, `01-11` e gli altri giorni di gennaio ancora scoperti.
- [ ] Memorie storiche di gennaio: da reperire con fonti vere.

## 130. Audit fonti prima del calendario Scopri 2026-07-06

Correzione di metodo:

- [x] Non ragionare come "copertura buchi" del calendario.
- [x] Prima si verifica il bacino fonti: memorie, detti, proverbi pubblicati, candidati Ostermann e review.
- [x] Solo dopo si assegna un contenuto a una data.
- [x] Le rotazioni editoriali non contano come `Accadde oggi`.
- [x] Nessuna data deve essere riempita senza fonte candidata o verificata.

Implementato/verificato:

- [x] Creato `frontend/src/domain/discover/discoverSourceAudit.js`.
- [x] Creato `frontend/src/domain/discover/discoverSourceAudit.test.js`.
- [x] L'audit traccia fonti pronte e candidate, non solo giorni mancanti.
- [x] Fotografia corrente fonti:
  - memorie locali: 9 record, 4 pronti, 1 con data esatta;
  - `Si diceva che...`: 6 record pronti, 3 con data esatta;
  - proverbi pubblicati: 104, di cui 95 home/almanacco eligible;
  - candidati Ostermann: 122 record, tutti con pagina fonte, 45 con date anchor;
  - review candidati Ostermann: 65 record in coda promozione, 21 con date anchor;
  - piano pagine Ostermann: 42/42 pagine chiuse come estratte o backlog Scopri.

Prossimo passo dati:

- [ ] Usare l'audit fonti per scegliere il prossimo batch: prima memorie con fonte debole da consolidare, poi candidati Ostermann gia datati.
- [ ] Non assegnare nuovi giorni solo per aumentare il numero di copertura.

## 131. Coda fonti Memoria del giorno 2026-07-06

Decisione:

- [x] `Memoria del giorno` non usa rotazioni generiche per fingersi `Accadde oggi`.
- [x] Una memoria con data esatta entra solo se ha fonte verificata, copy IT/FUR approvata e `readyForUi: true`.
- [x] Le memorie con fonte verificata ma copy/FUR non approvati restano coda di lavoro.
- [x] Le memorie con fonte `source_candidate` non contano come data coperta.

Fotografia prima della promozione:

- [x] Data esatta pubblicabile: `memory-draft-0703-aquileia-basilica`.
- [x] Rotazioni pronte ma non giornaliere: 3 record Aquileia senza data esatta.
- [x] Coda esatta con fonte verificata ma copy/FUR da chiudere:
  - `memory-ostermann-san-barnaba-viti` (`06-11`);
  - `memory-ostermann-sant-ermacora-bufere` (`07-12`).
- [x] Coda esatta con fonte ancora non abbastanza solida:
  - `memory-draft-0703-gorizia-ferrovie`.
- [x] Candidati senza data esatta e con fonte da consolidare:
  - `memory-draft-pirona-vocabolario`;
  - `memory-draft-grado-perdon-barbana`.

Implementato/verificato:

- [x] Esteso `getDiscoverSourceAudit` con `memoryTriage`.
- [x] Aggiunto test per distinguere date vere, rotazioni e fonti candidate.

Prossimo passo dati:

- [x] Lavorare prima `San Barnaba e la vite` e `Sant'Ermacora e le bufere`, perche hanno gia fonte verificata e data esatta.
- [ ] Cercare fonti migliori prima di usare Gorizia ferrovie, Pirona o Barbana.

## 132. Promozione Memorie Ostermann datate 2026-07-06

Decisione:

- [x] `San Barnaba e la vendemmia` entra come Memoria del giorno dell'11 giugno.
- [x] `Sant'Ermacora, la settimana inquieta` entra come Memoria del giorno del 12 luglio.
- [x] Entrambe restano `tradizioni`, non proverbi Almanacco.
- [x] Entrambe derivano da fonte Ostermann verificata su pagina clean.

Implementato/verificato:

- [x] `memory-ostermann-san-barnaba-viti` promosso a `ready_for_discover`.
- [x] `memory-ostermann-sant-ermacora-bufere` promosso a `ready_for_discover`.
- [x] Copy IT/FUR resa breve e leggibile per Scopri.
- [x] `readyForUi: true` e lingua IT/FUR `approved`.
- [x] Audit aggiornato: Memorie esatte pubblicabili 1 -> 3.
- [x] Gap Memoria del giorno: 365 -> 363.

Restano fuori:

- [ ] `memory-draft-0703-gorizia-ferrovie`: serve fonte migliore.
- [ ] `memory-draft-pirona-vocabolario`: serve fonte migliore e data.
- [ ] `memory-draft-grado-perdon-barbana`: serve fonte migliore e data.

## 133. Audit fonti Accadde oggi FVG scaricate 2026-07-06

Decisione:

- [x] I dati in `F:\proggetto Meteo Friul App\scarica dati fvg` sono utili come bacino grezzo, non come UI pronta.
- [x] `accadde_oggi_fvg.csv/json` coprono 366/366 giorni con 5039 record.
- [x] La fonte e Wikidata/SPARQL: buona per indice e coda editoriale, non sufficiente da sola per copy finale.
- [x] Ostermann resta fonte prioritaria per tradizioni, riti e cultura popolare.
- [x] Wikidata entra come supporto per cronaca storica, biografie, ricorrenze civili/culturali e ricerca per data/luogo.
- [x] `accadde_oggi_fvg_365giorni_esteso.csv/json` e la base migliore per il primo lavoro editoriale: 366 record, uno per giorno.
- [x] Il file esteso non e ancora pubblicabile: 250 nascite, 104 morti, 12 eventi; serve classificazione storico-culturale.

Implementato/verificato:

- [x] Creato `scripts/import-fvg-daily-history-source.mjs`.
- [x] Generato staging locale `backend_dryrun_staging/exports/discover_daily_history_wikidata_source.json`.
- [x] Generato staging locale `backend_dryrun_staging/exports/discover_daily_history_wikidata_extended_source.json`.
- [x] Lo staging resta `raw_wikidata_candidate`, `readyForUi: false`.
- [x] Creato `DISCOVER_DAILY_HISTORY_SOURCE_AUDIT.md`.

Regola:

- [x] Nessun record Wikidata entra direttamente in `localMemory.json`.
- [x] Prima serve scelta editoriale, fonte/controllo, copy IT, FUR e promozione controllata.
- [x] Il file grande da 5039 record resta bacino di recupero se il candidato del giorno esteso non convince.
- [ ] Classificare i 366 record estesi in A/B/C/D per importanza storico-culturale.
- [ ] Creare coda `dailyHistoryCandidates` separata.
- [ ] Selezionare 10 giorni pilota e verificare resa editoriale.

## 134. Coda editoriale Ostermann per Scopri 2026-07-06

Decisione:

- [x] Ostermann resta separato da `Accadde oggi`: i suoi testi alimentano tradizioni, proverbi, "Si diceva che..." e Archivio Scopri.
- [x] Nessun estratto granulare entra in UI solo perche' esiste in `extracts.json`.
- [x] Gli estratti gia collegati a `ostermannCulturalDiscover.json` non devono duplicare il FUR approvato.
- [x] I racconti folklorici delicati restano Archivio Scopri, non Home/Almanacco leggero.

Implementato/verificato:

- [x] Aggiunta coda testabile `getOstermannDiscoverQueue`.
- [x] Classificazione attuale dei 64 estratti:
  - 58 `already_curated_link`;
  - 0 `daily_or_saying_candidate`;
  - 1 `seasonal_context_candidate`;
  - 2 `discover_topic_candidate`;
  - 3 `archive_story_candidate`.
- [x] La coda usa anche `curatedLinks.json`: gli estratti gia' coperti da schede curate non rientrano piu' nei candidati da rilavorare.
- [x] Ogni elemento della coda conserva `sourcePage`, titolo, date, stato editoriale, stato FUR, prossima azione e, se presente, i record curati collegati.
- [x] Test aggiunto per bloccare cambi involontari nei bucket editoriali.
- [x] Verifica residui:
  - `ost-extract-057-giornate-santi` e' gia' parzialmente coperto da `proverbs.json` e `proverbCandidateReview.json`; restano varianti da scegliere, non un tema da riscrivere da zero.
  - `ost-extract-087-feste-ore-giorno` resta piu' adatto a Scopri/glossario che a proverbio giornaliero.

Prossimo passo dati:

- [x] Lavorare `ost-extract-057-giornate-santi` scegliendo una sola variante utile per gruppo:
  - pubblicato `ostermann-057-nadal-pascute-orute` come proverbio di Natale (`12-25`);
  - mantenuto `ostermann-057-san-tomas-zornade-curte` gia' presente su `12-21`;
  - mantenuto `ostermann-057-san-luigi-zornade-lunge` gia' presente su `06-21`;
  - spostato `ostermann-057-san-tomas-nadal-di-gial` a `archive_only/scopri`;
  - spostato `ostermann-057-san-lucio-nadal-gial` a `hold/scopri`;
  - evitata duplicazione tra Natale, Epifania, San Tomas e San Lucio.
- [x] Chiuso `ost-extract-057-giornate-santi` anche nella coda Ostermann tramite scheda Archivio Scopri `ost-0061-giornate-dei-santi`.
- [x] Chiuso `ost-extract-087-feste-ore-giorno` tramite scheda Archivio Scopri `ost-0060-ore-del-giorno`.
- [x] Copertura proverbi schedulati aggiornata: 31 -> 32 giorni.
- [x] Coda `daily_or_saying_candidate` azzerata: i residui non restano piu' sospesi.
- [ ] Usare i 58 `already_curated_link` come fonte controllata per Archivio Scopri, senza duplicare copy/FUR.
- [ ] Lasciare i 3 `archive_story_candidate` fuori dalle card giornaliere finche' non hanno cornice umana e prudente.

## 135. Audit master Accadde oggi FVG esteso 2026-07-06

File controllati:

- `F:\proggetto Meteo Friul App\scarica dati fvg\accadde_oggi_fvg_completo_esteso_metadata.csv`;
- `F:\proggetto Meteo Friul App\scarica dati fvg\accadde_oggi_fvg_completo_esteso_metadata.json`.

Esito:

- [x] Il master contiene 4081 record.
- [x] Le date coperte sono 366.
- [x] `wikidataId`, `wikipediaUrl`, `Descrizione_Base`, `Luogo`, `GiornoMese` presenti su tutti i record.
- [x] Nessun `wikidataId` duplicato.
- [x] Tutti i record hanno `sourceType = wikidata+wikipedia` e `sourceLanguage = it`.
- [x] Schema stabile: `GiornoMese`, `Anno`, `Luogo`, `Tipo`, `PunteggioSitelinks`, `Importanza`, `Descrizione_Base`, `wikidataId`, `wikipediaTitle`, `wikipediaUrl`, `retrievedAt`, `rawExtract`, `sourceLanguage`, `dayKey`, `sourceType`.

Problemi rilevati:

- [ ] Il campo `Importanza` ha mojibake sulle stelle (`â­` invece di stella corretta): prima di importare va normalizzato o sostituito con livello numerico.
- [ ] `rawExtract` manca in 956 record; non blocca il master, ma quei record non sono pronti per copy editoriale automatica.
- [ ] Distribuzione giorni sbilanciata: `01-01` ha 968 record, mentre `20-05` ne ha 1; serve ranking e scelta editoriale, non uso diretto.
- [ ] Alcuni `Luogo` sono entita' amministrative o oggetti non adatti come localita' utente (`provincia di Udine`, `ente di decentramento regionale`, stadi, musei, ecc.).
- [ ] Molti record sono nascite/morti a basso punteggio: vanno filtrati per rilevanza storico-culturale Meteo Friul.

Decisione:

- [x] Usare questo file come archivio sorgente completo, non come database pubblicabile.
- [x] Prossima fase: generare una coda Meteo Friul con scoring nostro, campi normalizzati, motivazione editoriale e stato review.
- [x] Preparato `scripts/score-fvg-daily-history-candidates.mjs` come strumento locale per ordinare i candidati storici; sintassi verificata con `node --check`.
- [x] Rigenerato `backend_dryrun_staging/exports/discover_daily_history_ranked_candidates.json`.
- [x] Ranking sorgente-first severo: 366 giorni coperti, ma solo 16 top-candidate in classe B/memoria; 235 in classe C/archivio; 115 in classe D/scarto o archivio profondo.
- [x] Lo scoring ora penalizza enti, aziende, denominazioni, sport e record "Evento" privi di vera semantica storica.
- [ ] Non importare in app finche' non esiste un sottoinsieme `reviewed/lab_ready`.

## 136. Coda pilota Accadde oggi / Memoria del giorno 2026-07-07

Decisione:

- [x] Creare una coda separata prima di toccare `localMemory.json`.
- [x] Non pubblicare i record Wikidata/Wikipedia direttamente in Scopri.
- [x] Tenere distinta la chiave sorgente `DD-MM` dalla chiave app `MM-DD`.
- [x] Ogni candidato resta `readyForUi: false` finche' non ha fonte migliore, copy IT, copy FUR e review.

Implementato:

- [x] Aggiunto `frontend/src/data/discover/dailyHistoryCandidates.json`.
- [x] Selezionati 10 giorni pilota dai 16 candidati classe B:
  - 1 aprile: Assedio di Aquileia del 238;
  - 3 novembre: Rivolta di Trieste del 1953;
  - 6 agosto: Sesta battaglia dell'Isonzo;
  - 9 ottobre: Disastro del Vajont;
  - 12 ottobre: Assedio di Trieste del 1813;
  - 15 aprile: Battaglia di Sacile;
  - 29 ottobre: Battaglia di Pozzuolo del Friuli;
  - 15 maggio: Battaglia di Tarvisio del 1809;
  - 16 marzo: Battaglia di Valvasone;
  - 26 aprile: Assedio di Osoppo.
- [x] Aggiunto dominio puro `frontend/src/domain/discover/dailyHistoryCandidates.js`.
- [x] Aggiunti test `frontend/src/domain/discover/dailyHistoryCandidates.test.js`.

Controlli:

- [x] La coda contiene 10 record.
- [x] Nessun record e' pubblicabile: `publishableRecords = 0`.
- [x] Nessun duplicato su `dateAnchor`.
- [x] Conversione data validata: esempio `03-11` sorgente diventa `11-03` app.
- [x] Tutti i record restano `wikidata_candidate`, quindi richiedono fonte migliore prima della copy.

Prossimo passo:

- [x] Scegliere i primi 2-3 candidati pilota e avviare verifica fonti non solo Wikidata:
  - Rivolta di Trieste 1953;
  - Disastro del Vajont 1963;
  - Assedio di Osoppo 1848.
- [x] Nessuno dei 3 e' stato promosso: le fonti trovate bastano come controllo iniziale, non come fonte finale pubblicabile.
- [x] Stato registrato in `dailyHistoryCandidates.json` come `sourceReview.status = needs_better_source`.
- [x] Per Vajont verificato anche il master locale `accadde_oggi_fvg_completo_esteso_metadata.json`: record presente, raw extract presente, ma non sufficiente come fonte finale.
- [x] Aggiunte piste bibliografiche Vajont candidate, senza promozione.
- [x] Trovata fonte culturale ufficiale comunale per Vajont:
  - Visit Longarone, `Percorsi della memoria`;
  - Visit Longarone, `Storia, tradizioni e musei`.
- [x] Stato Vajont aggiornato a `source_verified_for_copy`.
- [x] Aggiunta prima bozza IT sobria, senza pubblicazione e con FUR ancora `pending_review`.
- [x] Definita regola multi-voce per il 9 ottobre: Vajont primaria, altre voci solo come secondarie brevi se davvero rilevanti.
- [x] Candidate secondarie annotate per il 9 ottobre:
  - Francesco Bearzatti, come possibile nota culturale secondaria;
  - Giancarlo Rittmeyer, solo come contesto collegato al Vajont, non come card autonoma.
- [x] Scartate per ora le voci deboli del 9 ottobre: Elvio Ruffino e Rinaldo Fabris.
- [x] Definita selezione localizzata delle secondarie:
  - la memoria principale resta uguale per tutti;
  - le secondarie privilegiano citta' attiva, poi provincia/area;
  - se non ci sono secondarie locali rilevanti, non si mostra riempitivo.
- [x] Test esempio: con `Pordenone/PN` emergono Bearzatti e Rittmeyer; con `Gorizia/GO` non emerge nulla per il 9 ottobre.
- [ ] Scrivere copy IT breve, copy FUR e stato review solo dopo fonte confermata.
- [ ] Promuovere in `localMemory.json` solo i record davvero pronti.

## 137. Batch review candidati forti Accadde oggi 2026-07-07

Decisione:

- [x] Accelerare il lavoro passando da review singola a matrice batch.
- [x] Separare la matrice batch dalla coda pilota e dalla UI.
- [x] Non promuovere automaticamente nessun record da questa matrice.

Implementato:

- [x] Creato `frontend/src/data/discover/dailyHistoryBatchReview.json`.
- [x] Creato dominio puro `frontend/src/domain/discover/dailyHistoryBatchReview.js`.
- [x] Creati test `frontend/src/domain/discover/dailyHistoryBatchReview.test.js`.

Esito batch:

- [x] 16 candidati forti tracciati.
- [x] 11 candidati principali azionabili.
- [x] 1 candidato gia' `ready_for_copy`: Vajont.
- [x] 0 candidati principali ancora con `source_review_needed`.
- [x] 10 candidati principali avanzati a `source_lead_found`:
  - Battaglia di Sacile;
  - Battaglia di Valvasone;
  - Assedio di Osoppo;
  - Battaglia di Pozzuolo del Friuli;
  - Assedio di Aquileia del 238;
  - Rivolta di Trieste del 1953;
  - Sesta battaglia dell'Isonzo;
  - Assedio di Trieste del 1813;
  - Battaglia di Tarvisio del 1809;
  - Battaglia di Opicina.
- [x] 2 duplicati/temi sospesi:
  - Tarvisio 1797 vs Tarvisio 1809;
  - Aquileia 238 vs Aquileia 388.
- [x] 2 candidati secondari/locali:
  - Daniele Dolfin;
  - Giovanni di Moravia.
- [x] 1 candidato archivio/contesto:
  - Patriarcato di Grado.
- [x] Distribuzione province tracciata per futura localizzazione secondarie:
  - GO: 2;
  - PN: 3;
  - TS: 3;
  - UD: 8.

Prossimo passo:

- [x] Lavorare in batch i 6 `source_review_needed`, cercando fonti migliori a gruppi per provincia/tema.
- [ ] Verificare e trasformare i 10 `source_lead_found` in `source_verified_for_copy` solo quando la fonte e' abbastanza solida.
- [ ] Fare FUR/review del Vajont come primo record `ready_for_copy`.

## 138. Allineamento coda operativa Accadde oggi 2026-07-07

Decisione:

- [x] Non lasciare la matrice batch e la coda pilota in stati divergenti.
- [x] Usare il master locale `accadde_oggi_fvg_completo_esteso_metadata.json` solo come indice/evidenza di lavoro, non come fonte finale pubblicabile.
- [x] Non promuovere nessun nuovo record in UI.

Implementato:

- [x] Aggiornati i 9 candidati pilota non-Vajont con `reviewStatus: source_lead_found`.
- [x] Aggiunti `sourceReview.checkedSources` dalla matrice batch.
- [x] Aggiunta `sourceReview.localMasterEvidence` dove il master locale contiene il record Wikidata corrispondente.
- [x] Lasciato Vajont come unico `source_verified_for_copy`.

Esito:

- [x] Coda pilota: 9 `source_lead_found` + 1 `source_verified_for_copy`.
- [x] `readyForUi` resta `false` per tutti i 10 record.
- [x] La pubblicazione resta bloccata finche' fonte, copy IT e copy FUR non sono approvate.

Prossimo passo:

- [ ] Scegliere pochi record `source_lead_found` alla volta e verificare davvero la fonte finale.
- [ ] Solo dopo scrivere copy breve IT/FUR.

## 139. Tentativo verifica fonte finale Accadde oggi 2026-07-07

Decisione:

- [x] Non promuovere un record solo perche' esiste una pista o una voce Wikipedia.
- [x] Registrare anche gli esiti negativi/temporanei, cosi' non si ripete lo stesso controllo senza memoria.

Verificati:

- [x] Pozzuolo del Friuli:
  - fonte ufficiale Esercito individuata come pista;
  - accesso non riuscito in verifica odierna (`502_bad_gateway_on_2026-07-07`);
  - resta `source_lead_found`, non `source_verified_for_copy`.
- [x] Sacile:
  - solo cross-check e bibliografia per ora;
  - resta `source_lead_found`.
- [x] Osoppo:
  - solo cross-check e bibliografia per ora;
  - resta `source_lead_found`.

Esito:

- [x] Aggiunto audit `sourceVerificationAttemptedRecords`.
- [x] 3 tentativi tracciati:
  - 1 `official_link_temporarily_unreachable`;
  - 2 `bibliography_only_for_now`.
- [x] Nessun nuovo record pubblicabile.

Prossimo passo:

- [ ] Riprovare Pozzuolo quando la fonte ufficiale Esercito e' raggiungibile.
- [ ] Cercare fonti locali/storiche consultabili per Sacile e Osoppo prima della copy.

## 140. Secondo tentativo verifica fonte finale Accadde oggi 2026-07-07

Decisione:

- [x] Trattare Gorizia/Isonzo, Trieste 1953 e Aquileia 238 come candidati forti ma non ancora pubblicabili.
- [x] Non usare Wikipedia come fonte finale per testi pubblicati.
- [x] Per temi bellici/sensibili, richiedere fonte storica o istituzionale piu' forte prima della copy.

Verificati:

- [x] Sesta battaglia dell'Isonzo:
  - fonte enciclopedica e bibliografia individuate;
  - manca fonte storica/museale stabile per copy;
  - resta `source_lead_found`.
- [x] Rivolta di Trieste del 1953:
  - tema forte ma contemporaneo e sensibile;
  - servono fonte archivistica/storica e tono sobrio;
  - resta `source_lead_found`.
- [x] Assedio di Aquileia del 238:
  - fonti primarie antiche individuate come pista;
  - non ancora controllate direttamente;
  - resta `source_lead_found`.

Esito:

- [x] Tentativi fonte finale tracciati: 6 totali.
- [x] Nessun nuovo `source_verified_for_copy`.
- [x] Nessun nuovo record pubblicabile.

Prossimo passo:

- [ ] Lavorare i 4 candidati rimasti senza tentativo finale: Trieste 1813, Tarvisio 1809, Valvasone 1797, Opicina 1945.
- [ ] In parallelo cercare fonti migliori per Gorizia/Isonzo, Trieste 1953 e Aquileia 238.

## 141. Retry fonti Accadde oggi gia' tentate 2026-07-07

Decisione:

- [x] Riprovare i record gia' tentati prima di passare oltre.
- [x] Registrare il retry senza promuovere se la fonte resta debole, irraggiungibile o solo enciclopedica.

Retry eseguito:

- [x] Pozzuolo del Friuli:
  - fonte ufficiale Esercito ancora non raggiungibile;
  - resta `source_lead_found`.
- [x] Sacile:
  - nessuna fonte locale/storica stabile trovata nel retry;
  - resta `source_lead_found`.
- [x] Osoppo:
  - contesto locale utile, ma pagina finale non abbastanza pulita;
  - resta `source_lead_found`.
- [x] Sesta battaglia dell'Isonzo:
  - nessuna fonte museale/storica stabile trovata nel retry;
  - resta `source_lead_found`.
- [x] Rivolta di Trieste del 1953:
  - ancora tema sensibile senza fonte archivistica/istituzionale sufficiente;
  - resta `source_lead_found`.
- [x] Assedio di Aquileia del 238:
  - pista primaria confermata, ma non controllata direttamente;
  - resta `source_lead_found`.

Esito:

- [x] 6 retry tracciati in `sourceReview.verificationRetry`.
- [x] Nessun nuovo `source_verified_for_copy`.
- [x] Nessun nuovo record pubblicabile.

Prossimo passo:

- [ ] Smettere di insistere su questi 6 senza nuove fonti esterne piu' solide.
- [ ] Passare ai 4 candidati rimasti senza tentativo finale.

## 142. Sblocco fonte Osoppo da PDF locale 2026-07-07

Decisione:

- [x] Usare `pagine_friulane_1901-1902_9-assedio Osoppo.pdf` come fonte storica locale per il contesto dell'assedio.
- [x] Usare Wikipedia solo come cross-check della data 26 aprile 1848, non come fonte finale della copy.
- [x] Promuovere Osoppo a verificato per preparare la copy, senza pubblicarlo ancora.

Fonte:

- [x] PDF letto con `pypdf`: 16 pagine, testo estraibile.
- [x] Titolo fonte: `Memorie storiche sull'assedio di Osoppo (24 Marzo-13 Ottobre 1848)`.
- [x] Evidenza interna: nel testo compare il 26 aprile come data in cui Licurgo Zannini assunse l'effettivo comando della fortezza.
- [x] Cross-check data: l'assedio viene ancorato al 26 aprile 1848 come avvio operativo.

Implementato:

- [x] `daily-history-candidate-0426-assedio-osoppo-1848` promosso a `source_verified_for_copy`.
- [x] `wikidata-fvg-26-04-Q3625507` promosso a `ready_for_copy` nella matrice batch.
- [x] Aggiunta bozza IT breve, con FUR ancora `pending_review`.
- [x] `readyForUi` resta `false`.

Esito:

- [x] Verificati per copy: Vajont + Osoppo.
- [x] Nessun nuovo record pubblicato in app.

Prossimo passo:

- [ ] Rifinire copy IT Osoppo e preparare FUR.
- [ ] Poi decidere se promuovere Osoppo in `localMemory.json`.

## 143. Policy editoriale Scopri / Accadde oggi 2026-07-07

Decisione:

- [x] Non fare ricerca storica infinita per ogni micro-rubrica.
- [x] Separare rubriche leggere da schede forti.
- [x] Mantenere fonte forte per temi sensibili: guerre, battaglie, assedi, disastri, tragedie, politica contemporanea.
- [x] Consentire rubriche leggere solo per contenuti a basso rischio, con copy prudente e review umana.
- [x] Non pubblicare automaticamente nessun record dalla coda.

Implementato:

- [x] Creato `discoverEditorialPolicy` come modulo puro.
- [x] Aggiunti test su:
  - rubrica leggera a basso rischio;
  - tema sensibile che richiede fonte forte;
  - record verificato che resta pronto per copy, non pubblicato;
  - coda pilota reale.
- [x] Integrato l'audit editoriale in `dailyHistoryCandidates`.
- [x] Aggiornata la policy della coda dati con la distinzione `lightRubric` / `strongSourceRequired`.

Esito:

- [x] Coda pilota: 8 record richiedono fonte forte.
- [x] Coda pilota: 2 record sono `strong_ready_for_copy` (Vajont, Osoppo).
- [x] Coda pilota: 0 record leggeri pubblicabili.
- [x] Nessun nuovo record entrato in UI.

Prossimo passo:

- [ ] Usare questa policy per importare/triagiare il master Accadde oggi senza bloccarci su ogni singola data.
- [ ] Continuare Ostermann con estrazione accurata, ma destinare i testi lunghi ad Archivio Scopri e non a card giornaliere rapide.

## 144. Triage master Accadde oggi FVG 2026-07-07

Decisione:

- [x] Usare il master da 4081 record come archivio sorgente completo.
- [x] Non importare automaticamente record in `localMemory.json`.
- [x] Non fare ricerca fonte infinita per ogni record del master.
- [x] Separare:
  - candidati leggeri da review;
  - candidati da fonte forte;
  - archivio Scopri;
  - scarto/archivio profondo.

Implementato:

- [x] Creato `scripts/triage-fvg-daily-history-master.mjs`.
- [x] Input predefinito: `F:\proggetto Meteo Friul App\scarica dati fvg\accadde_oggi_fvg_completo_esteso_metadata.json`.
- [x] Output dry-run ignorato da git: `backend_dryrun_staging/exports/discover_daily_history_master_triage.json`.
- [x] Lo script usa la policy editoriale Scopri e produce ranking per giorno.

Esito dry-run:

- [x] 4081 record analizzati.
- [x] 366 giorni coperti dal master.
- [x] 697 record in `review_for_light_daily`.
- [x] 39 record in `needs_strong_source`.
- [x] 1428 record in `archive_candidate`.
- [x] 1917 record in `discard_or_deep_archive`.
- [x] 256 giorni hanno almeno un candidato leggero da review.
- [x] 28 giorni hanno almeno un candidato da fonte forte.
- [x] 103 giorni non hanno ancora un candidato giornaliero decente: non coprirli a forza.

Prossimo passo:

- [ ] Estrarre dal dry-run un primo pacchetto piccolo di candidati `review_for_light_daily` da controllare manualmente.
- [ ] Tenere `needs_strong_source` per schede piu' delicate o archivio, non per riempire velocemente il calendario.

## 145. Primo pacchetto review Accadde oggi 2026-07-07

Decisione:

- [x] Preparare un pacchetto piccolo da review, non una pubblicazione.
- [x] Escludere temi pesanti o rumorosi: guerra, politica, tragedie, societa'/enti, calcio, militare.
- [x] Bilanciare per luogo e categoria.
- [x] Accettare meno di 30 record se i filtri severi lasciano candidati migliori.

Implementato:

- [x] Creato `scripts/build-fvg-daily-history-review-pack.mjs`.
- [x] Creato `frontend/src/data/discover/dailyHistoryReviewPack.json`.
- [x] Creato dominio puro `dailyHistoryReviewPack`.
- [x] Aggiunti test sulla coda review.

Esito:

- [x] 326 record disponibili dopo filtro severo.
- [x] 24 record selezionati.
- [x] 0 record pubblicati in UI.
- [x] 11 record in `copy_candidate`.
- [x] 11 record in `archive_after_review`.
- [x] 2 record in `hold_after_review`.
- [x] 24 record senza copy IT/FUR approvata.
- [x] Massimo 4 record per luogo.

Distribuzione:

- [x] `arte_cultura`: 12.
- [x] `luoghi_patrimonio`: 9.
- [x] `scienza_territorio`: 2.
- [x] `tradizione_costume`: 1.

Prossimo passo:

- [ ] Fare review umana dei 24 candidati: promuovere solo quelli che diventano leggibili e utili.
- [ ] Trasformare i promossi in copy IT/FUR brevi prima di portarli in `localMemory.json`.

## 146. Review preliminare pacchetto Accadde oggi 2026-07-07

Decisione:

- [x] Non trasformare automaticamente i 24 record in contenuti.
- [x] Promuovere a copy solo i record davvero leggibili come rubrica breve.
- [x] Spostare in archivio i record interessanti ma troppo istituzionali, dinastici o poco immediati.
- [x] Bloccare i record con incoerenza fonte o data troppo recente/futura.

Esito:

- [x] `copy_candidate`: 11.
- [x] `archive_after_review`: 11.
- [x] `hold_after_review`: 2.
- [x] `readyForUi`: 0.

Copy candidate:

- [x] Italo Svevo.
- [x] Alessandro Moissi.
- [x] Carlo Rubbia.
- [x] Giorgio Mainerio.
- [x] Gino von Finetti.
- [x] Remo Anzovino.
- [x] Antonio Zucchelli.
- [x] Max Fabiani.
- [x] Laura Sturma Fanelli.
- [x] Bernardo Maria De Rubeis.
- [x] Ludwig Boltzmann.

Hold:

- [x] Susanna Pasolini: anteprima fonte incoerente.
- [x] Evelyne Lenton: data 2026 troppo recente/futura nel corpus.

Prossimo passo:

- [ ] Scrivere copy IT breve per i primi 3-5 `copy_candidate`.
- [ ] Solo dopo preparare FUR e valutare ingresso in `localMemory.json`.

## 147. Prime bozze IT Accadde oggi 2026-07-07

Decisione:

- [x] Scrivere solo bozze IT, non copy approvata.
- [x] Non pubblicare nessun record in UI.
- [x] Lasciare `readyForUi: false`.
- [x] Tenere FUR a parte, dopo lettura e approvazione IT.

Bozze preparate:

- [x] Italo Svevo.
- [x] Alessandro Moissi.
- [x] Carlo Rubbia.
- [x] Giorgio Mainerio.
- [x] Gino de Finetti.

Esito:

- [x] 5 record con `copyDraft.it`.
- [x] 0 record con `copyDraft.fur`.
- [x] 0 record pubblicati.

Prossimo passo:

- [ ] Rivedere le 5 bozze IT a voce umana.
- [ ] Poi preparare FUR solo per quelle approvate.

## 148. Prime bozze FUR Accadde oggi 2026-07-07

Decisione:

- [x] Preparare FUR come bozza di review, non come traduzione approvata.
- [x] Non cambiare `languageStatus.fur`: resta non approvato.
- [x] Non pubblicare nessun record in UI.

Bozze FUR preparate:

- [x] Italo Svevo.
- [x] Alessandro Moissi.
- [x] Carlo Rubbia.
- [x] Giorgio Mainerio.
- [x] Gino de Finetti.

Esito:

- [x] 5 record con `copyDraft.it`.
- [x] 5 record con `copyDraft.fur`.
- [x] 0 record pubblicati.

Prossimo passo:

- [ ] Review umana IT/FUR delle 5 bozze.
- [ ] Solo dopo eventuale promozione in `localMemory.json`.

## 149. Import controllato Accadde oggi in localMemory 2026-07-07

Decisione:

- [x] Spostare le 5 coppie IT/FUR dal pacchetto review al registro `localMemory.json`.
- [x] Non pubblicarle in Scopri.
- [x] Usare `editorialStatus: source_verified`, non `ready_for_discover`.
- [x] Usare `languageStatus.it: copy_draft`.
- [x] Usare `languageStatus.fur: human_review_needed`.
- [x] Tenere `readyForUi: false`.

Record importati:

- [x] `memory-review-1219-italo-svevo`.
- [x] `memory-review-0402-alessandro-moissi`.
- [x] `memory-review-0331-carlo-rubbia`.
- [x] `memory-review-0504-giorgio-mainerio`.
- [x] `memory-review-0805-gino-de-finetti`.

Guardrail:

- [x] Record `localMemory`: 14.
- [x] Record visibili in Scopri: 6, invariati.
- [x] Record `source_verified`: 5.
- [x] Record con copy IT draft: 5.
- [x] Record FUR da review: 5.

Prossimo passo:

- [ ] Review finale IT/FUR delle 5 bozze.
- [ ] Promuovere in UI solo i record effettivamente approvati.

## 150. Estrazione ampia Accadde oggi 2026-07-07

Decisione:

- [x] Continuare l'estrazione prima della pubblicazione.
- [x] Creare un pacchetto ampio separato dal primo review pack.
- [x] Escludere i Wikidata ID gia' presenti in `localMemory.json` e `dailyHistoryReviewPack.json`.
- [x] Non pubblicare nessun record.
- [x] Non trasformare automaticamente i record in copy.

File:

- [x] `scripts/build-fvg-daily-history-expanded-review.mjs`.
- [x] `frontend/src/data/discover/dailyHistoryExpandedReview.json`.
- [x] `frontend/src/domain/discover/dailyHistoryExpandedReview.js`.
- [x] `frontend/src/domain/discover/dailyHistoryExpandedReview.test.js`.

Esito:

- [x] 1598 candidati disponibili dopo esclusione dei gia noti.
- [x] 80 record selezionati per review.
- [x] 68 record `light_daily_review`.
- [x] 12 record `archive_review`.
- [x] 0 record `readyForUi`.
- [x] 0 duplicati Wikidata.
- [x] 0 duplicati data nel pacchetto.

Prossimo passo:

- [ ] Fare review dei primi blocchi da 10-15 record, promuovendo solo quelli davvero leggibili.
- [ ] I temi sensibili restano fuori dalla rubrica leggera finche non hanno fonte forte.

## 151. Scrematura IT Scopri e rinvio FUR 2026-07-11

Decisione:

- [x] Usare `GG-MM` nei file di revisione editoriale italiani.
- [x] Confermare prima la selezione e il copy IT; avviare FUR soltanto dopo.
- [x] Escludere tutte le morti.
- [x] Escludere i profili con una sola qualifica generica (politico, imprenditore, insegnante/docente, giornalista) senza altro contributo rilevante.
- [x] Valutare invece l'eventuale contributo storico, scientifico o culturale dei profili con ruoli misti.
- [x] Non pubblicare nessun nuovo record in Scopri.

Esito master:

- [x] 4081 record sorgente analizzati.
- [x] 1043 morti escluse.
- [x] 3038 record non-morte sottoposti a scoring e deduplicazione.
- [x] 166 profili esclusivamente politici riconosciuti dal filtro.
- [x] 31 profili esclusivamente mediatici riconosciuti dal filtro.
- [x] 16 profili con sola professione generica riconosciuti dal filtro.
- [x] I ruoli misti sostanziali (storici, scientifici, culturali, artistici o territoriali) non vengono esclusi per la sola presenza di una qualifica generica.
- [x] 0 record grezzi ancora non classificati sopra la soglia della coda pulita.
- [x] 0 lavoro FUR avviato nella nuova coda IT.

Code editoriali:

- [x] Eventi storici: 3 candidati esatti, 1 approfondimento evergreen e casi incerti in hold/scarto.
- [x] Profili: 9 nuovi candidati IT per Memoria del giorno.
- [x] Profili: 3 nuovi candidati IT per Archivio Scopri.
- [x] 25 candidati IT gia classificati raccolti nel foglio mirato `backend_dryrun_staging/exports/scopri_selezione_it_da_confermare.xlsx`.
- [x] Nuovi candidati con `readyForUi: true`: 0.
- [x] Nuovi candidati con FUR iniziato: 0.
- [x] Corrette le note incoerenti del record Italo Svevo senza cambiare il contenuto visibile.

Guardrail:

- [x] Il generatore indicizza anche le code storiche e dei profili, evitando di riproporre record gia esaminati.
- [x] Il generatore blocca morti, duplicati noti e FUR anticipato nella coda pulita.
- [x] Data editoriale validata in formato italiano `GG-MM`.

Prossimo passo:

- [ ] Confermare o scartare i nuovi copy IT preparati.
- [ ] Verificare le fonti dei soli record IT confermati.
- [ ] Solo dopo preparare e revisionare FUR per il sottoinsieme destinato alla UI.

## 152. Composizione giornaliera deterministica Scopri 2026-07-11

Decisione:

- [x] Separare la copertura primaria esatta dalle memorie secondarie dello stesso giorno.
- [x] Applicare la precedenza temporale: data esatta, ricorrenza mobile, intervallo, stagione, evergreen.
- [x] Escludere `archive_context` dal focus principale.
- [x] Riprovare il candidato successivo quando un contenuto collide con una card gia selezionata.
- [x] Mostrare al massimo una memoria secondaria per giorno e localita.
- [x] Usare soltanto record con `readyForUi: true` nelle raccolte pubblicabili.
- [x] Non promuovere nuovi record e non iniziare nuovo lavoro FUR in questa tranche.

Copertura verificata:

- [x] 33 giorni con una Memoria primaria a data esatta.
- [x] 42 giorni con almeno una Memoria esatta contando anche le sole secondarie.
- [x] 11 Memorie secondarie pronte.
- [x] 333 giorni ancora privi di una Memoria primaria esatta.

Guardrail e test:

- [x] Matrice completa su 366 giorni, 4 province e 2 lingue: 2928 combinazioni.
- [x] Nessun `contentKey` duplicato nella stessa composizione.
- [x] Al massimo una card per sezione giornaliera.
- [x] Nessun record `archive_context` nel focus.
- [x] Nessuna card FUR pendente resa visibile.
- [x] Supportate Pasqua, Domenica delle Palme e finestre che attraversano fine anno.

Nota operativa:

- [x] Corretto `scripts/start-dev.ps1` per inizializzare in modo compatibile le variabili d'ambiente dei processi dopo il riavvio del PC.
- [x] Frontend e backend avviati e raggiungibili su `5173` e `8001`.
- [ ] Controllo DOM nel browser integrato bloccato dalla policy URL del runtime; non dichiarato come verifica visiva completata.

## 153. Prima ondata parallela Scopri 2026-07-11

Metodo:

- [x] Quattro audit indipendenti e in sola lettura: Accadde oggi, proverbi Ostermann, riti/archivio, territorio/fonti.
- [x] Nessun agente ha modificato file runtime o copy FUR.
- [x] Integrazione centralizzata soltanto dopo controllo incrociato.

Selezione IT esistente:

- [x] Corretto il generatore `scripts/export-discover-review-sheet.mjs`.
- [x] Un record `ready_for_ui` non viene piu degradato da una coda successiva.
- [x] `wikidataId` viene letto anche da `source.wikidataId`.
- [x] I record gia pubblicati non vengono riproposti nel foglio di selezione.
- [x] Achille Tellini rimosso dalla coda duplicata, senza rimuovere il contenuto runtime.
- [x] 24 righe da confermare: 12 `KEEP_DAILY`, 10 `KEEP_ARCHIVE`, 2 `HOLD`.
- [x] 0 province mancanti.
- [x] Aggiunti comune, localita, provincia, livello territoriale e metadati tecnici della fonte.
- [x] Normalizzati Maranzanis/Comeglians, Tercimonte/Savogna, Sant'Andrea/Gorizia e Doberdo del Lago.
- [x] FUR non avviato.

Nuova ondata di staging:

- [x] Salvato `frontend/src/data/discover/discoverParallelReviewWave.json`, non letto dalla UI.
- [x] 7 nuovi candidati storici/profili forti da revisionare.
- [x] 19 candidati storici in `HOLD` per data, fonte o perimetro editoriale.
- [x] 4 candidati storici scartati per date giornaliere non affidabili.
- [x] 5 nuclei Ostermann conservati come candidati contestuali.
- [x] 15 varianti Ostermann lasciate in `HOLD` per duplicazione, contraddizione o incertezza.
- [x] 2 approfondimenti Ostermann conservati per Archivio Scopri.
- [x] 1 credenza stagionale mantenuta in `HOLD`.

Guardrail:

- [x] Tutti i nuovi record hanno `readyForUi: false`.
- [x] Nessun campo FUR editoriale nella nuova ondata.
- [x] Date giornaliere espresse in formato italiano `GG-MM`.
- [x] ID univoci e provincia presente per tutti i candidati storici mantenuti.

## 154. Seconda ondata DAILY Scopri 2026-07-11

Metodo:

- [x] Verifica fonti/date, proposta copy IT e controllo duplicati/copertura eseguiti separatamente.
- [x] Consolidamento basato sull'intersezione dei controlli, non sulla somma dei risultati.
- [x] Scartata la parte di un audit copy che aveva interpretato il file di selezione sbagliato.

Esito:

- [x] Salvato `discoverDailyItalianReviewWave.json`, non letto dalla UI.
- [x] 12 candidati `KEEP DAILY` con fonte forte, data `GG-MM`, copy IT e territorio.
- [x] 3 profili spostati verso Archivio Scopri.
- [x] 3 candidati collegati a record canonici gia esistenti, senza duplicazione.
- [x] 1 candidato mantenuto in `HOLD` per contesto giuridico/editoriale.
- [x] Copertura primaria potenziale: 45/366; copertura runtime invariata: 33/366.

Correzioni sostanziali:

- [x] Doberdo non trattato come nuova battaglia autonoma del solo 6 agosto.
- [x] Iacopo Pirona collegato al record runtime esistente.
- [x] Cercivento rinominato come fucilazione, non decimazione.
- [x] Opicina: 71 ostaggi, non 72.
- [x] SIOT: deposito costiero/serbatoi, non condotta generica.
- [x] Trieste 1954 mantenuta in `HOLD` finche il copy non distingue amministrazione e sistemazione giuridica.

Guardrail:

- [x] Tutti i record hanno `readyForUi: false`.
- [x] Nessun FUR avviato.
- [x] Nessuna collisione con i 33 giorni primari gia pubblicati.

## 155. Promozione canonica IT Scopri 2026-07-12

Decisione:

- [x] Promuovere i 12 `KEEP DAILY` nel corpus canonico soltanto come staging invisibile.
- [x] Non rendere visibile nessun record prima della revisione FUR.
- [x] Non introdurre un nuovo stato editoriale: usare `source_verified` con IT approvato.

Implementazione:

- [x] Creato `scripts/promote-discover-daily-it-review.mjs`.
- [x] Aggiunti 12 record a `localMemory.json` con `candidateId` e `wikidataId` tracciabili.
- [x] Date convertite esplicitamente da `GG-MM` editoriale a `MM-GG` runtime.
- [x] Fonte forte, comune, provincia e copy IT conservati nel record canonico.
- [x] Script idempotente rispetto a `candidateId` e `wikidataId`.

Stato pubblicazione:

- [x] `editorialStatus: source_verified`.
- [x] `languageStatus.it: approved`.
- [x] `languageStatus.fur: human_review_needed`.
- [x] `readyForUi: false` per tutti i 12 record.
- [x] Copertura visibile invariata: 33/366.
- [x] I record IT canonici non restano nel foglio `da confermare`.

## 156. Revisione FUR seconda ondata DAILY Scopri 2026-07-12

Metodo:

- [x] I 12 record IT canonici sono stati divisi in tre lotti di revisione indipendenti.
- [x] Proposte confrontate con corpus FUR approvato, lessico locale e fonti istituzionali disponibili.
- [x] Integrazione finale eseguita centralmente, senza modifiche concorrenti ai file dati.

Esito:

- [x] 9 record con FUR approvato e promossi a `ready_for_discover`.
- [x] 3 record ancora invisibili in `pending_human_review`.
- [x] Via Ghega bloccata sulla resa precisa di `impiccati`.
- [x] Opicina bloccata sulla resa precisa di `ostaggi`.
- [x] SIOT bloccata sulla terminologia `serbatoi/deposito costiero`.
- [x] Creato `discoverDailyFurReviewWave.json` con note e blocchi espliciti.
- [x] Creato script idempotente `promote-discover-daily-fur-review.mjs`.

Stato runtime:

- [x] 9 nuove Memorie del giorno bilingui e visibili nelle rispettive date.
- [x] Copertura primaria visibile portata da 33/366 a 42/366 giorni.
- [x] Nessun fallback italiano esposto come se fosse FUR.

## 157. Chiusura terminologica FUR seconda ondata DAILY 2026-07-12

Verifica lessicale:

- [x] `picjâts` confermato dal SuperDizionari ARLeF nel significato specifico di `impiccati`.
- [x] `ostaçs` confermato dal SuperDizionari ARLeF come plurale di `ostaggio`.
- [x] `cistiernis` scelto per i serbatoi industriali destinati a liquidi.
- [x] `dipuesit costîr` composto con entrambe le forme attestate dal SuperDizionari ARLeF.
- [x] Le formulazioni sono state confrontate con il corpus FUR già approvato.

Promozione:

- [x] Via Ghega, Opicina e SIOT promossi da `pending_human_review` ad `approved`.
- [x] I tre record canonici sono ora `ready_for_discover`, bilingui e visibili solo nella data esatta.
- [x] Il file di revisione contiene 12 approvati e 0 pendenti.
- [x] Lo script di promozione ha modificato solo i tre segmenti canonici previsti.
- [x] Nessuna riformattazione globale di `localMemory.json`.

Copertura:

- [x] Memorie Scopri pronte: 59 record.
- [x] Giorni primari esatti visibili: 45/366.
- [x] Giorni ancora privi di Memoria primaria esatta: 321/366.

## 158. Catalogo profili comunali Scopri 2026-07-19

- [x] Il catalogo Scopri copre tutti i 215 comuni presenti nel registro FVG ISTAT.
- [x] Codice ISTAT, nome e provincia restano derivati da `fvgPlaces.js`, senza un secondo elenco duplicato.
- [x] Tutti i comuni restituiscono una card in IT e FUR.
- [x] Pordenone, Udine, Gorizia e Trieste mantengono i profili storici editoriali e le fonti comunali esistenti.
- [x] I 211 comuni inizialmente anagrafici sono stati arricchiti e promossi da `registry` a `editorial`.
- [x] Nessuna data di fondazione, tappa storica o fonte comunale è stata inventata per completare il catalogo.
- [x] La sorgente dei profili anagrafici è la classificazione ufficiale ISTAT aggiornata al 21/02/2026.
- [x] Il match preferisce il codice ISTAT al nome della città.
- [x] Il rendering usa lo stemma locale per tutti i 215 profili; il marker resta solo fallback tecnico per codici sconosciuti.
- [x] Test mirati su catalogo completo, doppia lingua, precedenza ISTAT, fonte vuota e rendering di un comune fuori dal pilota.
- [x] Arricchiti i 211 profili `registry` con storia locale verificata e promossi come profili editoriali.
- [x] Aggiunti e collegati 215/215 stemmi dopo associazione deterministica e verifica binaria.
- [ ] Aggiungere fotografie comunali solo dopo revisione degli asset.

## 159. Raccolta fonti profili comunali Scopri 2026-07-19

- [x] Creati cinque archivi candidati separati per GO/TS, PN e tre blocchi UD.
- [x] Copertura candidati esatta: 211/211 comuni non ancora editoriali.
- [x] Nessuna sovrapposizione con Pordenone, Udine, Gorizia e Trieste.
- [x] Codice ISTAT, nome e provincia verificati contro `fvgPlaces.js`.
- [x] Ogni candidato contiene titolo IT, sintesi IT in due frasi e fonte HTTPS classificata.
- [x] Nessun candidato e marcato `readyForUi` durante la raccolta.
- [x] Audit stretto senza record mancanti, inattesi o duplicati.
- [x] Controllo Unicode diretto: nessun carattere sostitutivo o mojibake nei JSON.
- [x] Script di promozione bloccante: richiede revisione editoriale e approvazione IT/FUR.
- [x] Revisione editoriale italiana dei 211 candidati.
- [x] Gate `--require-it-reviewed` superato con 211/211 profili e zero errori.
- [x] Controllo indipendente delle anomalie ad alta/media/bassa gravita e correzione dei record segnalati.
- [x] Ridotti i riferimenti Wikipedia da 55 a 35 sostituendoli, quando disponibile, con fonti istituzionali o culturali.
- [x] Traduzione e revisione FUR dei soli profili IT approvati: 211/211 con entrambe le lingue approvate.
- [x] Gate bilingue pre-promozione `--require-bilingual-reviewed` superato con zero errori.
- [x] Gate post-promozione `--require-bilingual-reviewed --allow-promoted` superato: 211/211 corrispondenze esatte e zero divergenze.
- [x] Audit differenziale rispetto al commit IT `a284d81`: nessuna modifica a identita, fatti, date, fonti o copy italiana.
- [x] Promozione bilingue completata: archivio runtime 215/215, senza duplicati e senza fallback anagrafici attivi.
- [x] Test mirati Scopri dopo l'ultimo riallineamento FUR: 16/16; suite frontend completa, lint e build verificati nella tranche finale.
- [x] Browser verificato su Pordenone, Cordenons e Sappada in IT/FUR, light/dark e mobile 390x844.
- [x] Nessun overflow mobile e nessun errore o warning console durante l'audit browser.

## 160. Stemmi comunali Scopri 2026-07-19

- [x] Catalogo sorgente completo: 215/215 codici ISTAT, zero duplicati e zero mancanti.
- [x] 65 associazioni da Wikidata P94 e 150 dal campo `Stemma` degli infobox comunali.
- [x] Corretto il collegamento Wikidata errato Cassacco/Raspano usando la pagina costruita dal nome del Comune come fonte primaria dell'infobox.
- [x] Asset scaricati localmente: 215/215; nessuna richiesta Wikimedia necessaria durante l'uso dell'app.
- [x] Formati binari accettati e verificati: PNG e JPEG.
- [x] Manifest frontend ridotto a codice ISTAT e URL locale; metadati sorgente esclusi dal bundle.
- [x] Test di corrispondenza completa tra profili comunali e manifest visuale.
- [x] Verifica conclusiva browser IT/FUR, light/dark e viewport mobile su Cormons, Cordenons, Cavazzo Carnico e Drenchia; nessun fallback, overflow o errore console.

## 161. Tappe storiche comunali Scopri 2026-07-19

- [x] Collegato il campo `milestones` gia presente nel contratto dei profili comunali.
- [x] Mostrate soltanto tappe con periodo e copy IT/FUR approvate.
- [x] Copertura verificata: 147/215 profili, 206 tappe complessive, massimo tre per Comune.
- [x] Nessun riempimento automatico per i 68 profili senza tappe verificate.
- [x] Timeline semantica con titolo, lista ordinata, periodo e descrizione; nessuna pill.
- [x] Il blocco non viene renderizzato quando `milestones` e vuoto.
- [x] Test mirati su Pordenone, Cordenons, Amaro e copy FUR.
- [x] Browser verificato su Pordenone, Aquileia e Amaro in IT/FUR, light/dark e mobile 390x844.
- [x] Nessun overflow mobile e nessun errore o warning console.

## 162. Pilot fotografie comunali Scopri 2026-07-19

- [x] Manifest fotografico separato dal catalogo degli stemmi.
- [x] Pilot limitato a Pordenone, Udine, Gorizia e Trieste.
- [x] Autore, licenza, pagina sorgente, asset originale e modifiche registrati nel catalogo interno.
- [x] Quattro WebP locali ottimizzati, 431328 byte complessivi; nessuna richiesta remota a runtime.
- [x] Fotografia decorativa con `alt` vuoto; nome e stemma restano l'identita accessibile della card.
- [x] Posizione focale configurabile per singolo Comune.
- [x] I 211 profili non inclusi nel pilot mantengono il fallback blu con stemma, senza spazio fotografico vuoto.
- [x] Validator dedicato per schema, codici ISTAT, duplicati, file locali e copertura.
- [x] Browser verificato sui quattro capoluoghi: caricamento riuscito, nessun overflow e nessuna sovrapposizione con le tappe storiche.
- [x] Verifica light/dark e mobile 390x844 senza errori o warning console.
- [x] Superficie compatta `Impostazioni > Informazioni e crediti`, alimentata dal catalogo canonico e senza appesantire le card comunali.

## 163. Numeri arabi nei periodi storici comunali 2026-07-19

- [x] Nessun numero romano viene mostrato in titolo, sintesi, tappe o periodi delle 215 card comunali.
- [x] Conversione applicata nel modello UI, senza riscrivere il catalogo storico revisionato.
- [x] Periodi di secolo compatti e bilingui: `18°-19° sec.` / `Secui 18-19`.
- [x] Guardrail automatico sull'intero catalogo IT/FUR.
- [x] Browser verificato su Trieste: `1382`, `1719`, `18°-19° sec.`, nessun overflow.

## 164. Chiusura editoriale Scopri e corpus Ostermann 2026-07-20

Scopri:

- [x] Archivio Memorie consolidato a 525 record complessivi, di cui 511 bilingui e pronti per la UI.
- [x] Chiuse le ultime due revisioni FUR rimaste: Francesco Carnelutti e Gianpaolo Tosel.
- [x] Copertura primaria exact-date verificata: 312/366 giorni.
- [x] Restano 54 giorni senza una Memoria primaria esatta e senza candidati attuali utilizzabili.
- [x] I giorni mancanti non vengono riempiti con contenuti deboli, date adattate o fonti non controllate.

Ostermann:

- [x] Tutte le 63 pagine prioritarie del catalogo sono state lavorate.
- [x] Archivio granulare chiuso a 64 estratti su 62 pagine sorgente.
- [x] 63 estratti hanno una destinazione editoriale curata e collegata.
- [x] L'ultimo estratto stagionale, da fonte solo parzialmente controllata, e stato chiuso esplicitamente come `do_not_publish`.
- [x] Nessun estratto resta nella coda editoriale irrisolta.
- [x] Archivio culturale Scopri consolidato a 63 record, tutti con FUR approvato.
- [x] Repertorio proverbi consolidato a 105 record, di cui 96 eleggibili per la rotazione dell'Almanacco.
- [x] Nuove estrazioni Ostermann non sono necessarie per chiudere la prima versione: eventuali aggiunte future partiranno da nuove fonti o da una nuova decisione editoriale esplicita.

## 165. Separazione contenuti Home, Almanacco e Scopri 2026-07-20

- [x] Il campo attivo `homeEligible` e stato rinominato `almanacEligible` nei dati, nel selettore e negli audit.
- [x] La Home continua a mostrare soltanto il teaser dell'Almanacco e scarta il testo completo del proverbio.
- [x] Il proverbio breve resta una responsabilita esclusiva dell'Almanacco.
- [x] Scopri conserva soltanto detti spiegati, memorie, riti e contenuti d'archivio contestualizzati.
- [x] Il piano giornaliero e l'audit di Scopri non contano piu calendario dei santi, consigli della terra o proverbi dell'Almanacco.
- [x] Contratto editoriale fissato in `ALMANAC_DISCOVER_CONTENT_CONTRACT.md`.
- [x] Stato Scopri confermato: 525 memorie, 511 pronte IT/FUR, 312/366 giorni exact-date e 54 giorni senza fonte adatta.

## 166. Secondo passaggio giorni mancanti Scopri 2026-07-20

- [x] Generatore canonico della coda dei giorni senza Memoria primaria exact-date.
- [x] Separati senza ambiguita `dateIt` in formato italiano `DD-MM` e `dateAnchor` tecnico `MM-DD`.
- [x] Verificati tutti i candidati di classe B presenti nei 54 giorni inizialmente mancanti.
- [x] Decisioni di secondo passaggio registrate per 12 candidati, senza pubblicazione automatica.
- [x] Ida Vallerugo verificata su fonti autorevoli: confermati Meduno e il 1941, non il 13 maggio; resta fuori dal calendario exact-date.
- [x] Spiridon Gopcevic, Roberto Damiani e Olga Brunner restano memorie secondarie come deciso nei lotti editoriali originari.
- [x] Copertura confermata a 312/366; restano 54 giorni.
- [x] Tutti i 54 giorni richiedono una nuova fonte o un nuovo soggetto; non si abbassa la soglia editoriale per riempire il calendario.
- [x] Dodici candidati di classe B gia esclusi, sospesi, secondari o destinati all'archivio restano chiusi finche non emergono nuove prove.
- [x] Guardrail aggiuntivo sulle tre memorie secondarie gia approvate nei giorni scoperti.
- [x] Guardrail automatico: ogni candidato di classe B presente nella coda deve avere una decisione esplicita.

## 167. Memorie istituzionali di maggio Scopri 2026-07-21

- [x] Completata la revisione FUR della Memoria del 19 maggio sulla DOC Friuli Latisana.
- [x] Aggiunta la Memoria regionale del 20 maggio sulla prima riunione organizzativa degli Alpini per la ricostruzione del Friuli terremotato.
- [x] Aggiunte due Memorie di Gorizia per il 22 e il 30 maggio, ricavate dall'archivio istituzionale della Biblioteca Statale Isontina.
- [x] Le quattro date sono sostenute da fonti istituzionali con giorno esplicito; nessun adattamento di data e nessun uso di Wikipedia come fonte canonica.
- [x] Revisione IT e FUR completata; i quattro record canonici sono bilingui e `ready_for_discover`.
- [x] Test dedicati su formato italiano `DD-MM`, conversione tecnica `MM-DD`, unicita della Memoria primaria e gate bilingue.
- [x] Audit e coda rigenerati dai dati canonici: copertura primaria exact-date 317/366; restano 49 giorni da ricercare.

## 168. Obiettivo definitivo proverbi Almanacco 2026-07-21

- [x] Fissato il requisito finale a 366 proverbi distinti e approvati, uno per data.
- [x] La rotazione e classificata come comportamento provvisorio e non come copertura editoriale completa.
- [x] Corretto il doppio conteggio tra `proverbs.json` e `proverbCandidates.json`: 66 candidati erano gia pubblicati.
- [x] Stato reale verificato: 105 pubblicati, 96 `almanacEligible`, 122 candidati, 161 record di lavoro univoci.
- [x] Esposti separatamente il divario di 261 nuovi pubblicati e quello di 270 testi idonei.
- [ ] Revisionare i 9 proverbi pubblicati ma non `almanacEligible`.
- [ ] Reperire, verificare, tradurre in FUR e pubblicare 261 nuovi proverbi distinti.
- [ ] Completare la matrice 366 date senza ricorrere alla rotazione come risultato finale.

## 169. Revisione linguistica Ostermann 1876 - lotto 1 2026-07-22

- [x] Ricostruito il perimetro corretto: 60 decisioni preliminari, 51 blocchi sorgente e 49 candidati promuovibili.
- [x] Revisionati i primi 10 candidati del lotto 1 senza pubblicazione automatica.
- [x] Otto testi hanno copy IT finale e FUR normalizzato con riscontro sul facsimile e su repertori linguistici o paremiologici.
- [x] Il detto lunare e stato riconosciuto come duplicato e collegato al record esistente `ostermann-lune-sentade`.
- [x] Il detto pasquale conserva IT finale e FUR in bozza, esplicitamente in attesa di revisione madrelingua.
- [x] Ogni record dichiara una regola data/mese/festa/condizione; i detti meteo non possono essere usati come riempitivi casuali.
- [x] Nessun record del lotto e consumato dalla UI e tutti restano `publish: false`.
- [x] Aggiunto un validatore dedicato per provenienza, stati linguistici, doppioni, regole temporali e conteggio residuo.
- [x] Il lotto 1 lascia 39 candidati promuovibili da sottoporre alla stessa revisione IT/FUR.

## 170. Revisione linguistica Ostermann 1876 - lotto 2 2026-07-22

- [x] Revisionati 12 candidati provenienti dal secondo lotto preliminare, senza pubblicazione automatica.
- [x] Dieci testi hanno copy IT finale e FUR normalizzato con riscontro sul facsimile e, quando disponibile, su ARLeF, ParemioRom o Dizionari de Lenghe Furlane.
- [x] Due testi conservano IT finale ma restano esplicitamente in revisione FUR: il detto sull'ombra di agosto e quello sulla veccia.
- [x] La neve prima di Natale usa una finestra strutturata 1-24 dicembre, non il mese di dicembre indistinto.
- [x] Il detto di san Nicolo resta vincolato al 6 dicembre e quello di febbraio al solo mese di febbraio.
- [x] Il segno delle nuvole a balconi richiede una condizione meteo coerente e non puo essere usato come riempitivo casuale.
- [x] Corretti tre dettagli di normalizzazione tramite repertorio lessicografico: `vent`, `e fas` e `no ven su jerbe`.
- [x] Nessun record del lotto e consumato dalla UI e tutti restano `publish: false`.
- [x] Dopo il lotto 2 restavano 27 candidati promuovibili da sottoporre alla stessa revisione IT/FUR.

## 171. Revisione linguistica Ostermann 1876 - lotto 3 2026-07-22

- [x] Revisionati 12 candidati provenienti dal terzo lotto preliminare, senza pubblicazione automatica.
- [x] Dieci testi hanno copy IT finale e FUR normalizzato con riscontro sul facsimile e, quando disponibile, su ARLeF, ParemioRom o Dizionari de Lenghe Furlane.
- [x] Due testi conservano IT finale ma restano esplicitamente in revisione FUR: il detto agricolo sul cuculo e la massima sul ritardo.
- [x] Epifania e san Valentino restano vincolati rispettivamente al 6 gennaio e al 14 febbraio.
- [x] Prima pioggia di agosto e pioggia sottile di aprile restano vincolate al rispettivo mese.
- [x] Il detto sul cuculo e limitato a primavera ed estate; il validatore controlla anche le regole stagionali.
- [x] Le massime generali dichiarano esplicitamente la possibilita di assegnazione futura, senza consumare oggi uno slot del calendario.
- [x] Nessun record del lotto e consumato dalla UI e tutti restano `publish: false`.
- [x] Dopo il lotto 3 restavano 15 candidati promuovibili da sottoporre alla stessa revisione IT/FUR.

## 172. Revisione linguistica Ostermann 1876 - lotto 4 e chiusura coda 2026-07-22

- [x] Revisionati gli ultimi 15 candidati provenienti dal quarto lotto preliminare, senza pubblicazione automatica.
- [x] Quattordici testi hanno copy IT finale e FUR normalizzato con riscontro sul facsimile e su repertori linguistici o testi FUR istituzionali.
- [x] La massima `Co si e tal bal, bisugne bala` conserva IT finale ma resta in revisione FUR perche manca un'attestazione moderna sufficiente a scegliere la normalizzazione senza congetture.
- [x] Le forme moderne documentate sostituiscono soltanto grafia e costruzione storica: per esempio `Fur il dint e vie il dolor`, `il prin pinsir`, `cjapalu` e i pronomi soggetto.
- [x] Tutti i 15 testi sono massime generali prive di richiami incompatibili a date, feste, mesi o stagioni; l'assegnazione ai 366 giorni resta una promozione editoriale separata.
- [x] Completata la revisione di tutti i 49 candidati promuovibili: 42 `language_reviewed`, 1 `merge_existing`, 6 `needs_native_review`.
- [x] Nessuno dei 49 record e consumato dalla UI e tutti restano `publish: false`.
- [x] I 6 record in revisione madrelingua non possono essere promossi finche il FUR non viene approvato.
- [x] Validatori linguistico e preliminare superati: 49/49 candidati coperti, 60 decisioni e 51 blocchi sorgente coerenti.

## 173. Identita prodotto e launcher Android 2026-08-09

- [x] Voce storica superata: `icon_launcher_3.0` e' stato sostituito il 22 agosto 2026 dal pacchetto verificato `launcher-082026`; non va ripristinato.
- [x] Inserita in `Impostazioni > Informazioni` una riga prodotto compatta, separata dall'elenco delle fonti.
- [x] La riga mostra l'icona launcher a 48 x 48 px, il nome `Meteo Friûl` e il collegamento ufficiale a `https://meteofriul.it`.
- [ ] Mostrare la versione ricavata dai metadati di build quando verra definita la versione di pubblicazione.
- [ ] Mostrare ideazione, sviluppo e direzione editoriale usando esclusivamente i crediti confermati dal titolare.
- [ ] Dichiarare marchio e identita visiva con una formula approvata dal titolare.
- [ ] Inserire il copyright soltanto dopo avere definito titolare e formula finale, senza dati provvisori o inventati.
- [x] Evitata una seconda pagina o card crediti: la riga prodotto convive con le fonti dentro la superficie Informazioni gia esistente.
- [x] Distinzione domini registrata: `meteofriul.it` e il sito istituzionale; `meteofriul.app` identifica l'app e potra inoltrare alla pagina dello store.

## 174. Prima estrazione backend UI3 - location 2026-08-09

- [x] Creata una nuova API FastAPI modulare in `backend`, senza importare il monolite storico.
- [x] Separate route, contratti e servizio della famiglia `location`.
- [x] Generato e validato il catalogo runtime dei 215 Comuni FVG dalla fonte canonica frontend.
- [x] `GET /api/location/search` funziona senza rete e mantiene il ranking di Comuni principali e province.
- [x] `GET /api/location/reverse` normalizza i risultati FVG sul catalogo canonico e conserva provincia, codice ISTAT e coordinate.
- [x] Un errore della fonte reverse restituisce `503`; non viene inventata una localita FVG.
- [x] Aggiunto contratto v1 condiviso con fixture usate dai test frontend e backend.
- [x] Corretto il cache adapter frontend affinche non perda provincia e codice ISTAT.
- [x] Proxy incrementale verificato: `/api/location/*` usa la nuova API `8002`; le altre route restano sul backend storico `8001`.
- [x] Ricerca e reverse verificati attraverso il proxy frontend e nell'interfaccia reale senza errori console.
- [x] OpenAPI nuova API verificata con sole route `location` e health.
- [x] Rollback locale preservato mantenendo separati i due target nel proxy Vite.
- [x] Prossima famiglia migrata: `live` (webcam, segnalazioni e conferme).

## 175. Estrazione backend UI3 - live 2026-08-09

- [x] Congelati i cinque endpoint usati da Vedi in `contracts/runtime-api/v1/live`.
- [x] Importato con script validato il solo manifest necessario: 20 webcam,
  senza codice del monolite e senza percorsi locali esposti.
- [x] Il manifest remoto e' opzionale; errore o timeout usano il manifest locale
  pronto all'avvio.
- [x] Estratti route, contratti, servizio e repository delle segnalazioni.
- [x] Conservate le regole: durata 60 minuti, cooldown 45 minuti, annullamento
  60 secondi, correzione manuale entro 5 km e conferme si/no idempotenti.
- [x] Le coordinate GPS esatte non vengono pubblicate: il report usa il centro
  del Comune selezionato dal catalogo canonico dei 215 Comuni.
- [x] Persistenza compatibile con le tre collezioni Firestore storiche; memoria
  esplicita in locale e fallback in caso di errore.
- [x] Proxy Vite separato: `/api/live/*` e `/api/community/*` usano `8002`;
  meteo, Bollettino, Eventi e radar restano su `8001`.
- [x] Confronto reale: 20/20 webcam e 215/215 localita senza differenze nei
  campi consumati dalla UI; zero report attivi prima e dopo la prova.
- [x] Smoke test via proxy: creazione, gruppo, conferma, elenco e annullamento
  completati; nessun report di prova residuo.
- [x] Browser Vedi: mappa sociale, stato vuoto, webcam e cambio zona operativi;
  nessun overflow e nessun errore o warning console.
- [ ] Prima dello staging impostare `COMMUNITY_STORAGE=firestore`, credenziali
  nel secret store e verificare persistenza fra due istanze.
- [ ] Prossima famiglia da migrare: `events` (feed, ranking e immagini).

## 176. Ridenominazione Vedi in Territorio 2026-08-09

- [x] Nome utente aggiornato da `Vedi` a `Territorio`; route e identificatore
  tecnico restano `tab=live` per non rompere URL, cache o contratti.
- [x] Nome FUR aggiornato da `Cjale` a `Teritori`, coerente con il lessico gia
  usato nei contenuti revisionati dell'app.
- [x] Titolo della mappa sociale abbreviato in `Segnalazioni` / `Segnalazions`
  per evitare la ripetizione di `territorio` dentro la pagina.
- [x] Icona navbar aggiornata da occhio a mappa con posizione; Eventi mantiene
  la propria icona mappa semplice.
- [x] Verificati IT/FUR, light/dark e ingombro della navbar: `Territorio` e
  `Teritori` restano su una riga, senza overflow; icone distinte confermate.

## 177. Modello gratuito e sostegno volontario 2026-08-13

- [x] Meteo Friûl resta gratuito e senza pubblicita, abbonamenti o funzioni Premium.
- [x] Le funzioni restano identiche per chi contribuisce e chi non contribuisce.
- [x] Il contributo e' interamente facoltativo, senza vantaggi o servizi in cambio,
  e riconosce il tempo dedicato allo sviluppo e all'evoluzione del progetto.
- [x] Nel pilot e' presente soltanto l'anteprima visuale in Impostazioni: nessun
  pagamento, collegamento o provider e' attivo.
- [x] Verificata la card pilota in IT/FUR e nei temi chiaro/scuro prima della
  generazione dell'APK.
- [ ] Attivare un eventuale pagamento soltanto con una decisione separata e dopo
  verifica di provider, privacy, fiscalita e regole dello store.

## 178. Recensione Google Play - decisione post-beta 2026-08-24

- [x] Durante la beta raccogliere soltanto feedback privato: nessuna richiesta di
  recensione e nessun collegamento alla valutazione nello store.
- [ ] Implementare esclusivamente dopo la beta la scheda nativa Google Play per
  la recensione, senza popup personalizzato preliminare del tipo "Ti piace
  Meteo Friul?".
- [ ] Rendere l'utente idoneo alla richiesta soltanto dopo circa cinque utilizzi
  riusciti distribuiti su almeno sette giorni.
- [ ] Non mostrare mai la richiesta durante errori, onboarding, richieste di
  permesso, allerte ufficiali, avvisi meteo o altri flussi critici.
- [ ] Aggiungere soltanto in produzione il collegamento discreto `Valuta Meteo
  Friul` nella sezione Impostazioni > Informazioni.
- [x] Esclusione esplicita dalla prima AAB e dalla fase beta: l'intervento verra
  valutato e verificato in una successiva fase post-beta.

## 179. Rimozione controllata della documentazione legacy 2026-08-24

- [x] Decisione registrata: l'appendice legacy potra essere eliminata; la sua
  cronologia restera comunque recuperabile tramite Git.
- [ ] Prima della rimozione, trasferire nel flusso Play corrente tutte le sezioni
  ancora valide: notifiche e cache, build Web di anteprima, scheda dei risultati
  e indicazioni grafiche.
- [ ] Eliminare soltanto dopo il trasferimento le istruzioni `private_test`,
  Firebase App Distribution, vecchie allowlist e fasi di distribuzione legacy.
- [ ] Rimuovere anche la corrispondente sezione legacy dal README Android.
- [ ] Verificare con una ricerca completa che nessun documento corrente rimandi
  ancora al percorso di distribuzione legacy.
- [ ] Valutare gli script legacy uno per uno prima di cancellarli: questa
  decisione documentale non ne autorizza la rimozione automatica.
- [x] Nessuna appendice, documento o script eliminato in questa fase.

## 180. Moderazione UGC Territorio 2026-08-24

Aggiornamento 25 agosto 2026: per la prima beta e' stato approvato il modello
strutturato ed effimero. Non sono prerequisiti un job di digest, uno scheduler,
un canale email o policy Monitoring dedicate. Il gate Play verifica invece il
contratto chiuso dell'API e le policy TTL cloud.

- [x] Classificate come UGC le segnalazioni anonime visibili agli altri utenti,
  anche se limitate a otto fenomeni e prive di testo, foto o profilo.
- [x] Definito il contratto `community-guidelines-v2`, con App Check su tutte le
  mutazioni e motivi chiusi `inaccurate`, `duplicate`, `misuse`.
- [x] Separati `Segnala contenuto`, conferma/smentita del fenomeno e
  `Nascondi questa fonte`.
- [x] Definiti pseudonimi pubblici giornalieri e blocco locale fino al rinnovo
  giornaliero, comunque non oltre 24 ore, senza esporre identificatori interni
  o creare profili permanenti.
- [x] Escluso l'hide globale automatico: un flag nasconde localmente; un
  eventuale hide/ripristino/rimozione globale resta un intervento manuale.
  La scelta evita una soglia aggirabile con reinstallazioni.
- [x] Attestate in Google Cloud le policy TTL community e verificati i documenti
  correnti tramite il gate live in sola lettura.
- [x] Verificate in sola lettura le pagine pubbliche IT/FUR: il 25 agosto
  espongono entrambe la versione del 24 agosto, con posizione precisa effimera,
  Comune canonico pubblico, `client_id` pseudonimo e retention applicative.
- [x] Verificate, committate e pubblicate le sorgenti landing del 24 agosto.
- [x] Registrato l'handoff tecnico esatto in
  `docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`, senza modificare
  il repository landing separato o Play Console.
- [x] Aggiornare e pubblicare privacy IT/FUR con fenomeno e Comune pubblici,
  posizione precisa effimera, ID installazione pseudonimo, sicurezza community,
  retention 45 min/60 min/2 h/24 h e cancellazione TTL asincrona. Il circuito
  digest/log/email resta dormiente e non e' un trattamento attivo della beta.
- [ ] Allineare Data Safety e indicare Google Cloud/Firebase come
  fornitore/responsabile tecnico, senza omettere i dati pseudonimi.
- [x] Pubblicare il copy FUR della beta mantenendo l'italiano come testo di
  riferimento; ulteriori affinamenti restano manutenzione editoriale.
- [x] Completare test e visual QA locale.
- [x] Nessun AAB generato e nessuna modifica effettuata in Play Console.
