# Archivio delle fonti e delle lavorazioni Scopri

Recupero del 27 ottobre 2026. Questo archivio conserva gli originali e le
tracce di ricerca utili a Scopri e Almanacco. Non e' una sorgente runtime,
non entra nelle build Web/Android e non pubblica nuovi contenuti nell'app.

## Contenuto recuperato

| Origine logica | File | Byte |
| --- | ---: | ---: |
| Precedente checkout UI3, materiali Scopri/Ostermann selezionati | 472 | 226146705 |
| Archivio documentale esterno `ostermann-text`, copia completa | 2272 | 13630166 |
| Totale | 2744 | 239776871 |

```text
scopri/
  README.md
  manifest-sha256.json          inventario portabile di ogni file
  provenienza-locale.json       percorsi originali della macchina, solo locale
  materiali/                   originali locali esclusi da Git
    ostermann-1876/
      fonte/                   PDF completo dei Proverbi friulani
      ocr/                     289 pagine di testo, dalla 19 alla 307
      lavorazione/             immagini dei lotti, campioni e risultati preliminari
    ostermann-vita-in-friuli/
      ostermann-text/          pagine raw, pulite, normalizzate, OCR e report
    evidenze-storiche-scopri/   due schermate della precedente interfaccia
```

Il PDF 1876 ha SHA-256
`219ae631a8b13f49990760ca10fe6528ca00140603503b199cdd29a9653715a6`,
uguale a quello gia' registrato nel
[catalogo della fonte](../../../scripts/data/ostermann-proverbs-1876/source.json).
La copia `ostermann-text` corrisponde all'identificatore editoriale
`external:ostermann-text` del
[catalogo Ostermann](../../../frontend/src/data/ostermann/sourceCatalog.json).
Per questo secondo corpus sono conservati i file testuali e i report trovati:
questo recupero non certifica la presenza del relativo facsimile PDF completo.

## Tracciabilita' e conservazione

Il [manifest](manifest-sha256.json) registra percorso nell'archivio, origine
logica, percorso relativo originale, dimensione e SHA-256 di ciascun file.
Le copie sono state confrontate con le sorgenti per dimensione e SHA-256.
I duplicati presenti nei percorsi di lavorazione sono conservati e indicati
nel manifest: non sono state eliminate varianti o prove storiche.
Le cartelle di origine non sono state modificate o cancellate.

Indice e manifest sono versionabili. `materiali/` e
`provenienza-locale.json` sono esclusi da Git tramite il `.gitignore` locale,
conservando la regola di non pubblicare PDF, cache e percorsi macchina con il
codice. Un clone Git da solo **non contiene questi originali**: quando si
salva o trasferisce il progetto, includere esplicitamente questa cartella
completa e verificare il manifest. Non trattarla come `tmp/` o come cache
eliminabile.

Le copie archiviate vanno mantenute inalterate. Per nuove elaborazioni usare
una copia di lavoro in `tmp/`, mantenendo gli originali e i loro checksum.
Le pagine OCR, le immagini dei lotti e le schermate non costituiscono una
nuova approvazione editoriale, linguistica o una verifica della UI corrente.

## Materiale gia' nel progetto

Non viene duplicato in questo archivio:

- [estrazioni, revisioni e decisioni Ostermann 1876](../../../scripts/data/ostermann-proverbs-1876/README.md);
- [dati e revisioni Scopri](../../../frontend/src/data/discover/);
- [dati Almanacco](../../../frontend/src/data/almanac/);
- [cataloghi ed estratti Ostermann](../../../frontend/src/data/ostermann/);
- [foto e stemmi comunali](../../../frontend/public/municipalities/);
- [documentazione della migrazione UI3](../ui3-migration/README.md).

La pubblicazione nell'app continua a seguire il
[contratto Scopri/Almanacco](../../../ALMANAC_DISCOVER_CONTENT_CONTRACT.md).

## Verifica locale dell'inventario

Dalla radice del progetto, questo controllo legge soltanto i file:

```powershell
$archiveRoot = Join-Path (Get-Location).Path "docs/archive/scopri"
$inventory = Get-Content -Raw -LiteralPath (Join-Path $archiveRoot "manifest-sha256.json") | ConvertFrom-Json
foreach ($entry in $inventory.files) {
  $file = Get-Item -LiteralPath (Join-Path $archiveRoot $entry.path) -ErrorAction Stop
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
  if ($file.Length -ne $entry.bytes -or $hash -ine $entry.sha256) {
    throw "Archivio non conforme: $($entry.path)"
  }
}
Write-Output "Archivio verificato: $($inventory.files.Count) file."
```

## Perimetro del recupero

Il recupero riguarda i materiali Scopri/Ostermann individuati nel confronto.
Non e' un backup completo del vecchio checkout e non certifica che siano
eliminabili materiali di altre sezioni, release, installazioni o firma.
La cancellazione del vecchio progetto resta un'azione separata dell'utente.
