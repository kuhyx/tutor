/// Pictures and diagrams in a tutor message (DOCS-contract §8): Commons
/// thumbnails loaded only from upload.wikimedia.org, always with
/// "author · licence" linked to the Commons page (attribution stays even
/// when the picture fails to load); worker-drawn SVG rendered inline.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/common.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// One Commons picture with its attribution.
class CommonsFigure extends StatelessWidget {
  /// Creates the figure.
  const new(this.img, {super.key});

  /// The picture.
  final Img img;

  @override
  Widget build(BuildContext context) {
    final caption = Theme.of(context).textTheme.bodySmall;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (img.loadable)
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 360),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(AppRadius.sm),
                child: Image.network(
                  img.url,
                  semanticLabel: img.title,
                  fit: BoxFit.contain,
                  errorBuilder: (context, error, stack) => SpokenLabel(
                    semanticLabel: 'Picture did not load: ${img.title}',
                    child: Icon(
                      Icons.broken_image_outlined,
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              ),
            ),
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.xs,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              // Attribution is the picture's own metadata: content.
              ContentText('${img.title} - ${img.author} ·', style: caption),
              ContentScope(
                child: LinkText(img.licence, img.licenceUrl ?? img.pageUrl),
              ),
              Text('·', style: caption),
              GlyphButton(
                icon: Icons.open_in_new,
                semanticLabel: 'Wikimedia Commons',
                onPressed: () => openLink(img.pageUrl),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// A worker-drawn diagram.
class DiagramView extends StatelessWidget {
  /// Creates the view.
  const new(this.diagram, {super.key});

  /// The diagram.
  final Dgm diagram;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          color: AppPalette.paperRaised,
          padding: const EdgeInsets.all(AppSpacing.sm),
          constraints: const BoxConstraints(maxHeight: 320),
          child: SvgPicture.string(
            diagram.svg,
            semanticsLabel: diagram.title,
            errorBuilder: (context, error, stack) => SpokenLabel(
              semanticLabel: 'Diagram could not be drawn.',
              child: Icon(
                Icons.broken_image_outlined,
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ),
        ),
        Row(
          children: [
            const SpokenLabel(
              semanticLabel: 'drawn by code (schemdraw)',
              child: Icon(Icons.draw_outlined, size: AppTextSize.label),
            ),
            const SizedBox(width: AppSpacing.xs),
            Expanded(
              child: ContentText(
                diagram.title,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ],
    ),
  );
}
