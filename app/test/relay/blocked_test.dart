// The blocking results (`daily_new_cap`, `locked`, `no_card_left`) never
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

  test('daily_new_cap: why + what is open, never the worker text', () {
    const raw = 'Ten new cards today already. Reviews still work.';
    final f = blocked('daily_new_cap', {
      'subject_title': 'Apache',
      'new_today': 25,
      'new_cap': 25,
      'module_title': 'vhost-apache',
      'due_in_subject': 3,
      'next': 'lift_cap',
    }, raw);
    expect(
      f.text,
      'You learned 25 new cards today (the daily limit). '
      '“vhost-apache” is open.',
    );
    expect(f.text, isNot(contains('Reviews still work')));
    final b = f.blocked!;
    expect(b.code, 'daily_new_cap');
    expect(b.next, BlockedNext.liftCap);
    expect((b.dueInSubject, b.newToday, b.newCap), (3, 25, 25));
    // Every field optional: a plain line, still no worker text.
    final bare = blocked('daily_new_cap', const {}, raw);
    expect(bare.text, "You reached today's limit of new cards.");
    expect(bare.blocked!.next, BlockedNext.liftCap);
    expect(
      blocked('daily_new_cap', const {
        'new_today': 12,
        'new_cap': 10,
      }, raw).text,
      'You learned 12 new cards today (the daily limit is 10).',
    );
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
