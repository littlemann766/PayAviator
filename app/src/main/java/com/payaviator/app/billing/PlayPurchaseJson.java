package com.payaviator.app.billing;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/**
 * Turns Play Billing purchase rows into the JSON array billingGetPurchases returns.
 * Only purchaseState 1 (Purchase.PurchaseState.PURCHASED) is eligible to send to
 * POST /api/billing/google-play/verify. Pending and unknown states are omitted.
 * This class does not grant an entitlement and does not start a purchase.
 */
public final class PlayPurchaseJson {
    /** Matches com.android.billingclient.api.Purchase.PurchaseState.PURCHASED. */
    public static final int STATE_PURCHASED = 1;
    /** Matches Purchase.PurchaseState.PENDING. Not sent to verify. */
    public static final int STATE_PENDING = 2;

    public static final class Row {
        public final String productId;
        public final String purchaseToken;
        public final int purchaseState;

        public Row(String productId, String purchaseToken, int purchaseState) {
            this.productId = productId;
            this.purchaseToken = purchaseToken;
            this.purchaseState = purchaseState;
        }
    }

    private PlayPurchaseJson() {}

    public static boolean isEligible(int purchaseState) {
        return purchaseState == STATE_PURCHASED;
    }

    public static String toJson(List<Row> rows) {
        JSONArray arr = new JSONArray();
        if (rows == null) return arr.toString();
        for (Row row : rows) {
            if (row == null || !isEligible(row.purchaseState)) continue;
            if (!safeId(row.productId) || !safeToken(row.purchaseToken)) continue;
            try {
                JSONObject o = new JSONObject();
                o.put("productId", row.productId);
                o.put("purchaseToken", row.purchaseToken);
                o.put("purchaseState", row.purchaseState);
                arr.put(o);
            } catch (Exception ignored) { }
        }
        return arr.toString();
    }

    private static boolean safeId(String productId) {
        return productId != null && !productId.isEmpty() && productId.length() <= 200 && productId.indexOf(' ') < 0;
    }

    private static boolean safeToken(String token) {
        return token != null && !token.isEmpty() && token.length() <= 4096;
    }
}
