import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/config/app_version.dart';
import 'package:tutor/presence/client_beacon.dart';
import 'package:tutor/sync/json_tree.dart';

import '../support/fake_rtdb.dart';
import '../support/services.dart';

void main() {
  final binding = TestWidgetsFlutterBinding.ensureInitialized();
  late FakeRtdb db;
  late ClientBeacon beacon;
  const path = 'tutor/v1-e2e/presence/clients/$testDev';

  setUp(() {
    db = FakeRtdb()..serverTime = 111;
    beacon = ClientBeacon(
      client: db.client(),
      dev: testDev,
      platform: 'android',
      binding: binding,
    );
  });
  tearDown(() => beacon.stop());

  Future<void> settle() => Future<void>.delayed(Duration.zero);

  test('start writes platform, app version and the server time', () async {
    beacon.start();
    await settle();
    expect(getAt(db.root, path), {
      'platform': 'android',
      'app': appVersion,
      'seen': 111,
    });
  });

  test('resume writes again; other lifecycle states do not', () async {
    beacon.start();
    await settle();
    db.serverTime = 222;
    binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await settle();
    expect((getAt(db.root, path)! as Map)['seen'], 111);
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle();
    expect((getAt(db.root, path)! as Map)['seen'], 222);
  });

  test('stop ends the resume writes; start twice is one observer', () async {
    beacon
      ..start()
      ..start();
    await settle();
    beacon.stop();
    db.log.clear();
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle();
    expect(db.log, isEmpty);
  });

  test('a failed write is recorded, not thrown; the next one works', () async {
    db.offline = true;
    beacon.start();
    await settle();
    expect(beacon.lastError.value, isNotNull);
    db.offline = false;
    binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await settle();
    expect(beacon.lastError.value, isNull);
    expect((getAt(db.root, path)! as Map)['platform'], 'android');
  });

  test('the version constant is the pubspec version name', () {
    final line = File('pubspec.yaml')
        .readAsLinesSync()
        .firstWhere((l) => l.startsWith('version:'));
    expect(line.split(':')[1].trim().split('+').first, appVersion);
  });
}
