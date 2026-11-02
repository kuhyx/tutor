import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/rich_md.dart';

import '../../sql/sql_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/services.dart';
import '../../support/ui.dart';

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  Future<void> open(WidgetTester t, {double? keyboard}) async {
    db = FakeRtdb();
    stream = FakeStream();
    await pumpScreen(
      t,
      SqlDrillScreen(
        services: services(db, stream, kv: MemoryKv()),
        id: 'basics-1',
        title: 'Count rows',
      ),
      settle: false,
    );
    if (keyboard != null) {
      t.view
        ..physicalSize = const Size(1080, 2400)
        ..devicePixelRatio = 2.625
        ..padding = const FakeViewPadding(top: 132, bottom: 63)
        ..viewInsets = FakeViewPadding(bottom: keyboard);
    }
    await t.pump(const Duration(milliseconds: 50));
    await answer(t, db, stream, data: writeDrillData);
  }

  Finder editor() => find.byKey(const ValueKey('sql-editor'));

  String gutter(WidgetTester t) =>
      t.widget<Text>(find.byKey(const ValueKey('gutter'))).data!;

  testWidgets('phone: Answer tab keeps editor and Run above the keyboard', (
    t,
  ) async {
    await open(t, keyboard: 800);
    expect(find.byKey(const ValueKey('run')), findsNothing); // on Task tab
    await t.tap(find.byIcon(Icons.edit_note));
    await t.pumpAndSettle();
    await t.tap(editor());
    await t.pump(const Duration(milliseconds: 100));
    const dpr = 2.625;
    final run = t.getRect(find.byKey(const ValueKey('run')));
    final field = t.getRect(editor());
    expect(run.bottom, lessThanOrEqualTo((2400 - 800) / dpr));
    expect(field.top, greaterThanOrEqualTo(132 / dpr));
    expect(find.byKey(const ValueKey('key-*')), findsOneWidget);
  });

  testWidgets('symbol keys insert at the cursor and keep focus', (t) async {
    await open(t, keyboard: 0);
    await t.tap(find.byIcon(Icons.edit_note));
    await t.pumpAndSettle();
    await t.enterText(editor(), 'select  from emp');
    t.testTextInput.updateEditingValue(
      const TextEditingValue(
        text: 'select  from emp',
        selection: TextSelection.collapsed(offset: 7),
      ),
    );
    await t.pump();
    await t.tap(find.byKey(const ValueKey('key-*')));
    await t.pump();
    expect(find.text('select * from emp'), findsOneWidget);
    expect(find.byType(EditableText), findsOneWidget);
    expect(
      t.widget<EditableText>(find.byType(EditableText)).focusNode.hasFocus,
      isTrue,
    );
  });

  testWidgets('line numbers follow lines and wrapped lines', (t) async {
    await open(t);
    await t.enterText(editor(), 'select 1\nfrom emp\n');
    await t.pump();
    expect(gutter(t), '1\n2\n3');
    await t.enterText(editor(), 'x' * 400);
    await t.pump();
    expect(gutter(t), startsWith('1\n'));
    expect(gutter(t).trim(), '1');
  });

  testWidgets('RichMd renders fenced code and pipe tables', (t) async {
    await pumpScreen(
      t,
      const Scaffold(
        body: RichMd(
          'Intro\n\n```sql\nSELECT 1;\n```\n\n'
          '| a | b |\n|---|---|\n| 1 | NULL |\n\nAfter',
        ),
      ),
    );
    expect(find.text('Intro'), findsOneWidget);
    expect(find.text('SELECT 1;'), findsOneWidget);
    expect(find.text('a'), findsOneWidget);
    expect(find.text('NULL'), findsOneWidget);
    expect(find.text('After'), findsOneWidget);
    expect(find.text('|---|---|'), findsNothing);
  });

  testWidgets('a long query wraps in its block instead of clipping', (t) async {
    const query =
        'SELECT id, name FROM customers WHERE referee != 1 ORDER BY id DESC';
    await pumpScreen(
      t,
      const Scaffold(
        body: Align(
          alignment: Alignment.topLeft,
          child: SizedBox(width: 300, child: CodeBlock(query)),
        ),
      ),
    );
    final box = t.getSize(find.byType(CodeBlock));
    expect(box.width, lessThanOrEqualTo(300));
    expect(find.byType(SingleChildScrollView), findsNothing);
    expect(t.getSize(find.text(query)).height, greaterThan(24));
  });
}
