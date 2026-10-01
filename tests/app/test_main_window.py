from PyQt6.QtCore import Qt

from hallsim.app.controller import AppController
from hallsim.app.main_window import MainWindow


def test_main_window_starts_with_bound_scene(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)

    assert window.windowTitle() == "HallSim"
    assert len(window.control_panel._cards) == 1
    assert window.control_panel.heatmap_check.isChecked()
    assert window.control_panel.lines_check.isChecked()
    assert not window.control_panel.grid_check.isChecked()


def test_add_magnet_updates_panel(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)

    controller.add_magnet()

    assert len(window.control_panel._cards) == 2
    assert not window.control_panel.add_button.isEnabled()


def test_theme_switch_does_not_change_scene_revision(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)

    controller.set_theme("dark")

    assert controller.theme == "dark"
    assert controller.scene().revision == 0
    assert window.theme_switch.theme == "dark"


def test_help_button_opens_help_dialog(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.help_button, Qt.MouseButton.LeftButton)

    assert window._help_dialog is not None
    assert window._help_dialog.isVisible()


def test_visible_window_finishes_theme_transition(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)
    window.show()

    controller.set_theme("dark")
    qtbot.wait(350)

    assert window.theme_switch.theme == "dark"
    assert window._theme_overlay is None


def test_analysis_and_settings_navigation_is_enabled(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)

    qtbot.mouseClick(window.nav_buttons[1], Qt.MouseButton.LeftButton)
    assert window.page_stack.currentWidget() is window.analysis_page

    qtbot.mouseClick(window.nav_buttons[2], Qt.MouseButton.LeftButton)
    assert window.page_stack.currentWidget() is window.settings_page


def test_settings_page_updates_scene_without_physics_revision(qtbot):
    controller = AppController()
    window = MainWindow(controller)
    qtbot.addWidget(window)

    window.settings_page.normalization.setCurrentIndex(1)

    assert controller.scene().view.normalization.name == "LOG"
    assert controller.scene().revision == 0
