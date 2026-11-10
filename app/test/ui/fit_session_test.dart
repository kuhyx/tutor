// build-mobile-app R7: the session (chat, card, composer) fits one Pixel 6a
// screen; a long chat pages, and with the keyboard up the box typed in and
// Send stay visible.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/util/device.dart';
import 'package:tutor/widgets/spoken_label.dart';

import '../support/composer.dart';
import '../support/fit.dart';

void main() {
  tearDown(() => debugPhone = null);

  for (final questions in [true, false]) {
    fitTest('Session, questions: $questions', (t, scale) async {
      await openComposer(t, phone: true, questions: questions);
      pixelView(t, scale: scale);
      await t.pumpAndSettle();
      expectFits(t, state: 'chat');
      final box = find.byType(TextField).hitTestable();
      expect(box, findsWidgets);
      await t.tap(box.first);
      pixelView(t, scale: scale, keyboard: fitKeyboard);
      await t.pumpAndSettle();
      expectFits(t, state: 'keyboard');
      final send = find.byWidgetPredicate(
        (w) =>
            w is GlyphButton &&
            (w.semanticLabel == 'Send' || w.semanticLabel == 'Next'),
      );
      expectReachable(t, send, state: 'keyboard');
    });
  }

  for (final flag in ['card_done', 'stopped']) {
    fitTest('Session, $flag', (t, scale) async {
      final (db, stream) = await openComposer(t, phone: true);
      final meta = getAt(db.root, '$composeBase/meta')! as Map<String, Object?>;
      stream.emit('$composeBase/meta', RtdbPut('/', {...meta, flag: true}));
      pixelView(t, scale: scale);
      await t.pumpAndSettle();
      expectFits(t, state: flag);
    });
  }
}
