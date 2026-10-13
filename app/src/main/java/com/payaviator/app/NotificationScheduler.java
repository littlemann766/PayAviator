package com.payaviator.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * 4.1.2 notification rework (phase 1, local only).
 * The web app builds one flat plan of future alarms (paid and deleted bill occurrences are left out) and hands it
 * here. The plan is stored so it can be re-armed after a reboot or app update without opening the app.
 * When an alarm fires, the receiver re-checks that its key is still in the current plan (so a bill marked paid
 * after scheduling never notifies), shows it, and records it for the in-app Alerts center.
 */
public final class NotificationScheduler {
    static final String PREFS = "payaviator_notif_v2";
    static final String PLAN_KEY = "plan";
    static final String SLOTS_KEY = "slots";
    static final String FIRED_KEY = "fired";
    static final int REQUEST_BASE = 52000;
    static final int MAX_ALARMS = 450;
    static final String EXTRA_OPEN = "pa_open";

    private NotificationScheduler() {}

    /** Stores the plan and (re)arms every future alarm in it. Returns how many were armed. */
    public static synchronized int apply(Context ctx, String planJson) {
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        p.edit().putString(PLAN_KEY, planJson == null ? "" : planJson).apply();
        return arm(ctx);
    }

    /** Re-arms the stored plan (boot, app update, app start). */
    public static synchronized int arm(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        cancelAll(ctx, p.getInt(SLOTS_KEY, MAX_ALARMS));
        int armed = 0;
        try {
            String raw = p.getString(PLAN_KEY, "");
            if (raw == null || raw.isEmpty()) { p.edit().putInt(SLOTS_KEY, 0).apply(); return 0; }
            JSONObject plan = new JSONObject(raw);
            JSONArray alarms = plan.optJSONArray("alarms");
            long now = System.currentTimeMillis();
            AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
            for (int i = 0; alarms != null && i < alarms.length() && armed < MAX_ALARMS; i++) {
                JSONObject a = alarms.getJSONObject(i);
                long at = a.optLong("fireAt", 0L);
                if (at <= now) continue;
                Intent it = new Intent(ctx, MainActivity.ReminderReceiver.class);
                it.putExtra("key", a.optString("key", ""));
                PendingIntent pi = PendingIntent.getBroadcast(ctx, REQUEST_BASE + armed, it,
                        PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi);
                armed++;
            }
        } catch (Exception ignored) {}
        p.edit().putInt(SLOTS_KEY, armed).apply();
        return armed;
    }

    static void cancelAll(Context ctx, int slots) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        int n = Math.max(0, Math.min(MAX_ALARMS, slots));
        for (int i = 0; i < n; i++) {
            Intent it = new Intent(ctx, MainActivity.ReminderReceiver.class);
            PendingIntent pi = PendingIntent.getBroadcast(ctx, REQUEST_BASE + i, it,
                    PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE);
            if (pi != null) { am.cancel(pi); pi.cancel(); }
        }
    }

    /** The alarm for this key in the current plan, or null if it was removed (paid, edited, deleted, turned off). */
    static JSONObject find(Context ctx, String key) {
        if (key == null || key.isEmpty()) return null;
        try {
            String raw = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(PLAN_KEY, "");
            if (raw == null || raw.isEmpty()) return null;
            JSONObject plan = new JSONObject(raw);
            JSONArray alarms = plan.optJSONArray("alarms");
            for (int i = 0; alarms != null && i < alarms.length(); i++) {
                JSONObject a = alarms.getJSONObject(i);
                if (key.equals(a.optString("key"))) {
                    a.put("_showAmounts", plan.optBoolean("showAmountsOnLockScreen", false));
                    return a;
                }
            }
        } catch (Exception ignored) {}
        return null;
    }

    static synchronized void recordFired(Context ctx, JSONObject a) {
        try {
            SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            JSONArray arr = new JSONArray(p.getString(FIRED_KEY, "[]"));
            JSONObject o = new JSONObject();
            o.put("key", a.optString("key"));
            o.put("type", a.optString("type", "bill"));
            o.put("title", a.optString("title"));
            o.put("text", a.optString("text"));
            o.put("open", a.optString("open"));
            o.put("ts", System.currentTimeMillis());
            arr.put(o);
            JSONArray keep = new JSONArray();
            for (int i = Math.max(0, arr.length() - 100); i < arr.length(); i++) keep.put(arr.get(i));
            p.edit().putString(FIRED_KEY, keep.toString()).apply();
        } catch (Exception ignored) {}
    }

    static synchronized String takeFired(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String v = p.getString(FIRED_KEY, "[]");
        p.edit().putString(FIRED_KEY, "[]").apply();
        return v;
    }

    /** Re-arms alarms after a reboot or an app update (alarms do not survive either). */
    public static class BootReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            String a = intent == null ? null : intent.getAction();
            if (Intent.ACTION_BOOT_COMPLETED.equals(a) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)
                    || "android.intent.action.LOCKED_BOOT_COMPLETED".equals(a)
                    || "android.intent.action.QUICKBOOT_POWERON".equals(a)) {
                final PendingResult pr = goAsync();
                new Thread(() -> { try { arm(context.getApplicationContext()); } finally { pr.finish(); } }).start();
            }
        }
    }
}
