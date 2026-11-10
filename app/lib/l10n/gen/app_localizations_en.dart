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
  String unbackedMinutes(int n) {
    return '$n min unbacked (not counted)';
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
}
