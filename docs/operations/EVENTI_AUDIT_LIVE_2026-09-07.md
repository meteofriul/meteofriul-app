# Prima acquisizione diagnostica reale — 7 settembre 2026

Esecuzione locale di `backend/tools/probe_pilot_sources.py`, senza pubblicazione.
Nessuna modifica alla beta. Limite 120 secondi TurismoFVG, 60 per altra fonte.
Non è un confronto legacy/pilota a parità di raggio e finestra temporale.
I conteggi sono output regionali degli adattatori, NON il contatore Pordenone 20 km.

| Fonte | Record | Revisioni | Durata s | Esito |
| --- | ---: | ---: | ---: | --- |
| TurismoFVG | — | — | 35,2 | Connessione interrotta, non catalogo vuoto |
| Pordenonelegge | 445 | 0 | 4,5 | Programma acquisito |
| Azalea | 3 | 3 | 8,9 | Acquisito con esclusioni |
| CSS Udine | 29 | 6 | 17,9 | Acquisito con formati non riconosciuti |
| Pordenone Pensa | 2 | 0 | 1,4 | Solo In Giallo 2026 |
| Verdi Pordenone | 52 | 4 | 32,0 | Acquisito con revisioni |
| Verdi Trieste | 10 | 8 | 1,4 | Calendario pubblico parziale |

Nessun gruppo di duplicati esatti secondo la chiave diagnostica nei sei output
riusciti. Questo NON esclude duplicati semantici né unioni errate, e non misura
la completezza del sito.

## Evidenze e correzioni

- CSS: la pagina https://www.cssudine.it/stagione-contatto/2026/2828/i-turcs-tal-friul
  indica 11 e 12 settembre 2026 alle 20:30. Il parser non accettava la congiunzione
  nelle date. Aggiunto riconoscimento di liste con `e` e virgole e test permanente.
  Seconda acquisizione CSS dopo la correzione: 33 appuntamenti, 4 revisioni
  residue (prima 29 e 6). Recuperati quattro appuntamenti da due pagine.
  Terza acquisizione: 38 appuntamenti e 2 revisioni. Recuperati orari `20.30`
  e corsi con giorno della settimana e fascia `dalle ore 16 alle 19`;
  conservata anche `end_time`, senza inferire passaggi di mezzanotte.
  Restano Cieli sonori (anno assente dal blocco calendario) e presentazioni
  TIG con tre sedi/comuni alternati nel medesimo blocco. Non sono dichiarati
  eventi invalidi: richiedono un'estrazione più strutturata.
  Quarta acquisizione: 41 appuntamenti e 1 revisione. Il programma TIG ora
  associa le righe data/sede a Udine, Cervignano del Friuli e San Giorgio di
  Nogaro separatamente. Test su coordinate distinte e righe non accoppiate.
  Resta Cieli sonori; nessun anno ricavato automaticamente dall'URL.
- Azalea: https://www.azalea.it/eventi/claudio-baglioni-47/ dichiara rinvio al 2027.
  L'esclusione per revisione è giustificata; non si assegna automaticamente una
  nuova data completa dal solo anno.
- Il validatore pilot_source_policy è invocato direttamente solo da Azalea:
  gli altri adattatori hanno controlli propri. Non è ancora una barriera comune.

## Evidenze locali

Output JSON per fonte e summary.json nella directory temporanea
`C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-source-audit-wtc2vyfh`.
Questi file possono essere rimossi dalla pulizia temporanei del sistema.

## Aperto

Ripetere TurismoFVG con diagnostica del fallimento; revisionare le esclusioni
residue; acquisire fonti legacy e sperimentali con ambito dichiarato; eseguire
confronto equivalente. La singola raccolta non chiude l'audit delle 14 fonti.
