import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/focus_models.dart';
import 'package:tutor/focus/interview_models.dart';

import '_data.dart';

void main() {
  test('a status from the old protocol has no interview part', () {
    final s = parseStatus(statusOf({...oldProject, 'minutes': 3}));
    expect(s.active!.interview, isNull);
    expect(s.projects.single.interview, isNull);
  });

  test('a kind:focus row is not an interview even with stray fields', () {
    final s = parseStatus(
      statusOf({...oldProject, 'kind': 'focus', 'milestones': <Object>[]}),
    );
    expect(s.active!.interview, isNull);
  });

  test('an interview row parses milestones, trips and answers', () {
    final i = parseStatus(statusOf(interviewProject())).active!.interview!;
    expect(i.testAt, DateTime(2026, 11, 20, 10));
    expect(i.inviteUrl, 'https://app.codility.com/c/acme');
    expect(i.trips.single, (start: '2026-11-14', end: '2026-11-15'));
    expect(i.weekendAnswers, {'2026-11-14': true});
    expect(i.milestones.map((m) => m.id), [
      'rules',
      'trip_ask:2026-11-14',
      'phone:2026-11-14',
      'mock',
      'slot',
    ]);
    expect(i.milestones.first.due, DateTime(2026, 11, 10, 23, 59));
    expect(i.milestones.first.state, MilestoneState.pending);
    expect(i.missed, isFalse);
  });

  test('every wire state parses; an unknown word counts as unknown', () {
    expect(MilestoneState.parse('pending'), MilestoneState.pending);
    expect(MilestoneState.parse('done'), MilestoneState.done);
    expect(MilestoneState.parse('missed'), MilestoneState.missed);
    expect(MilestoneState.parse('late_done'), MilestoneState.lateDone);
    expect(MilestoneState.parse('unknown'), MilestoneState.unknown);
    expect(MilestoneState.parse('???'), MilestoneState.unknown);
    expect(MilestoneState.missed.red, isTrue);
    expect(MilestoneState.unknown.red, isTrue);
    expect(MilestoneState.lateDone.red, isFalse);
    expect(MilestoneState.lateDone.ok, isTrue);
    expect(MilestoneState.pending.ok, isFalse);
  });

  test('milestone ids split into a group and an argument', () {
    expect(groupOf('rules'), MilestoneGroup.rules);
    expect(groupOf('trip_ask:2026-11-14'), MilestoneGroup.tripAsk);
    expect(groupOf('phone:2026-11-14'), MilestoneGroup.phone);
    expect(groupOf('mock'), MilestoneGroup.mock);
    expect(groupOf('slot'), MilestoneGroup.slot);
    expect(groupOf('future-thing'), isNull);
    expect(argOf('trip_ask:2026-11-14'), '2026-11-14');
    expect(argOf('rules'), isNull);
  });

  test('a group is red when any member is red, else grey until all ok', () {
    Milestone m(String state) => (
      id: 'phone:x',
      due: DateTime(2026),
      state: MilestoneState.parse(state),
    );
    expect(groupLight([m('done'), m('late_done')]), Light.green);
    expect(groupLight([m('done'), m('pending')]), Light.grey);
    expect(groupLight([m('pending'), m('missed')]), Light.red);
    expect(groupLight([m('done'), m('unknown')]), Light.red);
    expect(groupLight(const []), Light.grey);
  });

  test('the actionable milestone is the first red, else the earliest due', () {
    Milestone m(String id, int day, String state) => (
      id: id,
      due: DateTime(2026, 11, day),
      state: MilestoneState.parse(state),
    );
    final list = [
      m('phone:a', 12, 'pending'),
      m('phone:b', 11, 'pending'),
      m('phone:c', 13, 'missed'),
      m('phone:d', 9, 'done'),
    ];
    expect(actionable(list)!.id, 'phone:c');
    expect(actionable(list.sublist(0, 2))!.id, 'phone:b');
    expect(actionable([m('phone:d', 9, 'done')]), isNull);
    expect(actionable(const []), isNull);
  });

  test('a milestone block from an evidence result redraws the state', () {
    final s = parseStatus(statusOf(interviewProject())).active!;
    final next = applyBlock(s.interview!, {
      'milestones': [
        ms('rules', '2026-11-10T23:59:00', 'done'),
        ms('mock', '2026-11-18T23:59:00', 'pending'),
      ],
      'missed': true,
      'trips': [
        {'start': '2026-11-13', 'end': '2026-11-15'},
      ],
      'weekend_answers': {'2026-11-14': true, '2026-11-21': false},
    });
    expect(next.milestones.map((m) => m.state), [
      MilestoneState.done,
      MilestoneState.pending,
    ]);
    expect(next.missed, isTrue);
    expect(next.trips.single.start, '2026-11-13');
    expect(next.weekendAnswers['2026-11-21'], isFalse);
    expect(next.testAt, s.interview!.testAt, reason: 'untouched fields kept');
    final moved = withInterview(s, next);
    expect(moved.interview, next);
    expect(moved.id, s.id);
    expect(moved.minutes, s.minutes);
  });
}
