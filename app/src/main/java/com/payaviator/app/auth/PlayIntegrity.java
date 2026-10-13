package com.payaviator.app.auth;

import android.content.Context;
import android.util.Log;

import com.google.android.gms.tasks.Tasks;
import com.google.android.play.core.integrity.IntegrityManagerFactory;
import com.google.android.play.core.integrity.StandardIntegrityManager;
import com.google.android.play.core.integrity.StandardIntegrityManager.PrepareIntegrityTokenRequest;
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityToken;
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityTokenProvider;
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityTokenRequest;

import java.util.concurrent.TimeUnit;

/**
 * Play Integrity standard request (backend PR #8). Prepared once with the Cloud project number;
 * one token is reused for create-link-token / hosted-status / exchange and refreshed after ~4 minutes.
 * Any failure returns null: the server decides (it ignores the header unless PLAY_INTEGRITY_ENFORCE=true).
 */
public final class PlayIntegrity {
    private static final String TAG = "PayAviatorIntegrity";

    /**
     * Google Cloud project number linked to the app in Play Console (Play Integrity API).
     * TODO(boss/Lucian): fill in. 0 = not configured, so no token is sent.
     */
    public static final long CLOUD_PROJECT_NUMBER = 0L;

    private final Context context;
    private StandardIntegrityTokenProvider provider;
    private boolean prepareFailed;
    private String token, tokenHash;
    private long issuedAt;

    public PlayIntegrity(Context context) { this.context = context.getApplicationContext(); }

    public static boolean isConfigured() { return CLOUD_PROJECT_NUMBER > 0; }

    /** Blocking; background thread only. */
    public synchronized String tokenFor(String requestHash) {
        if (!isConfigured() || requestHash == null) return null;
        long now = System.currentTimeMillis();
        if (BackendHeaders.canReuseToken(token, tokenHash, issuedAt, requestHash, now)) return token;
        try {
            if (provider == null) {
                if (prepareFailed) return null;
                StandardIntegrityManager m = IntegrityManagerFactory.createStandard(context);
                provider = Tasks.await(m.prepareIntegrityToken(
                        PrepareIntegrityTokenRequest.builder().setCloudProjectNumber(CLOUD_PROJECT_NUMBER).build()),
                        20, TimeUnit.SECONDS);
            }
            StandardIntegrityToken t = Tasks.await(provider.request(
                    StandardIntegrityTokenRequest.builder().setRequestHash(requestHash).build()),
                    20, TimeUnit.SECONDS);
            String v = t == null ? null : t.token();
            if (v == null || v.length() > BackendHeaders.MAX_INTEGRITY_TOKEN_CHARS) return null;
            token = v; tokenHash = requestHash; issuedAt = System.currentTimeMillis();
            return v;
        } catch (Exception e) {
            Log.w(TAG, "Play Integrity token unavailable: " + e.getClass().getSimpleName());
            // A provider can expire; drop it so the next call prepares again (once per failure).
            if (provider == null) prepareFailed = true; else provider = null;
            return null;
        }
    }
}
