# Pordenone Pensa — appartenenza al programma, 26 ottobre 2026

**Correzione locale verificata, da committare sul ramo
`codex/events-programme-membership`.** Base main
`4219581f17b35aa42bd346ff652058004d9cf5f0`. Nessun aggiornamento di main,
GitHub, backend, AAB o Web pubblica; sponsor disattivati e invariati.

## Problema e comportamento corretto

Nel collaudo della 0.1.15 / 300038 il Galaxy mostrava i cinque incontri ABC
sulle assicurazioni di ottobre/novembre sotto «Pordenone Pensa in Giallo
2026», con intervallo 5–7 settembre. Il dettaglio mostrava contemporaneamente
le date autunnali delle sessioni e quelle sbagliate del programma.

La fonte Pordenone Pensa pubblica più programmi. L'associazione per solo nome
della fonte in `pilotProgrammeProjection.js` era quindi insufficiente.
La correzione interviene solo sull'appartenenza a questo programma:

- richiede fonte e date all'interno dell'edizione verificata del 5–7 settembre;
- accetta l'identificativo esplicito corretto oppure, per dati precedenti senza
  identificativo, l'URL esatto del programma verificato;
- rifiuta metadati contraddittori (altra edizione, serie o intervallo), date
  assenti/invertite/esterne e un identificativo di settembre su incontri autunnali;
- lascia gli altri incontri autonomi e integri: titolo, date, orario, sede,
  descrizione, URL e restanti campi API non vengono riscritti.

I cinque incontri risultano quindi distinti, tutti alle 19:00:
27 ottobre; 3, 10, 17 e 24 novembre. Le schede compaiono secondo i filtri
ordinari di data dell'app; preservarle tutte nei dati non significa mostrarle
tutte nella scheda Oggi o oltre l'orizzonte temporale previsto.
Il programma storico «in Giallo» continua a raggrupparsi quando l'appartenenza
è verificata. Nessun nuovo programma ABC viene inventato dal frontend.

## Verifiche locali

**81 test superati in tre file**, con il caricatore nativo Vite/Vitest.
Regressioni sui cinque record pubblicati, catalogo misto settembre/autunno,
confini di data, URL e metadati incoerenti. Il test integrato percorre
API → identità distinta → ordinamento/deduplicazione → schede e filtro Oggi
per ciascuna delle cinque date, sia in italiano sia in friulano. Titoli
editoriali e descrizioni della fonte rimangono nella lingua originale.

Lint completo e build frontend `local-pilot-cloud` superati. Build in una
cartella temporanea unica, nessun Android sync/AAB. Solo il consueto avviso
sulla dimensione dei chunk; nessun aggiornamento di dipendenze/toolchain.
Dipendenze fisiche copiate integralmente dal checkout release dopo confronto
del lockfile, senza esclusioni ricorsive o collegamenti tra worktree.

Replay offline prima/dopo sugli stessi campioni API del collaudo, snapshot
`2026-10-26T04:00:47.538511+00:00`, senza nuova acquisizione:

| Campione | Righe API | Card prima | Card dopo | Esito |
| --- | --- | --- | --- | --- |
| Pordenone | 326 | 322 | 326 | Una card errata sostituita dai cinque incontri integri |
| Udine | 449 | 449 | 449 | Invariato |
| Gradisca d'Isonzo | 254 | 254 | 254 | Invariato |
| Trieste | 260 | 260 | 260 | Invariato |

Le righe di ogni altra fonte sono identiche prima/dopo. I campioni territoriali
possono sovrapporsi e i totali sono precedenti ai filtri di visualizzazione:
non sono conteggi di eventi unici regionali o delle schede Oggi.

[Ricevuta e hash](evidence/events-pnpensa-membership-20261026/verification.json).
Log e risultati completi nella radice canonica, cartella privata
`.tmp/events-programme-membership-20261026/`. Il campione di regressione
versionato contiene soltanto i campi editoriali pubblici dei cinque incontri;
nessun dato del dispositivo o dell'utente.

## Stato Android, Web e limiti

La 300038 installata dal proprietario e l'archivio Web da `7130c28a` restano
immutati e contengono ancora il difetto. Questa correzione appartiene al
frontend condiviso e dovrà entrare nella successiva base approvata di entrambi;
non richiede aggiornamenti dei job Eventi o dei contratti API.

Verifica della correzione completata il 26 ottobre su Brave 1.97.59 del Galaxy
A52, Android 14 / API 34. Anteprima avviata esclusivamente dal launcher canonico
con `-WeatherCloud -StableFrontend`, porta 5174, sul ramo dedicato; hash dei
sorgenti identici a quelli degli 81 test. Bundle effettivamente caricato dal
telefono registrato nella ricevuta. Nessuna installazione o modifica della
300038: questa prova riguarda il frontend condiviso in Brave.

Con dati e orologio reali, la lista Prossimi ha un orizzonte di 15 giorni:
sono quindi presenti tre incontri (27 ottobre, 3 e 10 novembre), ciascuno
con scheda autonoma e dettaglio corretto. Verificati titolo, data, ore 19:00,
sede, descrizione, fonte e assenza del programma di settembre per tutti e tre,
sia in italiano/chiaro sia in friulano/scuro. Screenshot e gerarchie salvati;
nessuna sovrapposizione o taglio dei contenuti nei sei dettagli osservati.
I titoli e i testi editoriali della fonte rimangono nella lingua originale.

Gli incontri del 17 e 24 novembre sono oltre l'orizzonte odierno: non vengono
dichiarati visualizzati sul Galaxy. Tutti e cinque rimangono verificati nei
test locali per le rispettive date. Presente anche una scheda ABC di un'altra
fonte, distinta dal vecchio raggruppamento errato: non modificata in questo
intervento. Non è un controllo generale della completezza del catalogo.

Indietro Android chiude il dettaglio e torna agli Eventi senza uscire da Brave.
Ripristinati italiano e tema chiaro della sola anteprima; app ufficiale e sue
preferenze non toccate. Le evidenze sono nella sottocartella privata `galaxy/`
della cartella già indicata. Nessun cambiamento ai sorgenti dopo il collaudo;
restano commit e promozione. La futura AAB minificata richiederà il proprio
collaudo: non si attribuisce questo PASS alla 300038 già installata.

I verbali del collaudo 300038 salvati nel ramo release restano separati e
non sovrascritti. Nessuna modifica al pannello editoriale dell'altra chat,
alla gestione Barcolana, ai job, agli allarmi, agli sponsor o alle automazioni.
Nessun commit/push, deploy, installazione, emulatore o invio manuale.
