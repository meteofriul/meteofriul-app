# Controlli eventi pilota — 7 settembre 2026

Modifiche locali, non ancora distribuite nel cloud. Beta non modificata.

## Copertura effettiva

| Fonte | Testo controllato per cambi di programma | Limite |
| --- | --- | --- |
| TurismoFVG | Descrizione estratta dal dettaglio, cache e budget 20 URL per esecuzione | Copertura progressiva, non completa a ogni aggiornamento |
| Azalea | Titolo e blocco single-event-text | Avvisi fuori dal blocco non verificati |
| CSS Udine | Titolo e blocchi venue con date | Corpo narrativo non verificato; programmi collegati dalla homepage |
| Pordenone Pensa | Titolo e orario/sede della singola sessione | Solo edizione In Giallo 2026 già verificata; altri blocchi esclusi |
| Verdi Pordenone | Titolo e article-dates | Corpo narrativo non verificato; sedi esterne richiedono revisione |
| Verdi Trieste | Titolo e data della tessera del calendario pubblico | Nessun aggiramento delle pagine dettaglio protette |
| Pordenonelegge | Titolo, access_notes, sede e ora della singola tessera | Programma completo, non pagine dettaglio |

Gli avvisi testuali sono segnali conservativi per revisione, non una comprensione
semantica garantita: possono produrre falsi positivi (anche titoli narrativi) e
non intercettano avvisi pubblicati in immagini o blocchi non letti. Le repliche
con orari diversi non devono essere eliminate come duplicati.

Descrizioni: il riuso automatico dei testi resta disabilitato per TurismoFVG;
questa modifica non introduce copie delle biografie/descrizioni delle altre fonti.
Prima di pubblicare descrizioni occorrono provenienza e condizioni compatibili.
Non dedurre mai una descrizione dal solo titolo.

Verifica locale: `python -m unittest discover -s tests -p 'test_pilot_*.py'`
da backend: 96 test superati. Non è una verifica live della copertura dei siti.

## Prima del rilascio

- Misurare i risultati del collettore reale per fonte (accettati, revisioni,
  errori, aggiornamento e URL effettivamente ispezionati).
- Revisionare i casi segnalati e i formati non riconosciuti; non dichiarare
  assenza di doppioni sulla sola base dei test sintetici.
- Verificare avvisi nei corpi delle pagine non ancora coperti prima di
  qualificare una fonte come completamente controllata.
- Distribuire e verificare solo il pilota, mantenendo invariata la beta.
