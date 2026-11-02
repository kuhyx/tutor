package com.kuhy.tutor

import android.Manifest
import android.app.Activity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * `com.kuhy.tutor/focus`: the Dart `AndroidCheckinNotifier`'s side.
 * Methods: ensurePermission -> bool, schedule {afterMs, everyMs, lapseMs}, cancel,
 * takePending -> [ms]. Native -> Dart: `tapped` (taps are stored first).
 */
class FocusChannel(private val activity: Activity, engine: FlutterEngine) {
    private val channel = MethodChannel(engine.dartExecutor.binaryMessenger, NAME)
    private var permissionResult: MethodChannel.Result? = null

    init {
        channel.setMethodCallHandler(::handle)
        FocusCheckin.onTap = { activity.runOnUiThread { channel.invokeMethod("tapped", null) } }
    }

    fun dispose() {
        FocusCheckin.onTap = null
        channel.setMethodCallHandler(null)
    }

    /** Forwarded from [Activity.onRequestPermissionsResult]. */
    fun onPermission(granted: Boolean) {
        permissionResult?.success(granted)
        permissionResult = null
    }

    private fun handle(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "ensurePermission" -> ensurePermission(result)
            "schedule" -> {
                FocusCheckin.schedule(
                    activity,
                    (call.argument<Number>("afterMs") ?: 0).toLong(),
                    (call.argument<Number>("everyMs") ?: 0).toLong(),
                    (call.argument<Number>("lapseMs") ?: 600_000).toLong(),
                )
                result.success(null)
            }
            "cancel" -> {
                FocusCheckin.cancel(activity)
                result.success(null)
            }
            "takePending" -> result.success(FocusCheckin.takePending(activity))
            else -> result.notImplemented()
        }
    }

    private fun ensurePermission(result: MethodChannel.Result) {
        if (FocusCheckin.notificationsAllowed(activity)) return result.success(true)
        permissionResult?.success(false)
        permissionResult = result
        activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST)
    }

    companion object {
        const val NAME = "com.kuhy.tutor/focus"
        const val REQUEST = 4102
    }
}
