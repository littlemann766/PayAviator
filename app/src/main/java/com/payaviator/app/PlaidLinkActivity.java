package com.payaviator.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONObject;

public class PlaidLinkActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String token = getIntent().getStringExtra("link_token");
        if (token == null || token.trim().isEmpty()) {
            finishWithError("Missing Plaid link token.");
            return;
        }

        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setJavaScriptCanOpenWindowsAutomatically(true);
        settings.setSupportMultipleWindows(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString());

        CookieManager cookies = CookieManager.getInstance();
        cookies.setAcceptCookie(true);
        cookies.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            private boolean handle(Uri uri) {
                if (uri == null) return false;
                if (!"plaidlink".equalsIgnoreCase(uri.getScheme())) return false;

                String host = uri.getHost() == null ? "" : uri.getHost();
                if ("connected".equalsIgnoreCase(host)) {
                    try {
                        JSONObject out = new JSONObject();
                        out.put("status", "connected");
                        out.put("public_token", value(uri, "public_token"));
                        out.put("institution_name", value(uri, "institution_name"));
                        out.put("institution_id", value(uri, "institution_id"));
                        out.put("link_session_id", value(uri, "link_session_id"));
                        Intent data = new Intent();
                        data.putExtra("plaid_result", out.toString());
                        setResult(RESULT_OK, data);
                    } catch (Exception ignored) {
                        finishWithError("Bank connection completed, but the result could not be read.");
                        return true;
                    }
                    finish();
                    return true;
                }

                if ("exit".equalsIgnoreCase(host)) {
                    try {
                        JSONObject out = new JSONObject();
                        out.put("status", "exit");
                        out.put("error_display_message", value(uri, "error_display_message"));
                        out.put("error_message", value(uri, "error_message"));
                        out.put("error_code", value(uri, "error_code"));
                        Intent data = new Intent();
                        data.putExtra("plaid_result", out.toString());
                        setResult(RESULT_OK, data);
                    } catch (Exception ignored) { }
                    finish();
                    return true;
                }

                // Event callbacks are informational; keep Link open.
                return true;
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handle(request == null ? null : request.getUrl());
            }

            @Override
            @SuppressWarnings("deprecation")
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handle(url == null ? null : Uri.parse(url));
            }
        });

        String url = "https://cdn.plaid.com/link/v2/stable/link.html?isWebview=true&token="
                + Uri.encode(token);
        webView.loadUrl(url);
    }

    private static String value(Uri uri, String key) {
        String v = uri.getQueryParameter(key);
        return v == null ? "" : v;
    }

    private void finishWithError(String message) {
        try {
            JSONObject out = new JSONObject();
            out.put("status", "error");
            out.put("message", message);
            Intent data = new Intent();
            data.putExtra("plaid_result", out.toString());
            setResult(RESULT_OK, data);
        } catch (Exception ignored) {
            setResult(RESULT_CANCELED);
        }
        finish();
    }

    @Override
    public void onBackPressed() {
        try {
            JSONObject out = new JSONObject();
            out.put("status", "exit");
            Intent data = new Intent();
            data.putExtra("plaid_result", out.toString());
            setResult(RESULT_OK, data);
        } catch (Exception ignored) {
            setResult(RESULT_CANCELED);
        }
        finish();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
