package com.kuhy.tutor

import android.app.Activity
import android.content.Intent
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * `kuhytutor://learn|review|rework/...` links (leetcode-guard's phone app;
 * Dart side `ui/deep_link_io.dart`). The launch intent's link goes out once
 * through `initialLink`; each later intent's link through the event channel,
 * held until Dart listens (the app may still be on sign-in or the e2e lock).
 * A link takes exactly one of the two paths, so a cold start opens it once.
 */
class DeepLinkChannel(private val activity: Activity, engine: FlutterEngine) :
    EventChannel.StreamHandler {
    private var sink: EventChannel.EventSink? = null
    private val pending = mutableListOf<String>()

    init {
        val messenger = engine.dartExecutor.binaryMessenger
        MethodChannel(messenger, "com.kuhy.tutor/deeplink").setMethodCallHandler { call, result ->
            if (call.method != "initialLink") return@setMethodCallHandler result.notImplemented()
            result.success(take(activity.intent))
        }
        EventChannel(messenger, "com.kuhy.tutor/deeplink/new").setStreamHandler(this)
    }

    /** A link sent to the running activity (launchMode singleTask). */
    fun onNewIntent(intent: Intent) {
        val link = take(intent) ?: return
        val out = sink
        if (out != null) out.success(link) else pending.add(link)
    }

    // Every listen flushes: a sign-out and sign-in remounts the Dart listener.
    override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
        sink = events
        pending.forEach(events::success)
        pending.clear()
    }

    override fun onCancel(arguments: Any?) {
        sink = null
    }

    companion object {
        /**
         * The VIEW link [intent] carries, cleared from it so it opens once;
         * null for a relaunch from Recents, which replays the old intent.
         */
        fun take(intent: Intent?): String? {
            if (intent == null || intent.action != Intent.ACTION_VIEW) return null
            if ((intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0) return null
            val link = intent.dataString
            intent.data = null
            return link
        }
    }
}
