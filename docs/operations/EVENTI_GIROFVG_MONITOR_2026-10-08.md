# GiroFVG — controllo diagnostico automatico, 8 ottobre 2026

GiroFVG resta un indice di scoperta: **non genera schede Eventi**. L'[audit
iniziale](EVENTI_GIROFVG_AUDIT_2026-10-07.md) ha trovato campi data e testi
di anteprima discordanti dall'organizzatore. Il job non copia quei campi;
una nuova scheda richiede la conferma della fonte diretta e la verifica dei
doppioni prima di entrare nel catalogo.

Il monitor legge la sitemap XML e tutte le sette categorie Eventi. Controlla
URL, date e luogo delle tessere, paginazione, numero di tessere nelle pagine
intermedie e nuove modifiche rispetto all'inventario revisionato il 7
ottobre. Alla fine rilegge la sitemap e la prima pagina di ogni categoria:
un cambiamento durante la scansione ferma il controllo. Rilegge il dettaglio
dei soli URL recenti modificati che non sono
nelle categorie, per capire se hanno campi evento. I cambiamenti di schede
attive o di articoli datati vengono segnalati e fanno fallire il job per
revisione; non vengono pubblicati automaticamente. Un errore nuovo di rete,
formato o paginazione blocca il controllo. Non vengono letti PDF o immagini.

La pagina storica `fiere-e-mostre?start=168` restituisce ancora HTTP 500.
Il monitor la registra come eccezione nota e dichiara
`source_complete=false`: **non** conta quella pagina come letta. Se cambia
o scompare dal catalogo un evento futuro gia' revisionato, il controllo lo
segnala. Tre articoli del 2026 privi di data strutturata sono eccezioni
esatte perche' i programmi di maggio, giugno e agosto sono terminati; una
modifica al loro `lastmod` li rimette in revisione.

La prova live dell'8 ottobre ha verificato **12.297 URL** nella sitemap,
**216 URL recenti o con anno corrente/futuro nel percorso**, **90 pagine**
di categoria attese, **89 lette**, **1.793 tessere** e **zero cambiamenti da
revisionare**, in **19,36 secondi** dopo il ricontrollo finale. I tre
controlli diagnostici gia' presenti hanno impiegato insieme 25,52 secondi
nella prova locale; con GiroFVG il tempo osservato e' circa 45 secondi.
Il tetto configurato delle 15 fonti
scende a **835 secondi** su un job cloud da 900: Pordenonelegge, Azalea e
CSS Udine passano tutti con il nuovo limite di 20 secondi nella prova locale
del processo e del gate. Il ciclo distribuito resta da verificare; questi
numeri sono prove locali senza pubblicazione cloud.

Il controllo riduce il lavoro manuale ai cambiamenti segnalati. La pagina
storica in HTTP 500 impedisce di dichiarare completa la copertura di tutto
l'archivio GiroFVG; il sito resta fuori dalle fonti che producono schede.
