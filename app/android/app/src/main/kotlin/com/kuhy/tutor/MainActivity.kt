package com.kuhy.tutor

import android.content.Intent
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var focus: FocusChannel? = null
    private var links: DeepLinkChannel? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        // Recreated after process death: the task replays the launch intent,
        // whose link was already opened.
        if (savedInstanceState != null) intent?.data = null
        super.onCreate(savedInstanceState)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        links?.onNewIntent(intent)
    }

    override fun onRequestPermissionsResult(
        code: Int, permissions: Array<out String>, results: IntArray
    ) {
        super.onRequestPermissionsResult(code, permissions, results)
        if (code == FocusChannel.REQUEST) {
            focus?.onPermission(results.firstOrNull() == android.content.pm.PackageManager.PERMISSION_GRANTED)
        }
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        focus?.dispose()
        focus = null
        links = null
        super.cleanUpFlutterEngine(flutterEngine)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        focus = FocusChannel(this, flutterEngine)
        links = DeepLinkChannel(this, flutterEngine)
        // "Sync Anki & credit": AnkiDroid's own sync intent (it throttles
        // this to once per 2 min). false = not installed or refused (not exported).
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.kuhy.tutor/anki")
            .setMethodCallHandler { call, result ->
                if (call.method != "sync") return@setMethodCallHandler result.notImplemented()
                val intent = Intent("com.ichi2.anki.DO_SYNC")
                    .addCategory(Intent.CATEGORY_DEFAULT)
                    .setPackage("com.ichi2.anki")
                try {
                    startActivity(intent)
                    result.success(true)
                } catch (e: RuntimeException) {
                    result.success(false)
                }
            }
    }
}
