package com.meteofriul.app;

import static org.junit.Assert.*;

import android.content.Context;
import android.os.SystemClock;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.webkit.WebView;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Run only against the debug APK on a dedicated emulator. */
@RunWith(AndroidJUnit4.class)
public class EdgeToEdgeInstrumentedTest {
    private ActivityScenario<MainActivity> scenario;

    @Before
    public void launch() throws Exception {
        scenario = ActivityScenario.launch(MainActivity.class);
        awaitScript("document.readyState === 'complete' && !!document.querySelector('.mf-app-shell')");
        awaitScript("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-top')) > 0");
    }

    @After
    public void close() {
        if (scenario != null) scenario.close();
    }

    @Test
    public void contentReachesWindowEdgesAndSafeAreaMatchesSystem() throws Exception {
        scenario.onActivity(activity -> {
            View decor = activity.getWindow().getDecorView();
            WebView web = activity.getBridge().getWebView();
            int[] position = new int[2];
            web.getLocationInWindow(position);
            assertEquals("WebView must draw behind the status bar", 0, position[1]);
            assertEquals("No native and CSS double bottom inset", decor.getHeight(), web.getHeight());
            assertFalse(WindowCompat.getInsetsController(activity.getWindow(), decor).isAppearanceLightStatusBars());
            assertFalse(WindowCompat.getInsetsController(activity.getWindow(), decor).isAppearanceLightNavigationBars());
        });
        assertRealSafeArea();
    }

    @Test
    public void reloadRestoresSafeAreaWithoutThemeCall() throws Exception {
        // A small offline document isolates the native page lifecycle from React's theme effect.
        scenario.onActivity(activity -> activity.getBridge().getWebView().loadDataWithBaseURL(
            "https://localhost/", "<html><head><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'></head><body>Insets reload probe</body></html>",
            "text/html", "UTF-8", null));
        awaitScript("document.body.textContent.includes('Insets reload probe')");
        awaitScript("parseFloat(document.documentElement.style.getPropertyValue('--safe-area-inset-top')) > 0");
        assertRealSafeArea();
    }

