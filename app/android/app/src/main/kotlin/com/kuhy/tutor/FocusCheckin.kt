package com.kuhy.tutor

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build

/**
 * The "Still working?" check-in outside the app (focus timer, DOCS-contract-focus.md).
 *
 * An exact alarm posts the prompt even with the app dead or the screen off;
 * its "Still working" action lands in [FocusActionReceiver], which stores the
 * tap time natively (the Flutter engine may not be running) and arms the next
 * prompt itself, so a phone left in a pocket keeps counting. Dart drains the
 * stored taps with [takePending].
 */
object FocusCheckin {
    const val CHANNEL_PROMPT = "focus_checkin_v1"
    const val CHANNEL_TIMER = "focus_timer_v1"
    const val ACTION_ALARM = "com.kuhy.tutor.focus.ALARM"
    const val ACTION_STILL = "com.kuhy.tutor.focus.STILL_WORKING"
    const val ID_TIMER = 4100
    const val ID_PROMPT = 4101

    private const val PREFS = "focus_checkin"
    private const val KEY_PENDING = "pending"
    private const val KEY_EVERY = "every_ms"
    private const val KEY_ARMED = "armed"

    /** Set while an Activity listens; told when a tap was stored. */
    @Volatile
    var onTap: (() -> Unit)? = null

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun notificationsAllowed(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 33 ||
            ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /** Arms the prompt [afterMs] from now and keeps the timer service alive. */
    fun schedule(ctx: Context, afterMs: Long, everyMs: Long) {
        prefs(ctx).edit().putLong(KEY_EVERY, everyMs).putBoolean(KEY_ARMED, true).apply()
        // An in-app check-in lands here too: the shade prompt is answered.
        notifications(ctx).cancel(ID_PROMPT)
        arm(ctx, afterMs)
        FocusTimerService.start(ctx)
    }

    /** The timer stopped: no alarm, no notification, no service. */
    fun cancel(ctx: Context) {
        prefs(ctx).edit().putBoolean(KEY_ARMED, false).apply()
        alarms(ctx).cancel(alarmIntent(ctx))
        notifications(ctx).cancel(ID_PROMPT)
        FocusTimerService.stop(ctx)
    }

    /** A tap on "Still working": store it, clear the prompt, arm the next one. */
    fun recordTap(ctx: Context, nowMs: Long = System.currentTimeMillis()) {
        synchronized(this) {
            val p = prefs(ctx)
            val old = p.getString(KEY_PENDING, "").orEmpty()
            p.edit().putString(KEY_PENDING, if (old.isEmpty()) "$nowMs" else "$old,$nowMs").commit()
        }
        notifications(ctx).cancel(ID_PROMPT)
        val p = prefs(ctx)
        if (p.getBoolean(KEY_ARMED, false)) arm(ctx, p.getLong(KEY_EVERY, 9 * 60_000L))
        onTap?.invoke()
    }

    /** Stored taps, oldest first; each is returned once. */
    fun takePending(ctx: Context): List<Long> = synchronized(this) {
        val p = prefs(ctx)
        val raw = p.getString(KEY_PENDING, "").orEmpty()
        if (raw.isEmpty()) return emptyList()
        p.edit().remove(KEY_PENDING).commit()
        raw.split(',').mapNotNull { it.toLongOrNull() }
    }

    /** The alarm fired: show "Still working?" with its action. */
    fun showPrompt(ctx: Context) {
        if (!prefs(ctx).getBoolean(KEY_ARMED, false) || !notificationsAllowed(ctx)) return
        ensureChannels(ctx)
        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val still = PendingIntent.getBroadcast(
            ctx, 1, Intent(ctx, FocusActionReceiver::class.java).setAction(ACTION_STILL),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val n = Notification.Builder(ctx, CHANNEL_PROMPT)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Still working?")
            .setContentText("Tap to keep the focus timer counting")
            .setContentIntent(open)
            .setCategory(Notification.CATEGORY_REMINDER)
            .addAction(Notification.Action.Builder(null, "Still working", still).build())
            .build()
        notifications(ctx).notify(ID_PROMPT, n)
    }

    fun ensureChannels(ctx: Context) {
        val nm = notifications(ctx)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_PROMPT, "Focus check-in", NotificationManager.IMPORTANCE_HIGH)
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_TIMER, "Focus timer", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun arm(ctx: Context, afterMs: Long) {
        val at = System.currentTimeMillis() + afterMs.coerceAtLeast(1_000L)
        val am = alarms(ctx)
        val pi = alarmIntent(ctx)
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi)
        }
    }

    private fun alarmIntent(ctx: Context): PendingIntent = PendingIntent.getBroadcast(
        ctx, 2, Intent(ctx, FocusAlarmReceiver::class.java).setAction(ACTION_ALARM),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun alarms(ctx: Context) = ctx.getSystemService(AlarmManager::class.java)

    private fun notifications(ctx: Context) = ctx.getSystemService(NotificationManager::class.java)
}
