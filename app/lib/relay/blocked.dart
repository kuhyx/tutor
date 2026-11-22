/// The blocking results (DOCS-contract §4): `locked` and `no_card_left`.
/// The worker adds flat fields next to `code`/`error`, each optional:
/// `subject_title`, `next` (`review_module` with `module` and
/// `module_title`, `reviews_due` with `due_at` in ms, or `none`),
/// `due_in_subject`, `writing` (the next module's cards are being written)
/// and `gate_cards` (the module gate, curriculum §6: the exact cards to
/// review before the next module; the app opens that review at once). The
/// app builds its own one-line "why" from those, never the worker's `error`
/// text. A result without `next` reads as `none`. An old `daily_new_cap`
/// (the cap is gone) is no block any more.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/progress/card_progress.dart';

/// No card left to teach.
const noCardLeft = 'no_card_left';

/// The card's module is not open yet.
const lockedCode = 'locked';

/// The codes that read as a call to action, not an error.
const Set<String> blockedCodes = {noCardLeft, lockedCode};

/// What fixes a block.
enum BlockedNext {
  /// Review a done module (`module`, `module_title`).
  reviewModule,

  /// Wait for reviews (`due_at`).
  reviewsDue,

  /// Nothing (or the worker did not say).
  none,
}

/// A blocking result's extra fields.
class Blocked {
  /// Creates the record.
  const new({
    this.code = noCardLeft,
    this.next = BlockedNext.none,
    this.subjectTitle,
    this.subject,
    this.module,
    this.moduleTitle,
    this.dueAt,
    this.dueInSubject,
    this.gateCards = const [],
    this.writing = false,
  });

  /// Reads the fields from the result node (or its `data`, to be safe).
  factory fromResult(Json result) {
    final data = result['data'];
    Object? field(String k) =>
        result[k] ?? (data is Map<String, dynamic> ? data[k] : null);
    String? text(String k) {
      final v = field(k);
      return v is String && v.trim().isNotEmpty ? v.trim() : null;
    }

    int? number(String k) => switch (field(k)) {
      final num v => v.toInt(),
      _ => null,
    };
    final code = text('code') ?? noCardLeft;
    return Blocked(
      code: code,
      next: switch (field('next')) {
        'review_module' => BlockedNext.reviewModule,
        'reviews_due' => BlockedNext.reviewsDue,
        _ => BlockedNext.none,
      },
      subjectTitle: text('subject_title'),
      subject: text('subject_id') ?? text('subject'),
      module: text('module'),
      moduleTitle: text('module_title'),
      dueAt: number('due_at'),
      dueInSubject: number('due_in_subject'),
      gateCards: switch (field('gate_cards')) {
        final List<dynamic> ids => [
          for (final id in ids)
            if (id is String && id.isNotEmpty) id,
        ],
        _ => const [],
      },
      writing: field('writing') == true,
    );
  }

  /// Which block.
  final String code;

  /// The next step.
  final BlockedNext next;

  /// The subject's title (never its id).
  final String? subjectTitle;

  /// The subject id (`subject_id`, DOCS-contract §4), when sent.
  final String? subject;

  /// Module id to review.
  final String? module;

  /// Its title.
  final String? moduleTitle;

  /// When reviews fall due (ms).
  final int? dueAt;

  /// Cards of this subject due for review now.
  final int? dueInSubject;

  /// The module gate: the cards to review before the next module starts
  /// (empty: nothing to review now).
  final List<String> gateCards;

  /// The next module's cards are still being written.
  final bool writing;

  /// The module gate holds the next card for a review.
  bool get gated => gateCards.isNotEmpty;

  /// A module waits for its review first.
  bool get reviewsModule => next == BlockedNext.reviewModule && module != null;

  /// The line for kuhy: why, and what is next; [now] decides whether the
  /// due time needs its date.
  String text({DateTime? now}) => switch (code) {
    lockedCode =>
      reviewsModule
          ? 'That is locked until “${moduleTitle ?? module}” is reviewed.'
          : 'That is locked until earlier modules are reviewed.',
    _ => _noCardText(now ?? DateTime.now()),
  };

  String _noCardText(DateTime now) {
    final where = subjectTitle ?? 'this subject';
    final headline = 'No card left to teach in $where right now.';
    final step = switch (next) {
      BlockedNext.reviewModule when module != null =>
        'Next: review ${moduleTitle ?? 'this module'}.',
      BlockedNext.reviewsDue when dueAt != null =>
        'Reviews due ${_when(dueAt!, now)}.',
      _ => null,
    };
    return step == null ? headline : '$headline $step';
  }

  /// The subject this block is about: the `subject` field, else the one
  /// titled [subjectTitle], else [hint] (the screen's subject).
  String? subjectId(Map<String, SubjectData> subjects, {String? hint}) {
    if (subjects.containsKey(subject)) return subject;
    final titled = subjects.values.where((s) => s.meta.title == subjectTitle);
    return titled.firstOrNull?.id ?? (subjects.containsKey(hint) ? hint : null);
  }

  /// The module to review, scoped to its subject: the `subject` field, else
  /// the subject whose plan has [module]: the one titled [subjectTitle]
  /// first (the worker always sends it), then [hint] (the screen's subject,
  /// which may be another session's). Null when no plan holds the module.
  ModuleRef? moduleRef(Map<String, SubjectData> subjects, {String? hint}) {
    final id = module;
    if (!reviewsModule || id == null) return null;
    bool has(SubjectData s) => s.plan?.modules.any((m) => m.id == id) ?? false;
    final named = subject == null ? null : subjects[subject];
    final candidates = subjects.values.where(has).toList();
    final hinted = subjects[hint];
    final s =
        named ??
        candidates.where((s) => s.meta.title == subjectTitle).firstOrNull ??
        (hinted != null && has(hinted) ? hinted : null) ??
        candidates.firstOrNull;
    if (s == null) return null;
    final title = s.plan?.modules.where((m) => m.id == id).firstOrNull?.title;
    return ModuleRef(
      subject: s.id,
      module: id,
      title: moduleTitle ?? title ?? id,
    );
  }
}

const _months = [
  ...['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
  ...['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
];

/// "at HH:mm" today, else "on 18 Oct at HH:mm" (the year if not this one),
/// in local time.
String _when(int ms, DateTime now) {
  final t = DateTime.fromMillisecondsSinceEpoch(ms);
  final n = now.toLocal();
  final hm =
      '${t.hour.toString().padLeft(2, '0')}:'
      '${t.minute.toString().padLeft(2, '0')}';
  if (t.year == n.year && t.month == n.month && t.day == n.day) return 'at $hm';
  final year = t.year == n.year ? '' : ' ${t.year}';
  return 'on ${t.day} ${_months[t.month - 1]}$year at $hm';
}
