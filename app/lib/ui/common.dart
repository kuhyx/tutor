/// Small widgets every screen shares: page width, links, and (re-exported)
/// the pills and a request's status cue.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/ui/fit_pages.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:url_launcher/url_launcher.dart';

export 'package:tutor/ui/pills.dart';
export 'package:tutor/ui/request_status.dart';

/// Widest a reading column gets on desktop.
const kPageMaxWidth = 760.0;

/// A centred, width-capped, scrolling column.
class PageList extends StatelessWidget {
  /// Creates the page.
  const new({required this.children, this.controller, super.key});

  /// Content; on a phone ([isCompact]) shown a page at a time, never
  /// scrolled.
  final List<Widget> children;

  /// Optional scroll controller.
  final ScrollController? controller;

  @override
  Widget build(BuildContext context) => isCompact(context)
      ? SafeArea(
          top: false,
          child: FitPages(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: children,
          ),
        )
      : Align(
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

/// Opens [url] in the browser; https only (DOCS-contract §10).
Future<void> openLink(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null || uri.scheme != 'https') return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

/// A text link that opens [url]; [label] is content (a host, a licence).
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
    child: ContentText(
      label,
      style: TextStyle(
        fontSize: AppTextSize.caption,
        decoration: TextDecoration.underline,
        color: Theme.of(context).colorScheme.primary,
      ),
    ),
  );
}
