import 'dart:async';

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/ui/coach/coach_chat.dart';
import 'package:tutor/ui/coach/coach_code_tab.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';
import 'package:tutor/ui/coach/coach_session.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_parts.dart';
import 'package:tutor/ui/sql/problem_cue.dart';
import 'package:tutor/ui/sql/rich_md.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/icon_field.dart';

/// A coaching session on one problem: statement (folding on a phone, a side
/// pane on a desktop), chat, and the code tab. `open` is the `lc_open` to
/// send; an `lc_id` in it resumes that session with its stored chat.
class CoachScreen extends StatefulWidget {
  /// Creates the screen.
  const new({
    required this.services,
    required this.open,
    this.title,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// The `lc_open` request.
  final RequestBody open;

  /// Shown until the problem is open.
  final String? title;

  @override
  State<CoachScreen> createState() => _CoachScreenState();
}

class _CoachScreenState extends State<CoachScreen> {
  late final _session = CoachSession(
    widget.services,
    open: widget.open,
    resumeId: widget.open.body['lc_id'] as String?,
  );

  @override
  void initState() {
    super.initState();
    unawaited(_session.start());
  }

  @override
  void dispose() {
    _session.dispose();
    super.dispose();
  }

  Future<void> _postMortem() => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => CoachPostMortemScreen(
        services: widget.services,
        lcId: _session.opened!.lcId,
        summaryMd: _session.summaryMd,
      ),
    ),
  );

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: _session,
    builder: (context, _) {
      final o = _session.opened;
      if (_session.needsStatement) return _PasteForm(_session);
      if (o == null) {
        return Scaffold(
          appBar: AppBar(title: ContentText(widget.title ?? '')),
          body: PageList(
            children: [
              for (final b in _session.thread) BubbleView(b),
              RequestStatusLine(_session.opener),
              if (_session.problem != null) problemCue(_session.problem!),
            ],
          ),
        );
      }
      final wide = MediaQuery.sizeOf(context).width >= kSqlTwoPanes;
      final tabs = TabBarView(
        children: [
          _Keep(
            CoachChat(
              session: _session,
              onPostMortem: () => unawaited(_postMortem()),
              sidePane: wide,
            ),
          ),
          _Keep(CoachCodeTab(session: _session, touch: !wide)),
        ],
      );
      return DefaultTabController(
        length: 2,
        child: Scaffold(
          appBar: AppBar(
            title: ContentText(o.title),
            bottom: const TabBar(
              tabs: [
                Tab(icon: Icon(Icons.forum_outlined, semanticLabel: 'Chat')),
                Tab(icon: Icon(Icons.code, semanticLabel: 'Code')),
              ],
            ),
          ),
          body: SafeArea(
            child: wide
                ? Row(
                    children: [
                      Expanded(
                        child: ListView(
                          key: const ValueKey('statement-pane'),
                          padding: const EdgeInsets.all(AppSpacing.md),
                          children: [RichMd(o.statementMd)],
                        ),
                      ),
                      const VerticalDivider(width: 1),
                      Expanded(flex: 2, child: tabs),
                    ],
                  )
                : tabs,
          ),
        ),
      );
    },
  );
}

class _Keep extends StatefulWidget {
  const new(this.child);

  final Widget child;

  @override
  State<_Keep> createState() => _KeepState();
}

class _KeepState extends State<_Keep> with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return widget.child;
  }
}

class _PasteForm extends StatefulWidget {
  const new(this.session);

  final CoachSession session;

  @override
  State<_PasteForm> createState() => _PasteFormState();
}

class _PasteFormState extends State<_PasteForm> {
  final _title = TextEditingController();
  final _statement = TextEditingController();

  @override
  void dispose() {
    _title.dispose();
    _statement.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(),
    body: PageList(
      children: [
        RequestStatusLine(widget.session.opener),
        FieldLabel(
          semanticLabel: 'Title',
          child: TextField(
            key: const ValueKey('paste-title'),
            controller: _title,
            decoration: iconDecoration(Icons.title),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        FieldLabel(
          semanticLabel: 'Statement',
          child: TextField(
            key: const ValueKey('paste-statement'),
            controller: _statement,
            minLines: 8,
            maxLines: 16,
            maxLength: coachMaxText,
            keyboardType: TextInputType.multiline,
            decoration: iconDecoration(Icons.description_outlined),
          ),
        ),
        ListenableBuilder(
          listenable: _statement,
          builder: (context, _) => FilledButton(
            key: const ValueKey('paste-go'),
            onPressed: _statement.text.trim().isEmpty
                ? null
                : () => widget.session.pasteStatement(
                    _title.text,
                    _statement.text,
                  ),
            child: const Icon(Icons.arrow_forward, semanticLabel: 'Start'),
          ),
        ),
      ],
    ),
  );
}
