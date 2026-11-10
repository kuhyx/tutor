/// Fakes for the interview UI tests: scripted prompts and a picked image.
library;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:tutor/ui/interview_prompts.dart';

/// Prompts that answer from fields and count how often each was asked.
class FakePrompts implements InterviewPrompts {
  /// Answer of [askTrip].
  bool? trip;

  /// Answer of [pickRange].
  ({DateTime start, DateTime end})? range;

  /// Answer of [pickDateTime].
  DateTime? dateTime;

  /// Answer of [askScore].
  double? score;

  /// Answer of [confirm].
  bool? confirmed;

  /// Calls per prompt name.
  final Map<String, int> asked = {};

  /// Bounds the last range / date-time prompt received.
  ({DateTime first, DateTime last})? bounds;

  void _ask(String name) => asked[name] = (asked[name] ?? 0) + 1;

  @override
  Future<bool?> askTrip(BuildContext context) async {
    _ask('trip');
    return trip;
  }

  @override
  Future<({DateTime start, DateTime end})?> pickRange(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  }) async {
    _ask('range');
    bounds = (first: first, last: last);
    return range;
  }

  @override
  Future<DateTime?> pickDateTime(
    BuildContext context, {
    required DateTime first,
    required DateTime last,
  }) async {
    _ask('dateTime');
    bounds = (first: first, last: last);
    return dateTime;
  }

  @override
  Future<double?> askScore(BuildContext context) async {
    _ask('score');
    return score;
  }

  @override
  Future<bool?> confirm(BuildContext context) async {
    _ask('confirm');
    return confirmed;
  }
}

/// A few bytes that sniff as a PNG.
final Uint8List fakePng = Uint8List.fromList([
  0x89,
  0x50,
  0x4e,
  0x47,
  0x0d,
  0x0a,
  0x1a,
  0x0a,
  ...List.generate(300, (i) => i & 0xff),
]);
