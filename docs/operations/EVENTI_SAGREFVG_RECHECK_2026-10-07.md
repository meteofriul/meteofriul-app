# SagreFVG — ricontrollo del 7 ottobre 2026

La [lista Sagris](https://sagrefvg.it/sagris/) e l'API pubblica
`/wp-json/tribe/events/v1/events` descrivono la stessa copertura attiva:
**28 URL nella lista e 28 record API con fine non passata**, senza URL mancanti
o aggiuntivi. Per includere le feste iniziate prima di oggi, il confronto
dell'indice ha letto la finestra API da settembre a dicembre, non solo le
schede con data iniziale dal 7 ottobre.

L'adattatore annuale del ramo ha letto tutte le **944 schede 2026** in
**19 pagine**, due anni futuri vuoti e il controllo finale di overflow. Ha
pubblicato 28 schede attive, zero revisioni, **28 anteprime**; il gate di
copertura passa. Le date e il comune sono ricavati dai campi evento e sede
dell'API, con la correzione motivata dal programma testuale per Gonars e il
comune di Tarvisio per la frazione Camporosso. Non si ricavano aperture
quotidiane da un intervallo: la scheda rimanda al programma sul sito fonte.

L'API associa un'immagine a tutte le 28 schede attive e offre per tutte una
variante orizzontale. La prova live ha verificato che i 28 URL scelti sono
HTTPS sul dominio SagreFVG, nel percorso di caricamento **2026** associato
all'evento; il job usa queste varianti come preview senza scaricare i file.
Un'immagine con anno diverso o URL non valido viene omessa. I 28 record
mantengono l'anteprima testuale anche quando l'immagine non fosse disponibile.

Il controllo dei doppioni gia' documentato in
[EVENTI_AUDIT_DOPPIONI_FONTI_2026-10-07.md](EVENTI_AUDIT_DOPPIONI_FONTI_2026-10-07.md)
lascia una sola scheda per Le Radici del Vino a Rauscedo e Festa d'Autunno
a Gonars, conservando l'anteprima della fonte piu' aggiornata. Il sito
SagreFVG e il nuovo job restano nel ramo, non nel catalogo online. Il primo
ciclo distribuito e la prova nell'APK sono controlli di rilascio ancora
aperti.

## Nuova scheda del 7 ottobre

Una [nuova Festa del Borgo di San Leonardo](https://sagrefvg.it/sagre/san-leonardo-di-campolongo-tapogliano-2a-festa-del-borgo-di-san-leonardo/)
e' entrata nell'API con la data **11 ottobre 2026** e un titolo senza sigla
di provincia. Il programma pubblicato conferma la giornata; il record della
sede indica Campolongo Tapogliano, Udine, e ripete la localita' nel nome e
nell'URL. Anche il [Comune di Campolongo Tapogliano](https://comune.campolongotapogliano.ud.it/media/files/md/030138/48.Elab.15_SNT_rapporto_ambientale.pdf)
colloca San Leonardo nel proprio territorio.

Il lettore ora accetta un titolo senza provincia solo se comune, provincia,
nome e URL della sede coincidono con la localita' del titolo. Eventuali
conflitti restano in revisione. La raccolta reale successiva ha letto **945
record 2026** in 19 pagine, **29 schede attive**, zero revisioni, anteprima
e immagine 2026 anche per la nuova scheda. Il gate e' verde in 42,43 secondi,
entro il limite di 60 secondi della fonte nel job.
