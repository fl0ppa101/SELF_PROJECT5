"""Numeric editors keep their unit suffix outside the editable selection."""

from PyQt6.QtWidgets import QDoubleSpinBox, QSpinBox


class _NumericCursor:
    def __init__(self, parent=None):
        super().__init__(parent)
        self._adjusting_cursor = False
        editor = self.lineEdit()
        editor.cursorPositionChanged.connect(self._keep_cursor_in_number)
        editor.selectionChanged.connect(self._keep_cursor_in_number)
        editor.textChanged.connect(self._keep_cursor_in_number)

    def _keep_cursor_in_number(self, *_):
        if self._adjusting_cursor:
            return
        editor = self.lineEdit()
        text = editor.text()
        suffix = self.suffix()
        if not suffix or not text.endswith(suffix):
            return
        start = len(self.prefix()) if text.startswith(self.prefix()) else 0
        end = max(start, len(text) - len(suffix))
        cursor = editor.cursorPosition()
        position = min(end, max(start, cursor))
        anchor = cursor
        if editor.hasSelectedText():
            anchor = (
                editor.selectionStart()
                if cursor == editor.selectionEnd()
                else editor.selectionEnd()
            )
        limited_anchor = min(end, max(start, anchor))
        if position == cursor and limited_anchor == anchor:
            return
        self._adjusting_cursor = True
        try:
            if position == limited_anchor:
                editor.setCursorPosition(position)
            else:
                editor.setSelection(limited_anchor, position - limited_anchor)
        finally:
            self._adjusting_cursor = False


class UnitDoubleSpinBox(_NumericCursor, QDoubleSpinBox):
    """Decimal input with a visible, non-editable unit suffix."""


class UnitSpinBox(_NumericCursor, QSpinBox):
    """Integer input with a visible, non-editable unit suffix."""
