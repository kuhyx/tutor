/// The blocking results (DOCS-contract §4): `daily_new_cap`, `locked` and
/// `no_card_left`. The worker adds flat fields next to `code`/`error`, each
/// optional: `subject_title`, `next` (`review_module` with `module` and
/// `module_title`, `reviews_due` with `due_at` in ms, `lift_cap`, or
/// `none`), `due_in_subject`, and for the cap `new_today`/`new_cap`. The app
/// builds its own one-line "why" from those, never the worker's `error` text
/// (it names the subject slug and repeated the headline). A result without
/// `next` reads as `none`, except the cap, which can always be lifted.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/progress/card_progress.dart';

/// No card left to teach.
const noCardLeft = 'no_card_left';

/// Today's new cards are used up.
const dailyNewCap = 'daily_new_cap';

/// The card's module is not open yet.
const lockedCode = 'locked';

/// The codes that read as a call to action, not an error.
const Set<String> blockedCodes = {noCardLeft, dailyNewCap, lockedCode};

/// What fixes a block.
enum BlockedNext {
  /// Review a done module (`module`, `module_title`).
  reviewModule,

  /// Wait for reviews (`due_at`).
  reviewsDue,

  /// Lift today's new-card cap (`session_start` with `lift_cap`).
  liftCap,

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
    this.newToday,
    this.newCap,
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
        'lift_cap' => BlockedNext.liftCap,
        _ when code == dailyNewCap => BlockedNext.liftCap,
        _ => BlockedNext.none,
      },
      subjectTitle: text('subject_title'),
      subject: text('subject'),
      module: text('module'),
      moduleTitle: text('module_title'),
      dueAt: number('due_at'),
      dueInSubject: number('due_in_subject'),
      newToday: number('new_today'),
      newCap: number('new_cap'),
    );
  }

  /// Which block.
  final String code;

  /// The next step.
  final BlockedNext next;

  /// The subject's title (never its id).
  final String? subjectTitle;

  /// The subject id, when the worker sends it.
  final String? subject;

  /// Module id to review (for the cap: none).
  final String? module;

  /// Its title (for the cap: the module that is open).
  final String? moduleTitle;

  /// When reviews fall due (ms).
  final int? dueAt;

  /// Cards of this subject due for review now.
  final int? dueInSubject;

  /// New cards learned today.
  final int? newToday;

  /// Today's new-card limit.
  final int? newCap;

  /// A module waits for its review first.
  bool get reviewsModule => next == BlockedNext.reviewModule && module != null;

  /// The line for kuhy: why, and what is next; [now] decides whether the
  /// due time needs its date.
  String text({DateTime? now}) => switch (code) {
    dailyNewCap => _capText(),
    lockedCode =>
      reviewsModule
          ? 'That is locked until “${moduleTitle ?? module}” is reviewed.'
          : 'That is locked until earlier modules are reviewed.',
    _ => _noCardText(now ?? DateTime.now()),
  };

  String _capText() {
    final n = newToday;
    final cap = newCap;
    final limit = cap == null || cap == n ? '' : ' is $cap';
    final why = n == null
        ? "You reached today's limit of new cards."
        : 'You learned $n new cards today (the daily limit$limit).';
    return moduleTitle == null ? why : '$why “$moduleTitle” is open.';
  }

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
