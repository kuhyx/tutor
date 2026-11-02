import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/focus/android_checkin_notifier.dart';
import 'package:tutor/focus/checkin_notifier.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('com.kuhy.tutor/focus');
  final calls = <MethodCall>[];
  var pending = <int>[];
  var permission = true;

  setUp(() {
    calls.clear();
    pending = [];
    permission = true;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          switch (call.method) {
            case 'ensurePermission':
              return permission;
            case 'takePending':
              final out = pending;
              pending = [];
              return out;
            default:
              return null;
          }
        });
  });

  Future<void> tap(AndroidCheckinNotifier n) async {
    await TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .handlePlatformMessage(
          channel.name,
          channel.codec.encodeMethodCall(const MethodCall('tapped')),
          (_) {},
        );
    await Future<void>.delayed(Duration.zero);
  }

  test(
    'schedule asks for permission once, then arms with the interval',
    () async {
      final n = AndroidCheckinNotifier();
      await n.schedule(const Duration(minutes: 3));
      await n.schedule(const Duration(minutes: 9));
      expect(calls.map((c) => c.method), [
        'ensurePermission',
        'schedule',
        'schedule',
      ]);
      expect(calls[1].arguments, {
        'afterMs': 180000,
        'everyMs': checkinEvery.inMilliseconds,
      });
    },
  );

  test('a denied permission is asked again next time but still arms', () async {
    permission = false;
    final n = AndroidCheckinNotifier();
    await n.schedule(const Duration(minutes: 9));
    await n.schedule(const Duration(minutes: 9));
    expect(calls.where((c) => c.method == 'ensurePermission'), hasLength(2));
    expect(calls.where((c) => c.method == 'schedule'), hasLength(2));
  });

  test('cancel is forwarded', () async {
    await AndroidCheckinNotifier().cancel();
    expect(calls.single.method, 'cancel');
  });

  test('takePending returns the stored tap times', () async {
    pending = [10, 20];
    final n = AndroidCheckinNotifier();
    expect(await n.takePending(), [10, 20]);
    expect(await n.takePending(), isEmpty);
  });

  test('a tap with a listener arrives on confirmations once', () async {
    final n = AndroidCheckinNotifier();
    final got = <int>[];
    final sub = n.confirmations.listen(got.add);
    pending = [111];
    await tap(n);
    expect(got, [111]);
    expect(await n.takePending(), isEmpty);
    await sub.cancel();
  });

  test('a tap with no listener stays pending for takePending', () async {
    final n = AndroidCheckinNotifier();
    pending = [222];
    await tap(n);
    expect(calls.where((c) => c.method == 'takePending'), isEmpty);
    expect(await n.takePending(), [222]);
  });

  test('platformCheckinNotifier is a no-op off Android', () {
    expect(
      platformCheckinNotifier(isAndroid: false),
      isA<NoopCheckinNotifier>(),
    );
    expect(
      platformCheckinNotifier(isAndroid: true),
      isA<AndroidCheckinNotifier>(),
    );
  });
}
