"""Cell widths, compact rows, tables, and scroll ranges without curses."""

from itertools import zip_longest
from typing import Iterable, List, Optional, Sequence, Tuple
from unicodedata import category, combining, east_asian_width

from .formatters import Entry, Field, Line, Panel, Sections, Table

Row = List[Line]
_GAP = "  "
_MIN_PANEL = 34
_FRAME = 4
_PREFERRED_VALUE = 32


def _cell(char: str) -> int:
    if combining(char) or category(char) in ("Mn", "Me"):
        return 0
    return 2 if east_asian_width(char) in ("W", "F") else 1


def cell_width(text: str) -> int:
    """Return the number of cells used by ordinary terminal text."""
    return sum(map(_cell, text))


def _clean(text: str) -> str:
    return "".join(
        char if category(char) not in ("Cc", "Cf", "Cs") else " "
        for char in text
    ).strip()


def _split(text: str, limit: int) -> Tuple[str, str]:
    """Break a line at a word boundary or at the last fitting cell."""
    used = end = 0
    for index, char in enumerate(text):
        used += _cell(char)
        if used > limit:
            break
        end = index + 1
    if end == len(text):
        return text, ""
    if end == 0:
        return "?", text[1:]
    space = text.rfind(" ", 0, end + 1)
    if space > 0:
        end = space
    return text[:end].rstrip(), text[end:].lstrip()


def wrap_lines(source: Iterable[Line], width: int) -> List[Line]:
    """Reflow terminal text and neutralize control characters."""
    if width <= 0:
        return []
    rows = []
    for line in source:
        text = _clean(line.text)
        while text:
            part, text = _split(text, width)
            rows.append(Line(part, line.tone))
    return rows


def pack_fields(source: Iterable[Line], width: int) -> List[Row]:
    """Share rows between fields and move a whole field when it fits alone."""
    rows: List[Row] = []
    row: Row = []
    used = 0
    for part in wrap_lines(source, width):
        size = cell_width(part.text)
        if row and used + len(_GAP) + size > width:
            rows.append(row)
            row = []
            used = 0
        if row:
            row.append(Line(_GAP))
            used += len(_GAP)
        row.append(part)
        used += size
    if row:
        rows.append(row)
    return rows


