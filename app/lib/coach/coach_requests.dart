/// Request bodies of the problem coach kinds (`lc_*`). Fields follow
/// tutor/relay/lc_protocol.py; DOCS-contract-coach.md wins once pushed.
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';

/// Longest message or code text the worker takes.
const coachMaxText = 8000;

/// The messages the coach reads as commands, not as chat.
const coachHint = 'hint';

/// The typed override that shows the solution.
const coachReveal = 'reveal';

/// `lc_list`.
RequestBody lcList() => const RequestBody.raw(RequestKind.lcList, {});

/// `lc_open`: a problem (slug or URL), a pasted `statement` with a `title`,
/// or an `lcId` to resume; `lang` is the language coached in.
RequestBody lcOpen({
  String? problem,
  String? statement,
  String? title,
  String? lang,
  String? lcId,
}) {
  if (problem == null && statement == null && lcId == null) {
    throw ArgumentError('a problem, a statement or a session');
  }
  return RequestBody.raw(
    RequestKind.lcOpen,
    compact({
      'problem': problem,
      'statement': statement,
      'title': title,
      'lang': lang,
      'lc_id': lcId,
    }),
  );
}

/// `lc_turn`: `text` to the coach; `solved` claims the problem is solved
/// (the text is the explanation).
RequestBody lcTurn(String lcId, String text, {bool solved = false}) =>
    RequestBody.raw(RequestKind.lcTurn, {
      'lc_id': lcId,
      'text': text,
      'intent': solved ? 'solved' : 'chat',
    });

/// `lc_run`: `code` in `lang` against the statement examples.
RequestBody lcRun(String lcId, {required String lang, required String code}) =>
    RequestBody.raw(RequestKind.lcRun, {
      'lc_id': lcId,
      'lang': lang,
      'code': code,
    });

/// A toolbox entry the post-mortem proposes.
typedef ToolboxEntry = ({
  String name,
  List<String> aliases,
  List<String> properties,
});

/// `lc_cards`: no entries asks for the cards; else confirms them (max 5).
RequestBody lcCards(String lcId, List<ToolboxEntry> entries) => RequestBody.raw(
  RequestKind.lcCards,
  compact({
    'lc_id': lcId,
    'confirm': entries.isEmpty
        ? null
        : [
            for (final e in entries)
              compact({
                'name': e.name,
                'aliases': e.aliases.isEmpty ? null : e.aliases,
                'properties': e.properties,
              }),
          ],
  }),
);
