import { CloudOff } from "lucide-react";

import { AppCard } from "./AppCard";

export function EmptyState({ body, title }) {
  return (
    <AppCard className="mf-empty-state" variant="default">
      <CloudOff aria-hidden="true" size={28} strokeWidth={2.1} />
      <div>
        <strong>{title}</strong>
        <p>{body}</p>
      </div>
    </AppCard>
  );
}
