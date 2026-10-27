# Ostermann 1876 - archivio sorgente

Questo archivio deriva dal volume completo *Proverbi friulani raccolti dalla viva voce del popolo* di Valentino Ostermann, Udine 1876.

Non e' contenuto applicativo e non viene letto dalla UI.

## File

- `source.json`: provenienza, hash del PDF e regole di uso.
- `master-pages.jsonl`: testo PDF, OCR e controllo qualita per pagina.
- `source-lines.csv`: inventario riga per riga utile alla ricerca.
- `source-blocks.csv`: raggruppamento preliminare con sezione e priorita editoriale.
- `quality-report.json`: conteggi deterministici dell'estrazione.
- `review-queue.csv`: coda P1/P2 ordinata, con possibili corrispondenze ai proverbi gia presenti.
- `review-queue-summary.json`: conteggi della coda e degli esiti preliminari.
- `review-decisions-batch-*.json`: lotti verificati sul facsimile; registrano decisioni editoriali senza pubblicare contenuti.
- `language-review-batch-*.json`: revisione IT/FUR dei soli candidati promuovibili, con destinazione e regola temporale esplicite; resta sempre `publish: false`.
- `editorial-selection-it.json`: esito editoriale italiano dei candidati, inclusi esclusioni, accorpamenti e vincoli di uso.
- `editorial-selection-fur.json`: approvazione FUR dei soli candidati promossi dalla selezione italiana.

La selezione corrente comprende 256 proverbi approvati per l'Almanacco, 6 contenuti destinati a Scopri, 4 segni meteorologici sospesi finche non esiste il dato necessario, 1 accorpamento e 3 esclusioni. I proverbi approvati vengono promossi nel repertorio applicativo; gli altri gruppi non entrano nella rotazione quotidiana.

L'ottavo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 153-160 del facsimile. Sono tutte massime generali, sottoposte a controllo dei duplicati e prive di date, feste o stagioni artificiali.

Il nono lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 174-176 del facsimile. Il gruppo riguarda esperienza, apprendimento e prudenza; le varianti ridondanti restano fuori.

Il decimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 177-180 del facsimile. Il gruppo riguarda abitudini, influenza, carattere e prudenza; testi offensivi, violenti, opachi o gia presenti restano fuori.

L'undicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 181-191 del facsimile. Il gruppo riguarda perseveranza, iniziativa, onesta e responsabilita; duplicati e formule opache restano fuori.

Il dodicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 201-216 del facsimile. Il gruppo riguarda misura, famiglia, lavoro, contentezza, apparenza e coerenza tra parole e azioni; le varianti ridondanti sul risparmio restano fuori.

Il tredicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 217-220 del facsimile. Il gruppo riguarda rispetto, paura, vendetta, invidia e convivenza; riferimenti locali opachi e varianti ridondanti restano fuori.

Il quattordicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 222-230 del facsimile. Il gruppo riguarda bisogno, difficolta, speranza, pazienza e conforto; duplicati gia pubblicati e varianti quasi equivalenti restano fuori.

Il quindicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 231-240 del facsimile. Il gruppo riguarda aiuto reciproco, amicizia nelle difficolta e prudenza nel parlare; da ogni blocco composito viene scelta una sola massima e i passaggi opachi, ridondanti o offensivi restano fuori.

Il sedicesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 241-250 del facsimile. Il gruppo riguarda consiglio, prudenza nel parlare, responsabilita e autocritica; doppioni interni, formule opache e passaggi offensivi o datati restano fuori.

Il diciassettesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 251-257 del facsimile. Il gruppo riguarda apparenza, promesse, verita, parole, gratitudine e responsabilita personale; doppioni gia pubblicati, testi offensivi o datati e formule opache restano fuori.

Il diciottesimo lotto aggiunge 15 proverbi verificati direttamente sulle pagine PDF 270-275 del facsimile. Il gruppo riguarda conoscenza, apprendimento, riflessione, collaborazione e conseguenze delle azioni; i detti gia presenti, le varianti ridondanti e i passaggi che richiedono un contesto esteso restano fuori.

