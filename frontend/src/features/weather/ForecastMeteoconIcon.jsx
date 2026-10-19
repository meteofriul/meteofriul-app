import { HomeMeteoconIcon } from "../home/HomeMeteoconIcon";
import drizzleDark from "./icons/drizzle-dark.svg";
import extremeRainDark from "./icons/extreme-rain-dark.svg";
import rainDark from "./icons/rain-dark.svg";
import sleetDark from "./icons/sleet-dark.svg";

const DARK_RAIN_BY_TYPE = {
  ExtremeRain: extremeRainDark,
  HeavyRain: extremeRainDark,
  LightRain: drizzleDark,
  Rain: rainDark,
  Showers: rainDark,
  Sleet: sleetDark,
};

export function ForecastMeteoconIcon({ icon, size }) {
  const darkSource = DARK_RAIN_BY_TYPE[icon?.type];
  if (!darkSource) return <HomeMeteoconIcon icon={icon} size={size} />;

  // CSS follows the app's explicit theme, including its system-theme preference.
  return <>
    <HomeMeteoconIcon className="mf-weather-icon--light" icon={icon} size={size} />
    <img
      alt=""
      aria-hidden="true"
      className="mf-home-meteocon-icon mf-weather-icon--dark"
      decoding="async"
      draggable="false"
      height={size}
      src={darkSource}
      width={size}
    />
  </>;
}
