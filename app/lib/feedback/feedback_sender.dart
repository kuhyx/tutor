/// Report a problem (DOCS-contract §6 `feedback/{fid}`): for the developer,
/// never the tutor. The worker drains the node into `feedback.jsonl`.
/// Offline-first: a report is kept on this install until it is written.
library;

import 'package:tutor/model/ids.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/sync/put_outbox.dart';
import 'package:tutor/util/ulid.dart';

/// Writes reports.
class FeedbackSender {
  /// Creates the sender for device [dev].
  new({
    required this.outbox,
    required this.dev,
    required this.ulid,
    int Function()? now,
  }) : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  /// Where a report waits until the database answers.
  final PutOutbox outbox;

  /// This install's device id.
  final String dev;

  /// fid source.
  final UlidGenerator ulid;
  final int Function() _now;

  /// Saves one report on this install (pushed by [outbox], offline too);
  /// returns its fid. Throws [ArgumentError] for empty or oversize text.
  Future<String> send({
    required FeedbackCategory category,
    required String text,
    required String route,
    String? session,
    String? msg,
  }) async {
    final body = text.trim();
    if (body.isEmpty || body.length > Feedback.maxText) {
      throw ArgumentError.value(
        body.length,
        'text',
        'must be 1-${Feedback.maxText} characters',
      );
    }
    final fid = ulid.next();
    final report = Feedback(
      category: category,
      text: body,
      dev: dev,
      at: _now(),
      route: route,
      session: session,
      msg: msg,
    );
    await outbox.put(Paths.feedback(fid), report.toJson());
    return fid;
  }
}
