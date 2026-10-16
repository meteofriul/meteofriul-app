# Pro Loco FVG — audit del 7 ottobre 2026

## Decisione

L'[indice Eventi Pro Loco](https://prolocoregionefvg.it/eventi-delle-associate/)
resta una **fonte diagnostica** nel ramo `codex/events-discovery-audit`: oggi non
aggiunge schede all'app. Le 32 schede attuali sono gia' coperte dal catalogo
TurismoFVG verificato. Pubblicarle una seconda volta produrrebbe doppioni e,
in alcuni casi, sceglierebbe date meno complete. Il vecchio estrattore in
`engine.py` non e' adatto al nuovo job: legge solo le prime due pagine.

Il job del ramo legge invece **solo l'indice HTML** dopo la raccolta delle
fonti. Ogni tessera deve trovare una corrispondenza univoca con la scheda
TurismoFVG per titolo, comune e data. Due titoli diversi sono ammessi solo
per le coppie esaminate qui sotto. Una tessera nuova, ambigua o con anno
diverso fa fallire il controllo e richiede revisione; non crea una scheda
automatica. Il controllo non apre PDF, locandine, immagini o i 32 dettagli
ad ogni esecuzione.

## Inventario e confronto

La scansione HTML completa del 7 ottobre ha seguito le sei pagine collegate
dall'indice: **54 tessere**, **32 URL di dettaglio distinti**, tutti HTTP 200.
Il confronto con le 1.418 schede della scansione annuale TurismoFVG dello
stesso giorno ha trovato 30 coppie con titolo uguale, stesso comune e data
compatibile. Altre due coppie sono state controllate singolarmente:

- [Farine di flôr / Formandi](https://prolocoregionefvg.it/eventi-delle-associate/farine-di-flor-formandi/)
  a Sutrio il 18 ottobre corrisponde alla rinnovata edizione
  [ForMandi: il sapore delle Malghe](https://www.turismofvg.it/eventi/formandi-il-sapore-delle-malghe).
  La scheda Pro Loco conserva anche le date 2024 e 2025; la pagina regionale
  presenta il programma 2026 aggiornato.
- [Halloween party](https://prolocoregionefvg.it/eventi-delle-associate/halloween-party-4/)
  a San Vito al Tagliamento contiene date 2025 e 2026. La scheda
  [Halloween party 2026](https://www.turismofvg.it/eventi/halloween-party-2026)
  copre il 31 ottobre 2026. Il controllo accetta questa coppia solo per la
  data 2026; un'edizione successiva richiedera' nuova verifica.

Tutti i 32 dettagli Pro Loco hanno una descrizione. Nel catalogo TurismoFVG
tutti i 32 corrispondenti hanno un'anteprima testuale, 31 hanno un URL
immagine. Solo 13 pagine Pro Loco espongono un URL candidato per l'immagine
dell'evento; `/media/not-found` e il logo nel footer sono esclusi. Non sono
stati scaricati i file immagine, quindi il conteggio degli URL non prova la
validita' o l'edizione del contenuto.

## Date che non vanno copiate alla cieca

Il campo strutturato `Quando` di Pro Loco omette l'ultimo giorno in almeno
questi casi documentati dal testo della stessa scheda e dal dettaglio regionale:

- [Sagra della Madonna del Rosario a San Foca](https://prolocoregionefvg.it/eventi-delle-associate/sagra-della-madonna-del-rosario-san-foca/):
  `Quando` termina il 10 ottobre; il testo e [TurismoFVG](https://www.turismofvg.it/eventi/sagra-della-madonna-del-rosario-san-foca)
  includono domenica 11.
- [40ª Sagra della Castagna](https://prolocoregionefvg.it/eventi-delle-associate/40a-sagra-della-castagna/):
  `Quando` termina il 24 ottobre; il testo e [TurismoFVG](https://www.turismofvg.it/eventi/40%C2%AA-sagra-della-castagna)
  includono il 25.
- [Festa d'Autunno a Gonars](https://prolocoregionefvg.it/eventi-delle-associate/festa-dautunno-12/):
  `Quando` riporta solo il 10 ottobre; il testo e [TurismoFVG](https://www.turismofvg.it/eventi/festa-d-autunno-504304)
  riportano anche l'11.
- [Sagra delle Castagne a Prata](https://prolocoregionefvg.it/eventi-delle-associate/sagra-delle-castagne-43a-edizione/):
  `Quando` termina il 26; il testo e [TurismoFVG](https://www.turismofvg.it/eventi/sagra-delle-castagne-43%C2%AA-edizione)
  indicano il 28 ottobre.

In sette schede complessive l'ultimo giorno regionale supera l'ultimo
giorno elencato in `Quando`; quattro sono documentate sopra. Le altre tre
restano una differenza di rappresentazione, senza inferire automaticamente
singole aperture giornaliere da un periodo regionale. Il monitor verifica
solo che **le date esposte dall'indice** siano comprese nella scheda
regionale, evitando di promuovere una data incoerente.

## Controllo automatico e verifica

`backend/app/events/pilot_proloco_watch.py` segue la paginazione reale e
legge comune, titolo e data da ogni tessera. Rifiuta pagine vuote, markup
inatteso, salti di paginazione, occorrenze duplicate, date illeggibili e
schede prive di corrispondenza regionale unica. I download HTML hanno limite
di dimensione e timeout. Il job registra nel log il numero di pagine,
tessere, URL distinti e le eventuali anomalie; una variazione non verificata
fa fallire il job dopo aver conservato il catalogo valido delle altre fonti.

La prova live dell'indice ha restituito **6 pagine, 54 tessere, 32 URL e zero
anomalie** contro la scansione TurismoFVG locale. I 18 test mirati di
`test_pilot_proloco_watch.py` e `test_pilot_cloud.py` passano. L'audit completo
dei dettagli e' ripetibile con `backend/tools/audit_proloco_fvg.py`, usando un
file JSON della scansione annuale regionale; il suo output locale e' in
`.dev-logs/events-proloco-2026-10-07/audit.json`.

Questa modifica e' solo nel ramo: il job online non esegue ancora il monitor.
Il controllo del primo ciclo distribuito e la prova sul telefono restano
parte della promozione complessiva del job, gia' rinviata per il dispositivo.
