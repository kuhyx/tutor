/// The io half of `kv_open.dart`.
library;

import 'package:tutor/storage/kv_store.dart';

/// Opens shared_preferences.
Future<KvStore> openKv() => PrefsKv.open();
