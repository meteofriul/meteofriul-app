package com.meteofriul.test.barprobe;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.WindowInsetsController;
import android.widget.TextView;

public class BarProbe extends Activity {
    private TextView label;
    private boolean darkIcons;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        label = new TextView(this);
        label.setBackgroundColor(Color.rgb(9, 29, 61));
        label.setTextColor(Color.WHITE);
        label.setTextSize(22);
        label.setPadding(60, 180, 40, 40);
        label.setOnClickListener(view -> { darkIcons = !darkIcons; apply(); });
        setContentView(label);
        getWindow().setNavigationBarContrastEnforced(false);
        apply();
    }
    @Override public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        if (focus) apply();
    }
    private void apply() {
        WindowInsetsController controller = getWindow().getInsetsController();
        controller.setSystemBarsAppearance(darkIcons ? 16 : 0, 24);
        label.setText("NATIVE ANDROID DIAGNOSTIC\nNo WebView / no Capacitor\n\nRequested nav icons: "
            + (darkIcons ? "DARK" : "LIGHT")
            + "\nAndroid appearance flags: " + controller.getSystemBarsAppearance()
            + "\n\nTap to toggle the request.");
    }
}
