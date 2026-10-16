import { AppCard } from "../../ui/components/AppCard";
import { EmptyState } from "../../ui/components/EmptyState";
import { TabPage } from "../../ui/layout/TabPage";

export function BulletinLabView({ copy, language }) {
  return (
    <TabPage language={language} title={copy.placeholders.bulletinTitle}>
      <AppCard className="mf-lab-map-shell" variant="official">
        <span>A1-A9</span>
        <span>OSMER</span>
      </AppCard>
      <EmptyState body={copy.placeholders.bulletinBody} title={copy.placeholders.bulletinTitle} />
    </TabPage>
  );
}
