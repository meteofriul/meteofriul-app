# Aria e pollini: caricamento distinto da indisponibilità

## Stato del lavoro

22 ottobre 2026. Ramo `codex/cams-loading-state`, creato da main
`d62683b9666ad38de42033fd2fe6db022ead8943`.
Correzione salvata nel commit `22c0fd62327d818c15edd2faf6fd7baedefe2f1b`.
La prova su Galaxy richiesta dal proprietario è completata con esito positivo:
il requisito dispositivo per la promozione locale su main è soddisfatto,
senza deroga. Il successivo commit documentale aggiunge soltanto queste
evidenze; il codice verificato resta identico a `22c0fd62`.
Il ramo release 0.1.15 resta invariato. Nessuna variazione a
versionName/versionCode. Il precedente controllo senza dispositivo è
superato dalla verifica fisica descritta sotto.

## Comportamento

| Stato | Italiano | Friulano |
| --- | --- | --- |
| Richiesta in corso, senza valori utilizzabili | Caricamento… | In cjariament… |
| Dati assenti/non utilizzabili dopo un esito esplicito | Dati non disponibili | Dâts no disponibii |
| Dati disponibili | Valori e provenienza | Valori e provenienza |

Le stesse diciture compaiono nelle schede Previsioni e nei dettagli.
Il caricamento iniziale viene seguito dalla route e quello differito dallo
stato CAMS. Un esito CAMS esplicito, compresa la revoca, prevale sul generico
caricamento meteo. Aria e pollini conservano disponibilità indipendente;
i valori validi, inclusi gli zeri, restano visibili durante l'aggiornamento.
Non cambiano acquisizione, cache, tolleranze, servizi, layout o soglie.

## Verifiche automatiche e browser integrato

- 250 test superati in 25 file: area weather, caricamento differito,
  avvio con revoche, continuità CAMS, candidato attivo e controller Home.
- Regressioni nuove: attesa iniziale/differita, errore terminale, recupero,
  aria/pollini indipendenti, zero reale e due lingue.
- Due regressioni di revoca hanno inizialmente evidenziato una precedenza
  errata del caricamento generico; corretta nel modello senza indebolire
  i controlli di revoca. La ripetizione completa sopra è verde.
- Lint frontend e `git diff --check`: superati.
- Browser integrato, launcher `scripts/start-local-weather-pilot.ps1`
  con `-NationalCloud`, esclusivamente porta 5174.
- Scenari locali simulati con i componenti reali: caricamento,
  indisponibilità, recupero e dettagli, in italiano e friulano.
  La pagina temporanea è ignorata da Git e non entra nell'app pubblicata.
- Pagina reale: osservato `Caricamento…` per entrambe le schede, seguito
  dai dati CAMS senza interventi sulla cache. PM2.5 9,4 µg/m³, PM10
  11,4 µg/m³, graminacee 0,11 grani/m³. Controllata anche la vista friulana.
- Italiano e tema chiaro ripristinati; posizione e notifiche non modificate.

Evidenze locali nella radice canonica:
`.tmp/cams-loading-state-20261022/` (screenshot IT/FUR, stati simulati
e albero accessibile del passaggio reale caricamento → dati).

## Verifica Galaxy del 22 ottobre

Candidato `22c0fd62`, Galaxy A52 SM-A525F, Android 14, Brave 1.97.59,
1080×2400 pixel e densità 420 dpi. Anteprima avviata esclusivamente con
`scripts/start-local-weather-pilot.ps1 -NationalCloud` sulla porta 5174,
raggiunta via USB reverse, senza installazioni. Screenshot e gerarchia
Android controllati sul telefono fisico.

| Controllo | Italiano | Friulano |
| --- | --- | --- |
| Dati CAMS reali nelle due card | Superato | Superato |
| Apertura/chiusura dei dettagli aria e pollini | Superato | Superato |
| Caricamento, card e dettagli | Superato | Superato |
| Dati non disponibili, card e dettagli | Superato | Superato |
| Recupero dei valori dopo l'attesa | Superato | Superato |
| Zero valido visualizzato come valore | Superato | Superato |

La pagina reale di Pordenone mostrava PM2.5 10,2 µg/m³, PM10 13,1 µg/m³
e graminacee 0,25 grani/m³ nella lettura italiana riferita alle 21:00.
La successiva lettura friulana, dopo il cambio d'ora, era riferita alle
22:00: rispettivamente 12, 15,1 e 0,23. Le differenze sono associate alle
ore valide mostrate nei dettagli, non al cambio di lingua.

Per rendere osservabili gli stati transitori si è usata una pagina locale
temporanea con i componenti e il modello reali dell'app, alimentati da
input simulati. Nessun guasto indotto nei servizi. Gli otto controlli della
gerarchia dei dettagli (due lingue × due stati × due contenuti) confermano
le diciture attese e l'assenza della dicitura opposta. Gli screenshot delle
card e dei dettagli sono leggibili, senza troncamenti del messaggio.
Il recupero simulato include PM2.5 uguale a zero, che resta un numero.

Ripristinati italiano, tema chiaro e vista delle previsioni reali;
Pordenone, stato della posizione e comandi notifiche non modificati.
I controlli delle impostazioni restano soltanto nelle evidenze locali
ignorate. La pagina di simulazione non è versionata né inclusa nell'app.

Evidenze selezionate e senza identificativi del dispositivo:
[riepilogo e hash](evidence/cams-loading-state-20261022/verification.json),
[dati reali IT](evidence/cams-loading-state-20261022/live-it.png),
[dati reali FUR](evidence/cams-loading-state-20261022/live-fur.png),
[attesa IT](evidence/cams-loading-state-20261022/fixture-loading-it.png),
[attesa FUR](evidence/cams-loading-state-20261022/fixture-loading-fur.png),
[indisponibilità IT](evidence/cams-loading-state-20261022/fixture-unavailable-it.png),
[indisponibilità FUR](evidence/cams-loading-state-20261022/fixture-unavailable-fur.png),
[recupero e zero](evidence/cams-loading-state-20261022/fixture-ready-fur.png).
Le catture complete restano in `.tmp/cams-loading-state-20261022/phone/`
nella radice canonica.

## Promozione locale

Il passaggio autorizzato su main usa `git merge --ff-only
codex/cams-loading-state`, dalla base `d62683b9`: include il commit della
correzione e il successivo verbale, senza modifiche alla release o ad altri
filoni. Prima del passaggio sono verificati working tree puliti, ascendenza,
assenza di modifiche al codice dopo i test e integrità delle evidenze.
Non è previsto un push: nessuna nuova CI remota viene avviata da questa
promozione locale.

## Limiti e perimetro

Questa è una verifica dell'anteprima Web su Brave e telefono fisico;
non attesta il runtime Android minificato né Safari/iPhone. Nessuna
installazione, AAB, push, deploy, invio, esecuzione manuale di job o emulatore.
Gli sponsor restano disattivati. Il lavoro non attribuisce a un job il
precedente episodio transitorio dell'anteprima: quella causa non era
dimostrata.
