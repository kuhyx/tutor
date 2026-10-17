import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';

const _t0 = 1791731346000;

StudyCard _card(String module, int order, {bool suspended = false}) =>
    StudyCard(
      module: module,
      order: order,
      front: 'F$order',
      back: 'B',
      source: 'https://x',
      excerpt: 'e',
      rev: 1,
      origin: 'seed',
      suspended: suspended,
    );

SubjectData _subject({ModuleStatus aStatus = ModuleStatus.ready}) =>
    SubjectData(
      id: 'car',
      meta: const SubjectMeta(
        title: 'Car',
        goal: '',
        status: SubjectStatus.active,
        created: 1,
        planRev: 1,
        rev: 1,
        origin: 'seed',
      ),
      plan: Plan(
        rev: 1,
        status: 'approved',
        modules: [
          Module(id: 'a', title: 'A', status: aStatus),
          const Module(id: 'b', title: 'B', status: ModuleStatus.ready),
          const Module(id: 'empty', title: 'Empty', status: ModuleStatus.ready),
        ],
      ),
      cards: {
        'a1': _card('a', 1),
        'a2': _card('a', 2),
        'a3': _card('a', 3),
        'a4': _card('a', 4, suspended: true),
        'b1': _card('b', 1),
      },
    );

int _n = 0;
LoggedEvent _e(LogEvent event, {String dev = 'd'}) => LoggedEvent(
  dev: dev,
  eid: 'E${(_n++).toString().padLeft(6, '0')}',
  event: event,
);
// Taught by the worker: its own reviews would be drill picks (curriculum §6).
LoggedEvent _taught(String c) => _e(
  TaughtEvent(subject: 'car', card: c, at: _t0),
  dev: 'pc',
);
LoggedEvent _review(String c, Grade g) =>
    _e(ReviewEvent(subject: 'car', card: c, at: _t0 + 1000, grade: g, rev: 1));
LoggedEvent _flag(String c) =>
    _e(FlagEvent(subject: 'car', card: c, at: _t0 + 1, rev: 1, reason: 'x'));

Map<String, ModuleReview> _states(SubjectData s, List<LoggedEvent> es) =>
    subjectProgress(
      s,
      fold(es, cardInfos([s])),
      DateTime.fromMillisecondsSinceEpoch(_t0, isUtc: true),
    ).review;

void main() {
  final s = _subject();

  test('module review state: open -> done -> reviewed', () {
    expect(_states(s, []), {
      'a': ModuleReview.open,
      'b': ModuleReview.open,
      'empty': ModuleReview.open, // no cards: never "done"
    });
    // Two of three taught: still open.
    expect(_states(s, [_taught('a1'), _taught('a2')])['a'], ModuleReview.open);
    final all = [_taught('a1'), _taught('a2'), _taught('a3')];
    expect(_states(s, all)['a'], ModuleReview.done); // suspended a4 ignored
    // A flagged card does not hold the module back.
    expect(
      _states(s, [_taught('a1'), _taught('a3'), _flag('a2')])['a'],
      ModuleReview.done,
    );
    final good = [...all, _review('a1', Grade.good), _review('a2', Grade.easy)];
    expect(_states(s, good)['a'], ModuleReview.done); // a3 not yet
    expect(
      _states(s, [...good, _review('a3', Grade.hard)])['a'],
      ModuleReview.done,
    );
    expect(
      _states(s, [...good, _review('a3', Grade.good)])['a'],
      ModuleReview.reviewed,
    );
    // Only flagged cards: nothing to review.
    expect(_states(s, [_taught('b1'), _flag('b1')])['b'], ModuleReview.open);
  });

  test('moduleToReview: first done module the PC has not unlocked past', () {
    final es = [_taught('a1'), _taught('a2'), _taught('a3'), _taught('b1')];
    final at = DateTime.fromMillisecondsSinceEpoch(_t0, isUtc: true);
    final p = subjectProgress(s, fold(es, cardInfos([s])), at);
    final ref = moduleToReview(s, p)!;
    expect((ref.subject, ref.module, ref.title), ('car', 'a', 'A'));
    // Already "mastered" on the PC: the next one is offered instead.
    final m = _subject(aStatus: ModuleStatus.mastered);
    final pm = subjectProgress(m, fold(es, cardInfos([m])), at);
    expect(moduleToReview(m, pm)!.module, 'b');
    expect(moduleToReview(s, subjectProgress(s, fold([], {}), at)), isNull);
  });
}
