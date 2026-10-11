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
    private boolean pendingHostedReturn = false;
    private long stoppedAtElapsed = 0L;
    private ValueCallback<Uri[]> filePathCallback;
    private String pendingBackupJson;
    private String pendingTextExport;
    private String pendingTextFilename;
    private boolean pendingTextBase64 = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Uri launchData = getIntent() == null ? null : getIntent().getData();
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
                intent.setType("application/json");
                intent.putExtra(Intent.EXTRA_MIME_TYPES,
                        new String[]{"application/json", "text/json", "text/plain"});

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
        setContentView(rootView);

        splashView = new CloudSplashLayout(this);
        splashView.setOrientation(LinearLayout.VERTICAL);
        splashView.setGravity(Gravity.CENTER);
        splashView.setPadding(dp(28), dp(32), dp(28), dp(32));
        splashView.setBackgroundColor(Color.rgb(5, 19, 40));

        ImageView logo = new ImageView(this);
        logo.setImageResource(com.payaviator.app.R.drawable.payaviator_app_icon);
        logo.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        LinearLayout.LayoutParams logoParams =
                new LinearLayout.LayoutParams(dp(230), dp(230));
        logoParams.bottomMargin = dp(22);
        splashView.addView(logo, logoParams);

        TextView title = new TextView(this);
        title.setText("PayAviator");
        title.setTextColor(Color.WHITE);
        title.setTextSize(32);
        title.setGravity(Gravity.CENTER);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        splashView.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        TextView subtitle = new TextView(this);
        subtitle.setText("TAKE CONTROL OF YOUR MONEY");
        subtitle.setTextColor(Color.rgb(22, 228, 234));
        subtitle.setTextSize(13);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setLetterSpacing(0.10f);
        LinearLayout.LayoutParams subParams =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
        subParams.topMargin = dp(10);
        splashView.addView(subtitle, subParams);

        splashStatus = new TextView(this);
        splashStatus.setText("Starting PayAviator…");
        splashStatus.setTextColor(Color.rgb(170, 197, 222));
        splashStatus.setTextSize(14);
        splashStatus.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams loadParams =
                new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.WRAP_CONTENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT);
        loadParams.topMargin = dp(30);
        splashView.addView(splashStatus, loadParams);

        splashStatus.postDelayed(() -> setSplashStatus("Loading bills…"), 500);
        splashStatus.postDelayed(() -> setSplashStatus("Loading debts…"), 1350);
        splashStatus.postDelayed(() -> setSplashStatus("Loading funds…"), 2200);
        splashStatus.postDelayed(() -> setSplashStatus("Preparing PayAviator Gauge…"), 3100);
        splashStatus.postDelayed(() -> setSplashStatus("PayAviator is taking off… ✈"), 4250);

        rootView.addView(splashView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        splashView.setOnClickListener(v -> forceRevealApp());

        // Hard fail-safe: never allow the splash screen to trap the user.
        splashView.postDelayed(this::forceRevealApp, 1800);
    }

    /**
     * Splash-only cloud layer. The clouds are painted inside the splash itself,
     * so they can never sit over the WebView or block taps after startup.
     */
    private static class CloudSplashLayout extends LinearLayout {
        private final Paint cloudPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private long cloudStart;

        CloudSplashLayout(Context context) {
            super(context);
            setWillNotDraw(false);
            cloudPaint.setColor(Color.WHITE);
            cloudStart = SystemClock.uptimeMillis();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            final float w = getWidth();
            final float h = getHeight();
            if (w <= 0 || h <= 0) return;

            float t = ((SystemClock.uptimeMillis() - cloudStart) % 12000L) / 12000f;
            drawCloud(canvas, wrap(w * (0.04f + t * 0.22f), w), h * 0.10f, w * 0.20f, 0.16f);
            drawCloud(canvas, wrap(w * (0.72f + t * 0.16f), w), h * 0.22f, w * 0.15f, 0.11f);
            drawCloud(canvas, wrap(w * (-0.08f + t * 0.19f), w), h * 0.43f, w * 0.18f, 0.12f);
            drawCloud(canvas, wrap(w * (0.78f + t * 0.13f), w), h * 0.66f, w * 0.13f, 0.09f);
            drawCloud(canvas, wrap(w * (0.12f + t * 0.17f), w), h * 0.82f, w * 0.17f, 0.10f);
            postInvalidateOnAnimation();
        }

        private float wrap(float x, float w) {
            float margin = w * 0.25f;
            float span = w + margin * 2f;
            return ((x + margin) % span) - margin;
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
                        setSplashStatus("PayAviator is taking off… ✈");
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
        Uri data = intent == null ? null : intent.getData();
        if (isPlaidReturnUri(data)) {
            externalActivityInProgress = false;
            hostedLinkInProgress = false;
            pendingHostedReturn = false;
            notifyHostedLinkReturned();
        }
    }

    private static final String PAYAVIATOR_API_BASE = "https://payaviator-backend-production.up.railway.app";
    private static final String DEVICE_PREFS = "payaviator_device_security_v1";
    private static final String DEVICE_ID_KEY = "device_id";
    private static final String DEVICE_SECRET_KEY = "device_secret";

    private String secureRandomToken(int bytes) {
        byte[] raw = new byte[bytes];
        new SecureRandom().nextBytes(raw);
        return Base64.encodeToString(raw, Base64.URL_SAFE | Base64.NO_WRAP | Base64.NO_PADDING);
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

    private synchronized String getSecureDeviceSecret() {
        SharedPreferences prefs = getSharedPreferences(DEVICE_PREFS, MODE_PRIVATE);
        String secret = prefs.getString(DEVICE_SECRET_KEY, "");
        if (secret == null || secret.length() < 40) {
            secret = secureRandomToken(48);
            prefs.edit().putString(DEVICE_SECRET_KEY, secret).apply();
        }
        return secret;
    }

    private void applyDeviceAuth(HttpURLConnection conn) {
        conn.setRequestProperty("X-PayAviator-Device-Id", getSecureDeviceId());
        conn.setRequestProperty("Authorization", "Bearer " + getSecureDeviceSecret());
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
                HttpURLConnection conn = null;
                try {
                    String safePath = (path == null || !path.startsWith("/")) ? "/api/health" : path;
                    URL url = new URL(PAYAVIATOR_API_BASE + safePath);
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setConnectTimeout(15000);
                    conn.setReadTimeout(20000);
                    conn.setUseCaches(false);
                    conn.setRequestProperty("Accept", "application/json");
                    applyDeviceAuth(conn);
                    String verb = (method == null || method.trim().isEmpty()) ? "GET" : method.trim().toUpperCase(Locale.US);
                    conn.setRequestMethod(verb);
                    if (!"GET".equals(verb) && !"HEAD".equals(verb)) {
                        conn.setDoOutput(true);
                        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                        byte[] bytes = (body == null ? "" : body).getBytes(StandardCharsets.UTF_8);
                        try (OutputStream out = conn.getOutputStream()) { out.write(bytes); }
                    }
                    int status = conn.getResponseCode();
                    InputStream in = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
                    StringBuilder text = new StringBuilder();
                    if (in != null) {
                        byte[] buf = new byte[4096];
                        int n;
                        while ((n = in.read(buf)) != -1) text.append(new String(buf, 0, n, StandardCharsets.UTF_8));
                        in.close();
                    }
                    deliverNativeApiResult(requestId, status, text.toString(), "");
                } catch (Exception e) {
                    deliverNativeApiResult(requestId, 0, "", e.getClass().getSimpleName() + ": " + (e.getMessage() == null ? "Network request failed" : e.getMessage()));
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }, "PayAviatorApi").start();
        }

        @JavascriptInterface
        public void openPlaidLink(final String linkToken) {
            runOnUiThread(() -> {
                try {
                    Intent intent = new Intent(MainActivity.this, PlaidLinkActivity.class);
                    intent.putExtra("link_token", linkToken == null ? "" : linkToken);
                    externalActivityInProgress = true;
                    startActivityForResult(intent, PLAID_LINK_REQUEST);
                } catch (Exception e) {
                    deliverPlaidResultToWeb("{\"status\":\"error\",\"message\":\"Unable to open secure bank connection.\"}");
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
        NotificationManager nm =
                (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);

        String channel = channelId(sound, vibrate);
        ensureChannel(context, sound, vibrate);

        Intent launch = context.getPackageManager()
                .getLaunchIntentForPackage(context.getPackageName());
        PendingIntent contentIntent = null;
        if (launch != null) {
            contentIntent = PendingIntent.getActivity(
                    context, 0, launch,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        }

        Notification.Builder builder =
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? new Notification.Builder(context, channel)
                        : new Notification.Builder(context);

        builder.setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(text)
                .setAutoCancel(true);

        if (contentIntent != null) builder.setContentIntent(contentIntent);

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            Uri uri = soundUri(sound);
            if (uri != null) builder.setSound(uri);
            if (vibrate) builder.setVibrate(new long[]{0, 250, 150, 250});
        }

        if (Build.VERSION.SDK_INT < 33 ||
                context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                        == PackageManager.PERMISSION_GRANTED) {
            nm.notify((int)(System.currentTimeMillis() & 0x7fffffff), builder.build());
        }
    }


    private boolean areRealAccountsConnected() {
        return getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE)
                .getBoolean(SECURITY_REAL_ACCOUNTS_KEY, false);
    }

    private boolean isAppLockEnabled() {
        SharedPreferences prefs = getSharedPreferences(SECURITY_PREFS, MODE_PRIVATE);
        // Real financial accounts make device authentication mandatory.
        return prefs.getBoolean(SECURITY_REAL_ACCOUNTS_KEY, false)
                || prefs.getBoolean(SECURITY_ENABLED_KEY, false);
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
        // A user may opt into app lock without banking, but cannot disable it while
        // real financial accounts are connected.
        if (!enabled && areRealAccountsConnected()) return;
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
        if (connected && !wasConnected) {
            // Require device authentication immediately after the first real account
            // is attached; PayAviator never stores a separate PIN.
            authenticatedForSession = false;
            clearUnlockGracePeriod();
            showLockedScreen();
            authenticateUser();
        }
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
    protected void onResume() {
        super.onResume();
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
