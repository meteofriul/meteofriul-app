const MAX_DESCRIPTION_LENGTH = 360;

function cleanText(value) {
  return String(value || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .trim();
}

function truncateText(value, maxLength = MAX_DESCRIPTION_LENGTH) {
  const text = cleanText(value);
  if (text.length <= maxLength) return text;

  const truncated = text.slice(0, maxLength + 1);
  const lastSpace = truncated.lastIndexOf(" ");
  const boundary = lastSpace >= Math.floor(maxLength * 0.72) ? lastSpace : maxLength;
  return `${truncated.slice(0, boundary).trimEnd()}…`;
}

function getSafeHttpsUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    return url.protocol === "https:" ? url.toString() : "";
  } catch {
    return "";
  }
}

function getTrustedMapsUrl(value) {
  const safeUrl = getSafeHttpsUrl(value);
  if (!safeUrl) return "";

  const url = new URL(safeUrl);
  const host = url.hostname.toLowerCase();
  const isGoogleMapsHost = host === "google.com" || host.endsWith(".google.com");
  const isGoogleMapsShortLink = host === "maps.app.goo.gl"
    || (host === "goo.gl" && url.pathname.toLowerCase().startsWith("/maps"));

  if (isGoogleMapsHost && url.pathname.toLowerCase().includes("/maps")) return safeUrl;
  if (isGoogleMapsShortLink) return safeUrl;
  return "";
}

function isFiniteCoordinate(value, minimum, maximum) {
  const number = Number(value);
  return Number.isFinite(number) && number >= minimum && number <= maximum;
}

function uniqueParts(values) {
  const seen = new Set();

  return values.reduce((parts, value) => {
    const text = cleanText(value);
    const key = text.toLocaleLowerCase("it-IT");
    if (!text || seen.has(key)) return parts;
    seen.add(key);
    parts.push(text);
    return parts;
  }, []);
}

function uniqueLocationParts(values) {
  return uniqueParts(values).reduce((parts, value) => {
    const key = value.toLocaleLowerCase("it-IT");
    const repeatsExistingDetail = parts.some((part) => (
      key.includes(part.toLocaleLowerCase("it-IT"))
    ));
    if (!repeatsExistingDetail) parts.push(value);
    return parts;
  }, []);
}

function getDescriptionData(event) {
  const raw = event?.raw || {};
  const title = cleanText(event?.title).toLocaleLowerCase("it-IT");
  const attributedExcerpt = truncateText(raw.description_excerpt);
  if (attributedExcerpt && attributedExcerpt.toLocaleLowerCase("it-IT") !== title) {
    return {
      description: attributedExcerpt,
      descriptionSourceName: cleanText(raw.description_source_name),
      descriptionSourceUrl: getSafeHttpsUrl(raw.description_source_url),
    };
  }
  const candidates = [
    raw.description,
    raw.summary,
    raw.context,
    raw.text,
  ];

  for (const candidate of candidates) {
    const description = truncateText(candidate);
    if (description && description.toLocaleLowerCase("it-IT") !== title) {
      return { description, descriptionSourceName: "", descriptionSourceUrl: "" };
    }
  }

  return { description: "", descriptionSourceName: "", descriptionSourceUrl: "" };
}

function getPageUrl(event) {
  const raw = event?.raw || {};
  return getSafeHttpsUrl(raw.official_site) || getSafeHttpsUrl(event?.url || raw.url);
}

function getDirectionsUrl(event) {
  const raw = event?.raw || {};
  if (raw.location_confidence === "multiple_municipalities") return "";
  const latitude = Number(raw.lat);
  const longitude = Number(raw.lon);
  const hasExactCoordinates = raw.location_confidence === "exact"
    && isFiniteCoordinate(latitude, -90, 90)
    && isFiniteCoordinate(longitude, -180, 180);
  if (hasExactCoordinates) {
    const url = new URL("https://www.google.com/maps/dir/");
    url.searchParams.set("api", "1");
    url.searchParams.set("destination", `${latitude},${longitude}`);
    return url.toString();
  }

  const venue = cleanText(raw.venue);
  const address = cleanText(raw.address);
  const eventCity = cleanText(raw.event_city);
  const place = cleanText(raw.place);
  const hasSpecificVenue = Boolean(venue)
    && venue.toLocaleLowerCase("it-IT") !== eventCity.toLocaleLowerCase("it-IT");
  const hasVerifiedTextDestination = Boolean(address || hasSpecificVenue);
  const destinationParts = uniqueLocationParts([
    venue,
    address,
    eventCity,
    place,
  ]);

  if (hasVerifiedTextDestination && destinationParts.length) {
    const url = new URL("https://www.google.com/maps/dir/");
    url.searchParams.set("api", "1");
    url.searchParams.set("destination", destinationParts.join(", "));
    return url.toString();
  }

  const trustedMapsUrl = raw.location_confidence === "exact"
    ? getTrustedMapsUrl(raw.maps_url)
    : "";
  if (trustedMapsUrl) return trustedMapsUrl;

  const hasMunicipalityCoordinates = raw.location_confidence === "municipality"
    && isFiniteCoordinate(latitude, -90, 90)
    && isFiniteCoordinate(longitude, -180, 180);
  if (hasMunicipalityCoordinates) {
    const url = new URL("https://www.google.com/maps/dir/");
    url.searchParams.set("api", "1");
    url.searchParams.set("destination", `${latitude},${longitude}`);
    return url.toString();
  }

  const municipality = [eventCity, place].find((value) => (
    value
    && !/\d/.test(value)
    && !/\b(?:via|viale|piazza|piazzale|corso|largo|strada|vicolo|borgo|localit[aà])\b/i.test(value)
  ));
  if (municipality) {
    const url = new URL("https://www.google.com/maps/dir/");
    url.searchParams.set("api", "1");
    url.searchParams.set("destination", municipality);
    return url.toString();
  }

  return "";
}

function getLocation(event) {
  const raw = event?.raw || {};
  const detailedParts = uniqueLocationParts([
    raw.venue,
    raw.address,
    raw.event_city,
    raw.place,
  ]);

  return detailedParts.length ? detailedParts.join(" · ") : cleanText(event?.location);
}

function getMonogram(title) {
  return Array.from(cleanText(title))
    .find((character) => /[\p{L}\p{N}]/u.test(character))
    ?.toLocaleUpperCase("it-IT") || "·";
}

export function buildEventPreviewModel(event) {
  const descriptionData = getDescriptionData(event);
  const civilTime = (value) => typeof value === "string"
    && /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(value) ? value : "";
  const startTime = civilTime(event?.raw?.time || event?.raw?.start_time);
  const endTime = civilTime(event?.raw?.end_time);
  return {
    category: event?.category || "other",
    categoryLabel: cleanText(event?.categoryLabel),
    dateLabel: cleanText(event?.dateChip?.accessibleLabel || event?.date),
    timeLabel: startTime ? `${startTime}${endTime ? `–${endTime}` : ""}` : "",
    ...descriptionData,
    directionsUrl: getDirectionsUrl(event),
    image: getSafeHttpsUrl(event?.image) || (String(event?.image || "").startsWith("/") ? event.image : ""),
    location: getLocation(event),
    monogram: getMonogram(event?.title),
    pageUrl: getPageUrl(event),
    source: cleanText(event?.source),
    title: cleanText(event?.title),
  };
}
