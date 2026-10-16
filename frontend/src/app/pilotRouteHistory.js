import { APP_ROUTE_IDS } from "./appConfig";

const normalize = (route) => APP_ROUTE_IDS.includes(route) ? route : "home";

// In-memory navigation only: no browser history, URLs or persisted beta state.
export function createPilotRouteHistory(initialRoute = "home") {
  const first = normalize(initialRoute);
  let routes = first === "home" ? ["home"] : ["home", first];
  return {
    visit(route) {
      const next = normalize(route);
      if (next === "home") routes = ["home"];
      else if (next !== routes.at(-1)) routes = ["home", ...routes.slice(1).slice(-30), next];
      return next;
    },
    back() {
      if (routes.length > 1) routes.pop();
      else routes = ["home"];
      return routes.at(-1);
    },
  };
}
