import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/plan/plan_ops.dart';

const _a = Module(id: 'a', title: 'A', summary: 's');
const _b = Module(id: 'b', title: 'B', requires: ['a'], cards: 4);
const _c = Module(id: 'c', title: 'C', requires: ['a', 'b']);

void main() {
  const plan = [_a, _b, _c];
  const free = Module(id: 'd', title: 'D');

  test('rename keeps everything else', () {
    final out = renameModule(plan, 1, ' Bee ', summary: ' new ');
    expect(out[1].title, 'Bee');
    expect(out[1].summary, 'new');
    expect(out[1].cards, 4);
    expect(out[1].requires, ['a']);
    expect(renameModule(plan, 0, 'X')[0].summary, 's');
  });

  test('move clamps and flags requires that are no longer earlier', () {
    final out = moveModule(plan, 0, 9);
    expect(out.map((m) => m.id), ['b', 'c', 'a']);
    expect(planProblems(out), hasLength(2));
    expect(planProblems(plan), isEmpty);
  });

  test('remove only modules without cards; drops them from requires', () {
    expect(() => removeModule(plan, 1), throwsStateError);
    expect(editable(_a), isTrue);
    final out = removeModule([...plan, free], 0);
    expect(out.map((m) => m.id), ['b', 'c', 'd']);
    expect(out.every((m) => !m.requires.contains('a')), isTrue);
  });

  test('add: unique slug, depth of the last module', () {
    final out = addModule(plan, 'A');
    expect(out.last.id, 'a-2');
    expect(out.last.depth, 1);
    expect(
      addModule(const [Module(id: 'd', title: 'D', depth: 2)], 'e').last.depth,
      2,
    );
    expect(addModule(const [], '!!!').single.id, 'module');
    expect(addModule(const [], 'x').single.depth, 1);
    expect(
      slugFor('Engine: the Basics', ['engine-the-basics']),
      'engine-the-basics-2',
    );
    expect(slugFor('a' * 39 + ' b', const []).length, 39);
  });

  test('set requires and validate', () {
    final out = setRequires(plan, 2, ['b']);
    expect(out[2].requires, ['b']);
    expect(
      planProblems(const [_a, _a, Module(id: 'Bad', title: ' ')]),
      containsAll(<Matcher>[
        contains('appears twice'),
        contains('no title'),
        contains('not valid'),
      ]),
    );
    expect(planProblems(const [_a]).single, contains('3-12 new modules'));
    // Only the newest depth counts: three depth-2 modules after one.
    expect(
      planProblems(const [
        _a,
        Module(id: 'x', title: 'X', depth: 2),
        Module(id: 'y', title: 'Y', depth: 2),
        Module(id: 'z', title: 'Z', depth: 2),
      ]),
      isEmpty,
    );
    expect(
      editable(const Module(id: 'r', title: 'R', status: ModuleStatus.ready)),
      isFalse,
    );
  });

  test('samePlan compares the wire form', () {
    const p = Plan(rev: 1, status: 'draft', modules: [_a, _b]);
    expect(
      samePlan(p, const Plan(rev: 1, status: 'draft', modules: [_a, _b])),
      isTrue,
    );
    expect(
      samePlan(p, const Plan(rev: 2, status: 'draft', modules: [_a, _b])),
      isFalse,
    );
    expect(samePlan(null, null), isTrue);
    expect(samePlan(p, null), isFalse);
  });
}
