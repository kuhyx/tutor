/// What a tap on an interview milestone sends (DOCS-contract-focus.md,
/// "Interview projects"): the evidence kinds, the trip and the weekend
/// answer, each one request through a [RequestRunner].
library;

import 'dart:typed_data';

import 'package:tutor/focus/evidence_upload.dart';
import 'package:tutor/model/interview_body.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';

String _day(DateTime d) => localMinute(d).substring(0, 10);

/// The requests of one interview project; every call ends in the final
/// [RelayStatus] (never throws: an upload that fails is a status too).
class InterviewActions {
  /// Creates the actions for project [projectId].
  const new({
    required this.runner,
    required this.uploader,
    required this.projectId,
  });

  /// One request at a time.
  final RequestRunner runner;

  /// Chunked image upload.
  final EvidenceUploader uploader;

  /// The interview project's id.
  final String projectId;

  Future<RelayStatus> _evidence(
    String milestone,
    String kind, {
    Object? value,
  }) => runner.run(
    focusEvidence(
      id: projectId,
      milestone: milestone,
      kind: kind,
      value: value,
    ),
  );

  /// `rules`: the screenshot [picked], chunked, then `file` evidence.
  Future<RelayStatus> file(String milestone, Uint8List picked) async {
    final UploadRef ref;
    try {
      ref = await uploader.upload(picked);
    } on UploadRefused catch (e) {
      return RelayFailed(code: 'upload_refused', text: e.reason);
    } on Object catch (e) {
      // Transport or token failure: nothing arrived; the screen shows it.
      return RelayNotSent(e);
    }
    return await runner.run(
      focusEvidence(
        id: projectId,
        milestone: milestone,
        kind: 'file',
        upload: ref,
      ),
    );
  }

  /// `phone:*`: the one-time "offline ok" tap.
  Future<RelayStatus> tap(String milestone) => _evidence(milestone, 'tap');

  /// `mock`: the score.
  Future<RelayStatus> score(String milestone, double value) =>
      _evidence(milestone, 'score', value: value);

  /// `slot`: the slot datetime.
  Future<RelayStatus> slot(DateTime at) =>
      _evidence('slot', 'slot', value: localMinute(at));

  /// `slot`: "no other duties".
  Future<RelayStatus> slotConfirm() =>
      _evidence('slot', 'slot_confirm', value: true);

  /// `focus_trip`: a trip over inclusive days [start]..[end].
  Future<RelayStatus> trip(DateTime start, DateTime end) =>
      runner.run(focusTrip(projectId, _day(start), _day(end)));

  /// `focus_weekend` with `trip:false` for [saturday].
  Future<RelayStatus> noTrip(String saturday) =>
      runner.run(focusWeekend(projectId, saturday, trip: false));
}

/// The app's own sentence for a failed [status] (never the worker's words),
/// null for one that did not fail.
String? failureText(RelayStatus status) => switch (status) {
  RelayFailed(:final text) => text,
  RelayNotSent(:final text) => text,
  _ => null,
};
