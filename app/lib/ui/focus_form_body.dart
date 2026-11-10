import 'package:tutor/model/request_body.dart';

/// The `focus_create` (no [id]) or `focus_update` ([id]) body of the project
/// form: both carry the same fields.
RequestBody focusFormBody({
  required String? id,
  required String name,
  required String start,
  required String end,
  required List<String> replaces,
  required int dailyMinutes,
  required int unlockMinutes,
  required List<String> subjects,
  required List<String> sitePatterns,
  required String workUrl,
}) => id == null
    ? RequestBody.focusCreate(
        name: name,
        start: start,
        end: end,
        replaces: replaces,
        dailyMinutes: dailyMinutes,
        unlockMinutes: unlockMinutes,
        subjects: subjects,
        sitePatterns: sitePatterns,
        workUrl: workUrl,
      )
    : RequestBody.focusUpdate(
        id: id,
        name: name,
        start: start,
        end: end,
        replaces: replaces,
        dailyMinutes: dailyMinutes,
        unlockMinutes: unlockMinutes,
        subjects: subjects,
        sitePatterns: sitePatterns,
        workUrl: workUrl,
      );
