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
 * An exact alarm posts the prompt even with the app dead or the screen off.
 * Since the check-in card (2026-11-08) the prompt only opens the app, where
 * the check-in is a graded recall card; it has no "Still working" action.
 * [FocusActionReceiver] stays for a prompt an older build already posted:
 * its stored taps are drained by Dart and no longer counted.
 */
object FocusCheckin {
    const val CHANNEL_PROMPT = "focus_checkin_v1"
    const val CHANNEL_TIMER = "focus_timer_v1"
    const val ACTION_ALARM = "com.kuhy.tutor.focus.ALARM"
    const val ACTION_LAPSE = "com.kuhy.tutor.focus.LAPSE"
    const val ACTION_STILL = "com.kuhy.tutor.focus.STILL_WORKING"
    const val ID_TIMER = 4100
    const val ID_PROMPT = 4101

    private const val PREFS = "focus_checkin"
    private const val KEY_PENDING = "pending"
    private const val KEY_EVERY = "every_ms"
    private const val KEY_ARMED = "armed"
    private const val KEY_LAPSE = "lapse_ms"
    private const val KEY_LAST_TAP = "last_tap"

    // Same fallbacks as Dart's checkinEvery / lapseAfter (focus_project: 600 s).
    private const val DEFAULT_EVERY_MS = 7 * 60_000L
    private const val DEFAULT_LAPSE_MS = 10 * 60_000L

    /** Set while an Activity listens; told when a tap was stored. */
    @Volatile
    var onTap: (() -> Unit)? = null

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun notificationsAllowed(ctx: Context): Boolean =
        Build.VERSION.SDK_INT < 33 ||
            ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * Arms the prompt [afterMs] from now and the lapse cleanup [lapseMs] from
     * now (this is a tap), and keeps the timer service alive.
     */
    fun schedule(
        ctx: Context,
        afterMs: Long,
        everyMs: Long,
        lapseMs: Long = DEFAULT_LAPSE_MS,
        nowMs: Long = System.currentTimeMillis(),
    ) {
        prefs(ctx).edit()
            .putLong(KEY_EVERY, everyMs)
            .putLong(KEY_LAPSE, lapseMs)
            .putLong(KEY_LAST_TAP, nowMs)
            .putBoolean(KEY_ARMED, true)
            .apply()
        // An in-app check-in lands here too: the shade prompt is answered.
        notifications(ctx).cancel(ID_PROMPT)
        arm(ctx, afterMs)
        armLapse(ctx, nowMs + lapseMs)
        FocusTimerService.start(ctx)
    }

    /** The timer stopped or lapsed: no alarms, no notification, no service. */
    fun cancel(ctx: Context) {
        prefs(ctx).edit().putBoolean(KEY_ARMED, false).apply()
        alarms(ctx).cancel(alarmIntent(ctx))
        alarms(ctx).cancel(lapseIntent(ctx))
        notifications(ctx).cancel(ID_PROMPT)
        FocusTimerService.stop(ctx)
    }

    /**
     * The lapse alarm fired (Dart may be dead): with no newer tap the run is
     * over, so disarm and tear the prompt and the service down.
     */
    fun onLapse(ctx: Context, nowMs: Long = System.currentTimeMillis()) {
        val p = prefs(ctx)
        if (!p.getBoolean(KEY_ARMED, false)) return
        if (p.getLong(KEY_LAST_TAP, 0L) + p.getLong(KEY_LAPSE, DEFAULT_LAPSE_MS) > nowMs) return
        cancel(ctx)
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
        if (p.getBoolean(KEY_ARMED, false)) {
            p.edit().putLong(KEY_LAST_TAP, nowMs).apply()
            arm(ctx, p.getLong(KEY_EVERY, DEFAULT_EVERY_MS))
            armLapse(ctx, nowMs + p.getLong(KEY_LAPSE, DEFAULT_LAPSE_MS))
        }
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

    /**
     * The alarm fired: post the check-in prompt, icon only (textgate: no
     * title or body); a tap opens the app, where the check-in card waits.
     */
    fun showPrompt(ctx: Context) {
        if (!prefs(ctx).getBoolean(KEY_ARMED, false) || !notificationsAllowed(ctx)) return
        ensureChannels(ctx)
        val open = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val n = Notification.Builder(ctx, CHANNEL_PROMPT)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(open)
            .setCategory(Notification.CATEGORY_REMINDER)
            .build()
        notifications(ctx).notify(ID_PROMPT, n)
    }

    /** Channel names are one glyph each (settings shows them; textgate). */
    fun ensureChannels(ctx: Context) {
        val nm = notifications(ctx)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_PROMPT, "🔔", NotificationManager.IMPORTANCE_HIGH)
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_TIMER, "⏱", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun arm(ctx: Context, afterMs: Long) =
        setAlarm(ctx, System.currentTimeMillis() + afterMs.coerceAtLeast(1_000L), alarmIntent(ctx))

    private fun armLapse(ctx: Context, atMs: Long) = setAlarm(ctx, atMs, lapseIntent(ctx))

    private fun setAlarm(ctx: Context, atMs: Long, pi: PendingIntent) {
        val am = alarms(ctx)
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi)
        }
    }

    private fun alarmIntent(ctx: Context): PendingIntent = PendingIntent.getBroadcast(
        ctx, 2, Intent(ctx, FocusAlarmReceiver::class.java).setAction(ACTION_ALARM),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun lapseIntent(ctx: Context): PendingIntent = PendingIntent.getBroadcast(
        ctx, 3, Intent(ctx, FocusLapseReceiver::class.java).setAction(ACTION_LAPSE),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun alarms(ctx: Context) = ctx.getSystemService(AlarmManager::class.java)

    private fun notifications(ctx: Context) = ctx.getSystemService(NotificationManager::class.java)
}
