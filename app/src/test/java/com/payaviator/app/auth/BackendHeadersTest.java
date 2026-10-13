package com.payaviator.app.auth;

import static org.junit.Assert.*;

import org.junit.Test;

public class BackendHeadersTest {
    private static final String AID = "A1B2C3D4E5F60718";

    @Test public void deviceIdOnlyOnNewBankCalls() {
        assertEquals("a1b2c3d4e5f60718", BackendHeaders.deviceIdFor("/api/plaid/create-link-token", AID));
        assertEquals("a1b2c3d4e5f60718", BackendHeaders.deviceIdFor("/api/plaid/exchange-public-token", AID));
        assertEquals("a1b2c3d4e5f60718", BackendHeaders.deviceIdFor("/api/plaid/hosted-status?x=1", AID));
        assertNull(BackendHeaders.deviceIdFor("/api/plaid/accounts", AID));
        assertNull(BackendHeaders.deviceIdFor("/api/billing/status", AID));
        assertNull(BackendHeaders.deviceIdFor("/api/health", AID));
        assertNull(BackendHeaders.deviceIdFor(null, AID));
    }

    @Test public void androidIdValidation() {
        assertTrue(BackendHeaders.isValidAndroidId("0123456789abcdef"));
        assertTrue(BackendHeaders.isValidAndroidId(AID));
        assertFalse(BackendHeaders.isValidAndroidId("0123456789abcde"));
        assertFalse(BackendHeaders.isValidAndroidId("0123456789abcdefa"));
        assertFalse(BackendHeaders.isValidAndroidId("0123456789abcdeg"));
        assertFalse(BackendHeaders.isValidAndroidId(null));
        assertNull(BackendHeaders.deviceIdFor("/api/plaid/create-link-token", "ppd_notanandroidid"));
    }

    @Test public void requestHashMatchesContractExample() throws Exception {
        String want = sha("a1b2c3d4e5f60718|abcUID123");
        assertEquals(want, BackendHeaders.integrityRequestHash("a1b2c3d4e5f60718", "abcUID123"));
        assertEquals(want, BackendHeaders.integrityRequestHash(AID, "abcUID123")); // androidId lowercased
        assertEquals(64, want.length());
        assertEquals(want.toLowerCase(), want);
        assertNull(BackendHeaders.integrityRequestHash(AID, ""));
        assertNull(BackendHeaders.integrityRequestHash("bad", "u"));
    }

    @Test public void tokenReuseAndLimits() {
        long t0 = 1_000_000L;
        assertTrue(BackendHeaders.canReuseToken("tok", "h", t0, "h", t0 + 239_000));
        assertFalse(BackendHeaders.canReuseToken("tok", "h", t0, "h", t0 + 240_000));
        assertFalse(BackendHeaders.canReuseToken("tok", "h", t0, "other", t0 + 1));
        assertFalse(BackendHeaders.canReuseToken(null, "h", t0, "h", t0 + 1));
        StringBuilder big = new StringBuilder();
        for (int i = 0; i < 8193; i++) big.append('a');
        assertNull(BackendHeaders.integrityHeaderFor("/api/plaid/create-link-token", big.toString()));
        assertNotNull(BackendHeaders.integrityHeaderFor("/api/plaid/create-link-token", big.substring(1)));
        assertNull(BackendHeaders.integrityHeaderFor("/api/plaid/accounts", "tok"));
    }

    @Test public void billingRoutesNeedAuth() {
        assertTrue(AuthedRequest.requiresAuth("/api/billing/google-play/verify"));
        assertFalse(AuthedRequest.requiresAuth("/api/health"));
    }

    private static String sha(String s) throws Exception {
        byte[] d = java.security.MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8"));
        StringBuilder b = new StringBuilder();
        for (byte x : d) b.append(String.format("%02x", x));
        return b.toString();
    }
}
