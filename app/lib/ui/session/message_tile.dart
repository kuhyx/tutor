/// One chat message, as `static/app.js` renderMessage draws it: tutor
/// (markdown, pictures, diagrams, check result, read-only questions, card
/// edit notices, Card done; at the top right ⚑ Report on live messages, the
/// thinking head that opens the trace under the text, and the low-effort
/// face), learner, or a card divider.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/ui/code_glyphs.dart';
import 'package:tutor/ui/session/md_text.dart';
import 'package:tutor/ui/session/media.dart';
import 'package:tutor/ui/session/message_parts.dart';
import 'package:tutor/ui/session/thinking_panel.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// A message bubble.
class MessageTile extends StatefulWidget {
  /// Creates the tile. [onReport] null = read-only (past session);
  /// [questionsAsBoxes] = its questions are live answer boxes below.
  const new({
    required this.message,
    this.onReport,
    this.questionsAsBoxes = false,
    this.pending = false,
    this.mediaHeight,
    super.key,
  });

  /// Caps pictures and diagrams (dp); null = their own caps.
  final double? mediaHeight;

  /// The message.
  final Message message;

  /// Reports a problem with this message.
  final VoidCallback? onReport;

  /// Leave the questions out (they are in the composer).
  final bool questionsAsBoxes;

  /// A learner text not yet answered (DOCS-contract §6 `busy.text`).
  final bool pending;

  @override
  State<MessageTile> createState() => _MessageTileState();
}

class _MessageTileState extends State<MessageTile> {
  bool _thinking = debugThinkingOpen; // the trace shows under the text

  // Top right of a tutor bubble: flag, thinking head, low-effort face.
  Widget _glyphs(Message m) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      if (widget.onReport case final report?)
        GlyphButton(
          icon: Icons.flag_outlined,
          semanticLabel: '⚑ Report',
          onPressed: report,
        ),
      if (m.trace.isNotEmpty)
        ThinkingGlyph(
          steps: m.trace,
          open: _thinking,
          onToggle: () => setState(() => _thinking = !_thinking),
        ),
      if (m.lowEffort)
        const Padding(
          padding: EdgeInsets.all(AppSpacing.xs),
          child: SpokenLabel(
            semanticLabel: 'Low effort',
            child: Icon(
              Icons.sentiment_dissatisfied_outlined,
              size: AppTextSize.body,
              color: AppPalette.warning,
            ),
          ),
        ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final m = widget.message;
    final pending = widget.pending;
    final mediaHeight = widget.mediaHeight;
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    if (m.role == 'card') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        child: Row(
          children: [
            const Expanded(child: Divider()),
            Flexible(
              flex: 4,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SpokenLabel(
                      // Longer than the Next card button's own label.
                      semanticLabel: 'Next card: ${m.text}',
                      child: const Icon(Icons.skip_next),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Flexible(
                      child: ContentText(
                        m.text,
                        style: text.labelLarge,
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const Expanded(child: Divider()),
          ],
        ),
      );
    }
    final tutor = m.role == 'tutor';
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (pending)
          const SpokenLabel(
            semanticLabel: 'You (sending...)',
            liveRegion: true,
            child: Icon(Icons.schedule_send_outlined, size: 16),
          ),
        MarkdownText(m.text),
        if (tutor && _thinking && m.trace.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: ThinkingBody(m.trace),
          ),
        for (final img in m.images)
          CommonsFigure(img, maxHeight: mediaHeight ?? 360),
        for (final d in m.diagrams)
          DiagramView(d, maxHeight: mediaHeight ?? 320),
        if (m.checkResult case final r?) CheckResultBanner(r),
        if (!widget.questionsAsBoxes)
          for (final a in askedOf(m)) AskedQuestion(a),
        if (m.masteredNew.isNotEmpty)
          Row(
            children: [
              const SpokenLabel(
                semanticLabel: 'Known',
                child: Icon(Icons.checklist, size: 16),
              ),
              const SizedBox(width: AppSpacing.xs),
              Expanded(
                child: ContentText(
                  m.masteredNew.join(', '),
                  style: text.bodySmall,
                ),
              ),
            ],
          ),
        // Card-edit notices: worker sentences, spoken only.
        for (final (i, n) in m.notices.indexed)
          Align(
            alignment: Alignment.centerLeft,
            child: CueChip(
              kind: CueKind.ok,
              icon: noticeIcon(m.noticeKind(i)),
              semanticLabel: n,
            ),
          ),
        if (m.cardDone)
          const MessageBanner(
            icon: Icons.check_circle,
            spoken: 'Card done ✓',
            ok: true,
          ),
      ],
    );
    return Align(
      alignment: tutor ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: AppSpacing.md),
        padding: const EdgeInsets.all(AppSpacing.md),
        constraints: const BoxConstraints(maxWidth: 680),
        decoration: BoxDecoration(
          color: tutor
              ? scheme.surfaceContainerLow
              : scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: pending ? Border.all(color: scheme.outline) : null,
        ),
        child: tutor
            ? Row(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // The "Tutor" tag is spoken only (no glyph).
                  Flexible(
                    child: Semantics(
                      container: true,
                      label: m.lowEffort
                          ? 'Tutor (last reply was low effort)'
                          : 'Tutor',
                      child: body,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  _glyphs(m),
                ],
              )
            : body,
      ),
    );
  }
}
