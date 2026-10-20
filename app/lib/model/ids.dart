/// Id formats from DOCS-contract §3, and the `/tutor/v1` paths built from
/// them. A path segment is only ever built from an id that passed these.
library;

/// Characters a slug word may hold: ASCII lowercase, digits and the nine
/// precomposed Polish letters. Combining marks are absent, so NFD spellings
/// never match (one word, one id).
const slugChars = 'a-z0-9ąćęłńóśźż';
final _slug = RegExp('^[$slugChars]+(-[$slugChars]+)*\$');
final _ulid = RegExp(r'^[0-9A-HJKMNP-TV-Z]{26}$');
final _sid = RegExp(r'^\d{8}-\d{6}-[0-9a-z]{4}$');
final _msg = RegExp(r'^m\d{4,}$');
final _receipt = RegExp(r'^r\d{4,}$');

/// Subject / module / card id: words of [slugChars] joined by single
/// hyphens, at most 48 characters (not bytes).
bool isSlug(String s) => s.length <= 48 && _slug.hasMatch(s);

/// `rid` / `eid` / `fid`: 26-char Crockford ULID.
bool isUlid(String s) => _ulid.hasMatch(s);

/// Session id `YYYYMMDD-HHMMSS-xxxx`.
bool isSessionId(String s) => _sid.hasMatch(s);

/// Message key `m0007`.
bool isMessageKey(String s) => _msg.hasMatch(s);

/// Receipt key `r0003`.
bool isReceiptKey(String s) => _receipt.hasMatch(s);

/// Message key for index [n] (`m%04d`; never a bare number, which RTDB
/// would turn into an array).
String messageKey(int n) => 'm${n.toString().padLeft(4, '0')}';

/// Device id: a uuid4 (lowercase, hyphenated).
bool isDeviceId(String s) => RegExp(
  r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
).hasMatch(s);

String _check(String id, bool Function(String) ok, String what) {
  if (!ok(id)) throw ArgumentError.value(id, what, 'not a valid $what');
  return id;
}

/// RTDB paths under the contract root.
abstract final class Paths {
  /// The contract root.
  static const root = 'tutor/v1';

  /// `meta`.
  static const meta = '$root/meta';

  /// `rev`.
  static const rev = '$root/rev';

  /// `live`.
  static const live = '$root/live';

  /// `prefs`.
  static const prefs = '$root/prefs';

  /// `stats`.
  static const stats = '$root/stats';

  /// `presence/workers`.
  static const workers = '$root/presence/workers';

  /// `subjects` (list with `shallow` only; never stream it).
  static const subjects = '$root/subjects';

  /// `log` (list with `shallow` only; never stream it).
  static const log = '$root/log';

  /// `session_index` (history rows, §6).
  static const sessionIndex = '$root/session_index';

  /// `presence/clients/{dev}`.
  static String client(String dev) =>
      '$root/presence/clients/${_check(dev, isDeviceId, 'device id')}';

  /// `requests` (streamed only ranged from a followed rid, §9).
  static const requests = '$root/requests';

  /// `requests/{rid}`.
  static String request(String rid) =>
      '$requests/${_check(rid, isUlid, 'rid')}';

  /// `requests/{rid}/req`.
  static String requestReq(String rid) => '${request(rid)}/req';

  /// `subjects/{subj}`.
  static String subject(String subj) =>
      '$subjects/${_check(subj, isSlug, 'subject id')}';

  /// `sessions/{sid}`.
  static String session(String sid) =>
      '$root/sessions/${_check(sid, isSessionId, 'session id')}';

  /// `log/{dev}`.
  static String logOf(String dev) =>
      '$log/${_check(dev, isDeviceId, 'device id')}';

  /// `log/{dev}/{eid}`.
  static String logEvent(String dev, String eid) =>
      '${logOf(dev)}/${_check(eid, isUlid, 'eid')}';

  /// `feedback/{fid}`.
  static String feedback(String fid) =>
      '$root/feedback/${_check(fid, isUlid, 'fid')}';
}
