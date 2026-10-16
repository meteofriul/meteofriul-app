package com.meteofriul.app;

import android.os.Bundle;
import android.view.View;
import android.webkit.WebView;

import androidx.core.splashscreen.SplashScreen;
import androidx.core.view.WindowCompat;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;
import com.google.firebase.FirebaseApp;

public class MainActivity extends BridgeActivity {
    private static final long SPLASH_SAFETY_TIMEOUT_MS = 6000L;

    private volatile boolean initialContentReady;
    private boolean launchDismissScheduled;
    private WebViewListener launchWebViewListener;
    private View launchRootView;
    private final Runnable launchSafetyTimeout = this::markInitialContentReady;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(MeteoFirebaseAppCheckPlugin.class);
        registerPlugin(MeteoBackgroundLocationPlugin.class);
        registerPlugin(MeteoNotificationSettingsPlugin.class);
        registerPlugin(MeteoSystemBarsPlugin.class);

        SplashScreen splashScreen = SplashScreen.installSplashScreen(this);
        splashScreen.setKeepOnScreenCondition(() -> !initialContentReady);
        WindowCompat.enableEdgeToEdge(getWindow());

        super.onCreate(savedInstanceState);

        launchRootView = findViewById(android.R.id.content);
        launchRootView.postDelayed(launchSafetyTimeout, SPLASH_SAFETY_TIMEOUT_MS);
        registerLaunchDismissal();

        if (FirebaseApp.getApps(this).isEmpty()) return;
        PilotAppCheckProviderInstaller.install();
    }

    private void registerLaunchDismissal() {
        if (getBridge() == null) return;

        launchWebViewListener = new WebViewListener() {
            @Override
            public void onPageLoaded(WebView webView) {
                if (launchDismissScheduled) return;
                launchDismissScheduled = true;

                webView.postVisualStateCallback(
                    System.nanoTime(),
                    new WebView.VisualStateCallback() {
                        @Override
                        public void onComplete(long requestId) {
                            webView.postOnAnimation(MainActivity.this::markInitialContentReady);
                        }
                    }
                );
            }
        };
        getBridge().addWebViewListener(launchWebViewListener);
    }

    private void markInitialContentReady() {
        runOnUiThread(() -> {
            if (initialContentReady) return;
            initialContentReady = true;

            if (launchRootView != null) {
                launchRootView.removeCallbacks(launchSafetyTimeout);
                launchRootView.invalidate();
                launchRootView = null;
            }

            if (getBridge() != null && launchWebViewListener != null) {
                getBridge().removeWebViewListener(launchWebViewListener);
                launchWebViewListener = null;
            }
        });
    }

    @Override
    public void onDestroy() {
        if (launchRootView != null) {
            launchRootView.removeCallbacks(launchSafetyTimeout);
            launchRootView = null;
        }

        if (getBridge() != null && launchWebViewListener != null) {
            getBridge().removeWebViewListener(launchWebViewListener);
            launchWebViewListener = null;
        }

        super.onDestroy();
    }
}
