package com.payaviator.app.billing;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;

public class PlayPurchaseJsonTest {
    @Test public void purchasedRowIsEligiblePendingIsNot() {
        assertTrue(PlayPurchaseJson.isEligible(PlayPurchaseJson.STATE_PURCHASED));
        assertFalse(PlayPurchaseJson.isEligible(PlayPurchaseJson.STATE_PENDING));
        assertFalse(PlayPurchaseJson.isEligible(0));
    }

    @Test public void jsonKeepsPurchasedAndDropsPending() throws Exception {
        String json = PlayPurchaseJson.toJson(Arrays.asList(
                new PlayPurchaseJson.Row("plus_monthly", "token-a", PlayPurchaseJson.STATE_PURCHASED),
                new PlayPurchaseJson.Row("plus_monthly", "token-pending", PlayPurchaseJson.STATE_PENDING),
                new PlayPurchaseJson.Row("", "token-b", PlayPurchaseJson.STATE_PURCHASED),
                null
        ));
        JSONArray arr = new JSONArray(json);
        assertEquals(1, arr.length());
        JSONObject row = arr.getJSONObject(0);
        assertEquals("plus_monthly", row.getString("productId"));
        assertEquals("token-a", row.getString("purchaseToken"));
        assertEquals(PlayPurchaseJson.STATE_PURCHASED, row.getInt("purchaseState"));
    }

    @Test public void emptyAndNullStayEmpty() {
        assertEquals("[]", PlayPurchaseJson.toJson(null));
        assertEquals("[]", PlayPurchaseJson.toJson(Collections.emptyList()));
    }
}
