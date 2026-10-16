import { recentListPreviewEnabled } from "./recentListPreview";

if (recentListPreviewEnabled) {
  await import("../../../main.jsx");
} else {
  document.getElementById("root").textContent = "Anteprima disponibile soltanto nel browser locale.";
}
