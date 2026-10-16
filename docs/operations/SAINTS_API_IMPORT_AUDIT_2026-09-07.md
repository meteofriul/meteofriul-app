# Verifica importazione santi

Verifica del 7 settembre 2026, senza modificare l'archivio pubblicato.

- Documentazione: https://santodelgiorno.marcointroini.it/
- Ricerca pubblica: https://santodelgiorno.marcointroini.it/cerca-per-data
- API per data: /api/v1/santo/data/{mese}/{giorno}; autenticazione Bearer richiesta.
- Dettaglio fonte: /api/v1/santo/{uuid}?include=fonte.
- Ricerca onomastico per nome: comprende primari e secondari; non equivale
  a una certificazione dell'elenco degli onomastici estratto per data.
- Il sito dichiara integrazione API gratuita anche commerciale e provenienza
  Cathopedia. La licenza MIT del repository riguarda il software: non va
  automaticamente attribuita al database importato.

L'archivio locale del 7 settembre contiene solo Santa Regina. La ricerca
pubblica mostra dieci record: l'archivio locale è incompleto per quel giorno.
Le celle onomastico nella rappresentazione testuale del sito non consentono
di determinare con affidabilità i flag: non inferirli dai nomi.

Non trovato un importatore originale nei percorsi scripts/backend ispezionati,
né variabili d'ambiente con nomi SANTO/SAINT/INTROINI. Nessun segreto letto o
stampato. Serve un token configurato in modo sicuro o un export JSON autenticato
per verificare schema e valori reali. Non inserire il token nel frontend.

Successivo passo: campione autenticato, confronto per data e flag, registrazione
di UUID/fonte/note, verifica delle condizioni di redistribuzione offline,
importazione in staging senza sovrascrivere traduzioni curate e biografie.
