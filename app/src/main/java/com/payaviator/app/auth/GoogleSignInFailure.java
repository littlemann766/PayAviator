package com.payaviator.app.auth;

import java.util.Locale;

/**
 * Maps a Google credential failure to a visible code and message.
 * An empty cancellation is not proof of why the account picker closed.
 */
public final class GoogleSignInFailure {
    public static final class Outcome {
        public final String code;
        public final String message;

        public Outcome(String code, String message) {
            this.code = code;
            this.message = message;
        }
    }

    private GoogleSignInFailure() {}

    public static Outcome fromCredentialError(boolean cancellation, String message) {
        String msg = message == null ? "" : message;
        String lower = msg.toLowerCase(Locale.US);
        if (lower.contains("28444") || lower.contains("developer") || lower.contains("10:")
                || lower.contains("configuration") || lower.contains("reauth failed")) {
            return new Outcome("GOOGLE_NOT_CONFIGURED",
                    "Google sign-in isn't enabled for this build yet. Use email and password.");
        }
        if (cancellation) {
            return new Outcome("GOOGLE_INCOMPLETE",
                    "Google sign-in did not finish. Try again, or use email and password.");
        }
        return new Outcome("GOOGLE_FAILED", "Google sign-in failed. Please try again.");
    }

    /** Does not link providers and does not tell anyone to delete an account. */
    public static String firebaseGoogleMessage(String code, String fallback) {
        if ("ERROR_ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL".equals(code)
                || "ERROR_EMAIL_ALREADY_IN_USE".equals(code)) {
            return "This email already has an email-and-password PayAviator account. Sign in with email and password. Google was not linked, and the account was not changed.";
        }
        if (fallback == null || fallback.isEmpty() || !redact(fallback).equals(fallback)) {
            return "Google sign-in failed. Please try again.";
        }
        return fallback;
    }

    /** Log text only. Drops email addresses and JWT-shaped values. */
    public static String safeDetail(String type, String message) {
        String kind = type == null ? "" : type.replaceAll("[^A-Za-z0-9._$]", "");
        String text = redact(message);
        if (text.length() > 120) text = text.substring(0, 120);
        return (kind + " " + text).trim();
    }

    static String redact(String message) {
        String text = message == null ? "" : message;
        text = text.replaceAll("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", "[redacted]");
        text = text.replaceAll("eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}", "[redacted]");
        return text;
    }
}
