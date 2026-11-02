import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

/// Study destinations of a missed item: SQL lesson by topic, coach by slug.
typedef MockLinks = ({
  Future<void> Function(BuildContext context, String topic) openLesson,
  Future<void> Function(BuildContext context, String slug) openCoach,
});

Future<void> _push(BuildContext context, Widget screen) =>
    Navigator.of(context).push<void>(MaterialPageRoute(builder: (_) => screen));

/// The real lesson and coach screens.
MockLinks mockRoutes(TutorServices s) => (
  openLesson: (context, topic) =>
      _push(context, SqlLessonScreen(services: s, topic: topic)),
  openCoach: (context, slug) => _push(
    context,
    CoachScreen(
      services: s,
      open: lcOpen(problem: slug),
      title: slug,
    ),
  ),
);
