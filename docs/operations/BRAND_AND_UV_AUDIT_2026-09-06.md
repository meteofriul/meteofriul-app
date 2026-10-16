# Pilota: icone e avvio UV

Nota storica: per il launcher questo rapporto è superato dal riferimento
del 9 settembre in `android/launcher-assets/README.md`. Il vecchio generatore
qui citato è ritirato e i PNG launcher obsoleti sono recuperabili solo da Git.

## Marchio e telefono

Pacchetto separato `android/launcher-assets/pilot-092026`: 43 asset,
hash verificati senza differenze. Dimensioni derivate dall'inventario approvato
082026, che resta immutato. Prompt e master sono documentati nel README del
nuovo pacchetto. Elaborazione AI per eliminare il bianco esterno, quindi
derivazione meccanica delle misure attraverso `scripts/package-pilot-brand.ps1`.
Launcher Android, round, adaptive, monochrome, notifica, splash, Play e web
preparati; solo le risorse localPilot e l'header pilota sono collegate.
Non è una pubblicazione Play né una modifica alla beta.

Sul telefono verificati home, avvio a freddo e header: bordo bianco assente.
Non verificati visivamente sul dispositivo i singoli temi monocromatici o
una notifica reale. APK installato: vedi audit Eventi della stessa data.

## UV: campione reale, non ancora funzionalità pubblicata

Richiesta ADS già esistente `e8729638-0fec-4570-b5ed-bd32c0817363` riuscita.
Nessuna nuova richiesta creata. Scaricato GRIB di 3648 byte in
`experiments/weather_autonomy/uv-pilot-local/source.grib`.
Lettura con ecCodes 2.48.0 in ambiente temporaneo isolato:
24 istanti distinti del 6 settembre, corsa 5 settembre 00 UTC, 15 punti griglia.
Parametro `214002`, `uvbed`, `stepType=instant`.

Attenzione: ecCodes restituisce `units=~` nel campione. Il lettore diagnostico
conserva questa evidenza; non accetta genericamente unità sconosciute in produzione.
La documentazione ECMWF identifica questo parametro in W/m² e indica il fattore
40 per l'indice UV. Calcolo diagnostico verificato, non pubblicato come dato attuale.

Fonte primaria:
https://confluence.ecmwf.int/spaces/CKB/pages/212454117/CAMS+Global+atmospheric+composition+forecast+data+documentation

Restano acquisizione automatica UV, contratto dati con validazione esplicita
del parametro/unità, gestione validità e integrazione UI. Nessuno scheduler UV
creato e nessun dato campione inserito nella previsione del telefono.