    @Test
    public void cutoutAndKeyboardInsetsAreAppliedExactlyOnce() throws Exception {
        AtomicReference<String> response = new AtomicReference<>();
        CountDownLatch ready = new CountDownLatch(1);
        scenario.onActivity(activity -> {
            WebView web = activity.getBridge().getWebView();
            View host = (View) web.getParent();
            WindowInsetsCompat synthetic = new WindowInsetsCompat.Builder()
                .setInsets(WindowInsetsCompat.Type.systemBars(), Insets.of(0, 72, 0, 60))
                .setInsets(WindowInsetsCompat.Type.displayCutout(), Insets.of(24, 90, 16, 0))
                .setInsets(WindowInsetsCompat.Type.ime(), Insets.of(0, 0, 0, 600))
                .setVisible(WindowInsetsCompat.Type.ime(), true)
                .build();
            WindowInsetsCompat forwarded = ViewCompat.dispatchApplyWindowInsets(host, synthetic);
            assertEquals(600, host.getPaddingBottom());
            assertEquals(0, host.getPaddingTop());
            assertEquals(Insets.NONE, forwarded.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout()));
            // Injection is queued on the same WebView; read immediately after that runnable.
            web.post(() -> web.evaluateJavascript(insetsScript(), value -> {
                response.set(value);
                ready.countDown();
            }));
        });
        assertTrue(ready.await(10, TimeUnit.SECONDS));
        JSONObject actual = new JSONObject(response.get());
        AtomicReference<Float> density = new AtomicReference<>();
        scenario.onActivity(activity -> density.set(activity.getResources().getDisplayMetrics().density));
        assertEquals(90 / density.get(), actual.getDouble("top"), 0.001);
        assertEquals(24 / density.get(), actual.getDouble("left"), 0.001);
        assertEquals(16 / density.get(), actual.getDouble("right"), 0.001);
        assertEquals(0, actual.getDouble("bottom"), 0.001);
        scenario.onActivity(activity -> ViewCompat.requestApplyInsets((View) activity.getBridge().getWebView().getParent()));
    }

    @Test
    public void keyboardShowAndHideRestoresBottomClearance() throws Exception {
        evaluate("(() => { const input = document.createElement('input'); input.id='edge-ime-probe'; input.style='position:fixed;top:120px;left:24px;z-index:99999'; document.body.append(input); input.focus(); return true; })()");
        scenario.onActivity(activity -> {
            WebView web = activity.getBridge().getWebView();
            web.requestFocus();
            ((InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE)).showSoftInput(web, 0);
        });
        awaitIme(true);
        awaitScript("parseFloat(document.documentElement.style.getPropertyValue('--safe-area-inset-bottom')) === 0");
        scenario.onActivity(activity -> {
            View host = (View) activity.getBridge().getWebView().getParent();
            assertEquals(ViewCompat.getRootWindowInsets(host).getInsets(WindowInsetsCompat.Type.ime()).bottom, host.getPaddingBottom());
            ((InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(host.getWindowToken(), 0);
        });
        awaitIme(false);
        assertRealSafeArea();
    }

    @Test
    public void bothThemesKeepNavigationAboveSystemBar() throws Exception {
        for (String theme : new String[] {"light", "dark"}) {
            evaluate("document.documentElement.dataset.theme='" + theme + "'");
            JSONObject bounds = new JSONObject(evaluate("(() => {const shell=document.querySelector('.mf-app-shell'); const nav=document.querySelector('.mf-bottom-nav'); const r=nav.getBoundingClientRect();return {bottom:r.bottom,height:innerHeight,inset:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-bottom')),strip:getComputedStyle(shell,'::after').backgroundColor};})()"));
            assertTrue(bounds.toString(), bounds.getDouble("bottom") <= bounds.getDouble("height") - bounds.getDouble("inset"));
            assertEquals(theme.equals("dark") ? "rgb(11, 39, 66)" : "rgb(9, 29, 61)", bounds.getString("strip"));
        }
    }

    @Test
    public void asymmetricCutoutsDoNotWidenTheDocument() throws Exception {
        String originalTheme = evaluate("document.documentElement.dataset.theme || ''");
        try {
            for (int[] sides : new int[][] {{52, 0}, {0, 52}, {0, 0}}) {
                String fits = evaluate("(() => { const root=document.documentElement;"
                    + "root.dataset.theme='light';"
                    + "root.style.setProperty('--safe-area-inset-left','" + sides[0] + "px');"
                    + "root.style.setProperty('--safe-area-inset-right','" + sides[1] + "px');"
                    + "return root.scrollWidth <= root.clientWidth + 1; })()");
                assertEquals("Header background must not widen the viewport for a side cutout", "true", fits);
            }
        } finally {
            evaluate("document.documentElement.dataset.theme=" + originalTheme);
            scenario.onActivity(activity -> ViewCompat.requestApplyInsets(
                (View) activity.getBridge().getWebView().getParent()));
        }
    }

    private void assertRealSafeArea() throws Exception {
        AtomicReference<float[]> expected = new AtomicReference<>();
        scenario.onActivity(activity -> {
            Insets insets = ViewCompat.getRootWindowInsets(activity.getWindow().getDecorView())
                .getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            float density = activity.getResources().getDisplayMetrics().density;
            expected.set(new float[] {insets.top / density, insets.right / density, insets.bottom / density, insets.left / density});
        });
        float[] e = expected.get();
        awaitScript("(() => { const v=" + insetsScript() + "; return Math.abs(v.top-" + e[0] + ")<0.001 && Math.abs(v.right-" + e[1] + ")<0.001 && Math.abs(v.bottom-" + e[2] + ")<0.001 && Math.abs(v.left-" + e[3] + ")<0.001; })()");
    }

    private String insetsScript() {
        return "(() => {const s=getComputedStyle(document.documentElement);return Object.fromEntries(['top','right','bottom','left'].map(k=>[k,parseFloat(s.getPropertyValue('--safe-area-inset-'+k))]));})()";
    }

    private void awaitIme(boolean visible) throws Exception {
        long deadline = SystemClock.uptimeMillis() + 10000;
        while (SystemClock.uptimeMillis() < deadline) {
            AtomicReference<Boolean> matches = new AtomicReference<>(false);
            scenario.onActivity(activity -> matches.set(ViewCompat.getRootWindowInsets(activity.getWindow().getDecorView()).isVisible(WindowInsetsCompat.Type.ime()) == visible));
            if (matches.get()) return;
            SystemClock.sleep(100);
        }
        fail("IME visibility did not become " + visible);
    }

    private void awaitScript(String script) throws Exception {
        long deadline = SystemClock.uptimeMillis() + 20000;
        String last = "";
        while (SystemClock.uptimeMillis() < deadline) {
            last = evaluate(script);
            if ("true".equals(last)) return;
            SystemClock.sleep(100);
        }
        fail("Timed out: " + script + "; result=" + last);
    }

    private String evaluate(String script) throws Exception {
        CountDownLatch ready = new CountDownLatch(1);
        AtomicReference<String> response = new AtomicReference<>();
        scenario.onActivity(activity -> activity.getBridge().getWebView().evaluateJavascript(script, value -> {
            response.set(value);
            ready.countDown();
        }));
        assertTrue("JavaScript callback", ready.await(10, TimeUnit.SECONDS));
        return response.get();
    }
}
