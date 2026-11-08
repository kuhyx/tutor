/// One module in the card editor.
library;

import 'package:flutter/material.dart';

/// A module's rows. Phone ([compact]): flat rows (header, Add card, then
/// the cards) so pages break between cards and Add card is two taps away
/// (build-mobile-app R7). Elsewhere: one ExpansionTile, Add card last.
List<Widget> moduleRows({
  required bool compact,
  required bool open,
  required VoidCallback onToggle,
  required Widget title,
  required Widget subtitle,
  required Widget addCard,
  required List<Widget> cards,
}) => compact
    ? [
        ListTile(
          title: title,
          subtitle: subtitle,
          onTap: onToggle,
          trailing: Icon(open ? Icons.expand_less : Icons.expand_more),
        ),
        if (open) ...[addCard, ...cards],
      ]
    : [
        ExpansionTile(
          title: title,
          subtitle: subtitle,
          children: [...cards, addCard],
        ),
      ];
