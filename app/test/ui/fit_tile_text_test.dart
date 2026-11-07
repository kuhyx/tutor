// Live check C13 (2026-11-07): on the Pixel 6a every FitTile whose title
// wrapped to two lines cut its status / count lines in half. FitGrid sized
// rows from `minSquare` x column width, not from what a tile has to show.
// Long titles at Pixel 6a geometry, at 100% and a larger "Display size":
// no text inside a FitTile may be squeezed below its own height or spill
// past the tile.
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/fit_parts.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/ui_scale.dart';
import 'package:tutor/ui/ui_zoom.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _long = 'Hosting WWW: DNS, Apache, PHP, poczta, TLS';

/// The fixture with every subject and car module title long enough to wrap.
FakeRtdb _longTitles() {
  final db = fixtureDb();
  for (final id in ['car', 'garden']) {
    db.root = setAt(db.root, 'tutor/v1/subjects/$id/meta/title', '$_long $id');
  }
  // setAt on a list index would turn the list into a map: replace it whole.
  final mods = getAt(db.root, 'tutor/v1/subjects/car/plan/modules')! as List;
  db.root = setAt(db.root, 'tutor/v1/subjects/car/plan/modules', [
    for (var i = 0; i < mods.length; i++)
      {...(mods[i] as Map), 'title': 'Module $i: $_long'},
  ]);
  return db;
}

Future<void> _pump(WidgetTester t, Widget screen, double zoom) async {
  t.view
    ..physicalSize = const Size(1080, 2400)
    ..devicePixelRatio = 2.625
    ..padding = const FakeViewPadding(top: 132, bottom: 63);
  addTearDown(t.view.reset);
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: buildLightTheme(),
      builder: (context, child) => UiZoomHost(
        zoom: UiZoom(initial: zoom),
        child: UiScale(child: child!),
      ),
      home: screen,
    ),
  );
  await t.pumpAndSettle();
}

/// Every line of every FitTile has its full height and stays in the tile.
void _expectWholeTileText(WidgetTester t) {
  final tiles = find.byType(FitTile).hitTestable();
  expect(tiles, findsWidgets);
  for (final tile in tiles.evaluate()) {
    final box = tile.renderObject! as RenderBox;
    final rect = box.localToGlobal(Offset.zero) & box.size;
    final title = (tile.widget as FitTile).title;
    void visit(RenderObject o) {
      if (o is RenderParagraph) {
        final need = o.getMinIntrinsicHeight(o.size.width);
        final top = o.localToGlobal(Offset.zero).dy;
        final text = o.text.toPlainText();
        expect(
          o.size.height,
          greaterThanOrEqualTo(need - 0.5),
          reason: '"$text" squeezed in tile "$title"',
        );
        expect(
          top + need,
          lessThanOrEqualTo(rect.bottom + 0.5),
          reason: '"$text" spills past tile "$title"',
        );
      }
      o.visitChildren(visit);
    }

    box.visitChildren(visit);
  }
}

void main() {
  // Home only at 100%: its AppBar (home_screen.dart, not part of this
  // change) already overflows on a Pixel 6a from 110% up.
  testWidgets('Home tiles show every line', (t) async {
    final s = await fixtureServices(_longTitles(), FakeStream());
    await _pump(t, HomeScreen(services: s, onSignedOut: () {}), 1);
    _expectWholeTileText(t);
  });

  for (final zoom in [1.0, 1.3]) {
    testWidgets('Plan tiles show every line at zoom $zoom', (t) async {
      final s = await fixtureServices(_longTitles(), FakeStream());
      await _pump(t, PlanScreen(services: s, subject: 'car'), zoom);
      _expectWholeTileText(t);
    });

    testWidgets('Progress tiles show every line at zoom $zoom', (t) async {
      final s = await fixtureServices(_longTitles(), FakeStream());
      await _pump(t, ProgressScreen(services: s), zoom);
      _expectWholeTileText(t);
    });
  }
}
