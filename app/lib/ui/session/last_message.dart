/// Phone, keyboard up over answer boxes: the tutor's latest message (its
/// text and pictures, without the questions, which are the boxes below)
/// fills the room above the question and scrolls inside it when long.
library;

import 'package:flutter/material.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/session/message_tile.dart';

/// Pictures stay small so the text beside them shows too (dp).
const double kLastMessageMedia = 120;

/// [message] in a scrollable region.
class LastMessage extends StatelessWidget {
  /// Creates the region for the tutor's [message].
  const new(this.message, {super.key});

  /// The tutor's latest message.
  final Message message;

  @override
  Widget build(BuildContext context) => SelectionArea(
    child: SingleChildScrollView(
      child: MessageTile(
        message: message,
        questionsAsBoxes: true,
        mediaHeight: kLastMessageMedia,
      ),
    ),
  );
}
