/// Read mode: new cards with no model, for when Claude is out (`read_next`
/// / `read_rate`). The front and a flip glyph; a tap on the card flips it to
/// the back, the source quote and link, and two big glyphs pinned at the
/// bottom rate it "again" or "got it", which brings the next card. Nothing
/// left: one inbox glyph. Keys: Space/Enter flip, 1 again, 2 got it.
library;

import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/drill/read_models.dart';
import 'package:tutor/drill/read_session.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/drill_parts.dart';
import 'package:tutor/ui/read_parts.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// The read-mode screen.
class ReadScreen extends StatefulWidget {
  /// Creates the screen; [subject] keeps it to one subject (null: any).
  const new({
    required this.services,
    this.subject,
    this.unavailable,
    this.onFreeChat,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Only this subject's cards (null: every subject in name order).
  final String? subject;

  /// The outage known when the screen opens (its glyph shows at once).
  final Unavailable? unavailable;

  /// Opens the free-model chat; null hides its glyph.
  final VoidCallback? onFreeChat;

  @override
  State<ReadScreen> createState() => _ReadScreenState();
}

class _ReadScreenState extends State<ReadScreen> {
  late final ReadSession _run = ReadSession(
    runner: RequestRunner(widget.services.relay),
    subject: widget.subject,
    unavailable: widget.unavailable,
  );

  @override
  void initState() {
    super.initState();
    unawaited(_run.next());
  }

  @override
  void dispose() {
    _run.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: _run,
    builder: (context, _) => Scaffold(
      appBar: AppBar(actions: [..._outage(), ..._freeChat()]),
      body: CallbackShortcuts(
        bindings: {
          const SingleActivator(LogicalKeyboardKey.space): _run.flip,
          const SingleActivator(LogicalKeyboardKey.enter): _run.flip,
          const SingleActivator(LogicalKeyboardKey.digit1): () =>
              _rate(ReadRating.again),
          const SingleActivator(LogicalKeyboardKey.digit2): () =>
              _rate(ReadRating.gotIt),
        },
        child: Focus(
          autofocus: true,
          child: Column(
            children: [
              Expanded(child: PageList(children: _children())),
              if (_run.prompt != null && _run.flipped && !_failed)
                ReadRateBar(onRate: _busy ? null : _rate),
            ],
          ),
        ),
      ),
    ),
  );

  bool get _busy => _run.stage == ReadStage.loading;

  bool get _failed => _run.stage == ReadStage.failed;

  void _rate(ReadRating rating) => unawaited(_run.rate(rating));

  List<Widget> _outage() {
    final gone = _run.unavailable;
    if (gone == null) return const [];
    return [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
        child: SpokenLabel(
          semanticLabel: gone.banner,
          child: Icon(unavailableIcon(gone.kind), color: AppPalette.danger),
        ),
      ),
    ];
  }

  List<Widget> _freeChat() {
    final open = widget.onFreeChat;
    if (open == null) return const [];
    return [
      GlyphButton(
        icon: Icons.forum_outlined,
        semanticLabel: 'Free chat',
        tooltip: (l) => l.tooltip_ask,
        tint: AppPalette.accent,
        onPressed: open,
      ),
      const SizedBox(width: AppSpacing.sm),
    ];
  }

  List<Widget> _children() {
    final p = _run.prompt;
    return [
      ReadDots(_run.rated),
      const SizedBox(height: AppSpacing.md),
      switch (_run.stage) {
        ReadStage.empty => SizedBox(
          height: 360,
          child: Center(
            child: SpokenLabel(
              semanticLabel:
                  'Nothing left to read. Every card of an open module is '
                  'taught.',
              child: Icon(
                Icons.inbox_outlined,
                size: 120,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ),
        ReadStage.failed => DrillFailed(
          _run.error ?? '',
          _run.retry,
          icon: switch (_run.failure) {
            final f? => failureIcon(f),
            null => null,
          },
        ),
        _ when p == null => const Center(
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.xl),
            child: CircularProgressIndicator(),
          ),
        ),
        _ => ReadCardView(
          p.card,
          flipped: _run.flipped,
          onFlip: _busy ? null : _run.flip,
        ),
      },
    ];
  }
}
