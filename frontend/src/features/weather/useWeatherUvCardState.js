import { useEffect, useState } from "react";

import { uvForecast } from "./uvForecast";
import { readUvForecastState, subscribeToUvForecast } from "./uvForecastRuntime";

export function useWeatherUvCardState({ point } = {}) {
  const [{ document, now, saved, error }, setState] = useState(readUvForecastState);
  useEffect(() => subscribeToUvForecast(setState), []);
  const model = uvForecast(document, point, now);
  const forecastDate = model ? new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(model.current.time) : "";

  return { error, forecastDate, model, saved };
}
