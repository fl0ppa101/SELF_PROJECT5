from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class CustomMagnetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пользовательский магнит")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(100)
        self.moment_spin = QDoubleSpinBox()
        self.moment_spin.setDecimals(4)
        self.moment_spin.setRange(0.0001, 10)
        self.moment_spin.setValue(0.5)
        self.moment_spin.setSingleStep(0.01)
        self.moment_spin.setSuffix(" А·м²")
        form.addRow("Название", self.name_edit)
        form.addRow("Магнитный момент", self.moment_spin)
        layout.addLayout(form)
        self.hint = QLabel("")
        layout.addWidget(self.hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Создать")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if not self.name_edit.text().strip():
            self.hint.setText("Введите название магнита")
            self.name_edit.setFocus()
            return
        super().accept()
