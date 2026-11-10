// The machine-code vocabularies shared with the Python worker:
// contract/codes.json at the repo root (checked by tutor/tests/test_codes.py).
// The Dart mirror must hold exactly the same wire values, and every parser
// maps an unknown or missing value to `other`.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/codes.dart';
import 'package:tutor/model/request.dart';

Map<String, dynamic> _vectors() {
  // `flutter test` runs from app/; the contract dir is the repo root's.
  final here = Directory.current.path;
  final root = here.endsWith('/app') ? Directory.current.parent.path : here;
  final raw = File('$root/contract/codes.json').readAsStringSync();
  return jsonDecode(raw) as Map<String, dynamic>;
}

Set<String> _set(Map<String, dynamic> v, String k) =>
    (v[k] as List<dynamic>).cast<String>().toSet();

void main() {
  final v = _vectors();

  test('every Dart vocabulary equals the contract', () {
    expect(RelayCode.values.map((c) => c.wire).toSet(), _set(v, 'relay_code'));
    expect(
      FailReason.values.map((c) => c.wire).toSet(),
      _set(v, 'fail_reason'),
    );
    expect(
      NoticeKind.values.map((c) => c.wire).toSet(),
      _set(v, 'notice_kind'),
    );
    expect(ErrorKind.values.map((c) => c.wire).toSet(), _set(v, 'error_kind'));
    expect(
      UnavailableReason.values
          .where((r) => r != UnavailableReason.other)
          .map((r) => r.wire)
          .toSet(),
      _set(v, 'unavailable_reason'),
    );
    final pause = (v['pause_reason'] as Map<String, dynamic>)
        .cast<String, String>();
    expect(PauseReason.lowEffort.wire, pause['low_effort']);
    expect(PauseReason.stalled.wire, pause['stalled']);
    expect(
      Phase.values.where((p) => p != Phase.other).map((p) => p.wire).toList(),
      (v['relay_phase'] as List<dynamic>).cast<String>(),
    );
  });

  test('unknown or missing values parse as other', () {
    expect(RelayCode.parse('no_card_left'), RelayCode.noCardLeft);
    expect(RelayCode.parse('exploded'), RelayCode.other);
    expect(RelayCode.parse(null), RelayCode.other);
    expect(FailReason.parse('paste_statement'), FailReason.pasteStatement);
    expect(FailReason.parse(42), FailReason.other);
    expect(NoticeKind.parse('mnemonic_cleared'), NoticeKind.mnemonicCleared);
    expect(NoticeKind.parse('zzz'), NoticeKind.other);
    expect(ErrorKind.parse('too_few_cards'), ErrorKind.tooFewCards);
    expect(ErrorKind.parse(null), ErrorKind.other);
    expect(UnavailableReason.parse('rate_limit'), UnavailableReason.rateLimit);
    expect(UnavailableReason.parse(''), UnavailableReason.other);
    expect(PauseReason.parse('low-effort reply'), PauseReason.lowEffort);
    expect(PauseReason.parse('no reply for 10 min'), PauseReason.stalled);
    expect(PauseReason.parse('tired'), PauseReason.other);
    expect(Phase.parse('checking_images'), Phase.checkingImages);
    expect(Phase.parse('dreaming'), Phase.other);
  });
}
