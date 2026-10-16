# Eventi — primo ciclo locale senza checkpoint, 8 ottobre 2026

La prova e' partita da un catalogo locale vuoto e ha usato il processo,
il limite di **360 secondi** e il gate del job condiviso per TurismoFVG.
Non ha letto PDF e non ha scritto nel cloud.

Il ciclo e' durato **319,28 secondi**: inventario di **2.433 URL** su
**485 pagine** del calendario, **960 dettagli** controllati e **1.473
pendenti**. Nessuna ambiguita' o scheda in revisione. Il catalogo locale
risultante conserva un checkpoint compresso di **561.223 byte** e zero
eventi TurismoFVG; la fonte e' `unavailable` con errore
`incomplete_source`. Questa e' la risposta corretta finche' il controllo
non ha esaminato tutti i dettagli.

Il [ciclo completo del 7 ottobre](EVENTI_CICLO_15_FONTI_2026-10-07.md)
ha gia' provato che il checkpoint verificato puo' produrre **15/15 fonti
`fresh`** nel job locale. I test verificano la conservazione e la ripresa
del checkpoint parziale. **Non** e' stata eseguita una seconda scansione
live da questo nuovo checkpoint: ripetere subito migliaia di richieste
aggiungerebbe carico al sito senza chiarire il comportamento del primo
ciclo.

La prima prova si e' fermata correttamente senza schede. Prima della
distribuzione occorre verificare la ripresa fino a un checkpoint completo,
poi provare il job in un ambiente di prova senza esporre un catalogo parziale
all'app. Il primo avvio distribuito e la prova nell'app restano da verificare.
La prova sul telefono e' rinviata su richiesta dell'utente.

## Ripresa del checkpoint l'8 ottobre

La ripresa locale ha usato il checkpoint parziale del primo ciclo. Lo strumento
di audit e' stato allineato al job: anche la scansione annuale iniziale usa
direttamente le finestre datate. Il ciclo successivo ha portato i dettagli
controllati a **1.776/2.433**, con 657 pendenti e tre schede in revisione.

Per non riscaricare subito le 485 pagine del calendario, la ripresa nello
stesso giorno ha riusato l'indice annuale e la sitemap appena salvati. Ha
controllato **2.433/2.433 dettagli**; la riconciliazione ha risolto la scheda
duplicata *Radici nella pietra* e una pagina storica senza anno. Restava il
torneo *WTT Youth Contender Lignano 2026*: la pagina marcata come italiana
restituisce la riga data in tedesco, pur indicando chiaramente **21–27 ottobre
2026**. Il parser tedesco gia' presente e' stato collegato al percorso del job,
con verifica dei giorni della settimana e test che rifiuta un giorno errato.

L'ultima ripresa locale dall'indice salvato ha prodotto **2.433/2.433 dettagli,
zero pendenti, zero ambigui, zero revisioni, `source_complete=true` e 1.441
schede TurismoFVG**. Il checkpoint e il risultato verificato sono rimasti
nei file locali ignorati sotto `.dev-logs/events-girofvg-2026-10-07/`;
nessun catalogo cloud e' stato pubblicato. Il riuso dell'indice e' valido
solo per questa ripresa locale ravvicinata: il job ordinario rilegge l'indice.
