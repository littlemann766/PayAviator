package com.payaviator.app.billing;

import android.content.Context;

import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.QueryPurchasesParams;

import java.util.ArrayList;
import java.util.List;

/**
 * Reads subscription purchases Google Play already associates with this install.
 * Does not start a purchase and does not acknowledge one. The server
 * verify route is what decides eligibility.
 */
public final class PlayBillingQuery {
    public interface Callback {
        void onResult(boolean ok, String code, String purchasesJson);
    }

    private final Context appContext;
    private BillingClient client;
    private volatile String lastJson = "[]";

    public PlayBillingQuery(Context context) {
        this.appContext = context.getApplicationContext();
    }

    public String lastJson() {
        return lastJson == null ? "[]" : lastJson;
    }

    public void end() {
        BillingClient c = client;
        client = null;
        if (c != null) {
            try { c.endConnection(); } catch (Exception ignored) { }
        }
    }

    public void query(Callback callback) {
        Callback cb = callback == null ? (ok, code, json) -> { } : callback;
        try {
            ensureClient();
        } catch (Exception e) {
            cb.onResult(false, "BILLING_UNAVAILABLE", "[]");
            return;
        }
        if (client.isReady()) {
            queryReady(cb);
            return;
        }
        client.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult result) {
                if (result.getResponseCode() == BillingClient.BillingResponseCode.OK) queryReady(cb);
                else cb.onResult(false, codeFor(result.getResponseCode()), "[]");
            }

            @Override
            public void onBillingServiceDisconnected() { }
        });
    }

    private void ensureClient() {
        if (client != null) return;
        // Listener is required by BillingClient. Purchases are not launched from here.
        PurchasesUpdatedListener ignored = (result, purchases) -> { };
        client = BillingClient.newBuilder(appContext)
                .setListener(ignored)
                .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
                .build();
    }

    private void queryReady(Callback cb) {
        QueryPurchasesParams params = QueryPurchasesParams.newBuilder()
                .setProductType(BillingClient.ProductType.SUBS)
                .build();
        client.queryPurchasesAsync(params, (result, purchases) -> {
            if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                cb.onResult(false, codeFor(result.getResponseCode()), "[]");
                return;
            }
            String json = PlayPurchaseJson.toJson(rowsFrom(purchases));
            lastJson = json;
            cb.onResult(true, "", json);
        });
    }

    static List<PlayPurchaseJson.Row> rowsFrom(List<Purchase> purchases) {
        List<PlayPurchaseJson.Row> rows = new ArrayList<>();
        if (purchases == null) return rows;
        for (Purchase purchase : purchases) {
            if (purchase == null) continue;
            int state = purchase.getPurchaseState();
            if (!PlayPurchaseJson.isEligible(state)) continue;
            List<String> products = purchase.getProducts();
            if (products == null) continue;
            String token = purchase.getPurchaseToken();
            for (String productId : products) {
                rows.add(new PlayPurchaseJson.Row(productId, token, state));
            }
        }
        return rows;
    }

    static String codeFor(int responseCode) {
        if (responseCode == BillingClient.BillingResponseCode.BILLING_UNAVAILABLE
                || responseCode == BillingClient.BillingResponseCode.SERVICE_UNAVAILABLE
                || responseCode == BillingClient.BillingResponseCode.SERVICE_DISCONNECTED) {
            return "BILLING_UNAVAILABLE";
        }
        return "QUERY_FAILED";
    }
}
