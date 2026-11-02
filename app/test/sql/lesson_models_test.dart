import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sql/lesson_models.dart';
import 'package:tutor/sql/sql_requests.dart';

import 'sql_fixtures.dart';

void main() {
  test('a full turn parses', () {
    final t = parseLessonTurn(lessonTurnData);
    expect(t.lessonId, 'a1b2c3d4e5f6');
    expect(t.concept, 'NULL comparisons');
    expect((t.index, t.total, t.check, t.done), (0, 2, false, false));
    expect(t.questionMd, contains('Which names'));
    expect(t.feedbackMd, 'Not quite.');
    expect(t.summaryMd, contains('UNKNOWN'));
    expect(t.tables!.single.name, 'customers');
    expect(t.tables!.single.rows.first, ['1', 'Ann', '2']);
    expect(t.result!.columns, ['name']);
    expect(t.result!.rows, [
      ['Ann'],
    ]);
  });

  test('a minimal turn: no tables, no result, a check phase', () {
    final t = parseLessonTurn(const {
      'lesson_id': 'x',
      'progress': {'phase': 'check'},
      'done': true,
    });
    expect(t.tables, isNull);
    expect(t.result, isNull);
    expect(t.questionMd, isNull);
    expect((t.check, t.done, t.concept, t.total), (true, true, '', 0));
    expect(parseLessonTurn(const {'lesson_id': 'y'}).check, isFalse);
  });

  test('topics walk in order and end', () {
    expect(nextLessonTopic('basics'), 'joins-null');
    expect(nextLessonTopic('window'), 'strings');
    expect(nextLessonTopic('strings'), isNull);
    expect(nextLessonTopic('nope'), isNull);
  });

  test('lesson body: start, resume, answer', () {
    expect(sqlLessonTurn('basics').body, {'topic': 'basics'});
    expect(sqlLessonTurn('basics', lessonId: 'a').body, {
      'topic': 'basics',
      'lesson_id': 'a',
    });
    final b = sqlLessonTurn('basics', lessonId: 'a', answer: 'Ann');
    expect(b.kind.wire, 'sql_lesson_turn');
    expect(b.body['answer'], 'Ann');
  });
}
