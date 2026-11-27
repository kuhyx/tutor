part of 'log_event.dart';

/// The old daily cap's setting (removed 2026-11-22): still parsed, so an
/// old log reads, but nothing writes or applies it.
class NewCapEvent extends LogEvent {
  /// Creates the event.
  const new({required this.n, required super.at})
    : super(subject: '', card: '');

  /// The old new-cards-per-day value.
  final int n;

  @override
  Json toJson() => {'k': 'new_cap', 'n': n, 'at': at};
}

/// `unchecked` (`src` read / free: taught without Claude) or `checked`
/// (Claude checked it): the fold's step 11, `README.md` "Fallback". Only the
/// worker writes them; the module gate waits while a card is unchecked.
class CheckMarkEvent extends LogEvent {
  /// Creates the event.
  const new({
    required super.subject,
    required super.card,
    required super.at,
    required this.unchecked,
    this.src,
  });

  /// `unchecked` when true, `checked` when false.
  final bool unchecked;

  /// Where an `unchecked` card was covered (`read` or `free`).
  final String? src;

  @override
  Json toJson() => compact({
    'k': unchecked ? 'unchecked' : 'checked',
    's': subject,
    'c': card,
    'at': at,
    'src': src,
  });
}
