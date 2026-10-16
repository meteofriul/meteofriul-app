import clearDay from "@meteocons/svg/fill/clear-day.svg";
import clearNight from "@meteocons/svg/fill/clear-night.svg";
import cloudy from "@meteocons/svg/fill/cloudy.svg";
import drizzle from "@meteocons/svg/fill/drizzle.svg";
import extremeRain from "@meteocons/svg/fill/extreme-rain.svg";
import fog from "@meteocons/svg/fill/fog.svg";
import hail from "@meteocons/svg/fill/hail.svg";
import haze from "@meteocons/svg/fill/haze.svg";
import mist from "@meteocons/svg/fill/mist.svg";
import mostlyClearDay from "@meteocons/svg/fill/mostly-clear-day.svg";
import mostlyClearNight from "@meteocons/svg/fill/mostly-clear-night.svg";
import overcast from "@meteocons/svg/fill/overcast.svg";
import overcastFog from "@meteocons/svg/fill/overcast-fog.svg";
import overcastNight from "@meteocons/svg/fill/overcast-night.svg";
import partlyCloudyDay from "@meteocons/svg/fill/partly-cloudy-day.svg";
import partlyCloudyNight from "@meteocons/svg/fill/partly-cloudy-night.svg";
import rain from "@meteocons/svg/fill/rain.svg";
import sleet from "@meteocons/svg/fill/sleet.svg";
import snow from "@meteocons/svg/fill/snow.svg";
import strongStorm from "@meteocons/svg/fill/thunderstorms-extreme.svg";
import stormHail from "@meteocons/svg/fill/thunderstorms-hail.svg";
import thunderstorms from "@meteocons/svg/fill/thunderstorms.svg";
import wind from "@meteocons/svg/fill/wind.svg";

const ICON_BY_TYPE = {
  ClearNight: clearNight,
  Cloud: cloudy,
  ExtremeRain: extremeRain,
  Fog: fog,
  Hail: hail,
  Haze: haze,
  HeavyRain: extremeRain,
  LightRain: drizzle,
  LowCloudFog: overcastFog,
  Mist: mist,
  MostlyClearNight: mostlyClearNight,
  MostlySunny: mostlyClearDay,
  Overcast: overcast,
  OvercastNight: overcastNight,
  PartlyCloudy: partlyCloudyDay,
  PartlyCloudyNight: partlyCloudyNight,
  Rain: rain,
  Showers: rain,
  Sleet: sleet,
  Snow: snow,
  Storm: thunderstorms,
  StormHail: stormHail,
  StrongStorm: strongStorm,
  Sun: clearDay,
  Wind: wind,
};

export function HomeMeteoconIcon({ className = "", icon, size = 92 }) {
  const fallbackType = icon?.night ? "OvercastNight" : "Cloud";
  const src = ICON_BY_TYPE[icon?.type] || ICON_BY_TYPE[fallbackType];

  return (
    <img
      alt=""
      aria-hidden="true"
      className={["mf-home-meteocon-icon", className].filter(Boolean).join(" ")}
      decoding="async"
      draggable="false"
      height={size}
      src={src}
      width={size}
    />
  );
}
