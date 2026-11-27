# Eventi: verifica TurismoFVG del 27 novembre 2026

## Stato osservato

Questa è evidenza datata, non un'autorizzazione a rilanciare il job. Il
controllo ha letto Cloud Run, Cloud Logging, Storage e l'API pubblica senza
modificare pianificazioni, policy o il ramo Mercati.

La struttura di osservazione esiste già: il job Eventi registra il riepilogo
`event_source_verification`, il recupero `event_source_recovered` e i guasti
`event_source_failure` in Cloud Logging. La policy del fallimento Eventi è
abilitata. Il canale di notifica è assente per scelta del riordino operativo
del 22 novembre; la presenza della policy da sola non prova un recapito.
Non è necessaria una nuova struttura generale di log per diagnosticare questo
incidente.

Le corse ordinarie del 25, 26 e 27 novembre alle 04:00 UTC sono terminate con
`Completed=False`; quella del 24 novembre era riuscita. Il 27 novembre
TurismoFVG è l'unica fonte attiva indisponibile. Galleria Spazzapan è in pausa
per controllo fonte, non è un errore nuovo. Le altre fonti attive sono `fresh`
o `partial` e le schede in revisione restano separate dai lotti `stale`.

TurismoFVG ha avuto un inventario di 1.599 dettagli il 27 novembre. Il
checkpoint del tentativo contiene 1.027 risultati e 572 non ancora verificati;
576 letture strutturate sono riuscite nella corsa, senza letture fallite, prima
della riserva del budget di 335 secondi della fonte. Il 26 novembre i dettagli
pendenti erano 98. Il checkpoint pubblicato e validato del 24 novembre resta
separato dal tentativo incompleto.

Una sola ripresa mirata con `--source TurismoFVG`, avviata il 27 novembre alle
07:31 UTC, è terminata alle 07:35 UTC con `Completed=False`: `ReadTimeout`
di 15 secondi durante la lettura della fonte. La versione corrente registra
host e tipo dell'errore, ma non la fase né il numero della pagina; perciò non
è dimostrato che il timeout riguardasse una pagina numerata del calendario.
Questo tentativo non ha sovrascritto i checkpoint: il validato resta a
1.532/1.532 del 24 novembre e il tentativo del 27 a 1.027/1.599. Le altre
fonti conservano i lotti della corsa ordinaria del 27 novembre.

L'API pubblica, provata su un punto cittadino di Udine, risponde HTTP 200 e
`ready`, ma `catalog_status=degraded` e TurismoFVG `stale`/`adapter_exception`:
le sue vecchie schede non sono esposte. Una lettura isolata della prima pagina
ufficiale dopo il timeout ha risposto HTTP 200 in circa due secondi; non prova
che tutte le pagine della ricerca siano disponibili.

Una sola riproduzione locale, senza Storage e senza dettagli, ha letto la
finestra 27 novembre–31 dicembre con quattro richieste concorrenti e limite
di 300 GET. Si è fermata dopo 218 GET in 196,7 secondi: è stato osservato un
`ReadTimeout` della pagina numerata 183, poi una `ValueError` di verifica.
L'output limitato della prova non conserva il messaggio della `ValueError`,
quindi non se ne deduce quale controllo abbia fallito. Il timeout della pagina
183 è stato seguito da un retry: la prova non dimostra che i retry siano
esauriti su quella pagina né identifica la pagina del timeout cloud.

## Candidato locale e limite

Nel ramo `codex/events-turismofvg-numbered-timeout-20261127`, da `main`
`9442ce97`, il candidato tratta un `ReadTimeout` **dopo i retry esistenti e
solo su una pagina numerata** come il 404 numerato già recuperabile tramite
partizioni di date. Restano obbligatori il confronto dei totali e l'unione
esatta; una partizione incompleta continua a fallire senza pubblicare dati.
Un timeout della pagina iniziale o dei dettagli non attiva il recupero.

I 195 test regionali, `compileall` del file modificato e `git diff --check`
sono passati. I test nuovi coprono la pagina numerata, la propagazione di un
errore della partizione e il timeout della pagina iniziale. Questi test sono
offline e **non dimostrano** che il timeout cloud osservato ricada nel caso
corretto. Il candidato non è stato distribuito, il job non è stato ripetuto
dopo l'unico tentativo mirato e l'app non è stata pubblicata.

La suite backend completa eseguita con il Python globale 3.13.5 ha contato
2.113 test, con due fallimenti nel test di sicurezza XML di `lxml` 5.4.0.
Lo stesso test fallisce su una worktree senza il diff Eventi e con lo stesso
codice backend di `main`; non riguarda il candidato. Non è stato modificato
né sostituito `lxml` per occultare il
fallimento. Un ambiente CI con dipendenze prescritte resta una verifica
necessaria prima di promuovere il candidato.

## Verifiche necessarie prima della promozione

1. Stabilire con una riproduzione isolata se il timeout riguarda una pagina
   numerata del calendario. Se riguarda la radice, la sitemap o i dettagli,
   scegliere una correzione diversa; non aumentare i retry alla cieca.
2. Collaudare la correzione su un catalogo QA separato e verificare il
   checkpoint e i conteggi, senza scrivere il catalogo pubblico.
3. Solo dopo CI e collaudo, aggiornare il solo job Eventi. Confrontare
   esecuzione, generazione Storage, stati delle 15 fonti e API prima di
   dichiarare recuperata TurismoFVG.
