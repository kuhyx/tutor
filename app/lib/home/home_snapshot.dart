/// Home's data: the subjects and the counts the loader folded for them.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/root.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';

/// One subject on Home.
class SubjectEntry {
  /// Creates the entry.
  const new(this.id, this.meta, [this.data]);

  /// Subject id.
  final String id;

  /// Its meta.
  final SubjectMeta meta;

  /// Plan, cards and concepts (null only when they failed to parse).
  final SubjectData? data;
}

/// Home's data.
class HomeSnapshot {
  /// Creates the snapshot.
  const new({
    required this.subjects,
    required this.due,
    required this.offline,
    this.today,
    this.currentSubject,
    this.live,
    this.toReview = const {},
    this.cardTally = const {},
    this.dueBySubject = const {},
    this.dueByModule = const {},
  });

  /// Subject id -> module id -> its due cards, only modules with some (the
  /// badge's module sheet; off-plan cards are in no module).
  final Map<String, Map<String, int>> dueByModule;

  /// Subject id -> its due cards (what its Review shows; 0 = absent).
  final Map<String, int> dueBySubject;

  /// Subject id -> its cards' tally (done / recalled / due; suspended
  /// cards not counted).
  final Map<String, Tally> cardTally;

  /// Subject id -> its first module that is done but not reviewed.
  final Map<String, ModuleRef> toReview;

  /// Subjects, by title.
  final List<SubjectEntry> subjects;

  /// Cards due for review now, all subjects.
  final int due;

  /// Built from the cache because the database was unreachable.
  final bool offline;

  /// `stats.today`, when reachable.
  final Today? today;

  /// `prefs.current_subject`, when reachable.
  final String? currentSubject;

  /// The live session, when reachable and one is live.
  final Live? live;
}
