/// Finders for the learning screens' text-free controls: one match per
/// control, by the spoken label it carries (the old wording).
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/progress/terms.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/ui/review_answer.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The control or mark spoken exactly [label] (taps hit its centre).
Finder spoken(String label) => find.byWidgetPredicate(
  (w) => w is SpokenLabel && w.semanticLabel == label,
  description: 'spoken "$label"',
);

/// The control or mark whose spoken label contains [part].
Finder spokenHas(String part) => find.byWidgetPredicate(
  (w) => w is SpokenLabel && w.semanticLabel.contains(part),
  description: 'spoken has "$part"',
);

/// The glyph chip spoken [label]; its `selected` state is on the widget.
Finder chipSpoken(String label) => find.byWidgetPredicate(
  (w) => w is GlyphChip && w.semanticLabel == label,
  description: 'chip "$label"',
);

/// Whether the [chipSpoken] chip is selected.
bool chipSelected(WidgetTester t, String label) =>
    t.widget<GlyphChip>(chipSpoken(label)).selected;

/// The rating button for [g]; its `filled` state is the lead rating.
Finder gradeButton(Grade g) => find.byWidgetPredicate(
  (w) => w is GradeButton && w.grade == g,
  description: 'rating $g',
);

/// Whether the rating button for [g] is the filled (lead) one.
bool gradeFilled(WidgetTester t, Grade g) =>
    t.widget<GradeButton>(gradeButton(g)).filled;

/// The glyph whose spoken label is [label] (a state mark).
Finder iconSpoken(String label) => find.byWidgetPredicate(
  (w) => w is Icon && w.semanticLabel == label,
  description: 'glyph "$label"',
);

/// The widget carrying the spoken hint [hint] (an explanation).
Finder hinted(String hint) => find.byWidgetPredicate(
  (w) => w is Semantics && w.properties.hint == hint,
  description: 'hint "$hint"',
);

/// The glyph button spoken [label] (one per button).
Finder glyph(String label) => find.byWidgetPredicate(
  (w) => w is GlyphButton && w.semanticLabel == label,
  description: 'glyph button "$label"',
);

/// Whether the [glyph] button [label] can be pressed.
bool pressable(WidgetTester t, String label) =>
    t.widget<GlyphButton>(glyph(label).first).onPressed != null;

/// The cue whose spoken label contains [part].
Finder cueHas(String part) => find.byWidgetPredicate(
  (w) => w is CueChip && w.semanticLabel.contains(part),
  description: 'cue has "$part"',
);

/// The text field inside the `FieldLabel` spoken [label].
Finder fieldLabelled(String label) => find
    .descendant(
      of: find.byWidgetPredicate(
        (w) => w is FieldLabel && w.semanticLabel == label,
      ),
      matching: find.byType(TextField),
    )
    .first;

/// Module marks showing [mark].
Finder markOf(ModuleMark mark) => find.byWidgetPredicate(
  (w) => w is ModuleMarkIcon && w.mark == mark,
  description: 'module mark $mark',
);

/// The module titles of the draft editor, in order: each tile's title, not
/// its summary or requires line (also content) nor the number badges.
List<String?> moduleTitles(WidgetTester t) => [
  for (final tile in t.widgetList<ListTile>(find.byType(ListTile)))
    if (tile.title case final ContentText title) title.data,
];
