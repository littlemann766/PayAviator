package com.payaviator.app.auth;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import org.junit.Test;

public class GoogleSignInFailureTest {
    @Test public void developerErrorIsVisibleEvenWhenMarkedCancelled() {
        GoogleSignInFailure.Outcome o = GoogleSignInFailure.fromCredentialError(true, "[28444] Developer console is not set up correctly");
        assertEquals("GOOGLE_NOT_CONFIGURED", o.code);
        assertFalse(o.message.isEmpty());
    }

    @Test public void blankCancelIsNotSilent() {
        GoogleSignInFailure.Outcome o = GoogleSignInFailure.fromCredentialError(true, "");
        assertEquals("GOOGLE_INCOMPLETE", o.code);
        assertFalse(o.message.isEmpty());
    }

    @Test public void existingPasswordAccountIsNotADeleteOrLinkInstruction() {
        String msg = GoogleSignInFailure.firebaseGoogleMessage("ERROR_ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL", "x");
        assertEquals(true, msg.contains("email and password"));
        assertEquals(true, msg.contains("was not linked"));
        assertEquals(false, msg.toLowerCase().contains("delete"));
    }
}
