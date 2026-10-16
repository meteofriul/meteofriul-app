# Collegamento UV pilota

Solo progetto meteofriul-pilot-20260906. Nessuna modifica beta.
UV integrato nel job CAMS con PILOT_UV_ENABLED=1: nessun nuovo scheduler,
CPU/memoria/timeout invariati. Il tempo UV consuma parte della finestra CAMS
esistente: va monitorata la durata totale. Nessuna garanzia di tetto fatturazione.

Una richiesta al giorno (corsa 00 UTC; prima delle 10 UTC usa il giorno precedente),
72 ore, sola area FVG. Intent create-only e job persistito evitano duplicazioni.
Ripresa manuale PILOT_UV_RECOVER_EXISTING=1 vieta nuove submission.
Permessi aggiunti alla sola identità pilot-cams: state/uv e weather/v1/uv;
sovrascrittura consentita esclusivamente su UV latest.json.

Parametro CAMS globale 214002 uvbed, istantaneo, moltiplicato per 40.
Eccezione units=~ limitata a quel parametro, come documentato da ECMWF:
https://confluence.ecmwf.int/pages/viewpage.action?pageId=673323626
Non si usa il parametro clear-sky 214003. Validati corsa, 72 ore distinte,
griglia stabile e valori finiti. Payload completo pubblicato atomicamente.

Endpoint: https://pilot-weather-335641913741.europe-west1.run.app/weather/v1/uv/latest.json
La scheda pilota usa il punto di griglia più vicino; è una previsione di modello,
non una misura locale. Dato scaduto dopo 48 ore dalla corsa, zero distinto da
assenza, massimo giornaliero solo con giorno locale completo. Refresh 15 minuti,
orologio di validità ogni minuto. Il campione locale del 5 settembre è escluso.

Prima richiesta reale registrata: 9a10c976-e91c-40e8-9745-7131f73b4a52.
Provider successful verificato. Primo download fallito per autenticazione:
corretto PRIVATE-TOKEN nella sola richiesta ADS, mai inoltrato allo storage.
Test frontend UV/previsioni: 14 superati. Build Linux include test decoder UV.

## Collaudo riuscito

Build corretta d8a0ba23-cd85-4080-bba7-a155ae9eba0c, digest job
sha256:8a61d900def7eb88e58a1a7b09e0486a9a9df92d4f56b1cc508fb9961638517b.
Esecuzione di recupero pilot-cams-sfxnq: UV published, CAMS no_op perché già
aggiornato. Nessuna seconda richiesta ADS. Lettore pilot-weather-00003-7lg.
HTTPS verificato: corsa 6 settembre 00 UTC, 72 ore e 35 punti griglia.
La funzione frontend sul payload reale restituisce zero notturno e massimo del
7 settembre circa 6,0 per Udine e 5,9 per Pordenone (previsione, non misura).
APK non ricostruito in questo intervento: il collegamento UI è nell'anteprima.
