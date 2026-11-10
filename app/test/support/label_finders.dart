/// Finders for the text-free UI: controls by their spoken label (the old
/// wording), fields by their spoken label, cues by kind. No
/// `ensureSemantics()` needed: they read the widgets' own fields.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

String? _spoken(Widget w) => switch (w) {
  GlyphButton(:final semanticLabel) => semanticLabel,
  SpokenLabel(:final semanticLabel) => semanticLabel,
  CueChip(:final semanticLabel) => semanticLabel,
  FieldLabel(:final semanticLabel) => semanticLabel,
  Icon(:final semanticLabel) => semanticLabel,
  // Not `Semantics`: every widget above builds one, so matching it would
  // find each label twice.
  _ => null,
};

/// Every widget whose spoken label is [label] (or starts with it when
/// [prefix]).
Finder bySpoken(String label, {bool prefix = false}) =>
    find.byWidgetPredicate((w) {
      final s = _spoken(w);
      return s != null && (prefix ? s.startsWith(label) : s == label);
    }, description: 'spoken "$label"${prefix ? '...' : ''}');

/// Keeps the matches with no other match above them. Unlike `.first` it
/// never throws on an empty parent, so `findsNothing` works.
class _Outermost extends ChainedFinder {
  new(super.parent);

  @override
  String get description => describeMatch(Plurality.many);

  @override
  String describeMatch(Plurality plurality) =>
      '${parent.describeMatch(plurality)} (outermost only)';

  @override
  Iterable<Element> filter(Iterable<Element> parentCandidates) {
    final all = parentCandidates.toSet();
    return all.where((e) {
      var covered = false;
      e.visitAncestorElements((a) {
        covered = all.contains(a);
        return !covered;
      });
      return !covered;
    }).toList();
  }
}

/// The control labelled [label]: the outermost match (tap target).
Finder controlByLabel(String label, {bool prefix = false}) =>
    _Outermost(bySpoken(label, prefix: prefix));

/// The text field spoken as [label].
Finder fieldByLabel(String label) => find.descendant(
  of: find.byWidgetPredicate(
    (w) => w is FieldLabel && w.semanticLabel == label,
  ),
  matching: find.byType(TextField),
);

/// Status cues of [kind].
Finder cueOfKind(CueKind kind) =>
    find.byWidgetPredicate((w) => w is CueChip && w.kind == kind);

/// The cue spoken as [label] (or starting with it when [prefix]).
Finder cueLabelled(String label, {bool prefix = false}) =>
    find.byWidgetPredicate(
      (w) =>
          w is CueChip &&
          (prefix
              ? w.semanticLabel.startsWith(label)
              : w.semanticLabel == label),
    );

/// The glyph buttons spoken as [label] (one per button, not per layer).
Finder glyphsLabelled(String label) => find.byWidgetPredicate(
  (w) => w is GlyphButton && w.semanticLabel == label,
  description: 'glyph button "$label"',
);

/// The `onPressed` of the glyph button spoken as [label].
VoidCallback? pressOf(WidgetTester t, String label) =>
    t.widget<GlyphButton>(glyphsLabelled(label).first).onPressed;

/// Cues whose spoken label contains [part].
Finder cueContaining(String part) => find.byWidgetPredicate(
  (w) => w is CueChip && w.semanticLabel.contains(part),
  description: 'cue containing "$part"',
);
