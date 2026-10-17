// Id vectors shared with the Python worker: contract/slug_vectors.json at the
// repo root (checked by tutor/tests/test_ids.py). Polish letters are kept in
// ids, NFD spellings are invalid, and Dart agrees with Python on all of it.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/plan/plan_ops.dart';

Map<String, dynamic> _vectors() {
  // `flutter test` runs from app/; the contract dir is the repo root's.
  final here = Directory.current.path;
  final root = here.endsWith('/app') ? Directory.current.parent.path : here;
  final raw = File('$root/contract/slug_vectors.json').readAsStringSync();
  return jsonDecode(raw) as Map<String, dynamic>;
}

void main() {
  final vectors = _vectors();

  test('slugFor agrees with Python slug() on every shared text', () {
    final rows = (vectors['slug'] as List<dynamic>)
        .cast<Map<String, dynamic>>();
    expect(rows, isNotEmpty);
    for (final row in rows) {
      final text = row['text'] as String;
      final want = row['slug'] as String;
      expect(slugFor(text, const []), want, reason: 'slugFor($text)');
      expect(isSlug(want), isTrue, reason: 'isSlug($want)');
    }
  });

  test('isSlug agrees with Python valid_id() on every shared id', () {
    final rows = (vectors['valid'] as List<dynamic>)
        .cast<Map<String, dynamic>>();
    expect(rows, isNotEmpty);
    for (final row in rows) {
      final id = row['id'] as String;
      expect(isSlug(id), row['ok'] as bool, reason: 'isSlug("$id")');
    }
  });

  test('a Polish id is a legal subject path, percent-encoded on the wire', () {
    expect(
      Paths.subject('pojęcia-z-łodzi'),
      'tutor/v1/subjects/pojęcia-z-łodzi',
    );
    expect(Uri.encodeComponent('pojęcia-z-łodzi'), 'poj%C4%99cia-z-%C5%82odzi');
    final nfd = 'zażo${String.fromCharCode(0x301)}łć';
    expect(() => Paths.subject(nfd), throwsArgumentError);
    expect(isSlug(nfd), isFalse);
  });

  test('slugFor keeps Polish letters and dedupes against taken ids', () {
    expect(slugFor('Pojęcia', ['pojęcia']), 'pojęcia-2');
    expect(slugFor('ŁÓDŹ', const []), 'łódź');
    expect(slugFor('ą' * 41, const []).length, 40);
  });
}
