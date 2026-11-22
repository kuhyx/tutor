import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'gen/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('en')];

  /// No description provided for @start.
  ///
  /// In en, this message translates to:
  /// **'Start'**
  String get start;

  /// No description provided for @stop.
  ///
  /// In en, this message translates to:
  /// **'Stop'**
  String get stop;

  /// No description provided for @stillWorking.
  ///
  /// In en, this message translates to:
  /// **'Still working'**
  String get stillWorking;

  /// No description provided for @newProject.
  ///
  /// In en, this message translates to:
  /// **'New project'**
  String get newProject;

  /// No description provided for @endProject.
  ///
  /// In en, this message translates to:
  /// **'End project'**
  String get endProject;

  /// No description provided for @createProject.
  ///
  /// In en, this message translates to:
  /// **'Create'**
  String get createProject;

  /// No description provided for @editProject.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get editProject;

  /// No description provided for @saveProject.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get saveProject;

  /// No description provided for @projectName.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get projectName;

  /// No description provided for @startDate.
  ///
  /// In en, this message translates to:
  /// **'From'**
  String get startDate;

  /// No description provided for @endDate.
  ///
  /// In en, this message translates to:
  /// **'Until'**
  String get endDate;

  /// No description provided for @daysLeft.
  ///
  /// In en, this message translates to:
  /// **'{n, plural, =1{1 day left} other{{n} days left}}'**
  String daysLeft(int n);

  /// No description provided for @banked.
  ///
  /// In en, this message translates to:
  /// **'(+{n} banked)'**
  String banked(int n);

  /// No description provided for @dailyMinutes.
  ///
  /// In en, this message translates to:
  /// **'Minutes per day'**
  String get dailyMinutes;

  /// No description provided for @unlockMinutes.
  ///
  /// In en, this message translates to:
  /// **'Unlock minutes'**
  String get unlockMinutes;

  /// No description provided for @gatesOff.
  ///
  /// In en, this message translates to:
  /// **'Turned off'**
  String get gatesOff;

  /// No description provided for @gateKept.
  ///
  /// In en, this message translates to:
  /// **'kept'**
  String get gateKept;

  /// No description provided for @subjects.
  ///
  /// In en, this message translates to:
  /// **'Tutor subjects'**
  String get subjects;

  /// No description provided for @sites.
  ///
  /// In en, this message translates to:
  /// **'Sites, comma separated'**
  String get sites;

  /// No description provided for @workUrl.
  ///
  /// In en, this message translates to:
  /// **'Work URL'**
  String get workUrl;

  /// No description provided for @queued.
  ///
  /// In en, this message translates to:
  /// **'Saved, sending later'**
  String get queued;

  /// No description provided for @missedCheckin.
  ///
  /// In en, this message translates to:
  /// **'Missed a check-in'**
  String get missedCheckin;

  /// No description provided for @noProject.
  ///
  /// In en, this message translates to:
  /// **'No focus project'**
  String get noProject;

  /// No description provided for @focus.
  ///
  /// In en, this message translates to:
  /// **'Focus'**
  String get focus;

  /// No description provided for @retestNoSubmit.
  ///
  /// In en, this message translates to:
  /// **'Re-test: do NOT submit this on LeetCode'**
  String get retestNoSubmit;

  /// No description provided for @todayTitle.
  ///
  /// In en, this message translates to:
  /// **'Today'**
  String get todayTitle;

  /// No description provided for @timerOn.
  ///
  /// In en, this message translates to:
  /// **'{n} min'**
  String timerOn(int n);

  /// No description provided for @timerOff.
  ///
  /// In en, this message translates to:
  /// **'Off'**
  String get timerOff;

  /// No description provided for @homeTooltip.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get homeTooltip;

  /// No description provided for @allDone.
  ///
  /// In en, this message translates to:
  /// **'All done'**
  String get allDone;

  /// No description provided for @stepOf.
  ///
  /// In en, this message translates to:
  /// **'{n}/{total}'**
  String stepOf(int n, int total);

  /// No description provided for @doneStep.
  ///
  /// In en, this message translates to:
  /// **'Done'**
  String get doneStep;

  /// No description provided for @tooltip_sync.
  ///
  /// In en, this message translates to:
  /// **'Sync'**
  String get tooltip_sync;

  /// No description provided for @tooltip_review.
  ///
  /// In en, this message translates to:
  /// **'Review'**
  String get tooltip_review;

  /// No description provided for @tooltip_drill.
  ///
  /// In en, this message translates to:
  /// **'Drill'**
  String get tooltip_drill;

  /// No description provided for @tooltip_plan.
  ///
  /// In en, this message translates to:
  /// **'Plan'**
  String get tooltip_plan;

  /// No description provided for @tooltip_cards.
  ///
  /// In en, this message translates to:
  /// **'Cards'**
  String get tooltip_cards;

  /// No description provided for @tooltip_next.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get tooltip_next;

  /// No description provided for @tooltip_retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get tooltip_retry;

  /// No description provided for @tooltip_archive.
  ///
  /// In en, this message translates to:
  /// **'Archive'**
  String get tooltip_archive;

  /// No description provided for @tooltip_save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get tooltip_save;

  /// No description provided for @tooltip_approve.
  ///
  /// In en, this message translates to:
  /// **'Approve'**
  String get tooltip_approve;

  /// No description provided for @tooltip_edit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get tooltip_edit;

  /// No description provided for @tooltip_send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get tooltip_send;

  /// No description provided for @tooltip_hint.
  ///
  /// In en, this message translates to:
  /// **'Hint'**
  String get tooltip_hint;

  /// No description provided for @tooltip_history.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get tooltip_history;

  /// No description provided for @tooltip_known.
  ///
  /// In en, this message translates to:
  /// **'Known'**
  String get tooltip_known;

  /// No description provided for @tooltip_open.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get tooltip_open;

  /// No description provided for @tooltip_redraft.
  ///
  /// In en, this message translates to:
  /// **'Redraft'**
  String get tooltip_redraft;

  /// No description provided for @tooltip_reload.
  ///
  /// In en, this message translates to:
  /// **'Reload'**
  String get tooltip_reload;

  /// No description provided for @tooltip_refresh.
  ///
  /// In en, this message translates to:
  /// **'Refresh'**
  String get tooltip_refresh;

  /// No description provided for @tooltip_stop.
  ///
  /// In en, this message translates to:
  /// **'Stop'**
  String get tooltip_stop;

  /// No description provided for @tooltip_switch.
  ///
  /// In en, this message translates to:
  /// **'Switch'**
  String get tooltip_switch;

  /// No description provided for @tooltip_report.
  ///
  /// In en, this message translates to:
  /// **'Report'**
  String get tooltip_report;

  /// No description provided for @tooltip_restore.
  ///
  /// In en, this message translates to:
  /// **'Restore'**
  String get tooltip_restore;

  /// No description provided for @tooltip_reveal.
  ///
  /// In en, this message translates to:
  /// **'Reveal'**
  String get tooltip_reveal;

  /// No description provided for @tooltip_deeper.
  ///
  /// In en, this message translates to:
  /// **'Deeper'**
  String get tooltip_deeper;

  /// No description provided for @tooltip_sql.
  ///
  /// In en, this message translates to:
  /// **'SQL'**
  String get tooltip_sql;

  /// No description provided for @tooltip_coach.
  ///
  /// In en, this message translates to:
  /// **'Coach'**
  String get tooltip_coach;

  /// No description provided for @tooltip_draft.
  ///
  /// In en, this message translates to:
  /// **'Draft'**
  String get tooltip_draft;

  /// No description provided for @tooltip_complete.
  ///
  /// In en, this message translates to:
  /// **'Complete'**
  String get tooltip_complete;

  /// No description provided for @tooltip_ask.
  ///
  /// In en, this message translates to:
  /// **'Ask'**
  String get tooltip_ask;

  /// No description provided for @tooltip_calendar.
  ///
  /// In en, this message translates to:
  /// **'Calendar'**
  String get tooltip_calendar;

  /// No description provided for @tooltip_live.
  ///
  /// In en, this message translates to:
  /// **'Live'**
  String get tooltip_live;

  /// No description provided for @tooltip_learn.
  ///
  /// In en, this message translates to:
  /// **'Learn'**
  String get tooltip_learn;

  /// No description provided for @tooltip_resume.
  ///
  /// In en, this message translates to:
  /// **'Resume'**
  String get tooltip_resume;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
