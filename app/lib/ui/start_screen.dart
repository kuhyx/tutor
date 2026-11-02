/// The signed-in start route: Today when the server has a plan for today,
/// else Home. A plan cached for today opens at once (cold start with no PC
/// reachable); otherwise `plan_today` is asked for, and after
/// [startWait] Home opens anyway.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/today_screen.dart';

/// How long a cold start waits for the plan before showing Home.
const startWait = Duration(seconds: 6);

/// Chooses between Today and Home.
class StartScreen extends StatefulWidget {
  /// Creates the screen; a deep link ([initialRoute]) always means Home.
  const new({
    required this.services,
    required this.onSignedOut,
    this.initialRoute,
    super.key,
  });

  /// Services.
  final TutorServices services;

  /// Called after sign-out.
  final VoidCallback onSignedOut;

  /// A route to open over Home.
  final String? initialRoute;

  @override
  State<StartScreen> createState() => _StartScreenState();
}

class _StartScreenState extends State<StartScreen> {
  late final RequestRunner _runner = RequestRunner(widget.services.relay);
  TodayPlan? _plan;
  bool _decided = false;

  @override
  void initState() {
    super.initState();
    if (widget.initialRoute != null) {
      _decided = true;
    } else {
      unawaited(_decide());
    }
  }

  @override
  void dispose() {
    unawaited(_runner.dispose());
    super.dispose();
  }

  Future<void> _decide() async {
    final s = widget.services;
    final cached = await cachedPlan(s.kv, localDay());
    if (cached != null) {
      _set(cached);
      return;
    }
    final result = await _runner.run(planToday()).timeout(
      startWait,
      onTimeout: () => RelayNotSent(TimeoutException('plan_today')),
    );
    if (result is RelayDone) {
      final plan = TodayPlan.fromJson(result.data);
      if (plan.steps.isNotEmpty) {
        await cachePlan(s.kv, result.data);
        _set(plan);
        return;
      }
    }
    _set(null);
  }

  void _set(TodayPlan? plan) {
    if (!mounted) return;
    setState(() {
      _plan = plan;
      _decided = true;
    });
  }

  Widget _home() => HomeScreen(
    services: widget.services,
    onSignedOut: widget.onSignedOut,
    initialRoute: widget.initialRoute,
  );

  @override
  Widget build(BuildContext context) {
    if (!_decided) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final plan = _plan;
    if (plan == null) return _home();
    return TodayScreen(
      services: widget.services,
      plan: plan,
      openHome: () => Navigator.of(context).push<void>(
        MaterialPageRoute(builder: (_) => _home()),
      ),
    );
  }
}
