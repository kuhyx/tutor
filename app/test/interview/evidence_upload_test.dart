import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/evidence_upload.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

Uint8List _png(int length) {
  final b = Uint8List(length)
    ..setAll(0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  for (var i = 8; i < length; i++) {
    b[i] = (i * 31) & 0xff;
  }
  return b;
}

void main() {
  late FakeRtdb db;
  EvidenceUploader uploader({Downscale? downscale}) => EvidenceUploader(
    client: db.client(),
    ulid: UlidGenerator(),
    downscale: downscale ?? (_, _) async => null,
  );

  setUp(() => db = FakeRtdb());

  test('mime comes from the magic bytes, not a name', () {
    expect(sniffMime(_png(20)), 'image/png');
    expect(
      sniffMime(Uint8List.fromList([0xff, 0xd8, 0xff, 0xe0, 0])),
      'image/jpeg',
    );
    expect(
      sniffMime(
        Uint8List.fromList([
          ...'RIFF'.codeUnits,
          1,
          2,
          3,
          4,
          ...'WEBP'.codeUnits,
        ]),
      ),
      'image/webp',
    );
    expect(sniffMime(Uint8List.fromList(utf8.encode('GIF89a....'))), isNull);
    expect(sniffMime(Uint8List(0)), isNull);
  });

  test('a small image goes up as c0001 and the ref names it', () async {
    final bytes = _png(1000);
    final ref = await uploader().upload(bytes);
    expect(isUlid(ref.upload), isTrue);
    expect(ref.chunks, 1);
    expect(ref.mime, 'image/png');
    expect(ref.sha256, sha256.convert(bytes).toString());
    expect(ref.sha256, matches(RegExp(r'^[0-9a-f]{64}$')));
    final chunk = getAt(db.root, 'tutor/v1/uploads/${ref.upload}/c0001');
    expect(base64Decode(chunk! as String), bytes);
  });

  test('a big image is split into <= 262144-char chunks that rejoin', () async {
    final bytes = _png(1500000);
    final ref = await uploader().upload(bytes);
    expect(ref.chunks, inInclusiveRange(2, 16));
    final parts =
        getAt(db.root, 'tutor/v1/uploads/${ref.upload}')!
            as Map<String, dynamic>;
    final keys = parts.keys.toList()..sort();
    expect(keys, [
      for (var n = 1; n <= ref.chunks; n++) 'c${n.toString().padLeft(4, '0')}',
    ]);
    final joined = StringBuffer();
    for (final k in keys) {
      final s = parts[k]! as String;
      expect(s.length, inInclusiveRange(1, 262144));
      joined.write(s);
    }
    expect(base64Decode(joined.toString()), bytes);
  });

  test('over the cap and no downscale result: refused, nothing written', () {
    final bytes = _png(maxImageBytes + 1);
    expect(uploader().upload(bytes), throwsA(isA<UploadRefused>()));
    expect(db.log.where((l) => l.startsWith('PUT')), isEmpty);
  });

  test('over the cap: the downscaled PNG is what is hashed and sent', () async {
    final small = _png(5000);
    var asked = 0;
    final jpegBig = Uint8List.fromList([
      0xff,
      0xd8,
      0xff,
      0,
      ...List.filled(maxImageBytes + 5, 7),
    ]);
    final ref = await uploader(
      downscale: (b, max) async {
        asked++;
        expect(max, maxImageBytes);
        return small;
      },
    ).upload(jpegBig);
    expect(asked, 1);
    expect(ref.mime, 'image/png');
    expect(ref.sha256, sha256.convert(small).toString());
  });

  test('not an image: refused before any write', () {
    expect(
      uploader().upload(Uint8List.fromList(utf8.encode('hello world!'))),
      throwsA(isA<UploadRefused>()),
    );
    expect(db.log.where((l) => l.startsWith('PUT')), isEmpty);
  });

  test('a failed chunk write surfaces as an error, never swallowed', () {
    db.offline = true;
    expect(uploader().upload(_png(100)), throwsA(anything));
  });

  test('upload paths check the ulid and zero-pad the chunk key', () {
    expect(
      Paths.uploadChunk('01HZZZZZZZZZZZZZZZZZZZZZZZ', 7),
      'tutor/v1/uploads/01HZZZZZZZZZZZZZZZZZZZZZZZ/c0007',
    );
    expect(() => Paths.upload('nope'), throwsArgumentError);
  });
}
