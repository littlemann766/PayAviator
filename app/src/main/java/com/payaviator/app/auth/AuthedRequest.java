package com.payaviator.app.auth;

import java.io.IOException;

/**
 * Pure-Java token contract for calls to the PayAviator backend's /api/plaid/* routes.
 * No Android or Firebase types here so the retry rules can be unit-tested on the JVM.
 *
 * Contract (backend PR #1):
 *  1. Send "Authorization: Bearer <Firebase ID token>" using the cached token (getIdToken(false)).
 *  2. On HTTP 401 (code UNAUTHENTICATED / INVALID_TOKEN) force-refresh the token (getIdToken(true))
 *     and retry exactly once.
 *  3. If the retry is still 401 (or the refresh shows the session is gone), sign the user out and
 *     ask the UI to show sign-in.
 *  4. With no signed-in user, never call the backend.
 */
public final class AuthedRequest {

    /** Supplies Firebase ID tokens. Returns null when nobody is signed in. */
    public interface TokenSource {
        String getToken(boolean forceRefresh) throws Exception;
    }

    /** Thrown by a TokenSource when the Firebase session is permanently invalid (user disabled/deleted, refresh token revoked). */
    public static final class SessionExpiredException extends Exception {
        public SessionExpiredException(String message, Throwable cause) { super(message, cause); }
    }

    /** One HTTP attempt with the given bearer token. */
    public interface Transport {
        Response execute(String bearerToken) throws IOException;
    }

    /** Called once when the session cannot be recovered (second 401 or expired session). */
    public interface SignOutHandler {
        void onSessionInvalid(String reason);
    }

    public static final class Response {
        public final int status;
        public final String body;
        public Response(int status, String body) {
            this.status = status;
            this.body = body == null ? "" : body;
        }
    }

    public enum Outcome {
        /** The backend answered (any status other than a final 401). */
        COMPLETED,
        /** Nobody is signed in; the backend was not called. */
        SIGN_IN_REQUIRED,
        /** The backend rejected the refreshed token too (or the session is gone); the user was signed out. */
        SESSION_EXPIRED
    }

    public static final class Result {
        public final Outcome outcome;
        public final Response response; // null for SIGN_IN_REQUIRED, may be null for SESSION_EXPIRED
        public final int attempts;
        Result(Outcome outcome, Response response, int attempts) {
            this.outcome = outcome;
            this.response = response;
            this.attempts = attempts;
        }
    }

    private AuthedRequest() { }

    /** Only these paths carry the Firebase token; /api/health stays public. */
    public static boolean requiresAuth(String path) {
        return path != null && path.startsWith("/api/plaid/");
    }

    /**
     * Runs the request under the token contract. Network errors (IOException) and transient
     * token-fetch failures propagate to the caller unchanged; they do NOT sign the user out.
     */
    public static Result run(TokenSource tokens, Transport transport, SignOutHandler signOut) throws Exception {
        String token;
        try {
            token = tokens.getToken(false);
        } catch (SessionExpiredException e) {
            signOut.onSessionInvalid("session_expired");
            return new Result(Outcome.SESSION_EXPIRED, null, 0);
        }
        if (token == null || token.isEmpty()) {
            return new Result(Outcome.SIGN_IN_REQUIRED, null, 0);
        }

        Response first = transport.execute(token);
        if (first.status != 401) return new Result(Outcome.COMPLETED, first, 1);

        String fresh;
        try {
            fresh = tokens.getToken(true);
        } catch (SessionExpiredException e) {
            signOut.onSessionInvalid("session_expired");
            return new Result(Outcome.SESSION_EXPIRED, first, 1);
        }
        if (fresh == null || fresh.isEmpty()) {
            // Signed out somewhere else between the two calls.
            signOut.onSessionInvalid("signed_out");
            return new Result(Outcome.SESSION_EXPIRED, first, 1);
        }

        Response second = transport.execute(fresh);
        if (second.status == 401) {
            signOut.onSessionInvalid("unauthorized");
            return new Result(Outcome.SESSION_EXPIRED, second, 2);
        }
        return new Result(Outcome.COMPLETED, second, 2);
    }
}
