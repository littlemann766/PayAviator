package com.payaviator.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.KeyguardManager;
import android.hardware.fingerprint.FingerprintManager;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceError;
import android.widget.Toast;

import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseUser;
import com.payaviator.app.auth.AuthedRequest;
import com.payaviator.app.auth.BackendHeaders;
import com.payaviator.app.auth.PlayIntegrity;
import com.payaviator.app.auth.FirebaseSignIn;
import com.plaid.link.Plaid;
import com.plaid.link.configuration.LinkTokenConfiguration;
import com.plaid.link.result.LinkResult;
import com.plaid.link.result.LinkSuccess;
import com.plaid.link.result.LinkExit;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import android.util.Base64;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends Activity {

    private static final int FILE_CHOOSER_REQUEST = 1001;
    private static final int SAVE_BACKUP_REQUEST = 1002;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 1003;
    private static final int DEVICE_CREDENTIAL_REQUEST = 1005;
    private static final int PLAID_LINK_REQUEST = 1006;
    private static final String SECURITY_PREFS = "payaviator_security";
    private static final String SECURITY_ENABLED_KEY = "app_lock_enabled";
    private static final String SECURITY_LAST_UNLOCK_KEY = "pin_lock_last_unlock_ms";
    private static final String SECURITY_STORAGE_VERSION_KEY = "security_storage_version";
    private static final String SECURITY_REAL_ACCOUNTS_KEY = "real_accounts_connected";
    private static final long RELOCK_AFTER_MS = 5 * 60 * 1000L; // 5-minute grace period
    private static final int SAVE_TEXT_REQUEST = 1004;
    private static final int REQUEST_BASE = 41000;
    private static final String APP_ASSET_ORIGIN = "https://appassets.androidplatform.net/assets/";

    private WebView webView;
    private FrameLayout rootView;
    private LinearLayout splashView;
    private TextView splashStatus;
    private boolean splashDismissed = false;
    private long splashStartedAt = 0L;
    private LinearLayout lockView;
    private boolean authenticatedForSession = false;
    private boolean authenticationInProgress = false;
    private boolean externalActivityInProgress = false;
    private boolean hostedLinkInProgress = false;
    private boolean nativePlaidInProgress = false;
    private boolean pendingHostedReturn = false;
    private long stoppedAtElapsed = 0L;
    private ValueCallback<Uri[]> filePathCallback;
    private String pendingBackupJson;
    private String pendingTextExport;
    private String pendingTextFilename;
    private boolean pendingTextBase64 = false;
    private FirebaseSignIn signIn;
    /** 4.1.2: alert target from a notification tap, handed to the web app via takeLaunchAlert / PayAviatorOpenAlert. */
    private String pendingAlertOpen;
    private final FirebaseAuth.AuthStateListener authStateListener = a -> { pushAuthState(null); registerPushTokenIfSignedIn(); };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        migrateAppLockDefaultOff();

        // Firebase sign-in only gates bank (Plaid) features; local bill tracking never needs it.
        signIn = new FirebaseSignIn(this, getString(com.payaviator.app.R.string.default_web_client_id));
        signIn.addStateListener(authStateListener);

        Uri launchData = getIntent() == null ? null : getIntent().getData();
        if (getIntent() != null) pendingAlertOpen = alertTargetFrom(getIntent());
        // 4.1.2: re-arm stored alarms on every start (covers phones that delay or block BOOT_COMPLETED).
        try { NotificationScheduler.arm(getApplicationContext()); } catch (Exception ignored) {}
        if (isPlaidReturnUri(launchData)) {
            pendingHostedReturn = true;
        }

        if (isAppLockEnabled() && !isWithinUnlockGracePeriod()) {
            showLockedScreen();
            authenticateUser();
            return;
        }

        unlockAndCreateWebView();
    }

    private void unlockAndCreateWebView() {
        authenticatedForSession = true;
        // 4.1.2: reconnect push channel + FCM token registration on app start (quietly no-op when signed out).
        try { PushService.ensureReconnectChannel(this); } catch (Exception ignored) {}
        registerPushTokenIfSignedIn();
        if (isAppLockEnabled()) rememberSuccessfulUnlock();
        authenticationInProgress = false;

        // Always reset splash state before creating a fresh WebView.
        splashDismissed = false;
        splashStartedAt = android.os.SystemClock.uptimeMillis();
        createLoadingShell();

        webView = new WebView(this);
        webView.setAlpha(0f);
        rootView.addView(webView, 0, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        WebView.setWebContentsDebuggingEnabled(false);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true); // IndexedDB is used by PayAviator.
        settings.setAllowFileAccess(false); // App assets are served through a secure HTTPS-like origin below.
        settings.setAllowContentAccess(true); // Required for user-selected backup files.
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setSaveFormData(false);
        settings.setSafeBrowsingEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        // 4.1.3: keep the user's Android font size, but cap it at 130% so the
        // layout (gauges, nav labels) can't break. The page reflows for up to 130%.
        if (settings.getTextZoom() > 130) settings.setTextZoom(130);

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, true); // Required by secure embedded bank-link flows.

        // The JavaScript bridge is exposed only to the bundled, trusted app page.
        // Any web link is handed to the device browser instead of loading inside
        // this WebView, preventing an external page from reaching AndroidBridge.
        webView.addJavascriptInterface(new AndroidBridge(), "AndroidBridge");
        webView.setWebViewClient(new WebViewClient() {
            private boolean handleNavigation(Uri uri) {
                if (uri == null) return true;
                String target = uri.toString();
                if (target.startsWith(APP_ASSET_ORIGIN) || "about:blank".equals(target)) {
                    return false;
                }

                String scheme = uri.getScheme();
                if ("mailto".equalsIgnoreCase(scheme)) {
                    try { startActivity(new Intent(Intent.ACTION_SENDTO, uri)); } catch (Exception ignored) { }
                    return true;
                }
                if ("https".equalsIgnoreCase(scheme) || "http".equalsIgnoreCase(scheme)) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    } catch (Exception ignored) {
                        Toast.makeText(MainActivity.this,
                                "Unable to open that link.", Toast.LENGTH_SHORT).show();
                    }
                }
                return true;
            }

            private WebResourceResponse localAssetResponse(Uri uri) {
                if (uri == null || !uri.toString().startsWith(APP_ASSET_ORIGIN)) return null;
                String path = uri.getPath();
                if (path == null || !path.startsWith("/assets/")) return null;
                String assetPath = path.substring("/assets/".length());
                if (assetPath.isEmpty()) assetPath = "index.html";
                try {
                    InputStream in = getAssets().open(assetPath);
                    String lower = assetPath.toLowerCase(Locale.US);
                    String mime = "application/octet-stream";
                    if (lower.endsWith(".html") || lower.endsWith(".htm")) mime = "text/html";
                    else if (lower.endsWith(".js")) mime = "application/javascript";
                    else if (lower.endsWith(".css")) mime = "text/css";
                    else if (lower.endsWith(".json") || lower.endsWith(".webmanifest")) mime = "application/json";
                    else if (lower.endsWith(".png")) mime = "image/png";
                    else if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) mime = "image/jpeg";
                    else if (lower.endsWith(".svg")) mime = "image/svg+xml";
                    return new WebResourceResponse(mime, "UTF-8", in);
                } catch (IOException ignored) {
                    return null;
                }
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                WebResourceResponse local = localAssetResponse(request == null ? null : request.getUrl());
                return local != null ? local : super.shouldInterceptRequest(view, request);
            }

            @Override
            @SuppressWarnings("deprecation")
            public WebResourceResponse shouldInterceptRequest(WebView view, String url) {
                WebResourceResponse local = localAssetResponse(url == null ? null : Uri.parse(url));
                return local != null ? local : super.shouldInterceptRequest(view, url);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleNavigation(request == null ? null : request.getUrl());
            }

            @Override
            @SuppressWarnings("deprecation")
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleNavigation(url == null ? null : Uri.parse(url));
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                if (url != null && url.startsWith(APP_ASSET_ORIGIN)) {
                    revealAppWhenReady();
                    if (pendingHostedReturn) {
                        pendingHostedReturn = false;
                        hostedLinkInProgress = false;
                        view.postDelayed(() -> notifyHostedLinkReturned(), 350);
                    }
                }
            }
        });

        webView.clearCache(true);
        webView.clearHistory();

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                    WebView webView,
                    ValueCallback<Uri[]> callback,
                    FileChooserParams params) {

                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;

                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                // 4.2.x: the same picker also serves "Import from spreadsheet" (.xlsx / .csv). The page asks for it
                // through the input's accept list; everything else keeps the original JSON-backup picker.
                boolean sheetPicker = false;
                String[] accept = params != null ? params.getAcceptTypes() : null;
                if (accept != null) {
                    for (String a : accept) {
                        if (a != null && (a.contains("xlsx") || a.contains("csv") || a.contains("spreadsheetml"))) sheetPicker = true;
                    }
                }
                if (sheetPicker) {
                    intent.setType("*/*");
                    intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "text/csv", "text/comma-separated-values", "application/csv",
                            "application/vnd.ms-excel", "text/plain", "application/octet-stream"});
                } else {
                    intent.setType("application/json");
                    intent.putExtra(Intent.EXTRA_MIME_TYPES,
                            new String[]{"application/json", "text/json", "text/plain"});
                }

                try {
                    externalActivityInProgress = true;
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception e) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this,
                            "Unable to open local files.", Toast.LENGTH_SHORT).show();
                    return false;
                }
            }
        });

        // 20.0.148: the bundled asset is the only in-app UI source.
        webView.loadUrl(APP_ASSET_ORIGIN + "index.html");
    }


    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void createLoadingShell() {
        rootView = new FrameLayout(this);
        rootView.setBackgroundColor(Color.rgb(5, 19, 40));
        // 4.1.3: targetSdk 36 is always edge-to-edge, so keep the page out from under
        // the status bar, navigation bar and camera cutout.
        rootView.setOnApplyWindowInsetsListener((v, insets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(
                        android.view.WindowInsets.Type.systemBars()
                                | android.view.WindowInsets.Type.displayCutout());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                        insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        setContentView(rootView);

        splashView = new CloudSplashLayout(this);
        splashView.setOrientation(LinearLayout.VERTICAL);
        splashView.setGravity(Gravity.CENTER);
        splashView.setPadding(dp(28), dp(32), dp(28), dp(32));
        splashView.setBackgroundColor(Color.rgb(5, 19, 40));

        // Redesigned splash: calm sky, one compact mark, wordmark, thin progress line.
        // Everything scales with the shorter screen side so phones, tablets and landscape all fit.
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        int shortSide = Math.min(dm.widthPixels, dm.heightPixels);
        int logoPx = Math.max(dp(84), Math.min(dp(132), Math.round(shortSide * 0.26f)));

        ImageView logo = new ImageView(this);
        logo.setImageResource(com.payaviator.app.R.drawable.payaviator_app_icon);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        final float logoRadius = logoPx * 0.22f;
        logo.setOutlineProvider(new android.view.ViewOutlineProvider() {
            @Override
            public void getOutline(View v, android.graphics.Outline o) {
                o.setRoundRect(0, 0, v.getWidth(), v.getHeight(), logoRadius);
            }
        });
        logo.setClipToOutline(true);
        LinearLayout.LayoutParams logoParams = new LinearLayout.LayoutParams(logoPx, logoPx);
        logoParams.bottomMargin = dp(18);
        splashView.addView(logo, logoParams);

        TextView title = new TextView(this);
        title.setText("PayAviator");
        title.setTextColor(Color.WHITE);
        title.setTextSize(26);
        title.setGravity(Gravity.CENTER);
        title.setLetterSpacing(0.02f);
        title.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        splashView.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        TextView subtitle = new TextView(this);
        subtitle.setText("TAKE CONTROL OF YOUR MONEY");
        subtitle.setTextColor(Color.rgb(22, 228, 234));
        subtitle.setTextSize(11);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setLetterSpacing(0.14f);
        LinearLayout.LayoutParams subParams =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
        subParams.topMargin = dp(8);
        splashView.addView(subtitle, subParams);

        SplashBar bar = new SplashBar(this);
        LinearLayout.LayoutParams barParams = new LinearLayout.LayoutParams(
                Math.max(dp(120), Math.min(dp(200), Math.round(shortSide * 0.42f))), dp(3));
        barParams.topMargin = dp(36);
        splashView.addView(bar, barParams);

        splashStatus = new TextView(this);
        splashStatus.setText("Getting things ready");
        splashStatus.setTextColor(Color.argb(210, 214, 232, 248));
        splashStatus.setTextSize(13);
        splashStatus.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams loadParams =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
        loadParams.topMargin = dp(14);
        splashView.addView(splashStatus, loadParams);

        if (!CloudSplashLayout.reducedMotion(this)) {
            for (int i = 0; i < splashView.getChildCount(); i++) {
                View c = splashView.getChildAt(i);
                c.setAlpha(0f);
                c.setTranslationY(dp(6));
                c.animate().alpha(1f).translationY(0f).setStartDelay(60L * i).setDuration(380).start();
            }
        }

        splashStatus.postDelayed(() -> setSplashStatus("Loading your bills"), 700);
        splashStatus.postDelayed(() -> setSplashStatus("Preparing your gauge"), 2000);
        splashStatus.postDelayed(() -> setSplashStatus("Almost ready"), 3600);

        rootView.addView(splashView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        splashView.setOnClickListener(v -> forceRevealApp());

        // Hard fail-safe: never allow the splash screen to trap the user.
        splashView.postDelayed(this::forceRevealApp, 1800);
    }

    /**
     * Splash-only sky layer: a navy-to-sky gradient (the app's original navy and light blue) with
     * three soft parallax cloud layers. Painted inside the splash itself, so it can never sit over
     * the WebView or block taps after startup. Honors the system "remove animations" setting.
     */
    private static class CloudSplashLayout extends LinearLayout {
        private final Paint cloudPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint skyPaint = new Paint();
        private final long cloudStart;
        private final boolean still;

        static boolean reducedMotion(Context c) {
            try {
                return android.provider.Settings.Global.getFloat(c.getContentResolver(),
                        android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f;
            } catch (Exception e) {
                return false;
            }
        }

        CloudSplashLayout(Context context) {
            super(context);
            setWillNotDraw(false);
            cloudPaint.setColor(Color.WHITE);
            cloudStart = SystemClock.uptimeMillis();
            still = reducedMotion(context);
        }

        @Override
        protected void onSizeChanged(int w, int h, int oldw, int oldh) {
            super.onSizeChanged(w, h, oldw, oldh);
            skyPaint.setShader(new android.graphics.LinearGradient(0, 0, 0, h,
                    new int[]{Color.rgb(5, 19, 40), Color.rgb(11, 35, 75), Color.rgb(12, 121, 187)},
                    new float[]{0f, 0.55f, 1f}, android.graphics.Shader.TileMode.CLAMP));
        }

        @Override
        protected void onDraw(Canvas canvas) {
            final float w = getWidth();
            final float h = getHeight();
            if (w <= 0 || h <= 0) return;
            canvas.drawRect(0, 0, w, h, skyPaint);

            long el = still ? 4000L : (SystemClock.uptimeMillis() - cloudStart);
            // far layer: small, faint, slow. mid and near layers drift faster and sit lower.
            float far = (el % 90000L) / 90000f, mid = (el % 60000L) / 60000f, near = (el % 42000L) / 42000f;
            float u = Math.min(w, h * 0.62f); // size unit that keeps clouds proportionate on tablets
            drawCloud(canvas, wrap(w * (0.10f + far), w), h * 0.12f, u * 0.30f, 0.10f);
            drawCloud(canvas, wrap(w * (0.68f + far), w), h * 0.20f, u * 0.24f, 0.08f);
            drawCloud(canvas, wrap(w * (0.30f + mid), w), h * 0.70f, u * 0.38f, 0.14f);
            drawCloud(canvas, wrap(w * (0.85f + mid), w), h * 0.58f, u * 0.28f, 0.11f);
            drawCloud(canvas, wrap(w * (0.05f + near), w), h * 0.84f, u * 0.50f, 0.20f);
            drawCloud(canvas, wrap(w * (0.62f + near), w), h * 0.90f, u * 0.44f, 0.17f);
            if (!still) postInvalidateOnAnimation();
            super.onDraw(canvas);
        }

        private float wrap(float x, float w) {
            float margin = w * 0.30f;
            float span = w + margin * 2f;
            return (((x + margin) % span) + span) % span - margin;
        }

        private void drawCloud(Canvas c, float x, float y, float width, float alpha) {
            cloudPaint.setAlpha(Math.max(0, Math.min(255, (int)(255f * alpha))));
            float ch = width * 0.42f;
            c.drawCircle(x + width * 0.26f, y + ch * 0.58f, ch * 0.23f, cloudPaint);
            c.drawCircle(x + width * 0.45f, y + ch * 0.43f, ch * 0.30f, cloudPaint);
            c.drawCircle(x + width * 0.63f, y + ch * 0.54f, ch * 0.24f, cloudPaint);
            c.drawCircle(x + width * 0.77f, y + ch * 0.62f, ch * 0.18f, cloudPaint);
            c.drawRoundRect(x + width * 0.16f, y + ch * 0.57f,
                    x + width * 0.85f, y + ch * 0.82f, ch * 0.13f, ch * 0.13f, cloudPaint);
        }
    }

    /** Thin indeterminate progress line for the splash (static fill when animations are off). */
    private static class SplashBar extends View {
        private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final long start = SystemClock.uptimeMillis();
        private final boolean still;

        SplashBar(Context c) {
            super(c);
            track.setColor(Color.argb(60, 255, 255, 255));
            fill.setColor(Color.rgb(22, 228, 234));
            still = CloudSplashLayout.reducedMotion(c);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float w = getWidth(), h = getHeight(), r = h / 2f;
            canvas.drawRoundRect(0, 0, w, h, r, r, track);
            float seg = w * 0.38f, x;
            if (still) {
                x = (w - seg) / 2f;
            } else {
                float t = ((SystemClock.uptimeMillis() - start) % 1500L) / 1500f;
                float e = t * t * (3f - 2f * t);
                x = -seg + (w + seg) * e;
            }
            canvas.save();
            canvas.clipRect(0, 0, w, h);
            canvas.drawRoundRect(x, 0, x + seg, h, r, r, fill);
            canvas.restore();
            if (!still) postInvalidateOnAnimation();
        }
    }

    private void setSplashStatus(String text) {
        if (splashStatus != null && !splashDismissed) {
            splashStatus.animate().alpha(0f).setDuration(90).withEndAction(() -> {
                if (splashStatus != null && !splashDismissed) {
                    splashStatus.setText(text);
                    splashStatus.animate().alpha(1f).setDuration(90).start();
                }
            }).start();
        }
    }

    private void forceRevealApp() {
        if (splashDismissed) return;
        splashDismissed = true;

        if (webView != null) {
            webView.setVisibility(View.VISIBLE);
            webView.animate().alpha(1f).setDuration(160).start();
        }

        if (splashView != null) {
            final LinearLayout viewToRemove = splashView;
            viewToRemove.animate()
                    .alpha(0f)
                    .setDuration(160)
                    .withEndAction(() -> {
                        if (rootView != null && viewToRemove.getParent() == rootView) {
                            rootView.removeView(viewToRemove);
                        }
                        if (splashView == viewToRemove) splashView = null;
                        splashStatus = null;
                    })
                    .start();
        }
    }

    private void revealAppWhenReady() {
        if (splashDismissed || webView == null) return;

        // Give the bundled JavaScript one short frame to finish its first money/gauge render.
        webView.evaluateJavascript(
                "(function(){try{" +
                "if(typeof render==='function')render();" +
                "if(typeof refreshPayAviatorLive==='function')refreshPayAviatorLive();" +
                "document.dispatchEvent(new Event('payaviator:gaugechange'));" +
                "}catch(e){} return !!document.getElementById('pp2059Gauge');})()",
                value -> {
                    long elapsed = android.os.SystemClock.uptimeMillis() - splashStartedAt;
                    long remaining = Math.max(0L, 5000L - elapsed);
                    webView.postDelayed(() -> {
                        if (splashDismissed) return;
                        setSplashStatus("Almost ready");
                        webView.postDelayed(this::forceRevealApp, 250);
                    }, remaining);
                }
        );
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    NOTIFICATION_PERMISSION_REQUEST);
        }
    }

    private static Uri soundUri(String sound) {
        if ("silent".equals(sound)) return null;
        if ("alarm".equals(sound))
            return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
        if ("ringtone".equals(sound))
            return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
        return RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
    }

    private static String channelId(String sound, boolean vibrate) {
        return "my_bills_" + sound + "_" + (vibrate ? "vibrate" : "quiet");
    }

    private static void ensureChannel(Context context, String sound, boolean vibrate) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;

        String id = channelId(sound, vibrate);
        NotificationManager nm =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm.getNotificationChannel(id) != null) return;

        NotificationChannel channel = new NotificationChannel(
                id, "PayAviator alerts", NotificationManager.IMPORTANCE_DEFAULT);
        channel.setDescription("Bills and reminder notifications");
        channel.enableVibration(vibrate);
        if (vibrate) channel.setVibrationPattern(new long[]{0, 250, 150, 250});

        Uri uri = soundUri(sound);
        if (uri == null) channel.setSound(null, null);
        else channel.setSound(uri, null);

        nm.createNotificationChannel(channel);
    }


    private void deliverPlaidResultToWeb(final String json) {
        if (webView == null) return;
        final String safe = JSONObject.quote(json == null ? "{}" : json);
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.PayAviatorPlaidNativeResult&&window.PayAviatorPlaidNativeResult(" + safe + ");", null));
    }

    /** Official Plaid Android SDK result: the public token is exchanged only on the backend. */
    private void handleNativePlaidResult(LinkResult result) {
        try {
            JSONObject out = new JSONObject();
            if (result instanceof LinkSuccess) {
                LinkSuccess success = (LinkSuccess) result;
                out.put("status", "connected");
                out.put("public_token", success.getPublicToken() == null ? "" : success.getPublicToken());
                if (success.getMetadata() != null) {
                    if (success.getMetadata().getInstitution() != null) {
                        out.put("institution_name", success.getMetadata().getInstitution().getName());
                        out.put("institution_id", success.getMetadata().getInstitution().getId());
                    }
                    out.put("link_session_id", success.getMetadata().getLinkSessionId());
                }
            } else if (result instanceof LinkExit) {
                LinkExit exit = (LinkExit) result;
                out.put("status", "exit");
                if (exit.getError() != null) {
                    out.put("error_display_message", exit.getError().getDisplayMessage());
                    out.put("error_message", exit.getError().getErrorMessage());
                    out.put("error_code", String.valueOf(exit.getError().getErrorCode()));
                }
            } else {
                out.put("status", "exit");
            }
            deliverPlaidResultToWeb(out.toString());
        } catch (Exception e) {
            deliverPlaidResultToWeb("{\"status\":\"error\",\"message\":\"Plaid finished but its result could not be processed.\"}");
        }
    }

    private void notifyHostedLinkReturned() {
        if (webView == null) return;
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.PayAviatorHostedLinkReturned&&window.PayAviatorHostedLinkReturned();", null));
    }

    private boolean isPlaidReturnUri(Uri data) {
        if (data == null || !"payaviator".equalsIgnoreCase(data.getScheme())) return false;
        String host = data.getHost();
        return "plaid-complete".equalsIgnoreCase(host) || "plaid-oauth-return".equalsIgnoreCase(host);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String alertOpen = alertTargetFrom(intent);
        if (alertOpen != null && !alertOpen.isEmpty()) {
            if (webView != null) {
                final String q = JSONObject.quote(alertOpen);
                runOnUiThread(() -> webView.evaluateJavascript(
                        "window.PayAviatorOpenAlert&&window.PayAviatorOpenAlert(" + q + ");", null));
            } else {
                pendingAlertOpen = alertOpen;
            }
        }
        Uri data = intent == null ? null : intent.getData();
        if (isPlaidReturnUri(data)) {
            // The native Plaid SDK owns its OAuth result. Do not mistake its
            // app-switch redirect for a Hosted Link completion callback.
            if (nativePlaidInProgress) return;
            externalActivityInProgress = false;
            hostedLinkInProgress = false;
            pendingHostedReturn = false;
            notifyHostedLinkReturned();
        }
    }

    /** Notification tap target: our own extra, or FCM data extras when the system showed a background push. */
    private static String alertTargetFrom(Intent intent) {
        if (intent == null) return null;
        String o = intent.getStringExtra(NotificationScheduler.EXTRA_OPEN);
        if (o != null && !o.isEmpty()) return o;
        if ("bank_reconnect".equals(intent.getStringExtra("type"))) {
            String id = intent.getStringExtra("item_id");
            return "reconnect:" + (id == null ? "" : id);
        }
        return null;
    }

    // ---- 4.1.2 FCM device registration (Lucian: POST/DELETE /api/devices/fcm). Fails quietly (404 until deployed). ----
    void registerPushTokenIfSignedIn() {
        try {
            if (signIn == null || signIn.currentUser() == null) return;
            com.google.firebase.messaging.FirebaseMessaging.getInstance().getToken()
                    .addOnSuccessListener(t -> { if (t != null && !t.isEmpty()) registerPushToken(t); });
        } catch (Exception ignored) {}
    }

    void registerPushToken(final String token) {
        if (token == null || token.isEmpty()) return;
        getSharedPreferences(PushService.PREFS, MODE_PRIVATE).edit().putString(PushService.TOKEN_KEY, token).apply();
        if (signIn == null || signIn.currentUser() == null) return;
        new Thread(() -> {
            try {
                JSONObject b = new JSONObject();
                b.put("token", token);
                b.put("platform", "android");
                callBackend("POST", "/api/devices/fcm", b.toString());
            } catch (Exception ignored) {}
        }, "PayAviatorPushRegister").start();
    }

    /** Blocking; call off the UI thread before signing out. */
    private void unregisterPushTokenBlocking() {
        String token = getSharedPreferences(PushService.PREFS, MODE_PRIVATE).getString(PushService.TOKEN_KEY, "");
        if (token == null || token.isEmpty() || signIn == null || signIn.currentUser() == null) return;
        try {
            JSONObject b = new JSONObject();
            b.put("token", token);
            callBackend("DELETE", "/api/devices/fcm", b.toString());
        } catch (Exception ignored) {}
    }

    void deliverPushToWeb(final String json) {
        if (webView == null) return;
        final String q = JSONObject.quote(json);
        runOnUiThread(() -> webView.evaluateJavascript(
                "window.PayAviatorPush&&window.PayAviatorPush.onMessage(" + q + ");", null));
    }

    static void showReconnectNotification(Context ctx, String title, String body, String itemId) {
        PushService.ensureReconnectChannel(ctx);
        Intent launch = new Intent(ctx, MainActivity.class);
        launch.setAction("com.payaviator.app.OPEN_ALERT");
        launch.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        launch.putExtra(NotificationScheduler.EXTRA_OPEN, "reconnect:" + itemId);
        String tag = "bank_reconnect_" + itemId;
        PendingIntent pi = PendingIntent.getActivity(ctx, tag.hashCode() & 0x7fffffff, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder nb = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(ctx, PushService.CHANNEL_RECONNECT) : new Notification.Builder(ctx);
        nb.setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle(title).setContentText(body)
                .setAutoCancel(true).setContentIntent(pi).setVisibility(Notification.VISIBILITY_PRIVATE);
        try {
            JSONObject a = new JSONObject();
            a.put("key", tag); a.put("type", "reconnect"); a.put("title", title); a.put("text", body);
            a.put("open", "reconnect:" + itemId);
            NotificationScheduler.recordFired(ctx, a);
        } catch (Exception ignored) {}
        if (Build.VERSION.SDK_INT < 33 || ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED) {
            NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            nm.notify(tag, 1, nb.build());
        }
    }

    private static final String PAYAVIATOR_API_BASE = "https://api.payaviator.app";
    private static final String DEVICE_PREFS = "payaviator_device_security_v1";
    private static final String DEVICE_ID_KEY = "device_id";

    private String secureRandomToken(int bytes) {
        byte[] raw = new byte[bytes];
        new SecureRandom().nextBytes(raw);
        return Base64.encodeToString(raw, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
    }

    private PlayIntegrity playIntegrity;

    private synchronized PlayIntegrity integrity() {
        if (playIntegrity == null) playIntegrity = new PlayIntegrity(this);
        return playIntegrity;
    }

    /** Settings.Secure.ANDROID_ID: 16 hex, per signing key + Android user; survives reinstall. */
    private String getAndroidId() {
        try {
            return android.provider.Settings.Secure.getString(getContentResolver(), android.provider.Settings.Secure.ANDROID_ID);
        } catch (Exception e) {
            return null;
        }
    }

    private synchronized String getSecureDeviceId() {
        SharedPreferences prefs = getSharedPreferences(DEVICE_PREFS, MODE_PRIVATE);
        String id = prefs.getString(DEVICE_ID_KEY, "");
        if (id == null || id.length() < 20) {
            id = "ppd_" + secureRandomToken(24);
            prefs.edit().putString(DEVICE_ID_KEY, id).apply();
        }
        return id;
    }

    /**
     * One HTTPS call to the PayAviator backend. /api/plaid/* calls carry
     * "Authorization: Bearer <Firebase ID token>". 4.1.0: the three new-bank calls (create-link-token,
     * exchange-public-token, hosted-status) also carry X-Device-Id = ANDROID_ID and, when configured, a
     * Play Integrity token bound to ANDROID_ID|uid (see BackendHeaders, PlayIntegrity).
     */
    private AuthedRequest.Response executeBackendCall(String verb, String safePath, String body, String bearerToken) throws IOException {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(PAYAVIATOR_API_BASE + safePath);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(20000);
            conn.setUseCaches(false);
            conn.setRequestProperty("Accept", "application/json");
            if (bearerToken != null && !bearerToken.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + bearerToken);
            }
            if (BackendHeaders.isNewBankCall(safePath)) {
                String androidId = getAndroidId();
                String deviceId = BackendHeaders.deviceIdFor(safePath, androidId);
                if (deviceId != null) conn.setRequestProperty(BackendHeaders.DEVICE_ID_HEADER, deviceId);
                FirebaseUser u = signIn == null ? null : signIn.currentUser();
                String hash = u == null ? null : BackendHeaders.integrityRequestHash(androidId, u.getUid());
                String it = BackendHeaders.integrityHeaderFor(safePath, hash == null ? null : integrity().tokenFor(hash));
                if (it != null) conn.setRequestProperty(BackendHeaders.INTEGRITY_HEADER, it);
            }
            conn.setRequestMethod(verb);
            boolean deleteWithBody = "DELETE".equals(verb) && safePath.startsWith("/api/devices/") && body != null;
            if ((!"GET".equals(verb) && !"HEAD".equals(verb) && !"DELETE".equals(verb)) || deleteWithBody) {
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] bytes = (body == null ? "" : body).getBytes(StandardCharsets.UTF_8);
                try (OutputStream out = conn.getOutputStream()) { out.write(bytes); }
            }
            int status = conn.getResponseCode();
            InputStream in = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
            java.io.ByteArrayOutputStream raw = new java.io.ByteArrayOutputStream();
            if (in != null) {
                byte[] buf = new byte[4096];
                int n;
                while ((n = in.read(buf)) != -1) raw.write(buf, 0, n);
                in.close();
            }
            return new AuthedRequest.Response(status, new String(raw.toByteArray(), StandardCharsets.UTF_8));
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static String errorBody(String message, String code) {
        try {
            JSONObject o = new JSONObject();
            o.put("error", message);
            o.put("code", code);
            o.put("request_id", JSONObject.NULL);
            return o.toString();
        } catch (Exception e) {
            return "{}";
        }
    }

    /** Runs a backend call under the Firebase token contract (see AuthedRequest). Blocking; background thread only. */
    private AuthedRequest.Response callBackend(String method, String path, String body) throws Exception {
        final String safePath = (path == null || !path.startsWith("/")) ? "/api/health" : path;
        final String verb = (method == null || method.trim().isEmpty()) ? "GET" : method.trim().toUpperCase(Locale.US);
        if (!AuthedRequest.requiresAuth(safePath)) {
            return executeBackendCall(verb, safePath, body, null);
        }
        AuthedRequest.Result r = AuthedRequest.run(
                signIn,
                token -> executeBackendCall(verb, safePath, body, token),
                this::onSessionInvalid);
        switch (r.outcome) {
            case SIGN_IN_REQUIRED:
                runOnUiThread(() -> pushAuthState("sign_in_required"));
                return new AuthedRequest.Response(401, errorBody("Sign in to use bank features.", "SIGN_IN_REQUIRED"));
            case SESSION_EXPIRED:
                return new AuthedRequest.Response(401, errorBody("Your session expired. Please sign in again.", "SESSION_EXPIRED"));
            default:
                return r.response;
        }
    }

    /** Second 401 (or a revoked session): sign out and ask the web layer to show sign-in. */
    private void onSessionInvalid(String reason) {
        runOnUiThread(() -> {
            if (signIn != null) signIn.signOut();
            pushAuthState("session_expired");
        });
    }

    /** Pushes sign-in state (never tokens) to the WebView. */
    private void pushAuthState(String reason) {
        if (webView == null || signIn == null) return;
        try {
            JSONObject state = signIn.stateJson();
            if (reason != null) state.put("reason", reason);
            final String payload = JSONObject.quote(state.toString());
            runOnUiThread(() -> {
                if (webView != null) webView.evaluateJavascript(
                        "window.PayAviatorAuthStateChanged&&window.PayAviatorAuthStateChanged(" + payload + ");", null);
            });
        } catch (Exception ignored) { }
    }

    private void deliverAuthResult(String requestId, boolean ok, String code, String message) {
        if (webView == null) return;
        try {
            JSONObject out = new JSONObject();
            out.put("requestId", requestId == null ? "" : requestId);
            out.put("ok", ok);
            out.put("code", code == null ? "" : code);
            out.put("error", message == null ? "" : message);
            out.put("state", signIn == null ? new JSONObject() : signIn.stateJson());
            final String payload = JSONObject.quote(out.toString());
            runOnUiThread(() -> {
                if (webView != null) webView.evaluateJavascript(
                        "window.PayAviatorAuthResult&&window.PayAviatorAuthResult(" + payload + ");", null);
            });
        } catch (Exception ignored) { }
    }

    /**
     * Account deletion: DELETE /api/plaid/user (removes every bank at Plaid and all stored data)
     * must succeed before the Firebase user is deleted, so no Item is orphaned at Plaid.
     */
    private void deleteAccountFlow(final String requestId) {
        if (signIn == null || signIn.currentUser() == null) {
            deliverAuthResult(requestId, false, "SIGN_IN_REQUIRED", "Sign in first.");
            return;
        }
        if (!signIn.hasRecentLogin()) {
            // Ask for a fresh sign-in BEFORE removing banks, so we never end up with banks
            // deleted but the Firebase user still present.
            deliverAuthResult(requestId, false, "REQUIRES_RECENT_LOGIN",
                    "For your security, sign in again, then delete your account.");
            return;
        }
        new Thread(() -> {
            try {
                AuthedRequest.Response r = callBackend("DELETE", "/api/plaid/user", "");
                if (r.status < 200 || r.status >= 300) {
                    String msg = "Could not remove your bank connections. Please try again.";
                    String code = "DELETE_BANKS_FAILED";
                    try {
                        JSONObject j = new JSONObject(r.body);
                        if (j.optString("code").length() > 0) code = j.optString("code");
                        if (j.optString("error").length() > 0) msg = j.optString("error");
                        if (j.has("request_id")) android.util.Log.w("PayAviatorAuth", "delete user failed request_id=" + j.optString("request_id"));
                    } catch (Exception ignored) { }
                    deliverAuthResult(requestId, false, code, msg);
                    return;
                }
                runOnUiThread(() -> signIn.deleteFirebaseUser((ok, code, message) -> {
                    deliverAuthResult(requestId, ok, code, message);
                    pushAuthState(ok ? "account_deleted" : null);
                }));
            } catch (Exception e) {
                deliverAuthResult(requestId, false, "NETWORK", "Couldn't reach PayAviator. Check your connection and try again.");
            }
        }, "PayAviatorDeleteAccount").start();
    }

    private void deliverNativeApiResult(final String requestId, final int status, final String body, final String error) {
        if (webView == null) return;
        try {
            JSONObject out = new JSONObject();
            out.put("requestId", requestId == null ? "" : requestId);
            out.put("status", status);
            out.put("body", body == null ? "" : body);
            out.put("error", error == null ? "" : error);
            final String payload = JSONObject.quote(out.toString());
            runOnUiThread(() -> webView.evaluateJavascript(
                    "window.PayAviatorNativeApiResult&&window.PayAviatorNativeApiResult(" + payload + ");", null));
        } catch (Exception ignored) { }
    }

    static final String SUPPORT_EMAIL = "support@payaviator.app";

    /** Subject 'PayAviator support'; body = app version + Android version only (no user id or account data). */
    static String supportBody(String appVersion, String androidVersion) {
        return "App version: " + (appVersion == null ? "" : appVersion) + "\nAndroid version: " + (androidVersion == null ? "" : androidVersion) + "\n\n";
    }

    private boolean startSupportEmail() {
        String ver = "";
        try { android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0); ver = info.versionName == null ? "" : info.versionName; } catch (Exception ignored) { }
        String body = supportBody(ver, Build.VERSION.RELEASE);
        Uri uri = Uri.parse("mailto:" + SUPPORT_EMAIL + "?subject=" + Uri.encode("PayAviator support") + "&body=" + Uri.encode(body));
        Intent i = new Intent(Intent.ACTION_SENDTO, uri);
        i.putExtra(Intent.EXTRA_EMAIL, new String[]{SUPPORT_EMAIL});
        i.putExtra(Intent.EXTRA_SUBJECT, "PayAviator support");
        i.putExtra(Intent.EXTRA_TEXT, body);
        try {
            if (i.resolveActivity(getPackageManager()) == null) return false;   // no email app: the page shows the address in-app
            final Intent f = i;
            runOnUiThread(() -> { try { startActivity(f); } catch (Exception ignored) { } });
            return true;
        } catch (Exception e) { return false; }
    }

    public class AndroidBridge {

        // Durable backup for the bill calendar. This is kept in Android private
        // app storage, separately from WebView localStorage and IndexedDB.
        @JavascriptInterface
        public boolean saveBillsSnapshot(String payload) {
            if (payload == null || payload.length() > 2500000) return false;
            try {
                JSONObject state = new JSONObject(payload);
                if (state.optJSONArray("bills") == null || state.optLong("rev", 0L) <= 0L) return false;
                return getSharedPreferences("payaviator_bill_calendar_v392", MODE_PRIVATE)
                        .edit().putString("snapshot", payload).commit();
            } catch (Exception ignored) { return false; }
        }

        @JavascriptInterface
        public String loadBillsSnapshot() {
            try {
                return getSharedPreferences("payaviator_bill_calendar_v392", MODE_PRIVATE)
                        .getString("snapshot", "");
            } catch (Exception ignored) { return ""; }
        }

        /** 4.1.1 Contact support: opens the email app (mailto intent). Body has only app + Android version. */
        @JavascriptInterface
        public boolean openSupportEmail() {
            return startSupportEmail();
        }

        @JavascriptInterface
        public String getAppVersionName() {
            try { android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0); return info.versionName == null ? "" : info.versionName; }
            catch (Exception ignored) { return ""; }
        }

        @JavascriptInterface
        public String getSecureDeviceId() {
            return MainActivity.this.getSecureDeviceId();
        }

        @JavascriptInterface
        public long getAppVersionCode() {
            try { android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0); if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) return info.getLongVersionCode(); return info.versionCode; }
            catch (Exception ignored) { return 0L; }
        }


        @JavascriptInterface
        public void apiRequest(final String requestId, final String method, final String path, final String body) {
            new Thread(() -> {
                try {
                    AuthedRequest.Response r = callBackend(method, path, body);
                    deliverNativeApiResult(requestId, r.status, r.body, "");
                } catch (Exception e) {
                    deliverNativeApiResult(requestId, 0, "", e.getClass().getSimpleName() + ": " + (e.getMessage() == null ? "Network request failed" : e.getMessage()));
                }
            }, "PayAviatorApi").start();
        }

        // ---- Firebase sign-in (bank features only). Tokens never cross into the WebView. ----

        @JavascriptInterface
        public String authGetState() {
            return signIn == null ? "{\"available\":false,\"signedIn\":false}" : signIn.stateJson().toString();
        }

        @JavascriptInterface
        public void authSignInWithGoogle(final String requestId) {
            runOnUiThread(() -> signIn.signInWithGoogle((ok, code, msg) -> deliverAuthResult(requestId, ok, code, msg)));
        }

        @JavascriptInterface
        public void authSignInWithEmail(final String requestId, final String email, final String password) {
            runOnUiThread(() -> signIn.signInWithEmail(email, password, (ok, code, msg) -> deliverAuthResult(requestId, ok, code, msg)));
        }

        @JavascriptInterface
        public void authCreateAccount(final String requestId, final String email, final String password) {
            runOnUiThread(() -> signIn.createAccount(email, password, (ok, code, msg) -> deliverAuthResult(requestId, ok, code, msg)));
        }

        @JavascriptInterface
        public void authSendEmailVerification(final String requestId) {
            runOnUiThread(() -> signIn.sendEmailVerification((ok, code, msg) -> deliverAuthResult(requestId, ok, code, msg)));
        }

        @JavascriptInterface
        public void authReloadUser(final String requestId) {
            runOnUiThread(() -> signIn.reloadAndRefreshToken((ok, code, msg) -> {
                deliverAuthResult(requestId, ok, code, msg);
                pushAuthState(null);
            }));
        }

        @JavascriptInterface
        public void authSendPasswordReset(final String requestId, final String email) {
            runOnUiThread(() -> signIn.sendPasswordReset(email, (ok, code, msg) -> deliverAuthResult(requestId, ok, code, msg)));
        }

        @JavascriptInterface
        public void authSignOut(final String requestId) {
            // 4.1.2: remove this phone's push token from the server first (best effort, never blocks sign-out on errors).
            new Thread(() -> {
                unregisterPushTokenBlocking();
                runOnUiThread(() -> {
                    signIn.signOut();
                    deliverAuthResult(requestId, true, "", "");
                    pushAuthState("signed_out");
                });
            }, "PayAviatorSignOut").start();
        }

        @JavascriptInterface
        public void authDeleteAccount(final String requestId) {
            runOnUiThread(() -> deleteAccountFlow(requestId));
        }

        @JavascriptInterface
        public void openPlaidLink(final String linkToken) {
            runOnUiThread(() -> {
                try {
                    if (linkToken == null || linkToken.trim().isEmpty())
                        throw new IllegalArgumentException("Missing Plaid link token");
                    LinkTokenConfiguration configuration = new LinkTokenConfiguration.Builder()
                            .token(linkToken).build();
                    nativePlaidInProgress = true;
                    externalActivityInProgress = true;
                    Plaid.createPlaidLinkSession(MainActivity.this, configuration).open(MainActivity.this);
                } catch (Exception e) {
                    nativePlaidInProgress = false;
                    externalActivityInProgress = false;
                    deliverPlaidResultToWeb("{\"status\":\"error\",\"message\":\"Plaid could not open. Check that the backend creates Android Link tokens and that com.payaviator.app is allowed in Plaid.\"}");
                }
            });
        }

        @JavascriptInterface
        public void openPlaidHostedLink(final String url) {
            runOnUiThread(() -> {
                try {
                    Uri uri = Uri.parse(url == null ? "" : url);
                    if (!"https".equalsIgnoreCase(uri.getScheme())) throw new IllegalArgumentException("Invalid URL");
                    externalActivityInProgress = true;
                    hostedLinkInProgress = true;
                    Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                    intent.addCategory(Intent.CATEGORY_BROWSABLE);
                    startActivity(intent);
                } catch (Exception e) {
                    externalActivityInProgress = false;
                    hostedLinkInProgress = false;
                    deliverPlaidResultToWeb("{\"status\":\"error\",\"message\":\"Unable to open secure bank connection.\"}");
                }
            });
        }

        @JavascriptInterface
        public boolean isAppLockEnabled() {
            return MainActivity.this.isAppLockEnabled();
        }

        @JavascriptInterface
        public boolean isDeviceSecure() {
            return MainActivity.this.isDeviceSecure();
        }

        @JavascriptInterface
        public boolean areRealAccountsConnected() {
            return MainActivity.this.areRealAccountsConnected();
        }

        @JavascriptInterface
        public void setRealAccountsConnected(boolean connected) {
            runOnUiThread(() -> MainActivity.this.setRealAccountsConnectedNative(connected));
        }

        @JavascriptInterface
        public void setAppLockEnabled(boolean enabled) {
            setAppLockEnabledNative(enabled);
            runOnUiThread(() -> Toast.makeText(
                    MainActivity.this,
                    enabled ? "PIN Lock enabled. Brief app switches stay unlocked for 5 minutes." : "PIN Lock disabled.",
                    Toast.LENGTH_SHORT
            ).show());
        }

        @JavascriptInterface
        public void lockNow() {
            runOnUiThread(() -> {
                authenticatedForSession = false;
                clearUnlockGracePeriod();
                showLockedScreen();
                authenticateUser();
            });
        }
        @JavascriptInterface
        public void saveBackup(final String json) {
            runOnUiThread(() -> {
                pendingBackupJson = json;

                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/json");
                intent.putExtra(Intent.EXTRA_TITLE, "payaviator-backup.json");

                try {
                    externalActivityInProgress = true;
            startActivityForResult(intent, SAVE_BACKUP_REQUEST);
                } catch (Exception e) {
                    pendingBackupJson = null;
                    Toast.makeText(MainActivity.this,
                            "Unable to choose a save location.", Toast.LENGTH_SHORT).show();
                }
            });
        }


        @JavascriptInterface
        public void saveBase64File(final String filename, final String base64) {
            runOnUiThread(() -> {
                pendingTextExport = base64 == null ? "" : base64;
                pendingTextBase64 = true;
                pendingTextFilename = (filename == null || filename.trim().isEmpty())
                        ? "PayAviator_summary.pdf" : filename;
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("application/pdf");
                intent.putExtra(Intent.EXTRA_TITLE, pendingTextFilename);
                try {
                    externalActivityInProgress = true;
                    startActivityForResult(intent, SAVE_TEXT_REQUEST);
                } catch (Exception e) {
                    pendingTextExport = null;
                    pendingTextFilename = null;
                    pendingTextBase64 = false;
                    Toast.makeText(MainActivity.this,
                            "Unable to choose a save location.", Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public void saveTextFile(final String filename, final String text) {
            runOnUiThread(() -> {
                pendingTextExport = text;
                pendingTextBase64 = false;
                pendingTextFilename = (filename == null || filename.trim().isEmpty())
                        ? "PayAviator_summary.txt" : filename;

                String name = pendingTextFilename.toLowerCase();
                String mime = "text/plain";
                if (name.endsWith(".pdf")) mime = "application/pdf";
                else if (name.endsWith(".json")) mime = "application/json";
                Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType(mime);
                intent.putExtra(Intent.EXTRA_TITLE, pendingTextFilename);

                try {
                    externalActivityInProgress = true;
            startActivityForResult(intent, SAVE_TEXT_REQUEST);
                } catch (Exception e) {
                    pendingTextExport = null;
                    pendingTextFilename = null;
                    Toast.makeText(MainActivity.this,
                            "Unable to choose a save location.", Toast.LENGTH_SHORT).show();
                }
            });
        }

        /** 4.1.2: notifications that fired while the app was closed, for the Alerts center (cleared once read). */
        @JavascriptInterface
        public String takeFiredAlerts() {
            return NotificationScheduler.takeFired(MainActivity.this);
        }

        /** 4.1.2: the alert target the app was launched from (notification tap), once. */
        @JavascriptInterface
        public String takeLaunchAlert() {
            String v = pendingAlertOpen;
            pendingAlertOpen = null;
            return v == null ? "" : v;
        }

        /** 4.1.2: true when Android allows PayAviator to post notifications. */
        @JavascriptInterface
        public boolean notificationsAllowed() {
            if (Build.VERSION.SDK_INT < 33) return true;
            return checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        }

        @JavascriptInterface
        public void requestNotificationPermission() {
            runOnUiThread(() -> requestNotificationPermissionIfNeeded());
        }

        @JavascriptInterface
        public void testNotification(final String json) {
            runOnUiThread(() -> {
                try {
                    requestNotificationPermissionIfNeeded();
                    JSONObject obj = new JSONObject(json);
                    String title = obj.optString("title", "PayAviator test");
                    String text = obj.optString("text", "Notifications are working.");
                    String sound = obj.optString("sound", "default");
                    boolean vibrate = obj.optBoolean("vibrate", true);
                    showNotification(MainActivity.this, title, text, sound, vibrate);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this,
                            "Could not send test notification.", Toast.LENGTH_SHORT).show();
                }
            });
        }

        @JavascriptInterface
        public void scheduleNotifications(final String json) {
            runOnUiThread(() -> {
                try {
                    JSONObject root = new JSONObject(json);
                    if (root.has("alarms")) {
                        // 4.1.2 plan: flat list built by the web app; stored for reboot re-arm.
                        cancelScheduledNotifications();
                        String snd = root.optString("sound", "default");
                        boolean vib = root.optBoolean("vibrate", true);
                        ensureChannel(MainActivity.this, snd, vib);
                        boolean any = root.optBoolean("enabled", false) || root.optBoolean("reminderEnabled", true);
                        JSONArray al = root.optJSONArray("alarms");
                        if (any && al != null && al.length() > 0) requestNotificationPermissionIfNeeded();
                        NotificationScheduler.apply(MainActivity.this, json);
                        return;
                    }
                    boolean billsEnabled = root.optBoolean("enabled", false);
                    boolean remindersEnabled = root.optBoolean("reminderEnabled", true);
                    String sound = root.optString("sound", "default");
                    boolean vibrate = root.optBoolean("vibrate", true);

                    cancelScheduledNotifications();
                    ensureChannel(MainActivity.this, sound, vibrate);

                    if (!billsEnabled && !remindersEnabled) return;

                    requestNotificationPermissionIfNeeded();

                    int daysBefore = Math.max(0, Math.min(31,
                            root.optInt("daysBefore", 3)));
                    String time = root.optString("time", "09:00");
                    int requestIndex = 0;

                    if (billsEnabled) {
                        JSONArray bills = root.optJSONArray("bills");
                        if (bills != null)
                            requestIndex = scheduleBillAlarms(
                                    bills, daysBefore, time, sound, vibrate, requestIndex);
                    }

                    if (remindersEnabled) {
                        JSONArray reminders = root.optJSONArray("reminders");
                        if (reminders != null)
                            scheduleReminderAlarms(
                                    reminders, sound, vibrate, requestIndex);
                    }

                    Toast.makeText(MainActivity.this,
                            "Notifications updated.", Toast.LENGTH_SHORT).show();
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this,
                            "Could not schedule notifications.", Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    private void cancelScheduledNotifications() {
        AlarmManager alarmManager =
                (AlarmManager) getSystemService(Context.ALARM_SERVICE);

        for (int i = 0; i < 1200; i++) {
            Intent intent = new Intent(this, ReminderReceiver.class);
            PendingIntent pi = PendingIntent.getBroadcast(
                    this, REQUEST_BASE + i, intent,
                    PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);
            if (pi != null) {
                alarmManager.cancel(pi);
                pi.cancel();
            }
        }
    }

    private void scheduleAlarm(long whenMillis, int requestCode,
                               String title, String text,
                               String sound, boolean vibrate) {
        if (whenMillis <= System.currentTimeMillis()) return;

        Intent intent = new Intent(this, ReminderReceiver.class);
        intent.putExtra("title", title);
        intent.putExtra("text", text);
        intent.putExtra("sound", sound);
        intent.putExtra("vibrate", vibrate);

        PendingIntent pi = PendingIntent.getBroadcast(
                this, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        AlarmManager alarmManager =
                (AlarmManager) getSystemService(Context.ALARM_SERVICE);
        alarmManager.setAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP, whenMillis, pi);
    }

    private int scheduleBillAlarms(JSONArray bills, int daysBefore, String time,
                                   String sound, boolean vibrate,
                                   int requestIndex) throws Exception {

        String[] hm = time.split(":");
        int hour = Integer.parseInt(hm[0]);
        int minute = hm.length > 1 ? Integer.parseInt(hm[1]) : 0;

        Calendar horizon = Calendar.getInstance();
        horizon.add(Calendar.MONTH, 12);
        SimpleDateFormat df = new SimpleDateFormat("yyyy-MM-dd", Locale.US);

        for (int i = 0; i < bills.length() && requestIndex < 1000; i++) {
            JSONObject b = bills.getJSONObject(i);
            String name = b.optString("name", "Bill");
            double amount = b.optDouble("amount", 0);
            String due = b.optString("due", "");
            boolean recurring = b.optBoolean("recurring", false);
            String recurrence = b.optString("recurrence", "monthly");

            Date firstDate = df.parse(due);
            if (firstDate == null) continue;

            Calendar occurrence = Calendar.getInstance();
            occurrence.setTime(firstDate);

            while (occurrence.before(horizon) && requestIndex < 1000) {
                Calendar fire = (Calendar) occurrence.clone();
                fire.add(Calendar.DAY_OF_MONTH, -daysBefore);
                fire.set(Calendar.HOUR_OF_DAY, hour);
                fire.set(Calendar.MINUTE, minute);
                fire.set(Calendar.SECOND, 0);
                fire.set(Calendar.MILLISECOND, 0);

                if (fire.getTimeInMillis() > System.currentTimeMillis()) {
                    String text = name + " — $" +
                            String.format(Locale.US, "%.2f", amount) +
                            " due " + df.format(occurrence.getTime());

                    scheduleAlarm(
                            fire.getTimeInMillis(),
                            REQUEST_BASE + requestIndex,
                            name + " bill reminder",
                            text, sound, vibrate);
                    requestIndex++;
                }

                if (!recurring) break;
                if ("weekly".equals(recurrence))
                    occurrence.add(Calendar.DAY_OF_MONTH, 7);
                else if ("biweekly".equals(recurrence))
                    occurrence.add(Calendar.DAY_OF_MONTH, 14);
                else
                    occurrence.add(Calendar.MONTH, 1);
            }
        }
        return requestIndex;
    }

    private int scheduleReminderAlarms(JSONArray reminders,
                                       String sound, boolean vibrate,
                                       int requestIndex) throws Exception {
        SimpleDateFormat df =
                new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US);

        for (int i = 0; i < reminders.length() && requestIndex < 1100; i++) {
            JSONObject r = reminders.getJSONObject(i);
            String name = r.optString("name", "Reminder");
            String date = r.optString("date", "");
            String time = r.optString("time", "09:00");
            String notes = r.optString("notes", "");

            Date fire = df.parse(date + " " + time);
            if (fire == null || fire.getTime() <= System.currentTimeMillis())
                continue;

            String text = notes.trim().isEmpty() ? name : notes;
            scheduleAlarm(
                    fire.getTime(),
                    REQUEST_BASE + requestIndex,
                    name, text, sound, vibrate);
            requestIndex++;
        }
        return requestIndex;
    }

    public static class ReminderReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            String key = intent.getStringExtra("key");
            if (key != null) {
                // 4.1.2 plan alarm: only show it if it is still in the current plan (not paid / edited / deleted).
                JSONObject a = NotificationScheduler.find(context, key);
                if (a == null) return;
                String snd = a.optString("sound", "default");
                boolean vib = a.optBoolean("vibrate", true);
                ensureChannel(context, snd, vib);
                showNotification(context, a.optString("title", "PayAviator"), a.optString("text", ""),
                        snd, vib, a.optString("open", "home"),
                        a.optString("publicTitle", "PayAviator reminder"),
                        a.optString("publicText", "Unlock to see details."),
                        a.optBoolean("_showAmounts", false), key.hashCode() & 0x7fffffff);
                NotificationScheduler.recordFired(context, a);
                return;
            }
            String title = intent.getStringExtra("title");
            String text = intent.getStringExtra("text");
            String sound = intent.getStringExtra("sound");
            boolean vibrate = intent.getBooleanExtra("vibrate", true);

            if (sound == null) sound = "default";
            ensureChannel(context, sound, vibrate);
            showNotification(context,
                    title != null ? title : "PayAviator",
                    text != null ? text : "You have an upcoming reminder.",
                    sound, vibrate);
        }
    }

    private static void showNotification(Context context,
                                         String title, String text,
                                         String sound, boolean vibrate) {
        showNotification(context, title, text, sound, vibrate, "home",
                "PayAviator", "Unlock to see details.", false,
                (int)(System.currentTimeMillis() & 0x7fffffff));
    }

    /**
     * 4.1.2: tapping opens the related screen (open target), and the lock screen shows a generic public
     * version ("A bill is due tomorrow") unless the user turned on "Show amounts on lock screen".
     */
    static void showNotification(Context context,
                                         String title, String text,
                                         String sound, boolean vibrate,
                                         String open, String publicTitle, String publicText,
                                         boolean showOnLockScreen, int notifyId) {
        NotificationManager nm =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);

        String channel = channelId(sound, vibrate);
        ensureChannel(context, sound, vibrate);

        Intent launch = new Intent(context, MainActivity.class);
        launch.setAction("com.payaviator.app.OPEN_ALERT");
        launch.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        launch.putExtra(NotificationScheduler.EXTRA_OPEN, open == null || open.isEmpty() ? "home" : open);
        PendingIntent contentIntent = PendingIntent.getActivity(
                context, notifyId, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder builder =
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? new Notification.Builder(context, channel)
                        : new Notification.Builder(context);

        builder.setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true);

        if (showOnLockScreen) {
            builder.setVisibility(Notification.VISIBILITY_PUBLIC);
        } else {
            Notification.Builder pub =
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                            ? new Notification.Builder(context, channel)
                            : new Notification.Builder(context);
            pub.setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setContentTitle(publicTitle)
                    .setContentText(publicText);
            builder.setVisibility(Notification.VISIBILITY_PRIVATE)
                    .setPublicVersion(pub.build());
        }

        if (contentIntent != null) builder.setContentIntent(contentIntent);

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            Uri uri = soundUri(sound);
            if (uri != null) builder.setSound(uri);
            if (vibrate) builder.setVibrate(new long[]{0, 250, 150, 250});
        }

        if (Build.VERSION.SDK_INT < 33 ||
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        == PackageManager.PERMISSION_GRANTED) {
            nm.notify(notifyId, builder.build());
        }
    }


    private boolean areRealAccountsConnected() {
        // 4.1.4: App lock is never mandatory, so the UI treats this as false (flag is still stored).
        if (true) return false;
        return getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .getBoolean(SECURITY_REAL_ACCOUNTS_KEY, false);
    }

    /** 4.1.4: one-time reset so App lock is OFF after upgrading from any older version. */
    private void migrateAppLockDefaultOff() {
        SharedPreferences prefs = getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE);
        if (prefs.getInt(SECURITY_STORAGE_VERSION_KEY, 0) >= 414) return;
        prefs.edit()
                .putBoolean(SECURITY_ENABLED_KEY, false)
                .remove(SECURITY_LAST_UNLOCK_KEY)
                .putInt(SECURITY_STORAGE_VERSION_KEY, 414)
                .apply();
    }

    private boolean isAppLockEnabled() {
        SharedPreferences prefs = getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE);
        // 4.1.4: App lock is opt-in only. Connecting a bank no longer forces it on.
        return prefs.getBoolean(SECURITY_ENABLED_KEY, false);
    }

    private boolean isWithinUnlockGracePeriod() {
        if (!isAppLockEnabled()) return true;
        long last = getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .getLong(SECURITY_LAST_UNLOCK_KEY, 0L);
        return last > 0L && (System.currentTimeMillis() - last) < RELOCK_AFTER_MS;
    }

    private void rememberSuccessfulUnlock() {
        getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .edit().putLong(SECURITY_LAST_UNLOCK_KEY, System.currentTimeMillis()).apply();
    }

    private void clearUnlockGracePeriod() {
        getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .edit().remove(SECURITY_LAST_UNLOCK_KEY).apply();
    }

    private void setAppLockEnabledNative(boolean enabled) {
        getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .edit()
                .putBoolean(SECURITY_ENABLED_KEY, enabled)
                .remove(SECURITY_LAST_UNLOCK_KEY)
                .apply();
    }

    private void setRealAccountsConnectedNative(boolean connected) {
        SharedPreferences prefs = getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE);
        boolean wasConnected = prefs.getBoolean(SECURITY_REAL_ACCOUNTS_KEY, false);
        prefs.edit().putBoolean(SECURITY_REAL_ACCOUNTS_KEY, connected).apply();
        // 4.1.4: no automatic lock when the first bank connects; the user turns App lock on in Settings.
    }

    private boolean isDeviceSecure() {
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (km == null) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            return km.isDeviceSecure();
        }
        return km.isKeyguardSecure();
    }

    private void showLockedScreen() {
        lockView = new LinearLayout(this);
        lockView.setOrientation(LinearLayout.VERTICAL);
        lockView.setGravity(Gravity.CENTER);
        lockView.setPadding(48, 48, 48, 48);
        lockView.setBackgroundColor(Color.rgb(7, 24, 51));

        TextView icon = new TextView(this);
        icon.setText("🔒");
        icon.setTextSize(44);
        icon.setGravity(Gravity.CENTER);

        TextView title = new TextView(this);
        title.setText("PayAviator Locked");
        title.setTextColor(Color.WHITE);
        title.setTextSize(26);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 18, 0, 8);

        TextView sub = new TextView(this);
        sub.setText("Authenticate to view your financial information.");
        sub.setTextColor(Color.rgb(197, 209, 226));
        sub.setTextSize(15);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, 0, 0, 26);

        Button unlock = new Button(this);
        unlock.setText("Unlock PayAviator");
        unlock.setOnClickListener(v -> authenticateUser());

        lockView.addView(icon);
        lockView.addView(title);
        lockView.addView(sub);
        lockView.addView(unlock);

        // Overlay on the existing root — never destroy the WebView.
        if (rootView != null) {
            if (lockView.getParent() == null) {
                rootView.addView(lockView, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.MATCH_PARENT));
            }
            lockView.setVisibility(View.VISIBLE);
            lockView.bringToFront();
            if (webView != null) webView.setVisibility(View.VISIBLE);
            setContentView(rootView);
        } else {
            setContentView(lockView);
        }
    }

    private void authenticateUser() {
        if (authenticationInProgress) return;

        if (!isAppLockEnabled()) {
            unlockAndCreateWebView();
            return;
        }

        if (!isDeviceSecure()) {
            Toast.makeText(
                    this,
                    "Set up a PIN, pattern, password, or fingerprint in Android first. PIN Lock stayed off for this session.",
                    Toast.LENGTH_LONG
            ).show();
            unlockAndCreateWebView();
            return;
        }

        authenticationInProgress = true;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            showBiometricPrompt();
        } else {
            showDeviceCredentialPrompt();
        }
    }

    private void showBiometricPrompt() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            authenticationInProgress = false;
            showDeviceCredentialPrompt();
            return;
        }

        FingerprintManager fingerprintManager =
                (FingerprintManager) getSystemService(FINGERPRINT_SERVICE);

        if (fingerprintManager == null
                || !fingerprintManager.isHardwareDetected()
                || !fingerprintManager.hasEnrolledFingerprints()) {
            authenticationInProgress = false;
            showDeviceCredentialPrompt();
            return;
        }

        CancellationSignal cancellationSignal = new CancellationSignal();

        fingerprintManager.authenticate(
                null,
                cancellationSignal,
                0,
                new FingerprintManager.AuthenticationCallback() {
                    @Override
                    public void onAuthenticationSucceeded(
                            FingerprintManager.AuthenticationResult result) {
                        super.onAuthenticationSucceeded(result);
                        authenticationInProgress = false;
                        unlockAndCreateWebView();
                    }

                    @Override
                    public void onAuthenticationFailed() {
                        super.onAuthenticationFailed();
                        Toast.makeText(
                                MainActivity.this,
                                "Fingerprint not recognized. Try again.",
                                Toast.LENGTH_SHORT
                        ).show();
                    }

                    @Override
                    public void onAuthenticationError(
                            int errorCode,
                            CharSequence errString) {
                        super.onAuthenticationError(errorCode, errString);
                        authenticationInProgress = false;
                        showDeviceCredentialPrompt();
                    }
                },
                null
        );
    }

    private void showDeviceCredentialPrompt() {
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        if (km == null) {
            authenticationInProgress = false;
            return;
        }

        Intent intent = km.createConfirmDeviceCredentialIntent(
                "Unlock PayAviator",
                "Confirm your phone security to continue."
        );

        if (intent == null) {
            authenticationInProgress = false;
            Toast.makeText(this, "Device security is unavailable.", Toast.LENGTH_SHORT).show();
            return;
        }

        externalActivityInProgress = true;
        startActivityForResult(intent, DEVICE_CREDENTIAL_REQUEST);
    }

    private void relockIfNeeded() {
        if (!isAppLockEnabled() || !authenticatedForSession || authenticationInProgress) return;

        long awayFor = stoppedAtElapsed > 0L
                ? SystemClock.elapsedRealtime() - stoppedAtElapsed
                : 0L;

        if (awayFor >= RELOCK_AFTER_MS) {
            authenticatedForSession = false;
            stoppedAtElapsed = 0L;
            showLockedScreen();
            authenticateUser();
        } else {
            // Quick app switches stay unlocked and refresh the grace window.
            stoppedAtElapsed = 0L;
            rememberSuccessfulUnlock();
            if (webView != null) {
                webView.setVisibility(View.VISIBLE);
                webView.setAlpha(1f);
            }
        }
    }

    @Override
    protected void onPause() {
        if (PushService.foreground == this) PushService.foreground = null;
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        PushService.foreground = this;
        if (webView != null) {
            webView.setVisibility(View.VISIBLE);
            webView.setAlpha(1f);
            webView.onResume();
            webView.post(() -> webView.evaluateJavascript(
                "(function(){try{" +
                "document.body&&document.body.classList.add('pp-gauge-ready');" +
                "var s=document.getElementById('mb119Shell');if(s){s.style.display='block';s.style.visibility='visible';s.style.opacity='1';}" +
                "var n=document.getElementById('mb119BottomNav');if(n){n.style.display='flex';n.style.opacity='1';n.style.pointerEvents='auto';}" +
                "['pp920AccountsModal','pp826Modal','ppThemeNotice'].forEach(function(id){var e=document.getElementById(id);if(e&&!e.classList.contains('show')){e.style.display='none';}});" +
                "var views=document.querySelectorAll('#mb119Shell > .mb119-view');" +
                "var any=false;views.forEach(function(v){if(v.classList.contains('active')){any=true;v.style.display='block';v.style.opacity='1';}});" +
                "if(!any&&views[0]){views[0].classList.add('active');views[0].style.display='block';}" +
                "}catch(e){}})();",
                null));
        }
        // Hosted Link runs outside the app. If the user returns via Back instead
        // of the custom callback, ask the web layer to check /link/token/get.
        if (hostedLinkInProgress) {
            hostedLinkInProgress = false;
            externalActivityInProgress = false;
            if (webView != null) {
                webView.postDelayed(() -> notifyHostedLinkReturned(), 450);
            } else {
                pendingHostedReturn = true;
            }
        }
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (!externalActivityInProgress) {
            relockIfNeeded();
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (!externalActivityInProgress && authenticatedForSession) {
            stoppedAtElapsed = SystemClock.elapsedRealtime();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == DEVICE_CREDENTIAL_REQUEST) {
            externalActivityInProgress = false;
            authenticationInProgress = false;
            if (resultCode == RESULT_OK) {
                unlockAndCreateWebView();
            } else {
                showLockedScreen();
                Toast.makeText(this, "PayAviator is still locked.", Toast.LENGTH_SHORT).show();
            }
            return;
        }

        externalActivityInProgress = false;

        // Plaid SDK v6 uses its own Activity request code. parseResult returns
        // null for unrelated activities (document chooser, authentication etc.).
        if (nativePlaidInProgress) {
            LinkResult plaidResult = Plaid.parseResult(requestCode, resultCode, data);
            if (plaidResult != null) {
                nativePlaidInProgress = false;
                externalActivityInProgress = false;
                handleNativePlaidResult(plaidResult);
                return;
            }
        }

        if (requestCode == PLAID_LINK_REQUEST) {
            if (resultCode == RESULT_OK && data != null) {
                String resultJson = data.getStringExtra("plaid_result");
                deliverPlaidResultToWeb(resultJson == null ? "{}" : resultJson);
            } else {
                deliverPlaidResultToWeb("{\"status\":\"exit\"}");
            }
            return;
        }

        if (requestCode == FILE_CHOOSER_REQUEST) {
            if (filePathCallback == null) return;

            Uri[] results = null;
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                results = new Uri[]{data.getData()};
            }

            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
            return;
        }


        if (requestCode == SAVE_TEXT_REQUEST) {
            if (resultCode == RESULT_OK
                    && data != null
                    && data.getData() != null
                    && pendingTextExport != null) {
                Uri uri = data.getData();
                try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                    if (out != null) {
                        byte[] bytes;
                        if (pendingTextBase64) {
                            bytes = Base64.decode(pendingTextExport, Base64.DEFAULT);
                        } else {
                            bytes = pendingTextExport.getBytes(StandardCharsets.UTF_8);
                        }
                        out.write(bytes);
                        out.flush();
                        Toast.makeText(this,
                                "PayAviator summary saved.", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(this,
                            "Could not save summary.", Toast.LENGTH_SHORT).show();
                }
            }
            pendingTextExport = null;
            pendingTextFilename = null;
            pendingTextBase64 = false;
            return;
        }

        if (requestCode == SAVE_BACKUP_REQUEST) {
            if (resultCode == RESULT_OK
                    && data != null
                    && data.getData() != null
                    && pendingBackupJson != null) {

                Uri uri = data.getData();
                try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                    if (out != null) {
                        out.write(pendingBackupJson.getBytes(StandardCharsets.UTF_8));
                        out.flush();
                        Toast.makeText(this,
                                "PayAviator backup saved.", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(this,
                            "Could not save backup.", Toast.LENGTH_SHORT).show();
                }
            }
            pendingBackupJson = null;
        }
    }

    @Override
    protected void onDestroy() {
        if (signIn != null) signIn.removeStateListener(authStateListener);
        super.onDestroy();
    }

    @Override
    public void onBackPressed() {
        // PayAviator 9.4.9: Android Back is always an in-app Back/Close first.
        // Do not rely on a single JavaScript module because older feature modules
        // may replace window.payAviatorHandleAndroidBack at runtime.
        if (webView == null) {
            super.onBackPressed();
            return;
        }

        final String closeCurrentUi =
                "(function(){" +
                "try{" +
                "var vis=function(el){if(!el)return false;var s=getComputedStyle(el),r=el.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&r.width>0&&r.height>0;};" +
                "var clickClose=function(root){if(!root)return false;var ss=['[data-close]','[data-dismiss]','.pp920-close','#mb2034SettingsClose','.pp826-close','.modal-close','.dialog-close-x','.close','[aria-label=\"Close\"]','[aria-label=\"Done\"]','button.cancel','button[data-cancel]'];for(var i=0;i<ss.length;i++){var b=root.querySelector(ss[i]);if(b&&vis(b)){b.click();return true;}}return false;};" +
                // Give the current app-level handler first chance.
                "try{if(window.payAviatorHandleAndroidBack&&window.payAviatorHandleAndroidBack())return 'closed';}catch(e){}" +
                // Themed PayAviator notice / loader.
                "var n=document.getElementById('ppThemeNoticeOverlay');if(n){try{window.PayAviatorCloseThemeNotice&&window.PayAviatorCloseThemeNotice();}catch(e){}if(document.getElementById('ppThemeNoticeOverlay'))n.remove();return 'closed';}" +
                // Native HTML dialogs, newest/topmost first.
                "var ds=document.querySelectorAll('dialog[open]');if(ds.length){var d=ds[ds.length-1];try{d.close();}catch(e){d.removeAttribute('open');}return 'closed';}" +
                // Connected Accounts overlay.
                "var acct=document.getElementById('pp920AccountsModal');if(acct&&acct.classList.contains('show')){if(!clickClose(acct))acct.classList.remove('show');return 'closed';}" +
                // Settings/submenu overlay.
                "var st=document.getElementById('mb123SettingsPanel');if(st&&st.classList.contains('mb2034-modal-open')){if(!clickClose(st)){try{window.mb2034CloseSettings&&window.mb2034CloseSettings();}catch(e){}st.classList.remove('mb2034-modal-open');document.body.classList.remove('mb2034-settings-open');}return 'closed';}" +
                // Tips/help bubbles.
                "var tip=document.getElementById('pp925TipPopup');if(tip&&tip.classList.contains('pp-show')){tip.classList.remove('pp-show');return 'closed';}" +
                // Legacy category menu.
                "var cm=document.getElementById('categoryMenu');if(cm&&!cm.hidden){cm.hidden=true;return 'closed';}" +
                // Generic PayAviator overlays/sheets/popups.
                "var q='[role=\"dialog\"]:not([hidden]),.modal:not([hidden]),.popup:not([hidden]),.menu.open,.dropdown.open,.sheet.show,.overlay.show,.pp-show';var xs=document.querySelectorAll(q);for(var j=xs.length-1;j>=0;j--){var el=xs[j];if(!vis(el))continue;if(!clickClose(el)){el.classList.remove('show','open','pp-show');if(el.hasAttribute('hidden'))el.hidden=true;else if(el.style)el.style.display='none';}return 'closed';}" +
                // Collapse the most recently opened details/advanced menu.
                "var det=document.querySelectorAll('details[open]');if(det.length){det[det.length-1].removeAttribute('open');return 'closed';}" +
                // Any secondary main tab returns Home before Android exits.
                "var active=document.querySelector('.mb119-nav.active');var v=active&&active.dataset?active.dataset.view:'';if(v&&v!=='home'){var h=document.querySelector('.mb119-nav[data-view=\"home\"]');if(h){h.click();return 'closed';}}" +
                "return 'none';" +
                "}catch(e){return 'none';}" +
                "})()";

        webView.evaluateJavascript(closeCurrentUi, result -> {
            if ("\"closed\"".equals(result)) return;

            // Browser history is only used after every PayAviator surface has had
            // a chance to close. This preserves normal Back behavior for any
            // genuine in-WebView navigation.
            if (webView.canGoBack()) {
                webView.goBack();
                return;
            }

            MainActivity.super.onBackPressed();
        });
    }}
