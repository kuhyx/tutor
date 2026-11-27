// `kuhytutor://learn|review|rework/...` (leetcode-guard's phone app):
// MainActivity hands the launch link once (`initialLink`) and each later
// intent's link (the event channel); only those three hosts open a route.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/deep_link.dart';
import 'package:tutor/ui/deep_link_io.dart' as io;
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

const _links = MethodChannel('com.kuhy.tutor/deeplink');
const _newLinks = EventChannel('com.kuhy.tutor/deeplink/new');

String? _route(String link) => routeFromAppLink(Uri.parse(link));

void main() {
  final messenger =
      TestWidgetsFlutterBinding.ensureInitialized().defaultBinaryMessenger;

  setUp(() => io.appLinksAvailable = true);
  tearDown(() {
    io.appLinksAvailable = false;
    messenger
      ..setMockMethodCallHandler(_links, null)
      ..setMockStreamHandler(_newLinks, null);
  });

  void answer(Object? Function() link) =>
      messenger.setMockMethodCallHandler(_links, (call) async {
        expect(call.method, 'initialLink');
        return link();
      });

  test('learn, review and rework links name their route', () {
    expect(_route('kuhytutor://learn/car/fuel'), '/learn/car/fuel');
    expect(_route('kuhytutor://review/car/fuel'), '/review/car/fuel');
    expect(_route('kuhytutor://rework/car/fuel/c1'), '/rework/car/fuel/c1');
    expect(_route('kuhytutor://learn/car/fuel?x=1#y'), '/learn/car/fuel');
  });

  test('another scheme, host or an empty path is no route', () {
    expect(_route('https://learn/car/fuel'), isNull);
    expect(_route('kuhytutor://plan/car'), isNull);
    expect(_route('kuhytutor://learn'), isNull);
    expect(_route('kuhytutor://learn/'), isNull);
    expect(_route('kuhytutor:learn/car'), isNull);
  });

  test('the launch link is the initial route', () async {
    answer(() => 'kuhytutor://review/car/fuel');
    expect(await initialRoute(), '/review/car/fuel');
  });

  test('no, a foreign or an unparsable launch link is none', () async {
    for (final link in [null, 'https://x/learn/a/b', 'kuhytutor://[', 7]) {
      answer(() => link);
      expect(await initialRoute(), isNull, reason: '$link');
    }
  });

  test('a channel failure is no initial route, never a throw', () async {
    expect(await initialRoute(), isNull); // no handler: MissingPlugin
    answer(() => throw PlatformException(code: 'x'));
    expect(await initialRoute(), isNull);
  });

  test('off Android: no channel call, no routes', () async {
    io.appLinksAvailable = false;
    answer(() => fail('called off Android'));
    expect(await initialRoute(), isNull);
    expect(await handedRoutes.toList(), isEmpty);
  });

  test('each later intent link is a handed route', () async {
    messenger.setMockStreamHandler(
      _newLinks,
      MockStreamHandler.inline(
        onListen: (_, sink) {
          sink
            ..success('kuhytutor://review/car/fuel')
            ..success('https://x/learn/a/b')
            ..success(null)
            ..success('kuhytutor://learn/car/fuel')
            ..endOfStream();
        },
      ),
    );
    expect(await handedRoutes.toList(), [
      '/review/car/fuel',
      '/learn/car/fuel',
    ]);
  });

  testWidgets('cold start: the launch link lands on the module', (t) async {
    answer(() => 'kuhytutor://learn/car/fuel');
    final route = await initialRoute();
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    await pumpScreen(
      t,
      HomeScreen(services: s, onSignedOut: () {}, initialRoute: route),
      settle: false,
    );
    for (var i = 0; i < 10; i++) {
      await t.pump(const Duration(milliseconds: 50));
    }
    expect(find.byType(SessionScreen), findsOneWidget);
    final body = lastRequest(db).$2['body'] as Map;
    expect((body['subject'], body['module']), ('car', 'fuel'));
  });
}
