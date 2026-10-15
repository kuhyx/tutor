import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/util/device.dart';

void main() {
  tearDown(() => debugPhone = false);

  test('forced phone / desktop', () {
    debugPhone = true;
    expect(isPhone, isTrue);
    expect(deviceName, 'phone');
    expect(defaultZoom, kPhoneZoom);
    debugPhone = false;
    expect(deviceName, 'desktop');
    expect(defaultZoom, 1);
  });

  test('unforced: the Android app is the phone (tests run as android)', () {
    debugPhone = null;
    expect(isPhone, isTrue);
  });
}
