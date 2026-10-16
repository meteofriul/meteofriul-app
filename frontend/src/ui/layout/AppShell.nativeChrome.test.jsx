import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { getUiShellCopy } from "../../app/uiShellCopy";
import { AppShell } from "./AppShell";

function renderShell(nativeAndroid) {
  return renderToStaticMarkup(
    <AppShell
      activeRoute="home"
      activeTab="home"
      copy={getUiShellCopy("it")}
      definitiveExperience
      language="it"
      nativeAndroid={nativeAndroid}
      tabs={[]}
    >
      <div>Contenuto</div>
    </AppShell>,
  );
}

describe("AppShell native chrome", () => {
  it("marks only the native Android shell for the bottom navy strip", () => {
    expect(renderShell(true)).toContain("is-native-android");
    expect(renderShell(false)).not.toContain("is-native-android");
  });
});
