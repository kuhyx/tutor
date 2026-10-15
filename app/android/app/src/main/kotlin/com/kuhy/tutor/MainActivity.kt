package com.kuhy.tutor

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
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
