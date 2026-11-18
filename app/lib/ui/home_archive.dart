/// Archiving a subject from Home (DOCS-relay-kinds.md "Archived subjects"):
/// one tap hides it at once and sends `subject_archive`; an undo glyph stays
/// for [undoArchiveFor] and sends `subject_unarchive`. No words: glyphs with
/// spoken labels only.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/learn_bits.dart';
import 'package:tutor/widgets/cue_chip.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// How long the undo glyph stays on screen.
const undoArchiveFor = Duration(seconds: 8);

/// `subject_archive` for [subject].
RequestBody archiveBody(String subject) =>
    RequestBody.raw(RequestKind.subjectArchive, {'subject': subject});

/// `subject_unarchive` for [subject].
RequestBody unarchiveBody(String subject) =>
    RequestBody.raw(RequestKind.subjectUnarchive, {'subject': subject});

/// Sends archive / undo and hides archived subjects until Home reloads
/// without them.
class SubjectArchiver {
  /// Creates the archiver; [reload] refreshes Home.
  new(this.relay, this.reload);

  /// Where requests go.
  final RequestRelay relay;

  /// Reloads Home (the catalog no longer lists an archived subject).
  final Future<void> Function() reload;

  /// Subject ids Home leaves out while their archive is in flight.
  final ValueNotifier<Set<String>> hidden = ValueNotifier(const {});

  /// Hides [subject], offers undo, and archives it on the PC. A refusal
  /// shows it again with an error cue.
  void archive(BuildContext context, String subject, String title) {
    final messenger = ScaffoldMessenger.maybeOf(context);
    hidden.value = {...hidden.value, subject};
    messenger
      ?..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          duration: undoArchiveFor,
          content: Align(
            alignment: Alignment.centerLeft,
            child: GlyphButton(
              icon: Icons.undo,
              semanticLabel: 'Undo archive $title',
              filled: true,
              onPressed: () {
                messenger.hideCurrentSnackBar();
                unawaited(_send(context, unarchiveBody(subject), subject));
              },
            ),
          ),
        ),
      );
    unawaited(_send(context, archiveBody(subject), subject));
  }

  Future<void> _send(
    BuildContext context,
    RequestBody body,
    String subject,
  ) async {
    final runner = RequestRunner(relay);
    final status = await runner.run(body);
    unawaited(runner.dispose()); // its stream closes on its own time
    final undo = body.kind == RequestKind.subjectUnarchive;
    if (status is RelayFailed || status is RelayNotSent) {
      if (!undo) _show(subject);
      if (context.mounted) {
        showCueSnack(context, CueKind.error, 'Not saved: ${body.kind.wire}');
      }
      return;
    }
    if (undo) _show(subject);
    await reload();
    if (!undo) _show(subject); // the reloaded catalog no longer has it
  }

  void _show(String subject) =>
      hidden.value = {...hidden.value}..remove(subject);

  /// Releases the notifier.
  void dispose() => hidden.dispose();
}
