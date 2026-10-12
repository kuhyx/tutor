// Fails when a logic file (lib/ minus lib/ui/ and main.dart) has an uncovered
// line that is not explicitly exempted.
//
// `flutter test --coverage` ignores `// coverage:ignore-*` markers entirely;
// they are a convention the reader of lcov.info must implement. This one
// honours ignore-file, ignore-start/-end, and ignore-line on the line itself
// or on the comment lines directly above it.
//
// Usage (from app/): fvm flutter test --coverage &&
//   dart run tool/check_coverage.dart [coverage/lcov.info]
import 'dart:io';

void main(List<String> args) {
  final lcov = File(args.isEmpty ? 'coverage/lcov.info' : args.first);
  final gaps = uncovered(lcov.readAsStringSync(), (p) {
    final f = File(p);
    return f.existsSync() ? f.readAsLinesSync() : const <String>[];
  });
  for (final entry in gaps.entries) {
    stdout.writeln('${entry.key}: ${entry.value.join(',')}');
  }
  stdout.writeln(gaps.isEmpty ? 'coverage: 100% of logic lines' : 'GAPS');
  exitCode = gaps.isEmpty ? 0 : 1;
}

/// Whether [path] is held to 100%.
bool isLogic(String path) =>
    path.startsWith('lib/') &&
    !path.startsWith('lib/ui/') &&
    path != 'lib/main.dart';

/// Uncovered, non-exempt line numbers per logic file.
Map<String, List<int>> uncovered(
  String lcov,
  List<String> Function(String path) readLines,
) {
  final out = <String, List<int>>{};
  String? file;
  var missed = <int>[];
  void flush() {
    if (file == null || !isLogic(file)) return;
    final keep = _exempt(readLines(file), missed);
    if (keep.isNotEmpty) out[file] = keep;
  }

  for (final line in lcov.split('\n')) {
    if (line.startsWith('SF:')) {
      file = line.substring(3);
      missed = [];
    } else if (line.startsWith('DA:')) {
      final parts = line.substring(3).split(',');
      if (parts[1] == '0') missed.add(int.parse(parts[0]));
    } else if (line == 'end_of_record') {
      flush();
      file = null;
    }
  }
  return out;
}

List<int> _exempt(List<String> src, List<int> missed) {
  if (src.any((l) => l.contains('coverage:ignore-file'))) return const [];
  final ignored = <int>{};
  var inBlock = false;
  for (var i = 0; i < src.length; i++) {
    if (src[i].contains('coverage:ignore-start')) inBlock = true;
    if (inBlock) ignored.add(i + 1);
    if (src[i].contains('coverage:ignore-end')) inBlock = false;
  }
  bool lineIgnored(int n) {
    if (n > src.length) return false;
    if (src[n - 1].contains('coverage:ignore-line')) return true;
    for (var i = n - 2; i >= 0 && src[i].trim().startsWith('//'); i--) {
      if (src[i].contains('coverage:ignore-line')) return true;
    }
    return false;
  }

  return [
    for (final n in missed)
      if (!ignored.contains(n) && !lineIgnored(n)) n,
  ];
}
