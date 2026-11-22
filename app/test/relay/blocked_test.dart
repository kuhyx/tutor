// The blocking results (`locked`, `no_card_left`) never
// show the subject slug or the worker's raw text: one short "why" line from
// the payload fields, each optional, plus the next step.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/relay/blocked.dart';
import 'package:tutor/relay/request_relay.dart';

Map<String, Object?> _result([Map<String, Object?> extra = const {}]) => {
  'result': {
    ...extra,
    'ok': false,
    'at': 1,
    'code': 'no_card_left',
    'error': 'no open card left in car',
    'retry': false,
  },
};

RelayFailed _failed([Map<String, Object?> extra = const {}]) =>
    statusOf(_result(extra)) as RelayFailed;

SubjectData _subject(String id, String title, List<String> modules) =>
    SubjectData(
      id: id,
      meta: SubjectMeta(
        title: title,
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
        modules: [for (final m in modules) Module(id: m, title: m)],
      ),
    );

void main() {
  test('no extra fields: a generic line, never the slug', () {
    final f = _failed();
    expect(f.text, 'No card left to teach in this subject right now.');
    expect(f.blocked!.next, BlockedNext.none);
  });

  test('subject title and "review a module"', () {
    final f = _failed({
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    });
    expect(
      f.text,
      'No card left to teach in How a car works right now. '
      'Next: review Fuel and ignition.',
    );
    expect(f.text, isNot(contains('left in car')));
    final n = f.blocked!;
    expect(n.next, BlockedNext.reviewModule);
    expect((n.module, n.moduleTitle), ('fuel', 'Fuel and ignition'));
  });

  test('fields under data are read too; reviews due at HH:mm', () {
    final now = DateTime(2026, 10, 17, 8);
    final due = DateTime(2026, 10, 17, 14, 5).millisecondsSinceEpoch;
    final n = Blocked.fromResult({
      'data': {'subject_title': 'Car', 'next': 'reviews_due', 'due_at': due},
    });
    expect(n.next, BlockedNext.reviewsDue);
    expect(
      n.text(now: now),
      'No card left to teach in Car right now. Reviews due at 14:05.',
    );
    // Not today: the date too (the year only when it differs).
    final tomorrow = DateTime(2026, 10, 18, 9, 30).millisecondsSinceEpoch;
    final later = Blocked.fromResult({
      'next': 'reviews_due',
      'due_at': tomorrow,
    });
    expect(
      later.text(now: now),
      'No card left to teach in this subject right now. '
      'Reviews due on 18 Oct at 09:30.',
    );
    final nextYear = DateTime(2027, 1, 2, 7).millisecondsSinceEpoch;
    expect(
      Blocked.fromResult({'next': 'reviews_due', 'due_at': nextYear})
          .text(now: now),
      endsWith('Reviews due on 2 Jan 2027 at 07:00.'),
    );
    // reviews_due without a time: no time line.
    expect(
      Blocked.fromResult({'next': 'reviews_due'}).text(now: now),
      'No card left to teach in this subject right now.',
    );
  });

  test('the module to review: subject field, else the plan holding it', () {
    final subjects = {
      'car': _subject('car', 'How a car works', ['engine', 'fuel']),
      'boat': _subject('boat', 'Boats', ['fuel']),
    };
    Blocked n(Map<String, Object?> j) =>
        Blocked.fromResult({'next': 'review_module', ...j});
    final named = n({'subject': 'boat', 'module': 'fuel'});
    expect(named.moduleRef(subjects)!.subject, 'boat');
    // No subject id: the one whose plan has that module (title breaks ties).
    expect(n({'module': 'engine'}).moduleRef(subjects)!.subject, 'car');
    final tie = n({'module': 'fuel', 'subject_title': 'Boats'});
    expect(tie.moduleRef(subjects)!.subject, 'boat');
    // The title beats the screen's subject (another session may be shown).
    expect(tie.moduleRef(subjects, hint: 'car')!.subject, 'boat');
    expect(
      n({'module': 'fuel'}).moduleRef(subjects, hint: 'boat')!.subject,
      'boat',
    );
    final ref = n({'module': 'fuel', 'module_title': 'Fuel'})
        .moduleRef(subjects, hint: 'car')!;
    expect((ref.subject, ref.module, ref.title), ('car', 'fuel', 'Fuel'));
    expect(n({'module': 'sails'}).moduleRef(subjects), isNull);
    expect(n({}).moduleRef(subjects), isNull);
  });

  RelayFailed blocked(String code, Map<String, Object?> extra, String error) =>
      statusOf({
        'result': {
          ...extra,
          'ok': false,
          'at': 1,
          'code': code,
          'error': error,
        },
      }) as RelayFailed;

  test('gate_cards and writing: the module gate, read safely', () {
    final b = blocked('no_card_left', {
      'next': 'review_module',
      'module': 'engine',
      'gate_cards': ['a', 7, '', 'b'],
      'writing': true,
    }, 'raw').blocked!;
    expect(b.gateCards, ['a', 'b']);
    expect(b.gated, isTrue);
    expect(b.writing, isTrue);
    final plain = blocked('no_card_left', const {'gate_cards': 'x'}, 'raw');
    expect(plain.blocked!.gated, isFalse);
    expect(plain.blocked!.writing, isFalse);
  });

  test('an old daily_new_cap is no block any more', () {
    expect(blocked('daily_new_cap', const {}, 'raw').blocked, isNull);
  });

  test('locked: names the module to review first', () {
    final f = blocked('locked', {
      'subject_title': 'How a car works',
      'next': 'review_module',
      'module': 'fuel',
      'module_title': 'Fuel and ignition',
    }, 'card eng-x locked in car');
    expect(f.text, 'That is locked until “Fuel and ignition” is reviewed.');
    expect(f.blocked!.next, BlockedNext.reviewModule);
    final bare = blocked('locked', {'next': 'none'}, 'locked in car');
    expect(bare.text, 'That is locked until earlier modules are reviewed.');
    expect(bare.text, isNot(contains('in car')));
  });

  test('no_card_left keeps due_in_subject', () {
    expect(_failed({'due_in_subject': 4}).blocked!.dueInSubject, 4);
    expect(_failed().blocked!.dueInSubject, isNull);
  });

  test('the subject to review: id, else the title, else the hint', () {
    final subjects = {
      'car': _subject('car', 'How a car works', ['engine']),
      'boat': _subject('boat', 'Boats', ['fuel']),
    };
    expect(Blocked.fromResult({'subject': 'boat'}).subjectId(subjects), 'boat');
    expect(
      Blocked.fromResult({'subject_title': 'Boats'})
          .subjectId(subjects, hint: 'car'),
      'boat',
    );
    expect(Blocked.fromResult({}).subjectId(subjects, hint: 'car'), 'car');
    expect(Blocked.fromResult({}).subjectId(subjects), isNull);
  });
}
