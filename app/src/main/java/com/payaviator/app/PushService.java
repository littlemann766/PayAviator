package com.payaviator.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.os.Build;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import org.json.JSONObject;

import java.util.Map;

/**
 * 4.1.2 phase 2 hook: FCM bank reconnect pushes from Lucian's server (docs/NOTIFICATIONS-CONTRACT.md).
 * Payload data {type:'bank_reconnect', item_id, reason}; no balances or amounts ever arrive here.
 * FCM is free; nothing here needs Firebase Blaze.
 */
public class PushService extends FirebaseMessagingService {
    static final String CHANNEL_RECONNECT = "bank_reconnect";
    static final String PREFS = "payaviator_push_v1";
    static final String TOKEN_KEY = "fcm_token";
    /** Set by MainActivity while it is resumed, so a foreground push goes straight to the web app. */
    static volatile MainActivity foreground;

    static void ensureReconnectChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm.getNotificationChannel(CHANNEL_RECONNECT) != null) return;
        NotificationChannel ch = new NotificationChannel(CHANNEL_RECONNECT, "Bank reconnect",
                NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("When a bank needs you to sign in again");
        nm.createNotificationChannel(ch);
    }

    @Override
    public void onNewToken(String token) {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(TOKEN_KEY, token).apply();
        MainActivity a = foreground;
        if (a != null) a.registerPushToken(token);
    }

    @Override
    public void onMessageReceived(RemoteMessage msg) {
        Map<String, String> d = msg.getData();
        if (d == null || !"bank_reconnect".equals(d.get("type"))) return;
        String itemId = d.get("item_id") == null ? "" : d.get("item_id");
        MainActivity a = foreground;
        if (a != null) {
            try {
                JSONObject o = new JSONObject();
                o.put("type", "bank_reconnect");
                o.put("item_id", itemId);
                o.put("reason", d.get("reason") == null ? "" : d.get("reason"));
                a.deliverPushToWeb(o.toString());
                return;
            } catch (Exception ignored) {}
        }
        ensureReconnectChannel(this);
        String title = msg.getNotification() != null && msg.getNotification().getTitle() != null
                ? msg.getNotification().getTitle() : "Reconnect your bank";
        String body = msg.getNotification() != null && msg.getNotification().getBody() != null
                ? msg.getNotification().getBody() : "Sign in again so your balances stay up to date.";
        MainActivity.showReconnectNotification(this, title, body, itemId);
    }
}
