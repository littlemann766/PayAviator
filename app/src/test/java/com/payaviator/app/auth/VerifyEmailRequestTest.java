package com.payaviator.app.auth;

import static org.junit.Assert.*;

import org.junit.Test;

public class VerifyEmailRequestTest {
    @Test public void urlCarriesTheWebApiKey() {
        String u = VerifyEmailRequest.url(VerifyEmailRequest.WEB_API_KEY);
        assertEquals("https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key=AIzaSyAcMkfgXQps-FaRC-hbQzwFOiPRI1wlEPk", u);
        assertTrue(VerifyEmailRequest.WEB_API_KEY.startsWith("AIza"));
        assertEquals(39, VerifyEmailRequest.WEB_API_KEY.length());
    }
    @Test(expected = IllegalArgumentException.class) public void emptyKeyRejected() { VerifyEmailRequest.url(""); }
    @Test public void bodyIsVerifyEmail() throws Exception {
        assertEquals("{\"requestType\":\"VERIFY_EMAIL\",\"idToken\":\"a.b-c_d\"}", VerifyEmailRequest.body("a.b-c_d"));
    }
}
