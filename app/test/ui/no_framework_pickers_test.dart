// textgate guard: Flutter's own date and time pickers paint month and
// weekday words; app/lib must use the numeric picker instead.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

final _call = RegExp(r'\bshow(?:Date|Time|DateRange)Picker\s*[<(]');

void main() {
  test('app/lib never calls a framework date or time picker', () {
    final files = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'))
        .toList();
    expect(files, isNotEmpty, reason: 'run from app/: no lib/*.dart found');
    final hits = <String>[
      for (final f in files)
        for (final (i, line) in f.readAsLinesSync().indexed)
          if (_call.hasMatch(line)) '${f.path}:${i + 1}: ${line.trim()}',
    ];
    expect(hits, isEmpty, reason: 'framework pickers paint words');
  });
}
