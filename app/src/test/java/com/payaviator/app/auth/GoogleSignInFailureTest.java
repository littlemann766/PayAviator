package com.payaviator.app.auth;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

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

    @Test public void cancelledGoogleStaysActionableWithoutTheRawDetail() {
        String leaked = "cancelled for tester@gmail.com eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature12";
        GoogleSignInFailure.Outcome o = GoogleSignInFailure.fromCredentialError(true, leaked);
        assertEquals("GOOGLE_INCOMPLETE", o.code);
        assertFalse(o.message.contains("@"));
        assertFalse(o.message.contains("eyJ"));
        assertTrue(o.message.contains("did not finish"));
    }

    @Test public void googleExceptionIsActionableAndLogsAreRedacted() {
        String leaked = "GetCredentialException user tester@gmail.com eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.signature12";
        GoogleSignInFailure.Outcome o = GoogleSignInFailure.fromCredentialError(false, leaked);
        assertEquals("GOOGLE_FAILED", o.code);
        assertEquals("Google sign-in failed. Please try again.", o.message);
        String log = GoogleSignInFailure.safeDetail("androidx.credentials.exceptions.GetCredentialException", leaked);
        assertFalse(log.contains("tester@gmail.com"));
        assertFalse(log.contains("eyJhbGciOi"));
        assertTrue(log.contains("[redacted]"));
        String passed = GoogleSignInFailure.firebaseGoogleMessage("AUTH_FAILED", leaked);
        assertFalse(passed.contains("@"));
        assertFalse(passed.contains("eyJ"));
    }

    @Test public void existingPasswordAccountIsNotADeleteOrLinkInstruction() {
        String msg = GoogleSignInFailure.firebaseGoogleMessage("ERROR_ACCOUNT_EXISTS_WITH_DIFFERENT_CREDENTIAL", "x");
        assertEquals(true, msg.contains("email and password"));
        assertEquals(true, msg.contains("was not linked"));
        assertEquals(false, msg.toLowerCase().contains("delete"));
    }
}
