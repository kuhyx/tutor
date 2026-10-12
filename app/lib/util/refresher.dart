/// Data a screen refreshes in place: the last good value stays on screen
/// while a reload runs (no spinner flash), a failed reload keeps it, and a
/// slow older reload never overwrites a newer one.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

/// Loads, keeps and reloads one value of type [T] ([T] may be nullable:
/// a record wraps it so "loaded null" differs from "not loaded yet").
class Refresher<T> extends ChangeNotifier {
  /// Creates the refresher; call [reload] to load the first time. `hold`
  /// decides whether a fresh value must wait (see [hasPending]) for
  /// [applyPending] rather than replace what is on screen (unsaved edits).
  new(this._load, {this._hold});

  final Future<T> Function() _load;
  final bool Function(T current, T next)? _hold;
  (T,)? _data;
  (T,)? _pending;
  Object? _error;
  bool _loading = false;
  int _seq = 0;
  int _resets = 0;
  bool _disposed = false;

  /// Whether a value has loaded at least once.
  bool get hasData => _data != null;

  /// The value on screen (check [hasData] first when [T] is nullable).
  T get data => _data!.$1;

  /// A newer value held back by `hold`, if any.
  bool get hasPending => _pending != null;

  /// The latest reload's error (cleared by the next success).
  Object? get error => _error;

  /// Bumped when a value replaces the screen past `hold` (a forced reload
  /// or [applyPending]): key local-edit state on it to drop the edits.
  int get resets => _resets;

  /// Whether a reload is running.
  bool get loading => _loading;

  /// Loads again. [force] skips `hold` (the user asked for it, or the
  /// change is the user's own request landing) and drops any pending value.
  Future<void> reload({bool force = false}) async {
    final seq = ++_seq;
    _loading = true;
    _notify();
    T next;
    try {
      next = await _load();
    } on Object catch (error) {
      // `on Object`: any failure is shown by the screen, never thrown into
      // a fire-and-forget refresh.
      if (seq != _seq) return;
      _error = error;
      _loading = false;
      _notify();
      return;
    }
    if (seq != _seq) return;
    _error = null;
    _loading = false;
    final current = _data;
    final hold = _hold;
    if (!force && current != null && hold != null && hold(current.$1, next)) {
      _pending = (next,);
    } else {
      if (force) _resets++;
      _data = (next,);
      _pending = null;
    }
    _notify();
  }

  /// Puts the held value on screen.
  void applyPending() {
    final pending = _pending;
    if (pending == null) return;
    _data = pending;
    _pending = null;
    _resets++;
    _notify();
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
