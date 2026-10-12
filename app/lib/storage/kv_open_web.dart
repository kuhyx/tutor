/// The web half of `kv_open.dart`.
library;

import 'package:idb_shim/idb_browser.dart';
import 'package:tutor/storage/kv_store.dart';

/// Opens the `tutor` IndexedDB database.
Future<KvStore> openKv() => IdbKv.open(idbFactoryBrowser);
