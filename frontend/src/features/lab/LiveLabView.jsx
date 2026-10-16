import { EmptyState } from "../../ui/components/EmptyState";
import { TabPage } from "../../ui/layout/TabPage";

export function LiveLabView({ copy, language }) {
  return (
    <TabPage language={language} title={copy.placeholders.liveTitle}>
      <EmptyState body={copy.placeholders.liveBody} title={copy.placeholders.liveTitle} />
    </TabPage>
  );
}
