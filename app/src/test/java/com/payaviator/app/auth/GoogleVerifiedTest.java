package com.payaviator.app.auth;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** 4.1.1: an account created through Google counts as a verified email. */
public class GoogleVerifiedTest {
    @Test public void googleCountsAsVerified() { assertTrue(FirebaseSignIn.isVerified(false, "google")); }
    @Test public void verifiedPasswordStaysVerified() { assertTrue(FirebaseSignIn.isVerified(true, "password")); }
    @Test public void unverifiedPasswordIsNotVerified() { assertFalse(FirebaseSignIn.isVerified(false, "password")); }
}
