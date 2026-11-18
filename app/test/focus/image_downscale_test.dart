import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/image_downscale.dart';

Future<Uint8List> _png(int w, int h) async {
  final rec = ui.PictureRecorder();
  ui.Canvas(rec).drawRect(
    ui.Rect.fromLTWH(0, 0, w.toDouble(), h.toDouble()),
    ui.Paint()..color = const ui.Color(0xff3366cc),
  );
  final image = await rec.endRecording().toImage(w, h);
  final data = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  return data!.buffer.asUint8List();
}

Future<ui.Image> _decode(Uint8List png) async {
  final codec = await ui.instantiateImageCodec(png);
  return (await codec.getNextFrame()).image;
}

void main() {
  testWidgets('a decodable image comes back as a PNG that fits', (t) async {
    await t.runAsync(() async {
      final src = await _png(64, 48);
      final out = await downscalePng(src, 1000000);
      expect(out, isNotNull);
      expect(out!.length, lessThanOrEqualTo(1000000));
      // The PNG magic: it re-encodes, not echoes the input.
      expect(out.sublist(1, 4), 'PNG'.codeUnits);
      expect((await _decode(out)).height, greaterThan(0));
    });
  });

  testWidgets('nothing small enough at any width is null', (t) async {
    await t.runAsync(() async {
      expect(await downscalePng(await _png(64, 48), 1), isNull);
    });
  });

  testWidgets('bytes that do not decode are null, not a crash', (t) async {
    await t.runAsync(() async {
      expect(
        await downscalePng(Uint8List.fromList([1, 2, 3, 4]), 1000000),
        isNull,
      );
    });
  });
}
