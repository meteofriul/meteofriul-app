import { Loader2, MapPin, Search, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";

import {
  appendStoredRecentLocation,
  readStoredRecentLocations,
  removeStoredRecentLocation,
} from "../../app/appLocation";
import {
  getLocationDisplayName,
  getMunicipalityDisplayName,
} from "../../domain/geo/locationDisplayName";
import { hasDistinctLocality } from "../../domain/geo/locationIdentity";
import {
  getLocalFvgLocationResults,
  mergeVerifiedMunicipalityResults,
  searchLocations,
  searchVerifiedMunicipalities,
} from "../../services/locationSearch";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { toAppLocation, toPlaceRecord } from "./locationPlaceRecords";
import { buildLocationSheetShortcuts, filterUniqueLocationPlaces, getLocationPlaceKey } from "./locationSheetLists";
import { createLocationSelectionController } from "./locationSelectionController";

const EMPTY_SELECTION_FEEDBACK = Object.freeze({
  locationName: "",
  status: "idle",
});

const COPY = {
  it: {
    close: "Chiudi",
    current: "Localita attiva",
    eyebrow: "Meteo locale",
    placeholder: "Cerca comune",
    quick: "Comuni rapidi",
    noResults: "Nessun comune trovato",
    searching: "Ricerca in corso",
    searchUnavailable: "La ricerca nazionale non è momentaneamente raggiungibile. Riprova tra poco.",
    selectionError: "Non riesco a caricare i dati meteo per {name}. Riprova.",
    selectionLoading: "Carico i dati meteo per {name}...",
    recent: "Recenti",
    removeRecent: "Rimuovi localita",
    clearSearch: "Cancella ricerca",
    municipality: "Comune di {name}",
    title: "Cambia localita",
  },
  fur: {
    close: "Siere",
    current: "Localitat ative",
    eyebrow: "Meteo local",
    placeholder: "Cir comun",
    quick: "Comuns rapits",
    noResults: "Nissun comun cjatat",
    searching: "Ricercje in cors",
    searchUnavailable: "La ricercje nazionâl no je disponibil cumò. Torne prove chi di pôc.",
    selectionError: "No rivi a cjariâ i dâts meteo par {name}. Torne prove.",
    selectionLoading: "Daûr a cjariâ i dâts meteo par {name}...",
    recent: "Recents",
    removeRecent: "Gjave localitat",
    clearSearch: "Nete ricercje",
    municipality: "Comun di {name}",
    title: "Cambie localitat",
  },
};

function getCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function normalizeText(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function LocationResult({
  copy,
  disabled = false,
  language,
  onRemove,
  onSelect,
  place,
  removable = false,
}) {
  const displayName = getLocationDisplayName(place, language) || place.name;
  const municipalityName = getMunicipalityDisplayName(place, language);
  const pilot = isDefinitiveAppExperience();
  const provinceLabel = String(
    place.province || place.municipality?.province
      || place.provinceName || place.municipality?.provinceName || "",
  ).trim();
  const title = pilot && provinceLabel ? `${displayName} (${provinceLabel})` : displayName;
  const countryFallback = String(place.country || place.countryName || "").trim()
    || (String(place.countryCode || "").trim().toUpperCase() === "IT" ? "Italia" : "");
  const secondaryLabel = hasDistinctLocality(place) && municipalityName
    ? copy.municipality.replace("{name}", municipalityName)
    : pilot
      ? [place.admin1 || place.region, countryFallback].filter(Boolean).join(" · ")
      : [place.provinceName, place.province].filter(Boolean).join(" · ")
      || place.admin1
      || countryFallback;

  return (
    <div className="mf-location-result">
      <button
        className="mf-location-result__main"
        disabled={disabled}
        onClick={() => onSelect?.(place)}
        type="button"
      >
        <span className="mf-location-result__icon">
          <MapPin aria-hidden="true" size={17} strokeWidth={2.3} />
        </span>
        <span className="mf-location-result__copy">
          <strong>{title}</strong>
          <small>{secondaryLabel}</small>
        </span>
      </button>
      {removable ? (
        <button
          aria-label={`${copy.removeRecent}: ${displayName}`}
          className="mf-location-result__remove"
          disabled={disabled}
          onClick={() => onRemove?.(place)}
          title={`${copy.removeRecent}: ${displayName}`}
          type="button"
        >
          <Trash2 aria-hidden="true" size={16} strokeWidth={2.35} />
        </button>
      ) : null}
    </div>
  );
}

export function LocationSearchSheet({
  activeLocation,
  isOpen,
  language = "it",
  onClose,
  onLocationSelect,
}) {
  const copy = getCopy(language);
  const inputRef = useRef(null);
  const selectionControllerRef = useRef(null);
  if (selectionControllerRef.current === null) {
    selectionControllerRef.current = createLocationSelectionController();
  }
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [resultsQuery, setResultsQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchUnavailable, setSearchUnavailable] = useState(false);
  const [recentLocations, setRecentLocations] = useState(() => readStoredRecentLocations());
  const [selectionFeedback, setSelectionFeedback] = useState(EMPTY_SELECTION_FEEDBACK);
  const selectionBusy = selectionFeedback.status === "loading";
  const cleanQuery = normalizeText(query);
  const localSearchResults = useMemo(
    () => (cleanQuery.length >= 2 ? getLocalFvgLocationResults(query) : []),
    [cleanQuery.length, query],
  );
  const recentPlaces = recentLocations.map(toPlaceRecord);
  const { visibleRecentPlaces, quickPlaces } = buildLocationSheetShortcuts({
    activeLocation,
    recentPlaces,
    pilot: isDefinitiveAppExperience(),
  });
  const searchPlaces = resultsQuery === cleanQuery && results.length > 0 ? results : localSearchResults;
  const searchResultPlaces = filterUniqueLocationPlaces(searchPlaces, { activeLocation });
  const visibleResults = cleanQuery.length >= 2 ? searchResultPlaces : quickPlaces;
  const showSpinner = cleanQuery.length >= 2 && isSearching;
  const showRecentPlaces = cleanQuery.length < 2 && visibleRecentPlaces.length > 0;
  const showQuickPlaces = cleanQuery.length < 2 && quickPlaces.length > 0;
  const showEmptyResults = cleanQuery.length >= 2
    ? visibleResults.length === 0 && !showSpinner
    : !visibleRecentPlaces.length && !quickPlaces.length;
  const showNoResults = showEmptyResults && !searchUnavailable;

  const handleClose = useCallback(() => {
    if (selectionControllerRef.current?.pending) return;
    setQuery("");
    setResults([]);
    setResultsQuery("");
    setIsSearching(false);
    setSearchUnavailable(false);
    setSelectionFeedback(EMPTY_SELECTION_FEEDBACK);
    onClose?.();
  }, [onClose]);

  usePilotBackHandler(handleClose, isOpen);

  const handleClearSearch = () => {
    setQuery("");
    setResults([]);
    setResultsQuery("");
    setIsSearching(false);
    setSearchUnavailable(false);
    setSelectionFeedback(EMPTY_SELECTION_FEEDBACK);
    inputRef.current?.focus();
  };

  const handleQueryChange = (value) => {
    setQuery(value);
    setSearchUnavailable(false);
    if (selectionFeedback.status === "error") {
      setSelectionFeedback(EMPTY_SELECTION_FEEDBACK);
    }

    if (normalizeText(value).length < 2) {
      setResults([]);
      setResultsQuery("");
      setIsSearching(false);
    }
  };

  const handleLocationPick = async (place) => {
    if (selectionControllerRef.current.pending) return;
    const nextLocation = toAppLocation(place);
    const locationName = getLocationDisplayName(nextLocation, language) || nextLocation.city;

    setSelectionFeedback({ locationName, status: "loading" });
    const result = await selectionControllerRef.current.select(nextLocation, onLocationSelect);
    if (result.status === "busy") return;
    if (result.status === "error") {
      setSelectionFeedback({ locationName, status: "error" });
      return;
    }

    setRecentLocations(appendStoredRecentLocation(nextLocation));
    handleClose();
  };

  const handleRecentRemove = (place) => {
    setRecentLocations(removeStoredRecentLocation(toAppLocation(place)));
  };

  useEffect(() => {
    if (!isOpen) return undefined;

    const frame = requestAnimationFrame(() => {
      setRecentLocations(readStoredRecentLocations());
      inputRef.current?.focus();
    });
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        handleClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [handleClose, isOpen]);

  useEffect(() => {
    if (!isOpen || cleanQuery.length < 2) {
      return undefined;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setIsSearching(true);
      const [ordinaryResult, verifiedResult] = await Promise.allSettled([
        searchLocations(query),
        searchVerifiedMunicipalities(query),
      ]);
      if (!cancelled) {
        const ordinary = ordinaryResult.status === "fulfilled" ? ordinaryResult.value : [];
        const verified = verifiedResult.status === "fulfilled" ? verifiedResult.value : [];
        setResults(verified.length
          ? mergeVerifiedMunicipalityResults(ordinary, verified, { query })
          : ordinary);
        setResultsQuery(cleanQuery);
        setSearchUnavailable(ordinaryResult.status === "rejected" && verifiedResult.status === "rejected");
        setIsSearching(false);
      }
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [cleanQuery, isOpen, query]);

  const activeCity = getLocationDisplayName(activeLocation, language) || "Udine";
  const activeMunicipality = getMunicipalityDisplayName(activeLocation, language);
  const activeMunicipalityLabel = hasDistinctLocality(activeLocation) && activeMunicipality
    ? copy.municipality.replace("{name}", activeMunicipality)
    : "";
  const resultLabel = cleanQuery.length >= 2 ? query : copy.quick;

  if (!isOpen) return null;

  const content = (
    <div className="mf-location-sheet" role="dialog" aria-modal="true" aria-labelledby="location-search-title">
      <button
        aria-label={copy.close}
        className="mf-location-sheet__backdrop"
        disabled={selectionBusy}
        onClick={handleClose}
        type="button"
      />
      <section aria-busy={selectionBusy ? "true" : "false"} className="mf-location-sheet__panel">
        <div className="mf-location-sheet__handle" aria-hidden="true" />
        <div className="mf-location-sheet__header">
          <div>
            <span>{copy.eyebrow}</span>
            <h2 id="location-search-title">{copy.title}</h2>
            <p>{copy.current}: {activeCity}</p>
            {activeMunicipalityLabel ? (
              <p className="mf-location-sheet__municipality">{activeMunicipalityLabel}</p>
            ) : null}
          </div>
          <button
            aria-label={copy.close}
            className="mf-location-sheet__close"
            disabled={selectionBusy}
            onClick={handleClose}
            type="button"
          >
            <X aria-hidden="true" size={19} strokeWidth={2.35} />
          </button>
        </div>

        <div className="mf-location-search">
          <Search aria-hidden="true" size={18} strokeWidth={2.35} />
          <input
            aria-label={copy.placeholder}
            disabled={selectionBusy}
            ref={inputRef}
            value={query}
            onChange={(event) => handleQueryChange(event.target.value)}
            placeholder={copy.placeholder}
            type="search"
          />
          {showSpinner ? <Loader2 aria-hidden="true" className="mf-location-search__spinner" size={16} /> : null}
          {query ? (
            <button
              aria-label={copy.clearSearch}
              className="mf-location-search__clear"
              disabled={selectionBusy}
              onClick={handleClearSearch}
              type="button"
            >
              <X aria-hidden="true" size={16} strokeWidth={2.35} />
            </button>
          ) : null}
        </div>

        {selectionFeedback.status !== "idle" ? (
          <p
            aria-live={selectionFeedback.status === "error" ? "assertive" : "polite"}
            className="mf-location-selection-feedback"
            role={selectionFeedback.status === "error" ? "alert" : "status"}
          >
            {copy[
              selectionFeedback.status === "error" ? "selectionError" : "selectionLoading"
            ].replace("{name}", selectionFeedback.locationName)}
          </p>
        ) : null}

        <div className="mf-location-results" aria-label={resultLabel}>
          {showRecentPlaces ? (
            <>
              <span className="mf-location-results__title">{copy.recent}</span>
              {visibleRecentPlaces.map((place) => (
                <LocationResult
                  copy={copy}
                  disabled={selectionBusy}
                  language={language}
                  key={`recent-${getLocationPlaceKey(place)}`}
                  onRemove={handleRecentRemove}
                  onSelect={handleLocationPick}
                  place={place}
                  removable
                />
              ))}
            </>
          ) : null}
          {showQuickPlaces ? <span className="mf-location-results__title">{copy.quick}</span> : null}
          {visibleResults.map((place) => (
            <LocationResult
              copy={copy}
              disabled={selectionBusy}
              language={language}
              key={getLocationPlaceKey(place)}
              onSelect={handleLocationPick}
              place={place}
            />
          ))}
          {searchUnavailable ? (
            <p className="mf-location-results__empty" role="alert">{copy.searchUnavailable}</p>
          ) : null}
          {showNoResults ? (
            <p className="mf-location-results__empty">{copy.noResults}</p>
          ) : null}
        </div>
      </section>
    </div>
  );

  return createPortal(content, document.body);
}
