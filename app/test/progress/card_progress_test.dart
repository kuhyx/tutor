import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/card.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/progress/card_progress.dart';

const int _h = 3600 * 1000;
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

final _subject = SubjectData(
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
  plan: const Plan(
    rev: 1,
    status: 'approved',
    modules: [
      Module(id: 'a', title: 'A'),
      Module(id: 'b', title: 'B'),
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
LoggedEvent _e(LogEvent event) => LoggedEvent(
  dev: 'd',
  eid: 'E${(_n++).toString().padLeft(6, '0')}',
  event: event,
);
LoggedEvent _taught(String c, int at) =>
    _e(TaughtEvent(subject: 'car', card: c, at: at));
LoggedEvent _review(String c, int at, Grade g) =>
    _e(ReviewEvent(subject: 'car', card: c, at: at, grade: g, rev: 1));

void main() {
  test('good: Good or Easy, 20 h after taught, latest review only', () {
    final r = fold([
      _taught('a1', _t0),
      _review('a1', _t0 + 20 * _h, Grade.good), // exactly 20 h: good
      _taught('a2', _t0),
      _review('a2', _t0 + 19 * _h, Grade.easy), // too soon
      _taught('a3', _t0),
      _review('a3', _t0 + 21 * _h, Grade.easy),
      _review('a3', _t0 + 30 * _h, Grade.hard), // latest is Hard
      _taught('b1', _t0),
      _review('b1', _t0 + 21 * _h, Grade.good),
      _taught('b1', _t0 + 22 * _h), // re-taught: needs a new review
      _e(const UntaughtEvent(subject: 'car', card: 'a2', at: _t0 + 40 * _h)),
    ], cardInfos([_subject]));
    expect(r.good, {'car/a1'});
  });

  test('per card, per module and subject totals', () {
    final infos = cardInfos([_subject]);
    expect(infos['car/a4']!.suspended, isTrue);
    final r = fold([
      _taught('a1', _t0),
      _review('a1', _t0 + 21 * _h, Grade.good),
      _taught('a2', _t0),
      _e(
        const FlagEvent(
          subject: 'car',
          card: 'a2',
          at: _t0 + 1,
          rev: 1,
          reason: 'wrong',
        ),
      ),
      _taught('b1', _t0),
    ], infos);
    final later = DateTime.fromMillisecondsSinceEpoch(
      _t0 + 400 * 24 * _h,
      isUtc: true,
    );
    final p = subjectProgress(_subject, r, later);
    expect(p.cards.keys, ['a1', 'a2', 'a3', 'b1']); // a4 suspended
    expect(p.cards['a1']!.label, 'mastered · due');
    expect(p.cards['a2']!.label, 'done · flagged');
    expect(p.cards['a3']!.label, 'not taught yet');
    expect(p.modules['a']!.summary, '2/3 done · 1 mastered · 1 due');
    expect(p.modules['b']!.summary, '1/1 done · 0 mastered · 1 due');
    expect(p.total.summary, '3/4 done · 1 mastered · 2 due');
    expect(p.total.doneText, '3 done · 1 mastered · 2 due');
    final soon = subjectProgress(
      _subject,
      r,
      DateTime.fromMillisecondsSinceEpoch(_t0, isUtc: true),
    );
    expect(soon.total.summary, '3/4 done · 1 mastered');
    final empty = SubjectData(id: 'x', meta: _subject.meta);
    expect(subjectProgress(empty, r, later).total.summary, '');
  });
}
