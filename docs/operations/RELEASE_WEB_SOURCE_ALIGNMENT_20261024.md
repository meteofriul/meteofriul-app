# Allineamento sorgenti release 0.1.15 e Web — 24 ottobre 2026

## Base e perimetro

Richiesta del proprietario: allineare a main e salvare su GitHub, mantenendo
coerenti codice e documenti. Nessuna autorizzazione a nuovi artefatti o deploy.

- Main di partenza: `23153e54fd84078c69d78ea0db58867ff52018b5`, PR 18.
- Correzioni frontend: `cd47176954d41ab9341e009199103878bb2e0611`.
- Allineamento nel ramo esistente `codex/release-0.1.15`: `ffa6194959b4870707323e8865d794ccf55d274c`.
- Nessun conflitto; nessuna differenza frontend fra `cd471769` e il merge.
- Incluse le due correzioni backend già in main (TurismoFVG e monitor ICON).
  Questo allineamento non avvia né distribuisce job.

## Correzioni e controlli

Le quattro modifiche riguardano il messaggio GPS Community che sovrapponeva
il testo, «Mostre altris» negli Eventi, errore OSMER in friulano e caricamento
aria/pollini durante il recupero da un errore di trasporto. Dettagli e prove
IT/FUR nel [verbale del 23 ottobre](WEB_0.1.15_300036_CORRECTIONS_20261023.md).

Dopo l’unione: **116 test in 10 suite superati**, con configurazione Vitest
nativa. ESLint dei file JS/JSX modificati e `git diff --check`: PASS.
I nove hash frontend coincidono con l’evidenza del 23 ottobre; verificati
anche i collegamenti locali nei sei documenti aggiornati.
Le prove browser PC precedenti restano riferite agli stessi sorgenti;
nessuna nuova prova sul browser o telefono in questa sessione.

**Promozione in main in attesa:** il Galaxy non risulta collegato.
AGENTS.md richiede test automatici e verifica sul dispositivo prima di main.
La prova della 300036 precede queste correzioni e non le copre. Il ramo può
essere salvato e sottoposto a CI su GitHub senza promuoverlo in main.

## Sorgenti e pacchetti restano distinti

| Oggetto | Stato al controllo |
| --- | --- |
| Base sorgente comune Web/Android | Ramo release aggiornato a main con le quattro correzioni, in attesa del controllo sul Galaxy |
| AAB 0.1.15 / 300036 | Sorgente immutabile `9d5ff2f4`, SHA256 `024212752b3af72f163d75849aa53c2b191ba0352e42423b11efccd2d7f8b51f`; quattro correzioni assenti |
| Web archiviata associata alla 300036 | Stessa sorgente `9d5ff2f4`, manifest SHA256 `42e81042e678be61091db42e401329f54353bddd8be28d4673eacbf898a75bc2`; quattro correzioni assenti |
| Test interno Play | Ultima verifica 23 ottobre: 0.1.15 / 300036, due account confermati dal proprietario |
| Produzione Play / Web pubblica | Ultime letture 23 ottobre: 0.1.14 / 300031 e Web 0.1.14 da `1b0287c1`; nessuna nuova interrogazione o pubblicazione in questa sessione |

Nessun nuovo codice versione riservato, nessuna AAB o Web distribuibile
ricostruita. Artefatti firmati, ledger e manifest preesistenti conservati.
Sponsor disattivati; codice, configurazione e servizi sponsor invariati.

## Passi ancora aperti

1. Verifica Galaxy delle quattro correzioni, poi promozione del codice in main.
2. Dopo autorizzazione, nuovi pacchetti Web e Android dalla stessa sorgente
   approvata; Android con codice superiore a 300036.
3. Collaudo Web dei servizi da origine autorizzata e aggiornamento cache dalla
   versione pubblica; Safari/iPhone/PWA ancora non verificati.
4. Build, caricamento Play e pubblicazioni restano azioni separate.

README, stato release e piano Web distinguono ora il codice successivo alla
300036 dagli artefatti già prodotti. Corretta la vecchia dicitura della PR 11
ancora in bozza: è già unita in `eb109518`. Evidenze del 23 ottobre mantenute
come storiche, senza attribuire loro nuove verifiche o modificare gli hash.
