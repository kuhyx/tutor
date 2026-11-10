/// The "Edit module" dialog of the draft plan editor: title, summary, and
/// which earlier modules this one requires.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';
import 'package:tutor/ui/learn_tiles.dart';
import 'package:tutor/widgets/content_text.dart';
import 'package:tutor/widgets/icon_field.dart';
import 'package:tutor/widgets/spoken_label.dart';

/// What the dialog returns on Done.
typedef ModuleEdit = ({String title, String summary, List<String> requires});

/// Asks for [m]'s new title, summary and requires (from [earlier] only);
/// null on Cancel.
Future<ModuleEdit?> editModuleDialog(
  BuildContext context,
  Module m,
  List<Module> earlier,
) async {
  final title = TextEditingController(text: m.title);
  final summary = TextEditingController(text: m.summary);
  final requires = {...m.requires};
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => StatefulBuilder(
      builder: (context, setLocal) => AlertDialog(
        semanticLabel: 'Edit module',
        icon: const Icon(Icons.edit),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              FieldLabel(
                semanticLabel: 'Title',
                child: TextField(
                  controller: title,
                  autofocus: true,
                  decoration: iconDecoration(Icons.title),
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              FieldLabel(
                semanticLabel: 'Summary',
                child: TextField(
                  controller: summary,
                  maxLength: 300,
                  maxLines: 3,
                  decoration: iconDecoration(Icons.notes),
                ),
              ),
              if (earlier.isNotEmpty)
                const LearnHeader(Icons.account_tree_outlined, 'Requires'),
              for (final e in earlier)
                CheckboxListTile(
                  value: requires.contains(e.id),
                  title: ContentText(e.title),
                  onChanged: (on) => setLocal(() {
                    if (on ?? false) {
                      requires.add(e.id);
                    } else {
                      requires.remove(e.id);
                    }
                  }),
                ),
            ],
          ),
        ),
        actions: [
          GlyphButton(
            icon: Icons.close,
            semanticLabel: 'Cancel',
            onPressed: () => Navigator.pop(context, false),
          ),
          GlyphButton(
            icon: Icons.check,
            semanticLabel: 'Done',
            filled: true,
            onPressed: () => Navigator.pop(context, true),
          ),
        ],
      ),
    ),
  );
  if (!(ok ?? false)) return null;
  return (
    title: title.text,
    summary: summary.text,
    requires: [
      for (final e in earlier)
        if (requires.contains(e.id)) e.id,
    ],
  );
}
