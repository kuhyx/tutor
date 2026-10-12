/// A tiny per-install string store: device id, the offline event queue,
/// pulled log events and cursors.
///
/// shared_preferences on Android, IndexedDB on web (DOCS-contract §1), a map
/// in tests. Values are strings (JSON where structured).
library;

import 'package:idb_shim/idb.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Get / set / remove by key.
abstract interface class KvStore {
  /// The value, or null.
  Future<String?> get(String key);

  /// Stores [value].
  Future<void> set(String key, String value);

  /// Deletes [key].
  Future<void> remove(String key);
}

/// In-memory store (tests, and a fallback that loses data on restart).
class MemoryKv implements KvStore {
  /// The backing map, visible to tests.
  final Map<String, String> data = {};

  @override
  Future<String?> get(String key) async => data[key];

  @override
  Future<void> set(String key, String value) async => data[key] = value;

  @override
  Future<void> remove(String key) async => data.remove(key);
}

/// shared_preferences-backed store (Android).
class PrefsKv implements KvStore {
  /// Wraps an opened [SharedPreferences].
  new(this._prefs);

  final SharedPreferences _prefs;

  /// Opens the app's preferences.
  static Future<PrefsKv> open() async =>
      PrefsKv(await SharedPreferences.getInstance());

  static const _prefix = 'tutor.';

  @override
  Future<String?> get(String key) async => _prefs.getString('$_prefix$key');

  @override
  Future<void> set(String key, String value) async {
    await _prefs.setString('$_prefix$key', value);
  }

  @override
  Future<void> remove(String key) async {
    await _prefs.remove('$_prefix$key');
  }
}

/// IndexedDB-backed store (web), one object store of strings.
class IdbKv implements KvStore {
  new _(this._db);

  final Database _db;
  static const _store = 'kv';

  /// Opens (creating) the `tutor` database through [factory].
  static Future<IdbKv> open(IdbFactory factory) async {
    final db = await factory.open(
      'tutor',
      version: 1,
      onUpgradeNeeded: (e) => e.database.createObjectStore(_store),
    );
    return IdbKv._(db);
  }

  @override
  Future<String?> get(String key) async {
    final txn = _db.transaction(_store, idbModeReadOnly);
    final value = await txn.objectStore(_store).getObject(key);
    await txn.completed;
    return value as String?;
  }

  @override
  Future<void> set(String key, String value) async {
    final txn = _db.transaction(_store, idbModeReadWrite);
    await txn.objectStore(_store).put(value, key);
    await txn.completed;
  }

  @override
  Future<void> remove(String key) async {
    final txn = _db.transaction(_store, idbModeReadWrite);
    await txn.objectStore(_store).delete(key);
    await txn.completed;
  }
}
