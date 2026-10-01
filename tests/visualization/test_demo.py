import numpy as np
from hallsim.core.enums import ColorRangeMode, FieldNormalization
from hallsim.visualization.demo import DemoWindow


def test_standalone_controls_and_no_physics_dependency(qapp):
    import sys
    window = DemoWindow(show_path=True)
    window.show()
    qapp.processEvents()
    assert not any(name.startswith("hallsim.physics") for name in sys.modules)
    window.scenario_combo.setCurrentIndex(1)
    assert len(window.scene.magnets) == 2
    assert not window.scene.path.enabled
    window.normalization.setCurrentText("Log")
    window.range_mode.setCurrentIndex(2)
    window.manual_min.setValue(.1)
    window.manual_max.setValue(30)
    assert window.scene.view.normalization == FieldNormalization.LOG
    assert window.scene.view.color_range_mode == ColorRangeMode.MANUAL
    assert window.canvas.heatmap.scale.minimum == .1
    assert window.canvas.heatmap.scale.maximum == 30
    window.object_combo.setCurrentIndex(0)
    window.x_spin.setValue(-22)
    window.angle_spin.setValue(45)
    assert window.scene.magnets[0].x_mm == -22
    assert window.scene.magnets[0].angle_deg == 45
    window.toggle_theme()
    assert window.canvas.theme_name == window.path_plot.theme_name == "dark"
    window.layer_boxes["show_heatmap"].setChecked(False)
    assert not window.canvas.heatmap.image.isVisible()
    window.close()
    qapp.processEvents()
