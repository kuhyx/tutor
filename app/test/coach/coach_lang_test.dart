import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_list.dart';

void main() {
  test('both SQL dialects are SQL, the text languages are not', () {
    expect(isSqlLang('mysql'), isTrue);
    expect(isSqlLang('postgresql'), isTrue);
    expect(isSqlLang(defaultCoachLang), isFalse);
    expect(isSqlLang('typescript'), isFalse);
  });
}
