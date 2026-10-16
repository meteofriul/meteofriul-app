# CSS Udine — tempo della raccolta nel job, 7 ottobre 2026

Nel ciclo locale a 15 fonti CSS Udine ha raggiunto il limite di 45 secondi.
La lettura isolata completava correttamente 128 pagine HTML (sei indici e 122
dettagli), 161 repliche future e zero revisioni, ma impiegava 49,01 secondi.

L'adattatore ora riusa una connessione HTTP per ciascuno dei quattro thread
gia' esistenti e chiude le sessioni al termine della raccolta. Non cambia
l'inventario letto, il numero di thread o il controllo dei dettagli. Una
prova isolata con le connessioni riusate ha impiegato 7,07 secondi; la prova
attraverso il processo, il limite e il gate del job ha restituito `fresh` in
10,04 secondi, con 122 dettagli, 161 repliche, `source_complete=true` e zero
revisioni. I dieci test dell'adattatore passano.

Il [ciclo condiviso ripetuto](EVENTI_CICLO_15_FONTI_2026-10-07.md) ha
confermato CSS `fresh` in 6,36 secondi e tutte le 15 fonti `fresh`.
Con l'[aggiunta del monitor GiroFVG](EVENTI_GIROFVG_MONITOR_2026-10-08.md),
il limite CSS nel job passa a 20 secondi. La prova locale del processo e
del gate dell'8 ottobre conferma `fresh`, 122 dettagli e 161 repliche.
