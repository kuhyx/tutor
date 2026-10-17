// `no_card_left` never shows the subject slug: the subject title and the
// next step (review a module / reviews due at / nothing) instead.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/relay/no_card.dart';
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
    expect(f.noCard!.next, NoCardNext.none);
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
    final n = f.noCard!;
    expect(n.next, NoCardNext.reviewModule);
    expect((n.module, n.moduleTitle), ('fuel', 'Fuel and ignition'));
  });

  test('fields under data are read too; reviews due at HH:mm', () {
    final now = DateTime(2026, 10, 17, 8);
    final due = DateTime(2026, 10, 17, 14, 5).millisecondsSinceEpoch;
    final n = NoCardLeft.fromResult({
      'data': {'subject_title': 'Car', 'next': 'reviews_due', 'due_at': due},
    });
    expect(n.next, NoCardNext.reviewsDue);
    expect(
      n.text(now: now),
      'No card left to teach in Car right now. Reviews due at 14:05.',
    );
    // Not today: the date too (the year only when it differs).
    final tomorrow = DateTime(2026, 10, 18, 9, 30).millisecondsSinceEpoch;
    final later = NoCardLeft.fromResult({
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
      NoCardLeft.fromResult({'next': 'reviews_due', 'due_at': nextYear})
          .text(now: now),
      endsWith('Reviews due on 2 Jan 2027 at 07:00.'),
    );
    // reviews_due without a time: no time line.
    expect(
      NoCardLeft.fromResult({'next': 'reviews_due'}).text(now: now),
      'No card left to teach in this subject right now.',
    );
  });

  test('the module to review: subject field, else the plan holding it', () {
    final subjects = {
      'car': _subject('car', 'How a car works', ['engine', 'fuel']),
      'boat': _subject('boat', 'Boats', ['fuel']),
    };
    NoCardLeft n(Map<String, Object?> j) =>
        NoCardLeft.fromResult({'next': 'review_module', ...j});
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
}
