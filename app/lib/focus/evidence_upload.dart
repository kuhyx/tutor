/// Chunked image upload for `focus_evidence` kind `file`
/// (DOCS-contract.md §3 "uploads", DOCS-contract-focus.md).
///
/// The image never rides in a request (40 KB cap): base64 text chunks go to
/// `uploads/{ulid}/c0001..` first, then the request names them with the
/// chunk count and the sha256 of the decoded bytes.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:tutor/focus/image_downscale.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/interview_body.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/util/ulid.dart';

/// Largest decoded image: 16 chunks of 262140 base64 chars hold 3.14 MB.
const int maxImageBytes = 3000000;

/// Chars per chunk: a multiple of 4 (whole base64 groups), under 262144.
const int chunkChars = 262140;

/// Shrinks [bytes] to a PNG of at most `maxBytes`; null when it cannot.
typedef Downscale = Future<Uint8List?> Function(Uint8List bytes, int maxBytes);

/// The picked file cannot be uploaded (not an image, or too big to shrink).
class UploadRefused implements Exception {
  /// Creates the refusal.
  const new(this.reason);

  /// Why.
  final String reason;

  @override
  String toString() => 'UploadRefused: $reason';
}

/// `image/png`, `image/jpeg` or `image/webp` by magic bytes; else null.
String? sniffMime(Uint8List b) {
  bool at(int i, List<int> magic) =>
      b.length >= i + magic.length &&
      [for (var k = 0; k < magic.length; k++) b[i + k]].toString() ==
          magic.toString();
  if (at(0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
    return 'image/png';
  }
  if (at(0, [0xff, 0xd8, 0xff])) return 'image/jpeg';
  if (at(0, 'RIFF'.codeUnits) && at(8, 'WEBP'.codeUnits)) return 'image/webp';
  return null;
}

/// Writes images to `uploads/`.
class EvidenceUploader {
  /// Creates the uploader; [downscale] shrinks an image over the cap.
  const new({
    required this.client,
    required this.ulid,
    this.downscale = downscalePng,
  });

  /// REST client.
  final RtdbClient client;

  /// Source of the upload id.
  final UlidGenerator ulid;

  /// Shrinks an image that is too big.
  final Downscale downscale;

  /// Uploads [picked]; returns the reference `focus_evidence` carries.
  /// Throws [UploadRefused] before writing anything when it is no image or
  /// cannot be made small enough; a failed write rethrows the transport
  /// error (the caller shows it).
  Future<UploadRef> upload(Uint8List picked) async {
    var bytes = picked;
    var mime = sniffMime(bytes);
    if (mime == null) throw const UploadRefused('not a png, jpeg or webp');
    if (bytes.length > maxImageBytes) {
      final small = await downscale(bytes, maxImageBytes);
      if (small == null || small.length > maxImageBytes) {
        throw const UploadRefused('image too big to shrink');
      }
      bytes = small;
      mime = 'image/png';
    }
    final id = ulid.next();
    final text = base64Encode(bytes);
    var n = 0;
    for (var i = 0; i < text.length; i += chunkChars) {
      n++;
      final end = i + chunkChars > text.length ? text.length : i + chunkChars;
      await client.put(Paths.uploadChunk(id, n), text.substring(i, end));
    }
    return (
      upload: id,
      chunks: n,
      sha256: sha256.convert(bytes).toString(),
      mime: mime,
    );
  }
}
