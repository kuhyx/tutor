package com.kuhy.tutor

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** The exact alarm armed by [FocusCheckin.schedule] fired. */
class FocusAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = FocusCheckin.showPrompt(context)
}

/** The "Still working" button was tapped; works with the app dead. */
class FocusActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) = FocusCheckin.recordTap(context)
}
