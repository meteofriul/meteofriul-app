# Archivio delle fonti e delle lavorazioni Scopri

Recupero del 27 ottobre 2026. Questo archivio conserva gli originali e le
tracce di ricerca utili a Scopri e Almanacco. Non e' una sorgente runtime,
non entra nelle build Web/Android e non pubblica nuovi contenuti nell'app.

## Primo recupero: Ostermann e lavorazioni storiche

| Origine logica | File | Byte |
| --- | ---: | ---: |
| Precedente checkout UI3, materiali Scopri/Ostermann selezionati | 472 | 226146705 |
| Archivio documentale esterno `ostermann-text`, copia completa | 2272 | 13630166 |
| Totale | 2744 | 239776871 |

```text
scopri/
  README.md
  manifest-sha256.json          inventario portabile di ogni file
  manifest-fonti-fvg.json       inventario del successivo recupero documentale FVG
  provenienza-locale.json       percorsi originali della macchina, solo locale
  provenienza-fvg-locale.json   provenienza del recupero FVG, solo locale
  materiali/                   originali locali esclusi da Git
    ostermann-1876/
      fonte/                   PDF completo dei Proverbi friulani
      ocr/                     289 pagine di testo, dalla 19 alla 307
      lavorazione/             immagini dei lotti, campioni e risultati preliminari
    ostermann-vita-in-friuli/
      ostermann-text/          pagine raw, pulite, normalizzate, OCR e report
    evidenze-storiche-scopri/   due schermate della precedente interfaccia
    memoria-del-giorno/
      fonti-fvg/               12 fonti e selezioni Accadde oggi, CSV e JSON
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

## Secondo recupero: sole fonti documentali FVG

Il successivo confronto del 27 ottobre 2026 ha recuperato **12 file,
9934492 byte**, dalla raccolta documentale esterna FVG citata
nell'[audit delle fonti](../ui3-migration/DISCOVER_DAILY_HISTORY_SOURCE_AUDIT.md).
Sono sei raccolte e selezioni storiche, ciascuna nei formati CSV e JSON:

| Nome senza estensione | Record nel JSON |
| --- | ---: |
| `accadde_oggi_fvg` | 5039 |
| `accadde_oggi_fvg_catalogato` | 4081 |
| `accadde_oggi_fvg_completo_esteso_metadata` | 4081 |
| `accadde_oggi_fvg_365giorni` | 366 |
| `accadde_oggi_fvg_365giorni_esteso` | 366 |
| `accadde_oggi_fvg_VIP` | 614 |

I conteggi sono letti dagli originali JSON. Le raccolte si sovrappongono:
non vanno sommati come eventi distinti. Si conservano entrambi i formati
originali, senza conversioni. Nessuno dei 12 file risulta identico per SHA-256
ai dati testuali versionati confrontati o al primo inventario dell'archivio.
Il [manifest FVG](manifest-fonti-fvg.json) registra ogni copia e il checksum
del precedente manifest, che resta invariato.

Il totale dei due recuperi e' **2756 file, 249711363 byte**.
In questo secondo intervento non sono state copiate immagini, schermate,
loghi, metadati fotografici, programmi o configurazioni. Il materiale del
primo recupero resta inalterato.

I riferimenti `external/fvg/...` nei
[candidati Memoria del giorno](../../../frontend/src/data/discover/dailyHistoryCandidates.json)
identificano queste fonti storiche. La copia nell'archivio non cambia tali
riferimenti e non importa automaticamente i dati nell'app. Rimangono
necessarie la selezione delle notizie, la verifica delle fonti e le revisioni
editoriali e linguistiche previste dal contratto.

### Materiale confrontato e non duplicato

- Nei 24 documenti editoriali selezionati, 22 sono gia' conservati identici
  (compreso l'audit spostato nell'archivio UI3). Il testo dei due precedenti
  piani Scopri e' gia' compreso nelle versioni attuali, con normalizzazione
  dei percorsi macchina nel piano di completamento.
- Gli otto file delle fonti e revisioni dei santi sono gia' identici in
  `scripts/data/saint-profiles/` e fanno parte del confronto precedente.
- I 24 export Scopri sono intermedi rigenerabili secondo il
  [contratto del laboratorio dati](../../../backend_dryrun_staging/README.md#contratto-exports-per-scopri).
  Nei sei XLSX le celle corrispondono ai CSV affiancati; non sono presenti
  commenti o ulteriori fogli. I campi per decisioni e priorita' umane sono
  vuoti; le note degli esclusi sono generate dal producer. Non sono emerse
  annotazioni manuali autonome da recuperare.
- Il file `eventi_fvg.csv` della raccolta esterna contiene solo
  l'intestazione. La pagina landing, le configurazioni webcam, i log e gli
  output tecnici non rientrano nelle fonti documentali Scopri.

## Tracciabilita' e conservazione

Il [manifest](manifest-sha256.json) registra percorso nell'archivio, origine
logica, percorso relativo originale, dimensione e SHA-256 di ciascun file.
Le copie sono state confrontate con le sorgenti per dimensione e SHA-256.
I duplicati presenti nei percorsi di lavorazione sono conservati e indicati
nel manifest: non sono state eliminate varianti o prove storiche.
Le cartelle di origine non sono state modificate o cancellate.

Indice e manifest sono versionabili. `materiali/`,
`provenienza-locale.json` e `provenienza-fvg-locale.json` sono esclusi da Git tramite il `.gitignore` locale,
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
$verifiedCount = 0
foreach ($manifestName in @("manifest-sha256.json", "manifest-fonti-fvg.json")) {
  $inventory = Get-Content -Raw -LiteralPath (Join-Path $archiveRoot $manifestName) | ConvertFrom-Json
  foreach ($entry in $inventory.files) {
    $file = Get-Item -LiteralPath (Join-Path $archiveRoot $entry.path) -ErrorAction Stop
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if ($file.Length -ne $entry.bytes -or $hash -ine $entry.sha256) {
      throw "Archivio non conforme: $($entry.path)"
    }
    $verifiedCount++
  }
}
Write-Output "Archivio verificato: $verifiedCount file."
```

## Perimetro del recupero

Il recupero riguarda i materiali Scopri/Ostermann e le fonti FVG individuati nel confronto.
Non e' un backup completo del vecchio checkout e non certifica che siano
eliminabili materiali di altre sezioni, release, installazioni o firma.
La cancellazione del vecchio progetto resta un'azione separata dell'utente.
