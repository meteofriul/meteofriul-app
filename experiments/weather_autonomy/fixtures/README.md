# Snapshot locale della pilota

`local-pilot-snapshot-20260904.zip` contiene esclusivamente i quattro artefatti
ICON/CAMS gia' verificati usati dal fallback offline della app pilota:

- payload ICON e relativo report;
- payload CAMS e relativo report.

Il launcher `scripts/start-local-weather-pilot.ps1` estrae soltanto gli
artefatti mancanti in `.dev-logs/weather-v1/`, verifica lo SHA-256 di ciascun
file e lascia che il writer ricrei l'Object DB locale. Il pacchetto non contiene
database, log, chiavi, configurazioni locali o credenziali.

Questa fixture rende riproducibile una clone pulita quando il reader cloud non
e' disponibile. Non e' una fonte meteo corrente e deve essere usata soltanto
con l'orologio di test dichiarato nella procedura di avvio.
