package com.kuhy.tutor

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder

/**
 * Foreground service that exists only while the focus timer runs: it keeps
 * the process (and the Dart timer) alive with the screen off and shows the
 * ongoing "Focus timer running" notification.
 */
class FocusTimerService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        FocusCheckin.ensureChannels(this)
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val n = Notification.Builder(this, FocusCheckin.CHANNEL_TIMER)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("Focus timer running")
            .setContentIntent(open)
            .setOngoing(true)
            .setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE)
            .build()
        startForeground(FocusCheckin.ID_TIMER, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        return START_NOT_STICKY
    }

    /**
     * Swiped out of recents: the run is over. Drop the alarms, the prompt and
     * this service at once; the stop event (stamped when the app was hidden)
     * is already queued by Dart and goes out on the next launch.
     */
    override fun onTaskRemoved(rootIntent: Intent?) {
        FocusCheckin.cancel(this)
        stopSelf()
        super.onTaskRemoved(rootIntent)
    }

    companion object {
        fun start(ctx: Context) {
            try {
                ctx.startForegroundService(Intent(ctx, FocusTimerService::class.java))
            } catch (e: IllegalStateException) {
                // Started from the background (Android 12+ refuses): the alarm
                // chain still prompts, only the process pinning is lost.
            }
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, FocusTimerService::class.java))
        }
    }
}
