import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/deep_link.dart';

void main() {
  test('the fragment route is the deep link', () {
    expect(
      routeFromUri(Uri.parse('http://127.0.0.1:8778/app/#/focus?start=1')),
      '/focus?start=1',
    );
    expect(routeFromUri(Uri.parse('http://x/app/#/progress')), '/progress');
  });

  test('no route fragment is no deep link', () {
    expect(routeFromUri(Uri.parse('http://127.0.0.1:8778/app/')), isNull);
    expect(routeFromUri(Uri.parse('http://x/app/#')), isNull);
    expect(routeFromUri(Uri.parse('http://x/app/#/')), isNull);
    expect(routeFromUri(Uri.parse('http://x/app/#section')), isNull);
  });

  test('forgetting the deep link is safe off the web', forgetDeepLink);
}
