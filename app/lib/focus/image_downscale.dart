/// Shrinks a picked screenshot with the engine's own codec (no image
/// package): decode at a smaller width, re-encode as PNG.
library;

import 'dart:typed_data';
import 'dart:ui' as ui;

const _widths = [2048, 1600, 1280, 1024, 800, 640];

/// [bytes] as a PNG of at most [maxBytes], trying smaller widths until it
/// fits; null when none does or [bytes] do not decode.
Future<Uint8List?> downscalePng(Uint8List bytes, int maxBytes) async {
  for (final width in _widths) {
    try {
      final codec = await ui.instantiateImageCodec(bytes, targetWidth: width);
      final frame = await codec.getNextFrame();
      final data = await frame.image.toByteData(format: ui.ImageByteFormat.png);
      frame.image.dispose();
      codec.dispose();
      if (data == null) return null;
      final png = data.buffer.asUint8List(
        data.offsetInBytes,
        data.lengthInBytes,
      );
      if (png.length <= maxBytes) return png;
    } on Exception {
      return null; // not decodable: the caller refuses it
    }
  }
  return null;
}
