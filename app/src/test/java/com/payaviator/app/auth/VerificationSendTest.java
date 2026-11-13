package com.payaviator.app.auth;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class VerificationSendTest {
    @Test public void successIsAccountCreatedAndRequestAccepted() {
        assertTrue(VerificationSend.restAccepted(true, 200, false));
        VerificationSend.Outcome o = VerificationSend.accepted(true);
        assertTrue(o.ok);
        assertEquals("VERIFY_EMAIL_REQUESTED", o.code);
        assertTrue(o.message.contains("account was created"));
        assertTrue(o.message.contains("Firebase accepted the verification-email request"));
        assertTrue(o.message.contains("cannot see whether it arrived"));
        assertFalse(o.message.contains("could not confirm"));
    }

    @Test public void failureKeepsTheAccountAndNamesTheReason() {
        VerificationSend.Outcome o = VerificationSend.failed(true, VerificationSend.reason(true, false, 403));
        assertTrue(o.ok);
        assertEquals("VERIFY_EMAIL_FAILED", o.code);
        assertTrue(o.message.contains("created and kept"));
        assertTrue(o.message.contains("status 403"));
        assertTrue(o.message.contains("Nothing was deleted"));
        assertTrue(o.message.contains("Send verification email"));
    }

    @Test public void fallbackIsASecondRequestNotDelivery() {
        assertFalse(VerificationSend.restAccepted(true, 403, false));
        VerificationSend.Outcome o = VerificationSend.fallbackAccepted(true);
        assertTrue(o.ok);
        assertEquals("VERIFY_EMAIL_REQUESTED", o.code);
        assertTrue(o.message.contains("tried again"));
        assertTrue(o.message.contains("cannot see whether it arrived"));
        assertFalse(o.message.contains("Firebase accepted the verification-email request"));
    }

    @Test public void networkDoesNotLookLikeAnAcceptedRequest() {
        assertFalse(VerificationSend.restAccepted(true, 0, true));
        assertEquals("network", VerificationSend.reason(true, true, 0));
        VerificationSend.Outcome o = VerificationSend.failed(true, "network");
        assertTrue(o.message.contains("network"));
        assertFalse(o.message.contains("@"));
    }

    @Test public void missingTokenSkipsTheAcceptedPath() {
        assertFalse(VerificationSend.restAccepted(false, 200, false));
        assertEquals("no sign-in token", VerificationSend.reason(false, false, 0));
        VerificationSend.Outcome o = VerificationSend.failed(true, "no sign-in token");
        assertTrue(o.ok);
        assertTrue(o.message.contains("no sign-in token"));
        assertTrue(o.message.contains("Nothing was deleted"));
    }

    @Test public void resendFailureDoesNotSayTheAccountWasCreated() {
        VerificationSend.Outcome o = VerificationSend.failed(false, "network");
        assertFalse(o.ok);
        assertFalse(o.message.contains("account was created"));
    }
}
