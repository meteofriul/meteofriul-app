package com.meteofriul.app;

/** Firebase is intentionally not enrolled for the side-by-side local pilot. */
final class PilotAppCheckProviderInstaller {
    private PilotAppCheckProviderInstaller() {}

    static void install() {
        // No-op: com.meteofriul.app.localpilot has no Firebase Android identity.
    }
}
