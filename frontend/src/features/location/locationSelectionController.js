export function createLocationSelectionController() {
  let pending = false;

  return {
    get pending() {
      return pending;
    },

    async select(location, onSelect) {
      if (pending) return { status: "busy" };
      if (typeof onSelect !== "function") {
        return {
          status: "error",
          error: new Error("Selezione localita non disponibile"),
        };
      }

      pending = true;
      try {
        return {
          status: "success",
          value: await onSelect(location),
        };
      } catch (error) {
        return {
          status: "error",
          error: error instanceof Error ? error : new Error("Cambio localita non riuscito"),
        };
      } finally {
        pending = false;
      }
    },
  };
}
