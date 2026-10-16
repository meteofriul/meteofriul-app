package com.meteofriul.app;

import android.app.Activity;
import android.content.res.Configuration;
import android.os.Build;
import android.view.View;
import android.view.Window;
import android.webkit.WebView;

import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import androidx.core.view.insets.ColorProtection;
import androidx.core.view.insets.ProtectionLayout;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.WebViewListener;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.Arrays;
import java.util.Locale;

@CapacitorPlugin(name = "MeteoSystemBars")
public final class MeteoSystemBarsPlugin extends Plugin {
    private View insetHost;
    private WebViewListener insetsWebViewListener;
    private boolean darkTheme;

    @Override
    public void load() {
        super.load();

        final Activity activity = getActivity();
        if (activity == null) return;
        activity.runOnUiThread(() -> configureEdgeToEdge(activity));
    }

    private void configureEdgeToEdge(Activity activity) {
        final WebView webView = getBridge().getWebView();
        if (!(webView.getParent() instanceof View)) return;

        insetHost = (View) webView.getParent();
        WindowCompat.enableEdgeToEdge(activity.getWindow());
        applyTheme(activity, darkTheme);
        ViewCompat.setOnApplyWindowInsetsListener(insetHost, (view, windowInsets) -> {
            final int systemBarTypes = WindowInsetsCompat.Type.systemBars()
                | WindowInsetsCompat.Type.displayCutout();
            final Insets systemBars = windowInsets.getInsets(systemBarTypes);
            final Insets ime = windowInsets.getInsets(WindowInsetsCompat.Type.ime());
            final boolean keyboardVisible = windowInsets.isVisible(WindowInsetsCompat.Type.ime());

            // CSS owns system-bar/cutout spacing; only the keyboard resizes the host.
            // ProtectionLayout is outside this host so it still reaches the window edges.
            view.setPadding(0, 0, 0, keyboardVisible ? ime.bottom : 0);
            injectSafeAreaInsets(
                webView,
                systemBars.top,
                systemBars.right,
                keyboardVisible ? 0 : systemBars.bottom,
                systemBars.left
            );

            // Do not consume all insets: WebView must still receive subsequent updates.
            return new WindowInsetsCompat.Builder(windowInsets)
                .setInsets(systemBarTypes, Insets.NONE)
                .build();
        });
        insetsWebViewListener = new WebViewListener() {
            @Override
            public void onPageCommitVisible(WebView view, String url) {
                requestEdgeToEdgeInsets();
            }

            @Override
            public void onPageLoaded(WebView view) {
                requestEdgeToEdgeInsets();
            }
        };
        getBridge().addWebViewListener(insetsWebViewListener);
        requestEdgeToEdgeInsets();
    }

    private void injectSafeAreaInsets(WebView webView, int top, int right, int bottom, int left) {
        final float density = getActivity().getResources().getDisplayMetrics().density;
        final String script = String.format(
            Locale.US,
            "if (document.documentElement) { document.documentElement.style.setProperty('--safe-area-inset-top', '%.3fpx');"
                + "document.documentElement.style.setProperty('--safe-area-inset-right', '%.3fpx');"
                + "document.documentElement.style.setProperty('--safe-area-inset-bottom', '%.3fpx');"
                + "document.documentElement.style.setProperty('--safe-area-inset-left', '%.3fpx');}",
            top / density,
            right / density,
            bottom / density,
            left / density
        );
        webView.post(() -> {
            if (insetHost != null) webView.evaluateJavascript(script, null);
        });
    }

    private void requestEdgeToEdgeInsets() {
        if (insetHost != null) ViewCompat.requestApplyInsets(insetHost);
    }

    private void refreshSystemBars() {
        final Activity activity = getActivity();
        if (activity == null) return;
        // Run after Capacitor has dispatched its own configuration hooks.
        activity.getWindow().getDecorView().post(() -> {
            if (insetHost == null) return;
            applyTheme(activity, darkTheme);
            requestEdgeToEdgeInsets();
        });
    }

    @Override
    protected void handleOnResume() {
        super.handleOnResume();
        refreshSystemBars();
    }

    @Override
    protected void handleOnConfigurationChanged(Configuration newConfig) {
        super.handleOnConfigurationChanged(newConfig);
        refreshSystemBars();
    }

    @Override
    protected void handleOnDestroy() {
        if (getBridge() != null && insetsWebViewListener != null) {
            getBridge().removeWebViewListener(insetsWebViewListener);
        }
        insetsWebViewListener = null;
        if (insetHost != null) ViewCompat.setOnApplyWindowInsetsListener(insetHost, null);
        insetHost = null;
        super.handleOnDestroy();
    }

    @PluginMethod
    public void apply(PluginCall call) {
        final String theme = call.getString("theme", "light");
        if (!"light".equals(theme) && !"dark".equals(theme)) {
            call.reject("system_bars_theme_invalid");
            return;
        }

        final Activity activity = getActivity();
        if (activity == null) {
            call.reject("system_bars_activity_unavailable");
            return;
        }

        activity.runOnUiThread(() -> {
            darkTheme = "dark".equals(theme);
            applyTheme(activity, darkTheme);
            requestEdgeToEdgeInsets();
            call.resolve();
        });
    }

    static boolean usesLightNavigationSurface(Activity activity) {
        // Android 15 can retain dark navigation buttons in system day mode even
        // when light icons are requested. Pair a light app-owned surface with
        // an explicit dark-icon request, including gesture navigation.
        return Build.VERSION.SDK_INT == Build.VERSION_CODES.VANILLA_ICE_CREAM
            && (activity.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_NO;
    }

    static void applyTheme(Activity activity, boolean darkTheme) {
        final Window window = activity.getWindow();
        final int statusBarColor = ContextCompat.getColor(
            activity,
            darkTheme ? R.color.system_status_bar_dark : R.color.system_status_bar_light
        );
        final boolean lightNavigation = usesLightNavigationSurface(activity);
        final int navigationBarColor = ContextCompat.getColor(
            activity,
            lightNavigation ? R.color.system_navigation_bar_android15_day
                : darkTheme ? R.color.system_navigation_bar_dark : R.color.system_navigation_bar_light
        );
        final ProtectionLayout protection = activity.findViewById(R.id.meteo_system_bar_protection);
        if (protection != null) {
            // App-owned surfaces replace Window's deprecated system-bar color setters.
            protection.setProtections(Arrays.asList(
                new ColorProtection(WindowInsetsCompat.Side.TOP, statusBarColor),
                new ColorProtection(WindowInsetsCompat.Side.BOTTOM, navigationBarColor),
                new ColorProtection(WindowInsetsCompat.Side.LEFT, navigationBarColor),
                new ColorProtection(WindowInsetsCompat.Side.RIGHT, navigationBarColor)
            ));
        }

        final WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(
            window,
            window.getDecorView()
        );
        // The status surface stays navy; navigation icons match its chosen surface.
        controller.setAppearanceLightStatusBars(false);
        controller.setAppearanceLightNavigationBars(lightNavigation);
    }
}
