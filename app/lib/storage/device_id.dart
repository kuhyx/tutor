/// The per-install device id: a uuid4 minted on first launch and kept
/// forever (never `pc`/`phone`; DOCS-contract §1). Reinstalling makes a new
/// device, which is fine: the log is keyed by it, never merged into it.
library;

import 'package:tutor/model/ids.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:uuid/uuid.dart';

const _key = 'device_id';

/// Returns this install's device id, minting and persisting one if needed.
///
/// A stored value that is not a uuid4 (corrupt store) is replaced.
Future<String> loadDeviceId(KvStore kv, {String Function()? mint}) async {
  final stored = await kv.get(_key);
  if (stored != null && isDeviceId(stored)) return stored;
  final id = (mint ?? const Uuid().v4)();
  await kv.set(_key, id);
  return id;
}
