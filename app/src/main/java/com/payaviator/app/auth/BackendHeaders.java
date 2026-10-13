package com.payaviator.app.auth;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;

/**
 * Pure-Java header rules for backend PR #8 (free-tier anti-abuse, contract update 2).
 * X-Device-Id is Settings.Secure.ANDROID_ID (16 hex) and X-Play-Integrity-Token a Play Integrity
 * standard token; both go only on the three new-bank calls.
 */
public final class BackendHeaders {
    public static final String DEVICE_ID_HEADER = "X-Device-Id";
    public static final String INTEGRITY_HEADER = "X-Play-Integrity-Token";
    public static final int MAX_INTEGRITY_TOKEN_CHARS = 8192;
    /** Tokens must be at most 5 minutes old at the server; refresh after 4. */
    public static final long INTEGRITY_TOKEN_MAX_AGE_MS = 4 * 60 * 1000L;

    private BackendHeaders() { }

    /** create-link-token, exchange-public-token and hosted-status (query string ignored). */
    public static boolean isNewBankCall(String path) {
        if (path == null) return false;
        int q = path.indexOf('?');
        String p = q >= 0 ? path.substring(0, q) : path;
        return p.equals("/api/plaid/create-link-token")
                || p.equals("/api/plaid/exchange-public-token")
                || p.equals("/api/plaid/hosted-status");
    }

    /** Exactly 16 hex characters (case-insensitive). */
    public static boolean isValidAndroidId(String id) {
        return id != null && id.matches("[0-9a-fA-F]{16}");
    }

    /** Header value (lowercased ANDROID_ID) for new-bank calls, else null. */
    public static String deviceIdFor(String path, String androidId) {
        if (!isNewBankCall(path) || !isValidAndroidId(androidId)) return null;
        return androidId.toLowerCase(Locale.US);
    }

    /** requestHash = lowercase hex SHA-256 of UTF-8 "<androidId lowercased>|<firebase uid>". */
    public static String integrityRequestHash(String androidId, String uid) {
        if (!isValidAndroidId(androidId) || uid == null || uid.isEmpty()) return null;
        try {
            byte[] d = MessageDigest.getInstance("SHA-256")
                    .digest((androidId.toLowerCase(Locale.US) + "|" + uid).getBytes(StandardCharsets.UTF_8));
            StringBuilder b = new StringBuilder(64);
            for (byte x : d) b.append(String.format(Locale.US, "%02x", x));
            return b.toString();
        } catch (Exception e) {
            return null;
        }
    }

    /** A cached token is reusable when it is for the same hash, fresh enough and not too long. */
    public static boolean canReuseToken(String token, String tokenHash, long issuedAtMs, String wantHash, long nowMs) {
        return token != null && !token.isEmpty() && token.length() <= MAX_INTEGRITY_TOKEN_CHARS
                && wantHash != null && wantHash.equals(tokenHash)
                && nowMs - issuedAtMs >= 0 && nowMs - issuedAtMs < INTEGRITY_TOKEN_MAX_AGE_MS;
    }

    /** Header value for the integrity token, or null if it must not be sent. */
    public static String integrityHeaderFor(String path, String token) {
        if (!isNewBankCall(path) || token == null || token.isEmpty() || token.length() > MAX_INTEGRITY_TOKEN_CHARS) return null;
        return token;
    }
}
