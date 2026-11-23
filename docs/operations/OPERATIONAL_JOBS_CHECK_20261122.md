# Controllo operativo del 20–22 novembre 2026

## Perimetro e limiti

Lettura delle esecuzioni e dei riepiloghi Cloud Run dei job di sintesi
mattutina, anticipazione serale ed Eventi; confronto con il catalogo Eventi
pubblico, l'API Eventi e un documento ICON pubblico immutabile. Nessun job
avviato, nessuna notifica inviata, nessuna fonte o risorsa modificata.
Gli esiti `sent` attestano l'accettazione dal sistema di invio, non la
visualizzazione sul telefono. Gli HTTP 200 delle pagine sorgente, ottenuti
dal PC il 22 novembre, non provano il successo dei loro lettori completi
nel job Cloud Run.

## Sintesi mattutina

| Giorno | Esecuzione | Destinatari idonei | Inviati | Errori | `location_changed` | Gruppi con testo ridotto |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 20 novembre | `...-jvb9b` | 66 | 66 | 0 | 0 | 0/24 |
| 21 novembre | `...-fj7jb` | 67 | 67 | 0 | 0 | 25/25 |
| 22 novembre | `...-t7p92` | 66 | 66 | 0 | 0 | 23/23 |

Tutte e tre le esecuzioni sono `Completed=True` e hanno `source_failed=0`,
`security_failed=0`. Il digest distribuito il 19 novembre e ancora in uso
alla generazione 10. Il caso di cambio di posizione del 19 novembre non si e
ripetuto: la classificazione `location_changed` e coperta dai test, ma non
ancora da una nuova occorrenza reale. Il testo ridotto del 21 e 22 indica
che la sintesi ha usato solo i dati meteorologici disponibili e verificati;
non ha esposto nel messaggio la frase tecnica sui campi mancanti.

## Anticipazione serale

| Giorno | Esecuzione | Destinatari idonei | Invii tentati | Gruppi scartati per fonte | Esito |
| --- | --- | ---: | ---: | ---: | --- |
| 20 novembre | `...-c67k8` | 67 | 0 | 26/26 | Fallita |
| 21 novembre | `...-nxzzs` | 66 | 0 | 24/24 | Fallita |
| 22 novembre | `...-r47kj` | 68 | 0 | 24/24 | Fallita |

In tutte le corse il documento ICON e stato letto; i run `12:00 UTC` del
giorno erano entro la soglia di freschezza di 10 ore. Non risultano errori
di dispositivo, storage o sicurezza: `source_failed` corrisponde al rifiuto
della sintesi del giorno successivo, prima di qualunque invio FCM. Il digest
del 19 novembre e ancora in uso alla generazione 7. Questi fallimenti non
sono causati dal nuovo contatore `location_changed`.

Come campione verificabile, il documento ICON pubblico di Pordenone del
run `20261122T120000Z` contiene tutte le 24 ore locali del 23 novembre.
`liquid_rain_mm` e `null` in sei ore (00, 05, 07, 09, 19, 23), con flag di
risoluzione della codifica; temperatura, precipitazione totale, neve, raffiche
e codice nativo sono presenti nel campione. Il lettore mantiene il valore
incerto come `null`, e il compositore serale richiede pioggia numerica in
**ogni** ora: il campione viene quindi scartato. I log mostrano che tutti i
gruppi delle tre corse sono stati scartati; il campione di Pordenone spiega
un caso concreto, non identifica da solo il campo mancante in ogni comune.
Non si deve tradurre il `null` in assenza di pioggia.

## Eventi

La corsa ordinaria del 20 novembre e riuscita. Quelle del 21 e 22 sono
`Completed=False` per verifiche di fonte incomplete:

| Giorno | Fonti che hanno impedito la riuscita |
| --- | --- |
| 21 novembre | Barcolana (timeout lettura calendario), CSS Udine (timeout connessione), TurismoFVG (timeout lettura) |
| 22 novembre | Azalea (timeout), Barcolana (timeout lettura calendario) |

Il job salva il catalogo con i diagnostici e le ultime schede verificate
conservate per il recupero; una fonte marcata `stale` e **esclusa** dalla
risposta degli eventi visibili. La verifica pubblica da Udine del 22
novembre ha restituito HTTP 200, `status=ready`, `catalog_status=degraded`,
snapshot `2026-11-22T05:00:55+01:00`: Azalea e Barcolana `stale`, CSS Udine
`partial`, Teatro Verdi Trieste `fresh`. Galleria Spazzapan resta in pausa.
Il lettore Eventi e il job sono ancora sulle revisioni distribuite il 19
novembre; non risultano aggiornamenti successivi dell'immagine del job.

Le pagine ufficiali di Barcolana, Azalea, CSS Udine e TurismoFVG hanno
risposto HTTP 200 dal PC il 22 novembre. Questo suggerisce di riprovare
**i lettori completi**, non di riattivare le schede senza verifica. I
controlli delle fonti candidate (Attems e GiroFVG) sono stati eseguiti nella
corsa riuscita del 20 novembre; il job interrompe la corsa prima di questi
controlli se una fonte obbligatoria fallisce, come il 21 e 22.

## Prossimi interventi consigliati

1. **Eventi:** prova mirata e in sola lettura dei lettori Azalea e Barcolana,
   e dei timeout CSS/TurismoFVG. Solo se le verifiche passano, ripetere la
   raccolta delle fonti interessate con il gate esistente e controllare API
   e catalogo prima di considerarle recuperate. Non sospendere le fonti solo
   per nascondere l'allarme.
2. **Serale:** analizzare la frequenza e le cause dei `null` ICON. Progettare
   nel ramo notifiche un testo ridotto basato soltanto su campi completi e
   verificati, come la temperatura se la copertura oraria basta; se neppure
   questo e possibile, non inviare e mantenere un segnale operativo chiaro.
   Una correzione deve avere test con documenti reali anonimizzati e prova
   controllata prima del deploy.
3. **Monitoraggio:** separare nei riepiloghi `fonte letta ma qualita
   insufficiente` da `fonte irraggiungibile`, e mostrare nel pannello la
   fonte e il suggerimento operativo. I fallimenti che impediscono tutte le
   notifiche serali o riducono il catalogo Eventi devono restare visibili.

Nessuna versione o artefatto Web/Android, pannello, Scheduler o policy di
Monitoring e stato modificato durante questo controllo.
