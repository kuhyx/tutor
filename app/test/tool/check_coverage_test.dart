import 'package:flutter_test/flutter_test.dart';

import '../../tool/check_coverage.dart';

void main() {
  const src = [
    'a();', // 1 uncovered
    '// coverage:ignore-line', // 2
    'b();', // 3 exempt (comment above)
    'c(); // coverage:ignore-line', // 4 exempt
    '// coverage:ignore-start', // 5
    'd();', // 6 exempt
    '// coverage:ignore-end', // 7
    'e();', // 8 uncovered
  ];
  const lcov =
      'SF:lib/a.dart\nDA:1,0\nDA:3,0\nDA:4,0\nDA:6,0\nDA:8,0\nDA:9,0\n'
      'DA:2,1\nend_of_record\n'
      'SF:lib/ui/x.dart\nDA:1,0\nend_of_record\n'
      'SF:lib/main.dart\nDA:1,0\nend_of_record\n'
      'SF:lib/skip.dart\nDA:1,0\nend_of_record\n'
      'SF:lib/full.dart\nDA:1,1\nend_of_record\n';

  test('honours every marker and skips UI files', () {
    final gaps = uncovered(lcov, (p) {
      if (p == 'lib/skip.dart') return ['// coverage:ignore-file'];
      return p == 'lib/a.dart' ? src : const [];
    });
    expect(gaps, {
      'lib/a.dart': [1, 8, 9],
    });
  });

  test('isLogic', () {
    expect(isLogic('lib/log/fold.dart'), isTrue);
    expect(isLogic('lib/ui/home.dart'), isFalse);
    expect(isLogic('lib/main.dart'), isFalse);
    expect(isLogic('tool/x.dart'), isFalse);
  });
}
