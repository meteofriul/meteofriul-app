package com.meteofriul.app;

import android.content.pm.ActivityInfo;
import android.content.res.Configuration;
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
        applyPreferredOrientation(getResources().getConfiguration());
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

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        applyPreferredOrientation(newConfig);
    }

    private void applyPreferredOrientation(Configuration configuration) {
        // Product choice: phones use the portrait layout. Large displays and
        // multi-window stay adaptive, including when a foldable changes size.
        int smallestWidth = configuration.smallestScreenWidthDp;
        boolean portraitPhone = smallestWidth > 0 && smallestWidth < 600
            && !isInMultiWindowMode();
        int orientation = portraitPhone
            ? ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            : ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED;
        if (getRequestedOrientation() != orientation) {
            setRequestedOrientation(orientation);
        }
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
