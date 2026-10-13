package com.payaviator.app.auth;

/**
 * 4.1.2 fix: verification emails had "apiKey=" (empty) in the link, so Firebase's hosted action page
 * (payaviator-app.firebaseapp.com/__/auth/action) said "The selected page mode is invalid".
 * The Android SDK's sendEmailVerification() request does not carry a browser-usable key into the link, so we
 * send the email through Identity Toolkit accounts:sendOobCode with the project's public web API key in ?key=,
 * which Firebase copies into the link's apiKey parameter. The SDK call stays as the fallback.
 */
public final class VerifyEmailRequest {
    /** Public Firebase web API key for project payaviator-app ("PayAviator Web (PWA)"). Not a secret. */
    public static final String WEB_API_KEY = "AIzaSyAcMkfgXQps-FaRC-hbQzwFOiPRI1wlEPk";
    public static final String ENDPOINT = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode";

    private VerifyEmailRequest() {}

    public static String url(String apiKey) {
        if (apiKey == null || apiKey.trim().isEmpty()) throw new IllegalArgumentException("empty api key");
        return ENDPOINT + "?key=" + apiKey.trim();
    }

    public static String body(String idToken) throws Exception {
        if (idToken == null || idToken.isEmpty()) throw new IllegalArgumentException("missing id token");
        // Built by hand so it is unit-testable without Android's org.json; ID tokens are JWTs (no quotes).
        String safe = idToken.replace("\\", "\\\\").replace("\"", "\\\"");
        return "{\"requestType\":\"VERIFY_EMAIL\",\"idToken\":\"" + safe + "\"}";
    }

    /** Blocking POST; returns the HTTP status (200 = email sent). Call off the main thread. */
    public static int send(String idToken) throws Exception {
        java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url(WEB_API_KEY)).openConnection();
        try {
            c.setConnectTimeout(15000);
            c.setReadTimeout(20000);
            c.setRequestMethod("POST");
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (java.io.OutputStream out = c.getOutputStream()) {
                out.write(body(idToken).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
            return c.getResponseCode();
        } finally {
            c.disconnect();
        }
    }
}
