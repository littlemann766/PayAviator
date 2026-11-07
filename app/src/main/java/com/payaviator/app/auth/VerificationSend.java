package com.payaviator.app.auth;

/**
 * Signup verification outcomes. HTTP 200 means Firebase accepted the send request.
 * It does not mean the message reached an inbox. The account is kept either way.
 */
public final class VerificationSend {
    public static final class Outcome {
        public final boolean ok;
        public final String code;
        public final String message;

        public Outcome(boolean ok, String code, String message) {
            this.ok = ok;
            this.code = code;
            this.message = message;
        }
    }

    private VerificationSend() {}

    public static boolean restAccepted(boolean tokenPresent, int httpStatus, boolean transportFailed) {
        return tokenPresent && !transportFailed && httpStatus == 200;
    }

    /** A label safe for logs and UI. Never includes an address or token. */
    public static String reason(boolean tokenPresent, boolean transportFailed, int httpStatus) {
        if (!tokenPresent) return "no sign-in token";
        if (transportFailed) return "network";
        return "status " + httpStatus;
    }

    public static Outcome accepted(boolean signup) {
        if (!signup) return new Outcome(true, "VERIFY_EMAIL_REQUESTED", "");
        return new Outcome(true, "VERIFY_EMAIL_REQUESTED",
                "Your account was created. Firebase accepted the verification-email request. Check inbox and spam. The app cannot see whether it arrived.");
    }

    public static Outcome fallbackAccepted(boolean signup) {
        if (!signup) return new Outcome(true, "VERIFY_EMAIL_REQUESTED", "");
        return new Outcome(true, "VERIFY_EMAIL_REQUESTED",
                "Your account was created. The first verification request was not accepted, so PayAviator tried again. Check inbox and spam. The app cannot see whether it arrived.");
    }

    public static Outcome failed(boolean signup, String reason) {
        String why = reason == null || reason.isEmpty() ? "unknown" : reason;
        if (signup) {
            return new Outcome(true, "VERIFY_EMAIL_FAILED",
                    "Your account was created and kept. PayAviator could not confirm the verification email was sent (" + why + "). Use Send verification email. Nothing was deleted.");
        }
        return new Outcome(false, "VERIFY_EMAIL_FAILED",
                "Could not confirm the verification email was sent (" + why + "). Try again.");
    }
}
