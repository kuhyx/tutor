/// Opens the platform's [KvStore]: shared_preferences on Android, IndexedDB
/// on web (the desktop build). A conditional export because `idb_browser`
/// cannot compile on the VM and shared_preferences' web backend is
/// localStorage, not IndexedDB.
library;

import 'package:tutor/storage/kv_store.dart' show KvStore;

export 'kv_open_io.dart' if (dart.library.js_interop) 'kv_open_web.dart';
