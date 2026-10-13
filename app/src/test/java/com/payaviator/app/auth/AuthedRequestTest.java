package com.payaviator.app.auth;

import static org.junit.Assert.*;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import org.junit.Test;

public class AuthedRequestTest {

    /** Scripted token source: records each forceRefresh flag and returns tokens in order. */
    static final class Tokens implements AuthedRequest.TokenSource {
        final List<Boolean> calls = new ArrayList<>();
        final Object[] script;
        int i = 0;
        Tokens(Object... script) { this.script = script; }
        @Override public String getToken(boolean forceRefresh) throws Exception {
            calls.add(forceRefresh);
            Object next = script[i++];
            if (next instanceof Exception) throw (Exception) next;
            return (String) next;
        }
    }

    /** Scripted transport: records the bearer tokens it was given and replies with statuses in order. */
    static final class Http implements AuthedRequest.Transport {
        final List<String> tokens = new ArrayList<>();
        final Object[] script;
        int i = 0;
        Http(Object... script) { this.script = script; }
        @Override public AuthedRequest.Response execute(String bearerToken) throws IOException {
            tokens.add(bearerToken);
            Object next = script[i++];
            if (next instanceof IOException) throw (IOException) next;
            int status = (Integer) next;
            return new AuthedRequest.Response(status, "{\"status\":" + status + "}");
        }
    }

    static final class SignOut implements AuthedRequest.SignOutHandler {
        final List<String> reasons = new ArrayList<>();
        @Override public void onSessionInvalid(String reason) { reasons.add(reason); }
    }

    @Test public void successUsesCachedTokenOnce() throws Exception {
        Tokens t = new Tokens("cached"); Http h = new Http(200); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.COMPLETED, r.outcome);
        assertEquals(200, r.response.status);
        assertEquals(1, r.attempts);
        assertEquals(Arrays.asList(false), t.calls);
        assertEquals(Arrays.asList("cached"), h.tokens);
        assertTrue(s.reasons.isEmpty());
    }

    @Test public void noUserNeverCallsBackend() throws Exception {
        Tokens t = new Tokens((Object) null); Http h = new Http(); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.SIGN_IN_REQUIRED, r.outcome);
        assertNull(r.response);
        assertTrue(h.tokens.isEmpty());
        assertTrue(s.reasons.isEmpty());
    }

    @Test public void first401ForceRefreshesAndRetriesOnce() throws Exception {
        Tokens t = new Tokens("stale", "fresh"); Http h = new Http(401, 200); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.COMPLETED, r.outcome);
        assertEquals(200, r.response.status);
        assertEquals(2, r.attempts);
        assertEquals(Arrays.asList(false, true), t.calls);
        assertEquals(Arrays.asList("stale", "fresh"), h.tokens);
        assertTrue(s.reasons.isEmpty());
    }

    @Test public void second401SignsOutAndStops() throws Exception {
        Tokens t = new Tokens("stale", "fresh"); Http h = new Http(401, 401); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.SESSION_EXPIRED, r.outcome);
        assertEquals(2, r.attempts);
        assertEquals(2, h.tokens.size()); // never a third attempt
        assertEquals(Arrays.asList("unauthorized"), s.reasons);
    }

    @Test public void non401ErrorsAreNotRetried() throws Exception {
        for (int status : new int[]{400, 403, 404, 409, 429, 500, 502, 503}) {
            Tokens t = new Tokens("cached"); Http h = new Http(status); SignOut s = new SignOut();
            AuthedRequest.Result r = AuthedRequest.run(t, h, s);
            assertEquals(AuthedRequest.Outcome.COMPLETED, r.outcome);
            assertEquals(status, r.response.status);
            assertEquals(1, h.tokens.size());
            assertEquals(Arrays.asList(false), t.calls);
            assertTrue(s.reasons.isEmpty());
        }
    }

    @Test public void expiredSessionDuringRefreshSignsOut() throws Exception {
        Tokens t = new Tokens("stale", new AuthedRequest.SessionExpiredException("user disabled", null));
        Http h = new Http(401); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.SESSION_EXPIRED, r.outcome);
        assertEquals(1, h.tokens.size());
        assertEquals(Arrays.asList("session_expired"), s.reasons);
    }

    @Test public void expiredSessionBeforeFirstCallSignsOutWithoutNetwork() throws Exception {
        Tokens t = new Tokens(new AuthedRequest.SessionExpiredException("revoked", null));
        Http h = new Http(); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.SESSION_EXPIRED, r.outcome);
        assertTrue(h.tokens.isEmpty());
        assertEquals(Arrays.asList("session_expired"), s.reasons);
    }

    @Test public void userSignedOutBetweenAttemptsIsSessionExpired() throws Exception {
        Tokens t = new Tokens("stale", null); Http h = new Http(401); SignOut s = new SignOut();
        AuthedRequest.Result r = AuthedRequest.run(t, h, s);
        assertEquals(AuthedRequest.Outcome.SESSION_EXPIRED, r.outcome);
        assertEquals(Arrays.asList("signed_out"), s.reasons);
    }

    @Test public void networkErrorPropagatesWithoutSignOut() {
        Tokens t = new Tokens("cached"); Http h = new Http(new IOException("offline")); SignOut s = new SignOut();
        try { AuthedRequest.run(t, h, s); fail("expected IOException"); }
        catch (Exception e) { assertTrue(e instanceof IOException); }
        assertTrue(s.reasons.isEmpty());
    }

    @Test public void transientTokenErrorPropagatesWithoutSignOut() {
        Tokens t = new Tokens(new IllegalStateException("network while refreshing")); Http h = new Http(); SignOut s = new SignOut();
        try { AuthedRequest.run(t, h, s); fail("expected exception"); }
        catch (Exception e) { assertTrue(e instanceof IllegalStateException); }
        assertTrue(h.tokens.isEmpty());
        assertTrue(s.reasons.isEmpty());
    }

    @Test public void onlyPlaidRoutesRequireAuth() {
        assertTrue(AuthedRequest.requiresAuth("/api/plaid/accounts"));
        assertTrue(AuthedRequest.requiresAuth("/api/plaid/user"));
        assertTrue(AuthedRequest.requiresAuth("/api/devices/fcm"));
        assertFalse(AuthedRequest.requiresAuth("/api/health"));
        assertFalse(AuthedRequest.requiresAuth(null));
    }
}
