import 'package:tutor/model/json.dart';

/// A focus project; `minutes` is today's count (active project only).
typedef FocusProject = ({
  String id,
  String name,
  String start,
  String end,
  int daysLeft,
  List<String> replaces,
  int dailyMinutes,
  int unlockMinutes,
  List<String> subjects,
  List<String> sitePatterns,
  String workUrl,
  int minutes,
});

/// A gate from the earner registry; `replaceable: false` is always kept.
typedef FocusGate = ({String id, String label, bool replaceable});

/// A tutor subject.
typedef FocusSubject = ({String id, String title});

/// The whole `focus_status` result.
typedef FocusStatus = ({
  String day,
  FocusProject? active,
  List<FocusProject> projects,
  List<FocusGate> gates,
  List<FocusSubject> subjects,
});

FocusProject _project(Json j) => (
  id: str(j, 'id'),
  name: str(j, 'name'),
  start: str(j, 'start'),
  end: str(j, 'end'),
  daysLeft: intOr(j, 'days_left') ?? 0,
  replaces: strings(j, 'replaces'),
  dailyMinutes: integer(j, 'daily_minutes'),
  unlockMinutes: intOr(j, 'unlock_minutes') ?? 0,
  subjects: strings(j, 'subjects'),
  sitePatterns: strings(j, 'site_patterns'),
  workUrl: strOr(j, 'work_url') ?? '',
  minutes: intOr(j, 'minutes') ?? 0,
);

/// Parses the result `data` of `focus_status`.
FocusStatus parseStatus(Json j) {
  final active = objOr(j, 'active');
  return (
    day: str(j, 'day'),
    active: active == null ? null : _project(active),
    projects: listOf(j, 'projects', (v) => _project(asJson(v))),
    gates: listOf(j, 'gates', (v) {
      final g = asJson(v);
      return (
        id: str(g, 'id'),
        label: str(g, 'label'),
        replaceable: flag(g, 'replaceable'),
      );
    }),
    subjects: listOf(j, 'subjects', (v) {
      final s = asJson(v);
      return (id: str(s, 'id'), title: str(s, 'title'));
    }),
  );
}

/// Labels of the gates the active project turns off, or of those it keeps.
List<String> gateLabels(FocusStatus s, {required bool off}) => [
  for (final g in s.gates)
    if ((s.active?.replaces.contains(g.id) ?? false) == off) g.label,
];

/// Whether [text] may be a project's work URL: empty, or http(s) with a host.
bool isWorkUrl(String text) {
  final uri = Uri.tryParse(text.trim());
  if (text.trim().isEmpty) return true;
  return uri != null &&
      (uri.scheme == 'http' || uri.scheme == 'https') &&
      uri.host.isNotEmpty &&
      !text.trim().contains(' ');
}
