/// `no_card_left` (DOCS-contract §4): the worker adds `subject_title` and
/// the next step to the result node (`next`: `review_module` with `module`
/// and `module_title`, `reviews_due` with `due_at` in ms, or `none`). The
/// app shows those instead of the worker's `error` text, so the subject slug
/// never reaches the screen. A result without `next` (the old deck path)
/// reads as `none`.
library;

import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/progress/card_progress.dart';

/// The code.
const noCardLeft = 'no_card_left';

/// What to do once no card is left.
enum NoCardNext {
  /// Review a done module (`module`, `module_title`).
  reviewModule,

  /// Wait for reviews (`due_at`).
  reviewsDue,

  /// Nothing (or the worker did not say).
  none,
}

/// A `no_card_left` result's extra fields.
class NoCardLeft {
  /// Creates the record.
  const new({
    this.next = NoCardNext.none,
    this.subjectTitle,
    this.subject,
    this.module,
    this.moduleTitle,
    this.dueAt,
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

    final due = field('due_at');
    return NoCardLeft(
      next: switch (field('next')) {
        'review_module' => NoCardNext.reviewModule,
        'reviews_due' => NoCardNext.reviewsDue,
        _ => NoCardNext.none,
      },
      subjectTitle: text('subject_title'),
      subject: text('subject'),
      module: text('module'),
      moduleTitle: text('module_title'),
      dueAt: due is num ? due.toInt() : null,
    );
  }

  /// The next step.
  final NoCardNext next;

  /// The subject's title (never its id).
  final String? subjectTitle;

  /// The subject id, when the worker sends it.
  final String? subject;

  /// Module id to review.
  final String? module;

  /// Its title.
  final String? moduleTitle;

  /// When reviews fall due (ms).
  final int? dueAt;

  /// The line for kuhy: the subject title and the next step; [now] decides
  /// whether the due time needs its date.
  String text({DateTime? now}) {
    final where = subjectTitle == null ? 'this subject' : subjectTitle!;
    final headline = 'No card left to teach in $where right now.';
    final step = switch (next) {
      NoCardNext.reviewModule when module != null =>
        'Next: review ${moduleTitle ?? 'this module'}.',
      NoCardNext.reviewsDue when dueAt != null =>
        'Reviews due ${_when(dueAt!, now ?? DateTime.now())}.',
      _ => null,
    };
    return step == null ? headline : '$headline $step';
  }

  /// The module to review, scoped to its subject: the `subject` field, else
  /// the subject whose plan has [module] ([hint] first, then the one titled
  /// [subjectTitle]). Null when there is no module or no plan holds it.
  ModuleRef? moduleRef(Map<String, SubjectData> subjects, {String? hint}) {
    final id = module;
    if (next != NoCardNext.reviewModule || id == null) return null;
    bool has(SubjectData s) => s.plan?.modules.any((m) => m.id == id) ?? false;
    final named = subject == null ? null : subjects[subject];
    final candidates = subjects.values.where(has).toList();
    final hinted = subjects[hint];
    final s =
        named ??
        (hinted != null && has(hinted) ? hinted : null) ??
        candidates.where((s) => s.meta.title == subjectTitle).firstOrNull ??
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
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
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
