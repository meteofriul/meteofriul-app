"""Explicit weather-code meaning and capability gaps for the isolated pilot.

WW labels follow the DWD ICON Database Reference Manual, table 6.1, and its
cloud-cover fallback (0..3), checked 2026-09-03:
https://www.dwd.de/SharedDocs/downloads/DE/modelldokumentationen/nwv/icon/icon_dbbeschr_aktuell.pdf

WW describes significant weather during the PREVIOUS HOUR, not an observation
at the current minute. Code 96 includes either hail OR a heavy thunderstorm.
Code 99 is not assumed for ICON-2I just because ICON-D2 can produce it. This
mapping is a conservative pilot interpretation, not a production validation of
ItaliaMeteo's entire WW post-processing chain. There are no app imports or I/O.
"""

import math
from numbers import Real


_CONDITIONS_IT = {
    0: "Sereno",
    1: "Poco nuvoloso",
    2: "Parzialmente nuvoloso",
    3: "Molto nuvoloso o coperto",
    45: "Nebbia",
    48: "Nebbia con deposito di brina",
    51: "Pioviggine debole",
    53: "Pioviggine moderata",
    55: "Pioviggine intensa",
    56: "Pioviggine gelata debole",
    57: "Pioviggine gelata moderata o intensa",
    61: "Pioggia debole",
    63: "Pioggia moderata",
    65: "Pioggia intensa",
    66: "Pioggia gelata debole",
    67: "Pioggia gelata moderata o intensa",
    71: "Nevicata debole",
    73: "Nevicata moderata",
    75: "Nevicata intensa",
    77: "Granuli di neve",
    80: "Rovesci di pioggia deboli",
    81: "Rovesci di pioggia moderati o intensi",
    82: "Rovesci di pioggia violenti",
    85: "Rovesci di neve deboli",
    86: "Rovesci di neve moderati o intensi",
    95: "Temporale debole o moderato",
    96: "Temporale con grandine o temporale forte",
}


def icon_condition(raw):
    """Return code/Italian label/status/period without a clear-sky fallback.

    Known finite integer-valued numbers (including 61.0) are ``valid``. Other
    integer codes are ``unknown`` and retained for diagnosis. Non-numbers,
    booleans, non-finite numbers and fractional codes are ``invalid`` with a
    null code. Unknown/invalid values have an explicit unavailable label.
    Status ``valid`` means the mapping is recognized, not meteorological truth.
    """
    result = {
        "code": None,
        "label": "Condizione meteo non disponibile",
        "status": "invalid",
        "period": "previous_hour",
    }
    if isinstance(raw, bool) or not isinstance(raw, Real):
        return result
    try:
        numeric = float(raw)
    except (OverflowError, ValueError):
        return result
    if not math.isfinite(numeric) or not numeric.is_integer():
        return result
    code = int(raw)
    if raw != code:
        return result
    result["code"] = code
    if code not in _CONDITIONS_IT:
        result.update(status="unknown", label="Codice meteo non riconosciuto nel pilota ICON-2I")
    else:
        result.update(status="valid", label=_CONDITIONS_IT[code])
    return result


def pilot_capabilities():
    """Return a new list describing pilot support AND every known major gap.

    This is a scope manifest, not a live health check: ``experimental`` indicates
    the pipeline can process the field under documented checks, not that today's
    remote download succeeded. Consumers must also inspect actual data quality.
    ``missing``, ``blocked``, ``pending``, ``unchanged`` and ``local_catalog`` are
    deliberately not upgraded to supported or silently filled from Open-Meteo.
    """
    definitions = (
        ("temperature", "Temperatura a 2 metri", "experimental", "ICON-2I T_2M, dato previsto sul punto di griglia più vicino; nessuna correzione altimetrica locale."),
        ("apparent_temperature", "Temperatura apparente", "experimental", "Steadman/BOM all'ombra da T2m, umidità derivata e vento a 10 m; non osservazione, non indice composito Heat Index/Wind Chill."),
        ("pressure_msl", "Pressione al livello del mare", "experimental", "ICON-2I PMSL convertita in hPa; non pressione alla quota del Comune."),
        ("relative_humidity", "Umidità relativa derivata", "experimental", "Approssimazione Magnus su acqua da T_2M e TD_2M; non un campo RH2m nativo scaricato."),
        ("wind", "Vento a 10 metri", "experimental", "Velocità e direzione da U_10M/V_10M dopo verifica dell'orientamento terrestre della griglia."),
        ("wind_gust", "Raffica massima oraria", "experimental", "ICON-2I VMAX_10M; il periodo di massimo deve coincidere con l'ora precedente, verificato dai metadati GRIB."),
        ("cloud_cover", "Copertura nuvolosa", "experimental", "ICON-2I CLCT; percentuale prevista di copertura totale, distinta dal codice di tempo significativo."),
        ("weather_condition", "Condizione meteo e icona", "experimental", "Interpretazione WW secondo la tabella DWD ICON 6.1: fenomeni dell'ora precedente; codici ignoti restano espliciti, senza ripiego su sereno."),
        ("precipitation_amount", "Quantità di precipitazione", "experimental", "Differenze fra accumuli della stessa corsa; cambi nonzero entro la risoluzione combinata restano nulli. I soli reference floor code-0 inferiori alla precisione numerica di un quantum sono normalizzati esplicitamente; mai asciutto inventato da un decremento."),
        ("precipitation_phase", "Componenti liquide e solide", "experimental", "Componenti di precipitazione espresse in equivalente d'acqua; la neve non viene convertita arbitrariamente in centimetri al suolo."),
        ("precipitation_probability", "Probabilità di precipitazione", "missing", "La corsa deterministica ICON-2I non fornisce qui una probabilità calibrata; quantità e WW non vengono trasformati in percentuali inventate."),
        ("visibility", "Visibilità", "missing", "Campo di visibilità non disponibile nel set pubblico verificato per questo pilota; la presenza di nebbia in WW non equivale a una distanza di visibilità."),
        ("cams_pollen", "Pollini CAMS", "blocked", "Download reale non eseguito: occorrono credenziali ADS/CAMS e accettazione delle condizioni del dataset da parte dell'utente; nessun dato fittizio."),
        ("five_day_forecast", "Previsione a cinque giorni", "missing", "Cinque giorni superano l'orizzonte nativo di 72 ore della corsa ICON-2I; non si estende artificialmente la previsione."),
        ("official_bulletin", "Bollettino ufficiale OSMER", "unchanged", "Resta OSMER nell'app operativa; il pilota non sostituisce o riscrive il bollettino ufficiale."),
        ("official_alerts", "Allerte ufficiali", "unchanged", "Resta il circuito ufficiale della Protezione Civile; il pilota ICON non emette né modifica allerte."),
        ("observations_comparison", "Confronto con osservazioni", "pending", "Validazione su più corse contro osservazioni reali ancora da svolgere; elaborazione riuscita non significa accuratezza meteorologica dimostrata."),
        ("geocoding", "Catalogo locale dei Comuni", "local_catalog", "Coordinate lette dal catalogo locale, originariamente geocodificato con Open-Meteo; nessuna chiamata geocoding live, provenienza non cancellata."),
    )
    return [dict(zip(("id", "label", "status", "detail"), definition)) for definition in definitions]
