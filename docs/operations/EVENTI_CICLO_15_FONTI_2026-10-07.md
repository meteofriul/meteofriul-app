# Eventi — ciclo locale delle 15 fonti, 7 ottobre 2026

Sul ramo `codex/events-discovery-audit`, il job di raccolta locale ha letto
in sequenza le 15 fonti registrate, con i limiti di tempo del job ufficiale,
il checkpoint annuale TurismoFVG verificato e i gate delle singole fonti.
Il secondo ciclo dopo le correzioni ha impiegato **435,89 secondi**:
**15/15 fonti `fresh`**, zero schede in revisione e nessun timeout. Nessun
catalogo cloud e' stato pubblicato. I 135 test pertinenti passano.

| Fonte | Record correnti dopo il gate | Stato |
| --- | ---: | --- |
| TurismoFVG | 1.468 | `fresh` |
| Pordenonelegge | 0 | `fresh` |
| Le Giornate del Cinema Muto | 47 | `fresh` |
| Azalea | 7 | `fresh` |
| CSS Udine | 161 | `fresh` |
| Pordenone Pensa | 1 | `fresh` |
| Teatro Verdi Pordenone | 88 | `fresh` |
| Teatro Verdi Trieste | 73 | `fresh` |
| Paesi in Festa | 22 | `fresh` |
| SagreFVG | 29 | `fresh` |
| Villa Manin | 5 | `fresh` |
| Magazzino delle Idee | 1 | `fresh` |
| MESS | 19 | `fresh` |
| Galleria Spazzapan | 4 | `fresh` |
| Barcolana | 1 | `fresh` |

I numeri sono record per fonte **prima** della deduplicazione tra fonti e
della proiezione per posizione; non sono il numero di schede distinte che
vedrebbe l'utente. Pordenonelegge ha letto 447 voci di programma, ma nessuna
cade nell'orizzonte corrente; Cinema Muto ne ha lette 87, di cui 47 restano
attive. Barcolana produce una scheda di festival con il programma ordinato.
Le sei iniziative regionali collegate a Barcolana ma assenti dal programma
ufficiale restano schede distinte, come motivato nell'[audit Barcolana](EVENTI_BARCOLANA_INTEGRAZIONE_2026-10-07.md).

Questo controllo prova il ciclo **locale con checkpoint**. Prima di promuovere
il ramo restano il primo ciclo distribuito da catalogo vuoto, il controllo
del catalogo risultante nell'app e la prova reale sul telefono, rinviata su
richiesta dell'utente. Le fonti ancora in audit diagnostico, come GiroFVG,
Pro Loco FVG, Anteprima Sagre e Palazzo Attems, non sono conteggiate fra le
15 fonti che producono schede.
