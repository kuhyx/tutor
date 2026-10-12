/// Small widgets every screen shares: page width, pills, links, the PC
/// presence banner and a request's status line.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/relay/request_runner.dart';
import 'package:url_launcher/url_launcher.dart';

/// Widest a reading column gets on desktop.
const kPageMaxWidth = 760.0;

/// A centred, width-capped, scrolling column.
class PageList extends StatelessWidget {
  /// Creates the page.
  const new({required this.children, this.controller, super.key});

  /// Content.
  final List<Widget> children;

  /// Optional scroll controller.
  final ScrollController? controller;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: kPageMaxWidth),
      child: ListView(
        controller: controller,
        padding: const EdgeInsets.all(AppSpacing.md),
        children: children,
      ),
    ),
  );
}

/// A small rounded label (paused, stalled, archived...).
class Pill extends StatelessWidget {
  /// Creates the pill; [warn] uses the warning fill.
  const new(this.text, {this.warn = false, super.key});

  /// Label.
  final String text;

  /// Warning colour instead of the muted surface.
  final bool warn;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: warn ? AppPalette.warning : scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: AppTextSize.caption,
          color: warn ? AppPalette.onFill : scheme.onSurface,
        ),
      ),
    );
  }
}

/// Opens [url] in the browser; https only (DOCS-contract §10).
Future<void> openLink(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null || uri.scheme != 'https') return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

/// A text link that opens [url].
class LinkText extends StatelessWidget {
  /// Creates the link.
  const new(this.label, this.url, {super.key});

  /// Shown text.
  final String label;

  /// Target.
  final String url;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: () => openLink(url),
    child: Text(
      label,
      style: TextStyle(
        fontSize: AppTextSize.caption,
        decoration: TextDecoration.underline,
        color: Theme.of(context).colorScheme.primary,
      ),
    ),
  );
}

/// "PC offline: replies wait; reviews still work" while the PC is silent.
class PcOfflineBanner extends StatelessWidget {
  /// Creates the banner.
  const new(this.presence, {super.key});

  /// PC presence.
  final ValueNotifier<PcPresence> presence;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<PcPresence>(
    valueListenable: presence,
    builder: (context, value, _) => value != PcPresence.offline
        ? const SizedBox.shrink()
        : const Card(
            child: ListTile(
              leading: Icon(Icons.cloud_off),
              title: Text(pcOfflineText),
            ),
          ),
  );
}

/// The status of a [RequestRunner]'s last request: waiting, phase, error
/// with Retry (the same request), nothing once done.
class RequestStatusLine extends StatelessWidget {
  /// Creates the line.
  const new(this.runner, {this.queuedText, super.key});

  /// The runner.
  final RequestRunner runner;

  /// Text while queued (default: waiting for the PC).
  final String? queuedText;

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<RelayStatus?>(
    valueListenable: runner.status,
    builder: (context, s, _) {
      final (text, error) = switch (s) {
        null || RelayDone() => (null, false),
        RelayQueued() => (queuedText ?? 'Sent; waiting for the PC...', false),
        RelayWorking(:final phase) => (phaseText(phase), false),
        RelayNotSent(:final text) => (text, true),
        RelayFailed(:final text) => (text, true),
      };
      if (text == null) return const SizedBox.shrink();
      final scheme = Theme.of(context).colorScheme;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Row(
          children: [
            if (!error)
              const SizedBox.square(
                dimension: AppSpacing.md,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            if (!error) const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                text,
                style: TextStyle(color: error ? scheme.error : null),
              ),
            ),
            if (runner.canRetry)
              TextButton(onPressed: runner.retry, child: const Text('Retry')),
            if (error)
              IconButton(
                tooltip: 'Dismiss',
                onPressed: runner.clear,
                icon: const Icon(Icons.close),
              ),
          ],
        ),
      );
    },
  );
}
