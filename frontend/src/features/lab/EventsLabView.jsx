import { EmptyState } from "../../ui/components/EmptyState";
import { TabPage } from "../../ui/layout/TabPage";

export function EventsLabView({ copy, language }) {
  return (
    <TabPage language={language} title={copy.placeholders.eventsTitle}>
      <EmptyState body={copy.placeholders.eventsBody} title={copy.placeholders.eventsTitle} />
    </TabPage>
  );
}
