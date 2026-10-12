import 'package:flutter_test/flutter_test.dart';

import '../../tool/write_firebase_config.dart';

void main() {
  const json =
      '{"apiKey":"k","databaseUrl":"https://db","uid":"u","email":"e"}';
  const todo = "const kServerClientId =\n    'todo-client';";

  test('reads the three identifiers and the todo client id', () {
    final v = parse(json, todoSource: todo);
    expect(v.apiKey, 'k');
    expect(v.databaseUrl, 'https://db');
    expect(v.syncUid, 'u');
    expect(v.serverClientId, 'todo-client');
  });

  test('env beats firebase.json beats todo', () {
    const withWeb =
        '{"apiKey":"k","databaseUrl":"d","uid":"u","webClientId":"w"}';
    expect(parse(withWeb, todoSource: todo).serverClientId, 'w');
    expect(
      parse(withWeb, envClientId: 'env', todoSource: todo).serverClientId,
      'env',
    );
    expect(parse(json, envClientId: '').serverClientId, '');
  });

  test('a missing identifier fails loudly', () {
    expect(
      () => parse('{"apiKey":"k","databaseUrl":""}'),
      throwsFormatException,
    );
  });

  test('render escapes quotes, backslashes and dollars', () {
    const v = FirebaseLocal(
      apiKey: r"a'b\c$d",
      databaseUrl: 'https://db',
      syncUid: 'u',
      serverClientId: '',
    );
    final out = render(v);
    expect(out, contains(r"const kFirebaseApiKey = 'a\'b\\c\$d';"));
    expect(out, contains("const kGoogleServerClientId = '';"));
    expect(render(FirebaseLocal.empty), contains("kFirebaseSyncUid = '';"));
  });
}
