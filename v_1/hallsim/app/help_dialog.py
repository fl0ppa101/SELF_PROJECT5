from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Справка HallSim")
        self.resize(720, 560)
        self.setMinimumSize(620, 480)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._page(self._quick_start()), "Быстрый старт")
        tabs.addTab(self._page(self._controls()), "Управление")
        tabs.addTab(self._page(self._sensor()), "Датчик Холла")
        tabs.addTab(self._page(self._about()), "О программе")
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def _page(html: str) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        browser.setFrameShape(QTextBrowser.Shape.NoFrame)
        return browser

    @staticmethod
    def _quick_start() -> str:
        return """
        <h2>Быстрый старт</h2>
        <ol>
          <li>Выберите тип магнита и задайте его координаты и угол.</li>
          <li>Перемещайте магнит за корпус, а вращайте за появившуюся ручку.</li>
          <li>Разместите датчик Холла в нужной точке.</li>
          <li>Включите нужные слои: тепловую карту, линии поля или сетку.</li>
          <li>Для графика выберите инструмент пути и задайте точки A и B.</li>
        </ol>
        <p>Все изменения магнитов пересчитываются автоматически. Во время движения
        используется облегчённая сетка, после отпускания — полная.</p>
        <h3>Пресеты</h3>
        <p>Доступны один магнит, два магнита одноимёнными полюсами и два магнита
        разноимёнными полюсами.</p>
        """

    @staticmethod
    def _controls() -> str:
        return """
        <h2>Управление</h2>
        <h3>Карта</h3>
        <ul>
          <li><b>Левая кнопка:</b> выбор и перемещение объекта.</li>
          <li><b>Средняя кнопка:</b> перемещение камеры.</li>
          <li><b>Колесо:</b> изменение масштаба.</li>
          <li><b>Ручка выбранного объекта:</b> вращение.</li>
        </ul>
        <h3>Горячие клавиши</h3>
        <ul>
          <li><b>R:</b> вернуть исходный вид карты.</li>
          <li><b>Esc:</b> отменить выбор точек пути.</li>
        </ul>
        <p>Рабочая область: X от −80 до +80 мм, Y от −50 до +50 мм.</p>
        """

    @staticmethod
    def _sensor() -> str:
        return """
        <h2>Датчик Холла</h2>
        <p>Угол датчика задаёт направление его <b>положительной чувствительной оси</b>.
        Показание является проекцией вектора магнитной индукции на эту ось, поэтому
        оно может быть положительным, отрицательным или близким к нулю.</p>
        <h3>Режимы ориентации</h3>
        <ul>
          <li><b>AUTO:</b> кнопка «Выровнять по полю» направляет чувствительную ось вдоль B.</li>
          <li><b>MANUAL:</b> угол задаётся пользователем. Ручное вращение автоматически
          включает этот режим.</li>
        </ul>
        <p>Магнитная индукция отображается в милли-теслах (мТл), координаты — в миллиметрах.</p>
        """

    @staticmethod
    def _about() -> str:
        return """
        <h2>HallSim</h2>
        <p>Учебное офлайн-приложение для исследования двумерного магнитного поля
        одного или двух постоянных магнитов и показаний виртуального датчика Холла.</p>
        <p>Стек: Python 3.11+, PyQt6, PyQtGraph и NumPy.</p>
        <p>Физические расчёты, интерфейс и визуализация разделены на независимые модули.</p>
        """
