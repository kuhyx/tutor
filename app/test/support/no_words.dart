/// The "no words" guard (textgate): nothing painted holds a word (two or
/// more letters) unless it is content ([ContentText] / [ContentScope]), a
/// text field's value, or an already-approved ledger string
/// (`text-approvals.json`). Tooltips and field decorations count as painted.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/text_free_theme.dart';

final _word = RegExp(r'\p{L}{2,}', unicode: true);

/// The approved ledger strings as patterns (`{n}` = anything; each plural
/// branch on its own).
final List<RegExp> approvedText = _loadApproved();

List<RegExp> _loadApproved() {
  final approvals = jsonDecode(
    File('../text-approvals.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final keys = (approvals['approved'] as Map<String, dynamic>).keys
      .where((k) => k.startsWith('app/lib/l10n/app_en.arb::'))
      .map((k) => k.split('::').last)
      .toSet();
  final arb = jsonDecode(
    File('lib/l10n/app_en.arb').readAsStringSync(),
  ) as Map<String, dynamic>;
  final out = <RegExp>[];
  for (final k in keys) {
    final v = arb[k];
    if (v is String) out.addAll(_patterns(v));
  }
  return out;
}

/// `{n, plural, =1{1 day left} other{{n} days left}}` -> its branches.
List<RegExp> _patterns(String value) {
  final plural = RegExp(r'^\{\w+, plural,(.*)\}$').firstMatch(value);
  final templates = plural == null
      ? [value]
      : [
          for (final m in RegExp(
            r'(?:=\d+|other|one|few|many|zero|two)\{((?:[^{}]|\{\w+\})*)\}',
          ).allMatches(plural.group(1)!))
            m.group(1)!,
        ];
  return [
    for (final t in templates)
      RegExp('^${t.split(RegExp(r'\{\w+\}')).map(RegExp.escape).join('.+')}\$'),
  ];
}

bool _approved(String text) => approvedText.any((p) => p.hasMatch(text.trim()));

bool _isContent(Element e) {
  var found = false;
  e.visitAncestorElements((a) {
    final w = a.widget;
    found = w is ContentText || w is ContentScope || w is EditableText;
    return !found;
  });
  return found;
}

/// Every painted word on screen that is not allowed, tagged by where.
List<String> wordsOnScreen(WidgetTester t) {
  final bad = <String>[];
  final texts = find.byType(RichText).evaluate().toList();
  // An empty walk proves nothing: something must be on screen (a text-free
  // screen may paint no RichText at all, only glyphs and spinners).
  expect(find.byType(MaterialApp), findsOneWidget, reason: 'nothing pumped');
  for (final e in texts) {
    final text = (e.widget as RichText).text.toPlainText();
    if (!_word.hasMatch(text) || _approved(text) || _isContent(e)) continue;
    bad.add('text: ${text.replaceAll('\n', ' ')}');
  }
  for (final e in find.byType(Tooltip).evaluate()) {
    final w = e.widget as Tooltip;
    final theme = TooltipTheme.of(e);
    final mode = w.triggerMode ?? theme.triggerMode;
    final wait = w.waitDuration ?? theme.waitDuration ?? Duration.zero;
    // Spoken only: never shown on long-press or hover.
    if (mode == TooltipTriggerMode.manual && wait >= spokenOnlyWait) continue;
    final msg = w.message ?? w.richMessage?.toPlainText() ?? '';
    if (_word.hasMatch(msg) && !_approved(msg)) bad.add('tooltip: $msg');
  }
  for (final e in find.byType(InputDecorator).evaluate()) {
    final d = (e.widget as InputDecorator).decoration;
    for (final s in [
      d.hintText,
      d.labelText,
      d.helperText,
      d.errorText,
      d.prefixText,
      d.suffixText,
      d.counterText,
    ]) {
      if (s != null && _word.hasMatch(s) && !_approved(s)) {
        bad.add('field: $s');
      }
    }
  }
  return bad;
}

/// Fails listing every painted word not allowed on screen ([state] names
/// the screen state for the report).
void expectNoWords(WidgetTester t, String state) {
  final bad = wordsOnScreen(t);
  expect(bad, isEmpty, reason: '$state paints words:\n${bad.join('\n')}');
}
