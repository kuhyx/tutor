/// Typed builders for every request kind's `body` (DOCS-contract §4).
///
/// Sizes are checked here so an oversize text fails in the UI, not as a
/// `bad_request` after a round trip.
library;

import 'package:tutor/model/json.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/model/request.dart';

/// A kind plus its body, ready for `RequestRelay.send`.
class RequestBody {
  const new _(this.kind, this.body);

  /// `subject_new`: "I want to learn how a car works" (<= 2000 chars).
  factory subjectNew(String text) =>
      RequestBody._(RequestKind.subjectNew, {'text': _cap(text, 2000)});

  /// `plan_revise`: redraft from a comment.
  factory planRevise(String subject, int planRev, String comment) =>
      RequestBody._(RequestKind.planRevise, {
        'subject': subject,
        'plan_rev': planRev,
        'comment': comment,
      });

  /// `plan_edit`: the full module list.
  factory planEdit(String subject, int planRev, List<Module> modules) =>
      RequestBody._(RequestKind.planEdit, {
        'subject': subject,
        'plan_rev': planRev,
        'modules': [for (final m in modules) m.toJson()],
      });

  /// `plan_approve`.
  factory planApprove(String subject, int planRev) => RequestBody._(
    RequestKind.planApprove,
    {'subject': subject, 'plan_rev': planRev},
  );

  /// `subject_finish`: [goDeeper] true = `go_deeper`, else `review_only`.
  factory subjectFinish(String subject, {required bool goDeeper}) =>
      RequestBody._(RequestKind.subjectFinish, {
        'subject': subject,
        'choice': goDeeper ? 'go_deeper' : 'review_only',
      });

  /// `card_edit`: a null [card] adds a new card.
  factory cardEdit({
    required String subject,
    required String module,
    required String front,
    required String back,
    required String source,
    required String excerpt,
    String? card,
    List<String> requires = const [],
  }) => RequestBody._(RequestKind.cardEdit, {
    'subject': subject,
    'card': card,
    'module': module,
    'front': front,
    'back': back,
    'source': source,
    'excerpt': excerpt,
    'requires': requires,
  });

  /// `session_start`: null [card] = next open card; [resume] (Continue)
  /// first makes the subject's open session live (DOCS-contract §4).
  factory sessionStart({String? subject, String? card, bool resume = false}) =>
      RequestBody._(RequestKind.sessionStart, {
        'subject': subject,
        'card': card,
        if (resume) 'resume': true,
      });

  /// `session_resume`.
  factory sessionResume(String session) =>
      RequestBody._(RequestKind.sessionResume, {'session': session});

  /// `message` (<= 8000 chars).
  factory message(String session, String text) => RequestBody._(
    RequestKind.message,
    {'session': session, 'text': _cap(text, 8000)},
  );

  /// `next`.
  factory next(String session) =>
      RequestBody._(RequestKind.next, {'session': session});

  /// `stop`.
  factory stop(String session) =>
      RequestBody._(RequestKind.stop, {'session': session});

  /// `card_done`: manual override.
  factory cardDone(String subject, String card, {bool done = true}) =>
      RequestBody._(RequestKind.cardDone, {
        'subject': subject,
        'card': card,
        'done': done,
      });

  /// `drill_next`: the next question; null [subject] = any.
  factory drillNext({String? subject}) =>
      RequestBody._(RequestKind.drillNext, {'subject': subject});

  /// `drill_answer`: option [choice] of question [promptId].
  factory drillAnswer(String promptId, int choice) => RequestBody._(
    RequestKind.drillAnswer,
    {'prompt_id': promptId, 'choice': choice},
  );

  /// `anki_status`.
  factory ankiStatus() => const RequestBody._(RequestKind.ankiStatus, {});

  /// The kinds whose body takes `device` (DOCS-contract §4).
  static const Set<RequestKind> deviceKinds = {
    RequestKind.message,
    RequestKind.sessionStart,
    RequestKind.next,
  };

  /// This request tagged with [device] (`phone` or `desktop`, so the tutor
  /// knows how much the learner can type); other kinds come back unchanged.
  RequestBody withDevice(String device) => deviceKinds.contains(kind)
      ? RequestBody._(kind, {...body, 'device': device})
      : this;

  /// Kind.
  final RequestKind kind;

  /// Body; null values are kept (RTDB drops them; the worker reads absent as
  /// null).
  final Json body;
}

String _cap(String text, int max) {
  if (text.length > max) {
    throw ArgumentError.value(text.length, 'text', 'longer than $max chars');
  }
  return text;
}
