import { CalendarDays, CloudSun, Compass, Home, Settings } from "lucide-react";

export const APP_TABS = [
  { id: "home", Icon: Home },
  { id: "weather", Icon: CloudSun },
  { id: "events", Icon: CalendarDays },
  { id: "discover", Icon: Compass },
];

export const WEATHER_SECTION_ROUTE_IDS = ["weather", "bulletin", "live"];

export const APP_ROUTE_IDS = [
  ...APP_TABS.map((tab) => tab.id),
  "bulletin",
  "live",
  "almanac",
  "settings",
];

export function getPrimaryTabId(routeId) {
  if (WEATHER_SECTION_ROUTE_IDS.includes(routeId)) return "weather";

  return APP_TABS.some((tab) => tab.id === routeId) ? routeId : "home";
}

export const APP_ACTIONS = {
  settings: { id: "settings", Icon: Settings },
};
