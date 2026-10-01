import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
from hallsim.core.contracts import FieldGrid


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    app.processEvents()


@pytest.fixture
def asymmetric_grid():
    x, y = np.array([-20., 0., 20., 40.]), np.array([-10., 10., 30.])
    data = np.arange(12., dtype=float).reshape(3, 4)
    return FieldGrid(x, y, np.ones_like(data), np.zeros_like(data), data,
                     np.ones_like(data, dtype=bool), 0)