def _grow(sizes: List[int], desired: List[int], width: int) -> List[int]:
    """Share spare cells across columns up to their preferred sizes."""
    free = width - sum(sizes)
    while free > 0:
        growing = [
            index for index, size in enumerate(sizes) if size < desired[index]
        ]
        if not growing:
            break
        step = max(1, free // len(growing))
        for index in growing:
            increase = min(step, desired[index] - sizes[index], free)
            sizes[index] += increase
            free -= increase
    return sizes


def _natural_columns(
    labels: Tuple[str, ...], records: List[Tuple[str, ...]]
) -> List[int]:
    return [max(map(cell_width, column)) for column in zip(labels, *records)]


def _column_widths(
    labels: Tuple[str, ...],
    records: List[Tuple[str, ...]],
    width: int,
    *,
    compact: bool,
) -> Optional[List[int]]:
    """Fill the available width while keeping compact records readable."""
    sizes = list(map(cell_width, labels))
    room = width - len(_GAP) * (len(labels) - 1)
    desired = _natural_columns(labels, records)
    if room < sum(desired if compact else sizes):
        return None
    spare = room - sum(desired)
    if spare >= 0:
        return _stretch(desired, desired, spare)
    return _grow(sizes, desired, room)


def _table_record(values: Sequence[str], widths: List[int]) -> List[Row]:
    """Wrap each cell independently and align a record's continuation rows."""
    cells = [
        [part.text for part in wrap_lines((Line(value),), width)]
        for value, width in zip(values, widths)
    ]
    rows = []
    for row in zip_longest(*cells, fillvalue=""):
        key, *values = row
        padded = [key + " " * (widths[0] - cell_width(key))]
        padded.extend(
            " " * (width - cell_width(text)) + text
            for text, width in zip(values, widths[1:])
        )
        rows.append([Line(_GAP.join(padded).rstrip())])
    return rows


def _table(data: Table, width: int, *, compact: bool) -> List[Row]:
    """Use a shared header when the columns fit, or label fields per record."""
    records = [tuple(map(_clean, row)) for row in data.records]
    sizes = _column_widths(data.labels, records, width, compact=compact)
    if sizes is None:
        return [
            row
            for record in records
            for row in detail_rows(
                [
                    Field(label, value)
                    for label, value in zip(data.labels, record)
                ],
                width,
            )
        ]
    key, *labels = data.labels
    header = [Line(key, "column")]
    gap = len(_GAP) + sizes[0] - cell_width(key)
    for label, size in zip(labels, sizes[1:]):
        header.extend(_right_aligned(Line(label, "column"), size + gap))
        gap = len(_GAP)
    rows = [header]
    for record in records:
        rows.extend(_table_record(record, sizes))
    return rows


def detail_rows(
    entries: Sequence[Entry], width: int, *, compact: bool = False
) -> List[Row]:
    """Render aligned values, tables, and section headings."""
    rows = []
    for entry in entries:
        if isinstance(entry, Table):
            rows.extend(_table(entry, width, compact=compact))
        elif isinstance(entry, Field):
            rows.extend(_field_rows(entry, width))
        elif entry.tone == "title":
            rows.extend(_section_rule(entry.text, width, "accent"))
        else:
            rows.extend([line] for line in wrap_lines((entry,), width))
    return rows


def _right_aligned(part: Line, space: int) -> Row:
    return [Line(" " * (space - cell_width(part.text))), part]


def _field_rows(item: Field, width: int) -> List[Row]:
    """Wrap around the label and use the full width on continuation lines."""
    label = Line(_clean(item.label), item.tone)
    tone = item.tone or "value"
    value = _clean(item.value)
    value_width = cell_width(value)
    available = width - cell_width(label.text)
    inline = available - len(_GAP)
    first_word = cell_width(value.partition(" ")[0])

    if value_width <= inline or (value_width > width and first_word <= inline):
        first, value = _split(value, inline)
        rows = [[label, *_right_aligned(Line(first, tone), available)]]
    else:
        rows = [[line] for line in wrap_lines((label,), width)]
    continuation = wrap_lines((Line(value, tone),), width)
    rows.extend(_right_aligned(line, width) for line in continuation)
    return rows


def _section_rule(title: str, width: int, tone: str) -> List[Row]:
    """Center the title between rules or wrap it in a narrow panel."""
    room = width - cell_width(title)
    if room < 4:
        return [
            [Line(" " * ((width - cell_width(line.text)) // 2)), line]
            for line in wrap_lines((Line(title, tone),), width)
        ]
    left = (room - 2) // 2
    right = room - 2 - left
    return [[Line(f"{'─' * left} {title} {'─' * right}", tone)]]


def _card(panel: Panel, width: int) -> List[Row]:
    """Frame one panel at the available width and its actual content height."""
    if width < 6:
        return detail_rows(
            [Line(panel.title, panel.tone), *panel.entries], width
        )
    title, _ = _split(panel.title, width - 5)
    top = f"╭─ {title} "
    head = top + "─" * (width - cell_width(top) - 1) + "╮"
    rows = [[Line(head, panel.tone)]]
    body = detail_rows(panel.entries, width - _FRAME, compact=panel.compact)
    for row in body:
        padding = width - 3 - sum(cell_width(part.text) for part in row)
        rows.append(
            [
                Line("│ ", panel.tone),
                *row,
                Line(" " * padding),
                Line("│", panel.tone),
            ]
        )
    rows.append([Line("╰" + "─" * (width - 2) + "╯", panel.tone)])
    return rows


def _entry_width(entry: Entry) -> int:
    """Measure the preferred width before wrapping."""
    if isinstance(entry, Field):
        value = min(_PREFERRED_VALUE, cell_width(entry.value))
        return cell_width(entry.label) + len(_GAP) + value
    if isinstance(entry, Table):
        columns = _natural_columns(entry.labels, entry.records)
        return sum(columns) + len(_GAP) * (len(columns) - 1)
    return cell_width(entry.text)


def _minimum_width(panel: Panel) -> int:
    """Fit table headers and the trust meter in their panels."""
    heading = cell_width(panel.title) + 5
    if panel.compact:
        return heading
    headers = [
        sum(map(cell_width, entry.labels))
        + len(_GAP) * (len(entry.labels) - 1)
        for entry in panel.entries
        if isinstance(entry, Table)
    ]
    meter = 32 if panel.title == "REPUTATION" else 0
    return max(
        _MIN_PANEL,
        heading,
        max(headers + [meter]) + _FRAME,
    )


def _stretch(sizes: List[int], weights: List[int], spare: int) -> List[int]:
    """Allocate every spare cell in proportion to the column weights."""
    total = sum(weights)
    if spare == 0 or total == 0:
        return sizes
    widths = []
    seen = previous = 0
    for size, weight in zip(sizes, weights):
        seen += weight
        share = spare * seen // total
        widths.append(size + share - previous)
        previous = share
    return widths


def _grid_widths(panels: List[Panel], width: int) -> List[int]:
    """Fit minimum widths first, then assign all remaining terminal cells."""
    room = width - len(_GAP) * (len(panels) - 1)
    minima = [min(room, _minimum_width(panel)) for panel in panels]
    desired = []
    for panel, minimum in zip(panels, minima):
        natural = max(
            (_entry_width(entry) for entry in panel.entries), default=0
        )
        desired.append(max(minimum, natural + _FRAME))
    if sum(desired) <= room:
        return _stretch(desired, desired, room - sum(desired))
    deficits = [want - minimum for want, minimum in zip(desired, minima)]
    return _stretch(minima, deficits, room - sum(minima))


def _join_row(fragments: Tuple[Row, ...]) -> Row:
    """Place equally tall frame fragments side by side."""
    row: Row = []
    for fragment in fragments:
        row.extend(fragment)
        row.append(Line(_GAP))
    return row[:-1]


def _grid_row(panels: List[Panel], width: int) -> List[Row]:
    """Extend every frame to the height of the tallest in its row."""
    widths = _grid_widths(panels, width)
    cards = [_card(panel, span) for panel, span in zip(panels, widths)]
    height = max(map(len, cards))
    for card, span, panel in zip(cards, widths, panels):
        missing = height - len(card)
        if missing:
            border = Line("│", panel.tone)
            blank = [border, Line(" " * (span - 2)), border]
            card[-1:-1] = [blank] * missing
    return [_join_row(parts) for parts in zip(*cards)]


def _panel_rows(panels: List[Panel], width: int) -> List[List[Panel]]:
    """Wrap each panel onto the next row when its minimum does not fit."""
    groups: List[List[Panel]] = []
    group: List[Panel] = []
    remaining = width
    for panel in panels:
        size = width if panel.full_width else min(width, _minimum_width(panel))
        if size > remaining:
            groups.append(group)
            group = []
            remaining = width
        group.append(panel)
        remaining -= size + len(_GAP)
    if group:
        groups.append(group)
    return groups


def tab_body(view: Sections, tab: str, width: int) -> List[Row]:
    """Draw rows of panels across the full terminal width."""
    groups = _panel_rows(view[tab], width)
    if len(groups) > 1 and len(groups[-1]) == 1 and len(groups[-2]) > 2:
        previous, last = groups[-2:]
        pair = _minimum_width(previous[-1]) + _minimum_width(last[0])
        if not last[0].full_width and pair + len(_GAP) <= width:
            last.insert(0, previous.pop())
    return [row for panels in groups for row in _grid_row(panels, width)]


def page(
    rows: List[Row], height: int, offset: int
) -> Tuple[List[Row], int, int]:
    """Return the visible slice, clamped offset, and last scroll position."""
    last = max(0, len(rows) - height)
    start = min(last, max(0, offset))
    stop = start + height
    return rows[start:stop], start, last
