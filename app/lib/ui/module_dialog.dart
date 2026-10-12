/// The "Edit module" dialog of the draft plan editor: title, summary, and
/// which earlier modules this one requires.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/model/plan.dart';

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
        title: const Text('Edit module'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: title,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              TextField(
                controller: summary,
                maxLength: 300,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Summary'),
              ),
              if (earlier.isNotEmpty) const SectionHeader('Requires'),
              for (final e in earlier)
                CheckboxListTile(
                  value: requires.contains(e.id),
                  title: Text(e.title),
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
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Done'),
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
