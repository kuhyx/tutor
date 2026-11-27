// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get start => 'Start';

  @override
  String get stop => 'Stop';

  @override
  String get stillWorking => 'Still working';

  @override
  String get newProject => 'New project';

  @override
  String get endProject => 'End project';

  @override
  String get createProject => 'Create';

  @override
  String get editProject => 'Edit';

  @override
  String get saveProject => 'Save';

  @override
  String get projectName => 'Name';

  @override
  String get startDate => 'From';

  @override
  String get endDate => 'Until';

  @override
  String daysLeft(int n) {
    String _temp0 = intl.Intl.pluralLogic(
      n,
      locale: localeName,
      other: '$n days left',
      one: '1 day left',
    );
    return '$_temp0';
  }

  @override
  String banked(int n) {
    return '(+$n banked)';
  }

  @override
  String get dailyMinutes => 'Minutes per day';

  @override
  String get unlockMinutes => 'Unlock minutes';

  @override
  String get gatesOff => 'Turned off';

  @override
  String get gateKept => 'kept';

  @override
  String get subjects => 'Tutor subjects';

  @override
  String get sites => 'Sites, comma separated';

  @override
  String get workUrl => 'Work URL';

  @override
  String get queued => 'Saved, sending later';

  @override
  String get missedCheckin => 'Missed a check-in';

  @override
  String get noProject => 'No focus project';

  @override
  String get focus => 'Focus';

  @override
  String get retestNoSubmit => 'Re-test: do NOT submit this on LeetCode';

  @override
  String get todayTitle => 'Today';

  @override
  String timerOn(int n) {
    return '$n min';
  }

  @override
  String get timerOff => 'Off';

  @override
  String get homeTooltip => 'Home';

  @override
  String get allDone => 'All done';

  @override
  String stepOf(int n, int total) {
    return '$n/$total';
  }

  @override
  String get doneStep => 'Done';

  @override
  String get tooltip_sync => 'Sync';

  @override
  String get tooltip_review => 'Review';

  @override
  String get tooltip_drill => 'Drill';

  @override
  String get tooltip_plan => 'Plan';

  @override
  String get tooltip_cards => 'Cards';

  @override
  String get tooltip_next => 'Next';

  @override
  String get tooltip_retry => 'Retry';

  @override
  String get tooltip_again => 'Again';

  @override
  String get tooltip_archive => 'Archive';

  @override
  String get tooltip_save => 'Save';

  @override
  String get tooltip_approve => 'Approve';

  @override
  String get tooltip_edit => 'Edit';

  @override
  String get tooltip_send => 'Send';

  @override
  String get tooltip_hint => 'Hint';

  @override
  String get tooltip_history => 'History';

  @override
  String get tooltip_known => 'Known';

  @override
  String get tooltip_open => 'Open';

  @override
  String get tooltip_redraft => 'Redraft';

  @override
  String get tooltip_reload => 'Reload';

  @override
  String get tooltip_refresh => 'Refresh';

  @override
  String get tooltip_stop => 'Stop';

  @override
  String get tooltip_switch => 'Switch';

  @override
  String get tooltip_report => 'Report';

  @override
  String get tooltip_restore => 'Restore';

  @override
  String get tooltip_reveal => 'Reveal';

  @override
  String get tooltip_deeper => 'Deeper';

  @override
  String get tooltip_sql => 'SQL';

  @override
  String get tooltip_coach => 'Coach';

  @override
  String get tooltip_draft => 'Draft';

  @override
  String get tooltip_complete => 'Complete';

  @override
  String get tooltip_ask => 'Ask';

  @override
  String get tooltip_calendar => 'Calendar';

  @override
  String get tooltip_live => 'Live';

  @override
  String get tooltip_learn => 'Learn';

  @override
  String get tooltip_resume => 'Resume';

  @override
  String get tooltip_own => 'Own';

  @override
  String get tooltip_leetcode => 'LeetCode';

  @override
  String get tooltip_all => 'All';

  @override
  String get tooltip_unchecked => 'Unchecked';

  @override
  String get tooltip_check => 'Check';
}
