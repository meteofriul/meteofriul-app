# TurismoFVG — tempo della scansione annuale, 7 ottobre 2026

Il job condiviso ha interrotto TurismoFVG dopo 360 secondi nel primo ciclo a
15 fonti. Il checkpoint dello stesso giorno conteneva tutti i 2.395 dettagli
verificati, quindi il problema non era una ricostruzione integrale dei
dettagli. La pagina annuale aveva oltre 300 pagine: il lettore provava prima
la scansione unica e, quando il totale cambiava durante la lettura,
ricominciava da capo con finestre datate.

Il collettore del job ora usa direttamente la scansione a finestre gia'
presente. Ogni finestra controlla il totale dichiarato, il numero di tessere
per pagina e la paginazione. L'unione deduplica le tessere che compaiono in
piu' finestre e deve coincidere con il totale annuale; la prima pagina
annuale viene riletta alla fine. La sitemap e le schede dettaglio continuano
a essere verificate dallo stesso controllo di fonte.

La prova locale in sola lettura, con il checkpoint precedente, e' terminata
in **217,13 secondi** con `source_complete=true`: **2.445 URL**
nell'inventario, **1.468 schede**, **1.356 anteprime**, zero URL pendenti,
ambigui o in revisione. Il gate di pubblicazione della fonte passa. Non sono
stati scaricati PDF ne' pubblicati dati cloud.

Il [ciclo locale completo a 15 fonti](EVENTI_CICLO_15_FONTI_2026-10-07.md)
e' poi passato: TurismoFVG `fresh` in 167,13 secondi, con 1.468 schede e
zero revisioni. Restano il primo ciclo distribuito e la prova reale nell'app
prima della promozione del ramo.
