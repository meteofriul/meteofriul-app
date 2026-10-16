# Asset precedenti della pilota — non usare per il launcher attivo

Snapshot residuo in `inventario.csv`, con dimensione file e SHA-256.
Le 20 vecchie immagini launcher a colori sono state rimosse il 9 settembre;
la versione completa precedente è recuperabile da Git. Non ricreare questo
launcher: il riferimento unico attuale è descritto nel README della cartella padre.
Le dimensioni raster riprendono il pacchetto 082026; due ulteriori icone web
any usano composizione 78,1%. Android adattivo/maskable 54%, splash 66%,
notifica piccola con margine 2 dp e sagoma monocromatica.

Master: `frontend/public/brand/meteo-eventi-friul-edge-master.png`.
Modifica con generazione integrata, prompt: preservare sagoma, dimensioni e
colori; estendere soltanto lo sfondo azzurro fino ai bordi, senza bianco,
testi o nuovi elementi. Controllati visivamente Home Android e splash reali.

Il generatore generale precedente è stato ritirato per impedire la sovrascrittura
del nuovo launcher. Le versioni web e Play sono preparate ma NON pubblicate. Il pacchetto
approvato 082026 e le risorse `main` della beta restano intatti.

I nomi interni 082026 sono mantenuti nel nuovo pacchetto per compatibilità
con i riferimenti Android; non implicano identità degli hash con il vecchio
pacchetto. Questo pacchetto non sostituisce il gate di rilascio Play.