Il diciannovesimo lotto aggiunge 3 proverbi verificati direttamente sulla pagina PDF 275 del facsimile. Il gruppo riguarda responsabilita e conseguenze delle azioni e porta il repertorio applicativo al minimo di 366 proverbi distinti idonei all'Almanacco, senza assegnazioni temporali artificiali.

Il ventesimo lotto aggiunge 4 proverbi generali verificati sulle pagine PDF 202 e 275 del facsimile. Sostituiscono nel calendario quotidiano quattro varianti che collidevano con la stessa data o festa mobile; le varianti restano archiviate per Scopri.

Il ventunesimo lotto aggiunge 4 proverbi generali verificati sulle pagine PDF 113, 133 e 135 del facsimile. Formano una piccola riserva per gli anni in cui ricorrenze fisse e feste mobili coincidono, senza introdurre ripetizioni o vincoli temporali artificiali.

## Regola editoriale

I testi OCR possono contenere errori e i blocchi possono unire varianti, traduzioni o spiegazioni. Nessuna riga o blocco e' pubblicabile automaticamente.

Per entrare in `frontend/src/data/almanac/proverbs.json`, un testo deve essere:

1. verificato sul facsimile;
2. separato da varianti e note;
3. normalizzato in FUR;
4. tradotto e revisionato in IT;
5. classificato per data, stagione o rotazione generale;
6. approvato editorialmente.

I file `review-decisions-batch-*.json` fermano il lavoro alla decisione editoriale preliminare. I record con `publish: false` non sono consumati dalla UI e non autorizzano da soli normalizzazione FUR, traduzione definitiva o assegnazione al calendario.

## Rigenerazione

Il PDF originale e la cache OCR recuperati sono conservati nell'
[archivio permanente Scopri](../../../docs/archive/scopri/README.md), insieme
a checksum, provenienza e pagine usate nelle revisioni. Per una nuova
elaborazione preparare una copia di lavoro della cache:

```powershell
New-Item -ItemType Directory -Force -Path tmp/ostermann-proverbs-1876-ocr-cache | Out-Null
Get-ChildItem -LiteralPath docs/archive/scopri/materiali/ostermann-1876/ocr -File |
  Copy-Item -Destination tmp/ostermann-proverbs-1876-ocr-cache

python scripts/extract-ostermann-proverbs-1876.py `
  --pdf docs/archive/scopri/materiali/ostermann-1876/fonte/ostermann-proverbi-friulani-1876.pdf `
  --output scripts/data/ostermann-proverbs-1876 `
  --cache tmp/ostermann-proverbs-1876-ocr-cache `
  --ocr missing --workers 4
```

Il PDF e la cache originali restano nell'archivio locale, esclusi da Git;
soltanto la cache di lavoro resta in `tmp/`. Non modificare gli originali
archiviati e non confondere l'inventario versionato con un backup dei file.

La coda editoriale si rigenera con:

```powershell
python scripts/build-ostermann-1876-review-queue.py
```

Le decisioni manuali si controllano con:

```powershell
python scripts/validate-ostermann-1876-review-decisions.py
```

Le revisioni linguistiche si controllano separatamente con:

```powershell
python scripts/validate-ostermann-1876-language-reviews.py
python scripts/validate-ostermann-1876-it-selection.py
python scripts/validate-ostermann-1876-fur-selection.py
```

La promozione controllata e ripetibile dei soli proverbi approvati per l'Almanacco si esegue con:

```powershell
node scripts/promote-ostermann-1876-reviewed-content.mjs
```

Lo script non sovrascrive uno slot calendario gia occupato: conserva la voce principale e segnala la seconda come conflitto editoriale. I testi con condizione meteo e quelli destinati a Scopri restano esclusi dalla promozione.
