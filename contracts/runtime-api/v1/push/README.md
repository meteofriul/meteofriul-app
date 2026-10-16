# Contratto push v1

Le mutazioni push richiedono sempre `X-Firebase-AppCheck` e non sono endpoint
pubblici anonimi:

- `POST /api/push/devices/register` registra o aggiorna un target Android/Web;
- `POST /api/push/devices/unregister` disattiva l'installazione;
- `POST /api/push/devices/location` aggiorna esclusivamente il target geografico
  di un'installazione Android gia registrata.

La route location accetta `installation_id`, `lat`, `lon`, `accuracy_m`,
`captured_at` e un `trigger` allowlistato. Rifiuta fix oltre 250 m, vecchi oltre
10 minuti, futuri oltre 2 minuti, attestazioni Web e installazioni assenti. Il
servizio applica di nuovo il gate sul confine comunale e risolve Comune/localita
con gli snapshot offline ISTAT/IRDAT.

Latitudine e longitudine servono soltanto durante la richiesta e non sono
salvate nel documento Firestore. La risposta contiene esclusivamente stato,
Comune/localita canonici e l'eventuale eleggibilita agli Avvisi. La transazione
verifica piattaforma e App ID gia registrati: la route non puo iscrivere un
nuovo dispositivo e non modifica token o preferenze.
