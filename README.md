# HallSim

Интерактивное настольное приложение для исследования магнитного поля постоянных магнитов и показаний виртуального датчика Холла.

## Текущий этап

Реализован первый вертикальный срез GUI:

- PyQt6 `MainWindow` по согласованному макету;
- светлая и тёмная темы;
- анимированный переключатель и плавный переход между темами;
- встроенная справка по управлению и датчику Холла;
- рабочая вкладка «Анализ» с настройкой пути A-B и отдельным графиком;
- рабочая вкладка «Настройки» с нормализацией и цветовым диапазоном;
- локальное восстановление темы, геометрии окна и последней сцены;
- единые контракты `hallsim.core` в миллиметрах и мТл;
- `SceneState` и `AppController`;
- один или два магнита;
- панель датчика AUTO/MANUAL;
- три пресета;
- сворачиваемая область графика A-B;
- mock Canvas и mock calculation service;
- адаптер для подключения `hallsim.visualization.FieldCanvas` и `PathProfilePlot`;
- защита интерфейса от прямой зависимости от Physics/Visualization.

Mock-компоненты нужны только для независимой разработки GUI и не содержат физической модели.

## Запуск

Требуется Python 3.11 или новее.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
```

В Windows используйте `.venv\Scripts\python.exe` вместо `.venv/bin/python`.

## Тесты

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

Переменная `QT_QPA_PLATFORM` нужна только для headless-запуска на Linux.

## Подключение визуализации

Когда появятся модули:

```text
hallsim.visualization.field_canvas.FieldCanvas
hallsim.visualization.path_plot.PathProfilePlot
```

фабрики в `hallsim.app.visualization_bridge` автоматически будут использовать их вместо mock-компонентов.

`FieldCanvas` должен реализовать методы:

```text
set_scene
set_field_grid
set_sensor_reading
set_theme
set_interaction_quality
reset_view
```

и сигналы из `03_VISUALIZATION_TZ_v2.md`. Все координаты передаются в миллиметрах.

## Ограничения

- GUI не содержит физических формул.
- GUI поддерживает максимум два магнита.
- Physics и Visualization используют общие типы из `hallsim.core`.
- PySide6 в проекте не используется.
