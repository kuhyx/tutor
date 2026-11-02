/// The grid a predict drill is answered in: type the output cell by cell,
/// grow it with + and shrink it with -.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/sql/sql_models.dart';
import 'package:tutor/ui/sql/data_grid.dart';

const _maxRows = 60;
const _maxCols = 30;

/// Editable cells seeded from [initial] (at least 2 x 2); [onChanged]
/// gets the whole grid on every edit.
class PredictionGrid extends StatefulWidget {
  /// Creates the grid.
  const new({
    required this.initial,
    required this.onChanged,
    this.marked = const {},
    super.key,
  });

  /// Starting cells.
  final Grid initial;

  /// Called with the grid after each change.
  final ValueChanged<Grid> onChanged;

  /// Cells to flag after a check.
  final Set<(int, int)> marked;

  @override
  State<PredictionGrid> createState() => _PredictionGridState();
}

class _PredictionGridState extends State<PredictionGrid> {
  late final List<List<TextEditingController>> _cells = [
    for (final row in widget.initial) [for (final c in row) _controller(c)],
  ];

  @override
  void initState() {
    super.initState();
    while (_cells.length < 2) {
      _cells.add([]);
    }
    final cols = _cols < 2 ? 2 : _cols;
    for (final row in _cells) {
      while (row.length < cols) {
        row.add(_controller(''));
      }
    }
  }

  @override
  void dispose() {
    for (final row in _cells) {
      for (final c in row) {
        c.dispose();
      }
    }
    super.dispose();
  }

  int get _cols => _cells.fold(0, (n, r) => r.length > n ? r.length : n);

  TextEditingController _controller(String text) =>
      TextEditingController(text: text)..addListener(_emit);

  void _emit() => widget.onChanged([
    for (final row in _cells) [for (final c in row) c.text],
  ]);

  void _change(void Function() edit) {
    setState(edit);
    _emit();
  }

  void _discard(TextEditingController c) =>
      WidgetsBinding.instance.addPostFrameCallback((_) => c.dispose());

  void _removeRow() => _change(() => _cells.removeLast().forEach(_discard));

  void _removeColumn() => _change(() {
    for (final row in _cells) {
      _discard(row.removeLast());
    }
  });

  void _addRow() => _change(
    () => _cells.add([for (var i = 0; i < _cols; i++) _controller('')]),
  );

  void _addColumn() => _change(() {
    for (final row in _cells) {
      row.add(_controller(''));
    }
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    Widget cell(int r, int c) => Padding(
      padding: const EdgeInsets.all(AppSpacing.xs),
      child: TextField(
        key: ValueKey('cell-$r-$c'),
        controller: _cells[r][c],
        autocorrect: false,
        enableSuggestions: false,
        style: sqlMono,
        decoration: InputDecoration(
          isDense: true,
          border: const OutlineInputBorder(),
          enabledBorder: widget.marked.contains((r, c))
              ? const OutlineInputBorder(
                  borderSide: BorderSide(color: AppPalette.danger, width: 3),
                )
              : OutlineInputBorder(
                  borderSide: BorderSide(color: scheme.outline),
                ),
        ),
      ),
    );
    Widget step(Key key, IconData icon, VoidCallback? onTap) =>
        IconButton(key: key, onPressed: onTap, icon: Icon(icon));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Table(
                defaultColumnWidth: const FixedColumnWidth(104),
                children: [
                  for (var r = 0; r < _cells.length; r++)
                    TableRow(
                      children: [
                        for (var c = 0; c < _cells[r].length; c++) cell(r, c),
                      ],
                    ),
                ],
              ),
              Column(
                children: [
                  step(
                    const ValueKey('add-col'),
                    Icons.add,
                    _cols < _maxCols ? _addColumn : null,
                  ),
                  step(
                    const ValueKey('remove-col'),
                    Icons.remove,
                    _cols > 1 ? _removeColumn : null,
                  ),
                ],
              ),
            ],
          ),
        ),
        Row(
          children: [
            step(
              const ValueKey('add-row'),
              Icons.add,
              _cells.length < _maxRows ? _addRow : null,
            ),
            step(
              const ValueKey('remove-row'),
              Icons.remove,
              _cells.length > 1 ? _removeRow : null,
            ),
          ],
        ),
      ],
    );
  }
}
