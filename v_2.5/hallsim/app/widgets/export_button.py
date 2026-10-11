from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMenu, QMessageBox, QToolButton


class ExportButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Экспорт…")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setMenu(QMenu(self))
        self.directory = ""

    def add_export(self, label, extension, name, prepare):
        action = self.menu().addAction(label)
        action.triggered.connect(lambda: self._export(extension, name, prepare))
        return action

    def _export(self, extension, name, prepare):
        try:
            writer = prepare()
            dialog = QFileDialog(self, "Экспорт")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setDefaultSuffix(extension)
            dialog.setNameFilter(
                f"{'Книга Excel' if extension == 'xlsx' else 'Изображение PNG'} (*.{extension})"
            )
            if self.directory:
                dialog.setDirectory(self.directory)
            dialog.selectFile(
                f"hallsim_{name}_{datetime.now():%Y%m%d_%H%M%S}.{extension}"
            )
            if dialog.exec() != QFileDialog.DialogCode.Accepted:
                return
            destination = Path(dialog.selectedFiles()[0])
            writer(destination)
            self.directory = str(destination.parent)
            QMessageBox.information(
                self, "Экспорт завершён", f"Файл сохранён:\n{destination}"
            )
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Не удалось экспортировать", str(exc))
