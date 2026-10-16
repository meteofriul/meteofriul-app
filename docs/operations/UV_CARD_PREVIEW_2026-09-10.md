# Card UV — rifinitura dell'anteprima, 10 settembre 2026

Base: `2d80ef0`. Intervento frontend separato dalla diagnosi CAMS e dal sito.

- Valore previsto per l'ora corrente e picco giornaliero distinti, senza riquadro interno.
- Curva dei campioni orari reali di oggi in Europe/Rome, pallino sul campione
  corrente e picco nel suo orario effettivo. Nessuna campana sintetica,
  interpolazione del valore UV o massimo giornaliero per una giornata incompleta.
- Scala continua con cursore del valore corrente; categorie e arrotondamento
  esistenti invariati. I valori estremi non sono troncati nel testo.
- Consigli brevi con icone. Nessuna nuova prescrizione SPF o promessa universale
  di protezione non necessaria. Il consiglio resta riferito al picco giornaliero,
  se disponibile, non al solo valore serale. Riferimento consultato:
  [OMS, indice UV e protezione](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-%28uv%29-index).
- Footer a una riga; fonte, data della previsione, corsa e legenda completa
  consultabili attraverso un disclosure nativo accessibile, inizialmente chiuso.
- IT/FUR; nessun cambiamento a validità di 48 ore, cache, timer, endpoint,
  acquisizioni, backend, scheduler, ICON, notifiche o Android.

## Verifiche

Da `frontend`:

```powershell
npm run test -- src/features/weather/WeatherUvCard.test.jsx src/features/weather/uvForecast.test.js src/features/weather/uvForecastRuntime.test.js src/features/weather/WeatherForecastView.test.jsx
# 48 superati, 0 falliti, 0 saltati; quattro file nella stessa sessione.

npm run lint
# Exit 0, nessun errore o avviso.

npx vite build --mode local-pilot --configLoader native --outDir "$env:TEMP\meteofriul-uv-card-20260910-1612"
# Bloccato dal controllo esistente: local_weather_pilot_is_development_only_no_build.
# Nessuna modifica o elusione del controllo; nessun pacchetto pilota generato.

npx vite build --configLoader native --outDir "$env:TEMP\meteofriul-uv-card-20260910-1614"
# Compilazione web di produzione riuscita, exit 0, output temporaneo.
# Non è una build/rilascio Android né un deploy della web app.
```

Test aggiunti: campioni reali senza trasformazioni, cambio d'ora, mezzanotte
locale, giorni DST di 23/25 ore, giornata parziale, zeri validi, primo massimo
a pari valore/non necessariamente a mezzogiorno, serie accessibile IT/FUR,
posizione dei marker, valori estremi e assenza di grafica dopo scadenza.
Restano eseguiti i test runtime preesistenti su cache, errori e validità.
La suite diagnostica CAMS isolata del commit precedente non è parte di questa
verifica e il suo difetto noto non è modificato né dichiarato risolto.

Verifica manuale nel browser su `http://127.0.0.1:5174/`, con i dati già
pubblicati: valore orario 0,8 alle 16:00, picco 1,4 alle 12:00; apertura/chiusura
fonte e dettagli, IT/FUR, viewport stretto di 360 px e ripristino del viewport.
Anteprima lasciata in italiano. Nessuna acquisizione ADS, test live opt-in,
installazione sul telefono, pubblicazione o push.

## Avvisi della compilazione, non modificati

1. Avviso preesistente sugli import:

```text
[INEFFECTIVE_DYNAMIC_IMPORT] src/features/almanac/AlmanacView.jsx is dynamically imported by src/app/AppRoutes.jsx but also statically imported by src/features/weather/WeatherSkyCard.jsx, dynamic import will not move module into another chunk.
```

2. Avviso preesistente sulla dimensione dei chunk:

```text
[plugin builtin:vite-reporter]
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
```

3. Avviso relativo all'output temporaneo esterno al progetto:

```text
(!) outDir C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-uv-card-20260910-1614 is not inside project root and will not be emptied.
Use --emptyOutDir to override.
```

Nessuna soglia alzata, nessun controllo disattivato, nessuna cancellazione
dell'output temporaneo preesistente.
