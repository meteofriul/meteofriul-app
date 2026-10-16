import {
  CircleCheck,
  CloudFog,
  CloudHail,
  CloudLightning,
  CloudRain,
  Gem,
  Snowflake,
  Wind,
} from "lucide-react";

export const LIVE_REPORT_ICONS = Object.freeze({
  fog: CloudFog,
  hail: CloudHail,
  ice: Snowflake,
  quiet: CircleCheck,
  rain: CloudRain,
  snow: Snowflake,
  storm: CloudLightning,
  wind: Wind,
});

export const PILOT_LIVE_REPORT_ICONS = Object.freeze({
  ...LIVE_REPORT_ICONS,
  ice: Gem,
});
