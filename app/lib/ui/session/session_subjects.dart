/// The subjects the Session side panel reads (target card, mastered list):
/// the catalog cache at first, then a fresh fetch of the session's subject
/// whenever `rev.catalog` moves or a different session shows up. Reading
/// the cache once left the panel at a stale "-" (Home refreshes it only
/// while Home is in front).
library;

import 'dart:async';
import 'dart:developer';

import 'package:flutter/foundation.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/session/session_feed.dart';

/// Follows [_feed] and `rev.catalog`, keeping [subjects] fresh.
class SessionSubjects {
  /// Creates the follower; call [start] once.
  new(this._s, this._feed);

  final TutorServices _s;
  final SessionFeed _feed;
  late final StreamSubscription<int> _changes;
  bool _closed = false;
  String? _loadedFor;

  /// Subjects by id.
  final ValueNotifier<Map<String, SubjectData>> subjects = ValueNotifier(
    const {},
  );

  /// Loads the cache and starts following.
  void start() {
    unawaited(
      _s.catalog.cached().then((c) {
        // A fetch that landed first is newer than the cache.
        if (!_closed) subjects.value = {...c, ...subjects.value};
      }),
    );
    _changes = _s.rev.catalogChanges.listen((_) => _refresh(force: true));
    _feed.view.addListener(_refresh);
    _refresh();
  }

  /// Fetches the shown session's subject, unless that was done for this
  /// session already (or [force]).
  void _refresh({bool force = false}) {
    final view = _feed.view.value;
    final id = view?.meta?.subject;
    if (view == null || id == null) return;
    final key = '${view.sid}/$id';
    if (!force && key == _loadedFor) return;
    _loadedFor = key;
    unawaited(_fetch(id));
  }

  Future<void> _fetch(String id) async {
    try {
      final fresh = await _s.catalog.fetch(id);
      if (!_closed && fresh != null) {
        subjects.value = {...subjects.value, id: fresh};
      }
    } on Object catch (error) {
      // Offline: the cached subject stays on screen.
      log('subject $id not refreshed', level: 900, error: error);
    }
  }

  /// Stops following.
  Future<void> dispose() async {
    _closed = true;
    _feed.view.removeListener(_refresh);
    await _changes.cancel();
    subjects.dispose();
  }
}
