# Correzioni locali dopo la verifica Web 300036 — 23 ottobre 2026

## Ripresa del 24 ottobre

Correzioni salvate in `cd471769`; ramo release allineato a main `23153e54`
con merge `ffa61949`. Nuovamente superati i 116 test mirati. Questa ripresa
prepara il salvataggio su GitHub; promozione in main ancora subordinata alla
prova Galaxy (telefono non collegato). [Stato corrente](RELEASE_WEB_SOURCE_ALIGNMENT_20261024.md).
Lo stato e le evidenze sotto descrivono la sessione originale del 23 ottobre.

## Stato e perimetro al 23 ottobre

Autorizzazione: «Procedi con le correzioni». Lavoro sul ramo release esistente
`codex/release-0.1.15`, base `eb1095185023636efde111dd93b295a5a07ec10f`.
Correzioni e verbali sono salvati nel commit locale del ramo release che contiene
questo documento. Non sono stati promossi su main né inviati a GitHub.
Sponsor disattivati; nessuna modifica a configurazione o servizi sponsor.
Nessuna AAB, installazione, push, deploy, invio, job manuale o prova sul Galaxy.

La AAB **0.1.15 / 300036** e il pacchetto Web archiviato da `9d5ff2f4` restano
immutati: **non contengono queste nuove correzioni**. Il manifest della candidata
conserva SHA256 `42e81042e678be61091db42e401329f54353bddd8be28d4673eacbf898a75bc2`.
Il [verbale iniziale](WEB_0.1.15_300036_FINAL_CHECK_20261023.md) resta storico.

## Modifiche e risultati

| Rilievo | Correzione | Verifica |
| --- | --- | --- |
| WEB-300036-01, testo GPS FUR fuori dalla scheda | Le righe del corpo della scheda conservano l'altezza del contenuto; scorre il corpo, senza comprimere il messaggio | Componente reale con timeout simulato, IT/FUR chiaro/scuro; anche FUR a 375×812 |
| WEB-300036-02, Eventi «Mostra altri» in FUR | Dicitura in dizionario: IT «Mostra altri», FUR «Mostre altris» | Catalogo reale nel pilot: da 16 a 19 eventi dopo il comando FUR |
| WEB-300036-03, errore OSMER in italiano nella Home FUR | Aggiunte entrambe le diciture FUR per fonte non raggiungibile | Test del view model con errore: testo tradotto, nessuna mappa fittizia |
| WEB-300036-04, indisponibilità CAMS durante refresh | Lo stato della richiesta supplementare viene passato anche alla UI; un precedente errore di trasporto mostra caricamento mentre la nuova richiesta è attiva | Regressione prima fallita, poi superata in IT/FUR; successo, errore terminale e diagnostiche del fornitore distinti |

Nel caso GPS FUR a 1280×720 il riquadro passa da 52 a circa 75,97 px:
il testo termina a y=404,97, il box a y=413,97, la privacy inizia a y=424,97.
A 375×812 il riquadro arriva a 94,16 px: nessuna sovrapposizione.
La prova usa il componente effettivo e il CSS dell'app, con errore GPS iniettato:
non prova il rilevamento della posizione, non accetta regole né invia segnalazioni.
La pagina di prova è ignorata da Git, esterna agli ingressi della build.

Per CAMS il flag era già restituito al coordinatore del refresh, ma non allo stato
mostrato dalle Previsioni. Ora la UI lo riceve durante la richiesta e lo rimuove
all'esito terminale. Il view model usa il caricamento per il recupero da errore di
trasporto; diagnostiche del fornitore, revoche o contratto invalido restano visibili.
I valori già verificati, compreso zero, continuano a essere mostrati. Non aggiunti
retry, timeout, richieste o nuovi default dei dati. Nessuna modifica ai job.

La regressione controllata copre recuperi CAMS ritardati e ripetuti dopo warm-up,
con asserzioni sul testo visibile in entrambe le lingue. Nel pilot con dati reali
sono stati osservati PM2.5 6,8 e PM10 8,1 µg/m³, graminacee 0,14 grani/m³ anche
al rientro FUR. Questa osservazione non è un filmato della transizione originale:
la causa di quell'episodio specifico, non strumentato, non è dimostrata a posteriori.

## Controlli locali

- 10 file Vitest, **116 test superati**, configurazione nativa.
- ESLint sui file JavaScript/JSX modificati: PASS.
- Compilazione Vite 8.1.6 in modalità `cloudflare`, output temporaneo: PASS.
  È solo un controllo di compilazione, non il pacchetto distribuibile del runbook:
  non assemblati service worker né attestazioni CARTO/backend. Primo tentativo
  rifiutato correttamente per endpoint assente; ripetuto con l'API fissata della
  candidata nel solo processo, senza alterare o disattivare il controllo.
  Avvisi su dimensione chunk e import misto di AlmanacView non bloccanti.
- Browser PC tramite pilot canonico 5174; IT/chiaro ripristinati alla fine.
- `git diff --check`: PASS. Nessun cambiamento a dipendenze o configurazioni native.

## Limiti e consegna

I quattro rilievi hanno una correzione locale verificata nel perimetro descritto.
Non dichiarare per questo concluso il collaudo pubblico della Web: restano la
prova del pacchetto ufficiale con servizi da origine autorizzata, aggiornamento
della cache dalla Web pubblica precedente e Safari/iPhone/PWA. Non aggirate le
regole CORS che impedivano le chiamate remote dal bundle statico su localhost.
Non effettuate nuove prove su telefono o emulatore. La futura integrazione e
ricostruzione dei pacchetti dovrà mantenere Web e Android sulla stessa sorgente.

[Evidenza sanificata e hash](evidence/web-0.1.15-300036-corrections-20261023/verification.json).
Screenshot, misure, pagina di prova e log di compilazione sono conservati fuori
versionamento in `release-artifacts/web-candidates/corrections-300036-20261023/`
nella radice canonica; il pacchetto immutabile precedente non è stato riscritto.
