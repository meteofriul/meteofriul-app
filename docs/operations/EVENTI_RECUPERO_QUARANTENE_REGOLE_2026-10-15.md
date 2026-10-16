# Recupero delle quarantene con regole riutilizzabili

15 ottobre 2026 — ramo `codex/events-quarantine-recovery`.
Candidata implementata e verificata: `f39c223cc2f2a0a00c8cf8ca2c105d82c1f33078`.
Base dell'audit: `0928e7d6`.

**Resoconto del collaudo locale iniziale, prima della distribuzione.**
In quella fase main, API/job cloud, APK, AAB e Play non erano stati modificati,
e non era stato eseguito un nuovo ciclo completo delle fonti live.

**Aggiornamento del 15 ottobre:** distribuzione Cloud Run e collaudo completo
conclusi con la candidata `2a2a5f10`. I nove eventi sono visibili nell'API:
sette nuove schede e due eventi già presenti sotto URL equivalenti. Le quarantene
attuali sono sei. La verifica cloud ha incluso ulteriori correzioni alla ripresa
delle letture e alle clausole ipotetiche di maltempo. Vedi il
[verbale della distribuzione](EVENTI_QUARANTENE_DEPLOY_2026-10-15.md)
per esiti, limiti e confronto con questo audit iniziale.
Main, APK e Play restano invariati; nessun push GitHub.

## Regole permanenti

| Problema | Regola e limiti | Schede dell'audit recuperate |
| --- | --- | --- |
| Condizione meteo scritta `casodi` | Accettare lo spazio mancante nella condizione. Una cancellazione effettiva, separata o accompagnata da una forma verbale che la dichiara avvenuta, rimane da verificare. Una clausola non nasconde altri avvisi vicini. | Campagna Amica |
| Titolo con refuso o prefisso della sede | Solo una trasposizione di due lettere adiacenti in una parola lunga, con le altre parole identiche; oppure un prefisso prima dei due punti uguale alla sede dichiarata. Servono URL ufficiale, provenienza dal calendario, stesso Comune e date esplicite coincidenti con gli estremi dei giorni del calendario. Nessun confronto approssimativo generico. | Smarrimenti e rinvenimenti; Digger |
| Giorno preciso perso durante la preparazione della scheda | Se il dettaglio indica solo mese e anno, conservare l'unico giorno del calendario quando città, mese, anno e date del risultato ispezionato concordano. Il testo non deve contraddire quel giorno. Nessuna espansione in aperture giornaliere o repliche presunte. | Le quattro schede di Moggio Udinese |
| Separatore della località senza spazi | Accettare il trattino subito dopo la provincia tra parentesi, mantenendo il resto del titolo e tutti i controlli geografici. | Sagra della Madonna della Salute |
| Frazione non presente negli alias | Ricavare il Comune dall'indirizzo completo della fonte, con CAP, Comune e provincia. Località nel titolo e nella sede devono coincidere; provincia del titolo, della sede e dell'indirizzo devono concordare. Sono necessarie coordinate della sede, poi validate dai controlli esistenti. Non è stato aggiunto un alias speciale per Tribil Superiore. | Burnjak |

Le nuove regole non contengono URL, titoli o date dei nove eventi come eccezioni.
Gli esempi sintetici dei test usano anche altri titoli, Comuni, frazioni e il 2027.
Le riconciliazioni dei titoli sono annotate nel risultato dell'ispezione.

## Collaudo

- 117 test mirati superati, inclusi i casi reali e controesempi con date,
  Comuni, province, coordinate e titoli discordanti.
- Intera suite backend: **1.838 test eseguiti, 1.837 superati, 1 saltato**,
  zero errori/fallimenti, 57,267 secondi. Il test saltato richiede un artefatto
  locale ISTAT opzionale non presente; è estraneo a questa modifica Eventi.
- Compilazione in memoria di tutti i moduli Python del backend e controllo
  `git diff --check` superati.
- Fixture ricavate dalle risposte pubbliche salvate il 15 ottobre: undici
  dettagli TurismoFVG e due righe API SagreFVG. I test non correggono i dati
  di ingresso e non simulano le nuove regole con monkeypatch.
- Confronto offline sul checkpoint del ciclo Spazzapan: TurismoFVG passa da
  **1.316 a 1.323** schede. Le 1.316 precedenti restano identiche campo per campo.
  Le due sagre aggiuntive superano il controllo individuale di pubblicazione:
  **7 + 2 = 9 recuperi**.
- Capuozzo rimane escluso. I programmi non ancora gestiti restano in revisione;
  i vecchi URL con errore 404 non vengono sostituiti automaticamente.

La prova sul checkpoint non equivale a una nuova raccolta completa: gli altri
risultati del checkpoint sono conservati, non riletti dalla rete. Non è stata
marcata come completa una raccolta con il vecchio numero di versione.

## Cache e futura distribuzione

Le versioni di ispezione passano a 12 per il dettaglio e 11 per il controllo
annuale. Al prossimo ciclo con questa candidata, i risultati delle versioni
precedenti vengono riesaminati, senza riutilizzare un giudizio obsoleto.
La prima raccolta può quindi richiedere più letture: durata, completamento e
quarantene residue vanno verificati nel ciclo cloud dopo l'eventuale distribuzione.
Questo collaudo locale non dichiara quel controllo già superato.

## Restano nove schede da trattare separatamente

- Quattro programmi/aperture: Biblioteca Austriaca, Autunno musicale,
  Una Terra una Storia, ABC assicurazioni. Servono estrazione delle sessioni
  e associazione corretta di sede, data e orario.
- Due riconciliazioni: Friuli 1976 e Itinerari CSS, per evitare duplicati.
- Tre esclusioni da mantenere con le prove attuali: incontro Capuozzo,
  vecchio Il segno della memoria, vecchio Latino Mediterraneo.

Resta aperta anche l'incoerenza titolo/descrizione della scheda Lipizer 506076,
esterna alle 18 dell'audit. Nessuna correzione di questo caso è inclusa qui.

## Riproduzione ed evidenze

Dalla directory `backend`:

```powershell
python -m unittest tests.test_pilot_quarantine_recovery -v
python -m unittest discover -s tests -q
```

- [Audit originario delle 18 schede](EVENTI_AUDIT_18_QUARANTENE_2026-10-15.md)
- [Riepilogo verifiche e hash del codice candidato](evidence/events-quarantine-recovery-2026-10-15/validation-summary.json)
- [Confronto del catalogo](evidence/events-quarantine-recovery-2026-10-15/catalog-replay.json)
- [Schede ancora da trattare](evidence/events-quarantine-recovery-2026-10-15/remaining-reviews.json)
- [Hash delle evidenze](evidence/events-quarantine-recovery-2026-10-15/SHA256SUMS.txt)
