import { EmptyState } from "../../ui/components/EmptyState";
import { LocationContext } from "../../ui/components/LocationContext";
import { TabPage } from "../../ui/layout/TabPage";

const DISCOVER_LOCATION_COPY = {
  fur: { change: "Cambie", prefix: "A" },
  it: { change: "Cambia", prefix: "A" },
};

export function DiscoverLabView({ activeLocation, copy, language, onLocationSearchOpen }) {
  const locationCopy = DISCOVER_LOCATION_COPY[language === "fur" ? "fur" : "it"];

  return (
    <TabPage language={language} title={copy.placeholders.discoverTitle}>
      <div className="mf-discover-placeholder">
        <LocationContext
          changeLabel={locationCopy.change}
          city={activeLocation?.city}
          onChange={onLocationSearchOpen}
          prefix={locationCopy.prefix}
        />
        <EmptyState body={copy.placeholders.discoverBody} title={copy.placeholders.discoverTitle} />
      </div>
    </TabPage>
  );
}
