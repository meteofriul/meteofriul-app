# Preview pilota: collegamenti del 7 settembre

La preview Vite `local-pilot` usa il reader meteo cloud pilota già operativo,
non lo snapshot SQLite del 4 settembre. Nessun job, deploy o modifica beta.
Override per prove offline: `VITE_LOCAL_WEATHER_PROXY_TARGET=http://127.0.0.1:8781`.
Il server Vite deve avere accesso HTTPS; una partenza senza rete produce 502.

Verifiche attraverso la preview 5176:
- ICON e famiglia CAMS: corsa 7 settembre 00 UTC.
- UV: corsa 6 settembre, orizzonte fino all'8 settembre; non dichiarata corsa odierna.
- API locale: bollettino, allerte, webcam HTTP 200; radar Trieste fresh, 2 prodotti;
  eventi Trieste 65 record.
- 27 test passati, inclusi 2 test reali del client con orologio reale e dati
  aria/pollini, anche con aggiornamento differito.
- Browser: Home Tarvisio mostra 23 °C, vento, umidità, pressione, graminacee,
  evoluzione oraria, bollettino e 3 eventi. Pioggia corrente non disponibile:
  il collegamento non autorizza a inventare i singoli dati mancanti.

Push e funzioni native non sono abilitate da questo intervento. Le verifiche
HTTP non certificano ogni immagine webcam o ogni fotogramma radar.
