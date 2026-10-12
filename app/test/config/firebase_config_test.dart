import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/config/firebase_config.dart';

void main() {
  test('an all-empty config names what is missing', () {
    const c = FirebaseConfig(
      apiKey: '',
      databaseUrl: '',
      syncUid: '',
      serverClientId: 'x',
    );
    expect(c.missing, ['apiKey', 'databaseUrl', 'syncUid']);
    expect(c.isComplete, isFalse);
  });

  test('a filled config is complete without a client id', () {
    const c = FirebaseConfig(
      apiKey: 'k',
      databaseUrl: 'https://db',
      syncUid: 'u',
      serverClientId: '',
    );
    expect(c.isComplete, isTrue);
    expect(FirebaseConfig.compiled, isA<FirebaseConfig>());
  });
}
