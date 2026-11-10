import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/subject.dart';
import 'package:tutor/widgets/status_glyph.dart';

import '../support/label_finders.dart';
import '../support/no_words.dart';

void main() {
  testWidgets('each status has its own glyph and a spoken word', (t) async {
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              for (final s in SubjectStatus.values) StatusGlyph(s, size: 18),
              const StatusGlyph(SubjectStatus.failed, detail: 'no sources'),
            ],
          ),
        ),
      ),
    );
    final icons = {for (final s in SubjectStatus.values) statusIcon(s)};
    expect(icons.length, SubjectStatus.values.length);
    expect(bySpoken('review only'), findsOneWidget);
    expect(bySpoken('failed · no sources'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsNWidgets(2));
    expectNoWords(t, 'status glyphs');
  });
}
