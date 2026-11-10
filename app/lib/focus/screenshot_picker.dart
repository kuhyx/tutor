/// Lets kuhy pick the rules screenshot: the Android document picker, or the
/// browser's file input on the desktop build.
library;

import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';

/// Opens the picker for an image; null when cancelled.
typedef PickImage = Future<Uint8List?> Function();

/// The real picker; widget tests pass their own [PickImage].
// coverage:ignore-start
Future<Uint8List?> pickScreenshot() async {
  final files = await FilePicker.pickFiles(type: FileType.image);
  if (files.isEmpty) return null;
  return await files.first.readAsBytes();
}
// coverage:ignore-end
