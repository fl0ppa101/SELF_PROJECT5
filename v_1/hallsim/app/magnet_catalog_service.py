"""Keep Physics core unchanged; user-defined prototypes belong to the app."""
from dataclasses import asdict
import json
import math
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QStandardPaths
from hallsim.core.contracts import MagnetDefinition
from hallsim.core.magnet_catalog import MAGNET_CATALOG


class MagnetCatalogService:
    def __init__(self, path=None):
        data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        self.path = Path(path) if path is not None else data_dir / "custom_magnets.json"
        self._catalog = dict(MAGNET_CATALOG)
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
            for record in records:
                definition = MagnetDefinition(**record)
                if (not definition.is_builtin and definition.id.startswith("custom_")
                        and definition.display_name.strip() and math.isfinite(definition.moment_Am2)
                        and 1e-4 <= definition.moment_Am2 <= 10):
                    self._catalog[definition.id] = definition
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass

    def definitions(self):
        return dict(self._catalog)

    def create_custom(self, name, moment_Am2):
        name = name.strip()
        moment = float(moment_Am2)
        if not name:
            raise ValueError("Введите название магнита")
        if not math.isfinite(moment) or not 1e-4 <= moment <= 10:
            raise ValueError("Магнитный момент должен быть от 0.0001 до 10 А·м²")
        identifier = "custom_" + uuid4().hex
        definition = MagnetDefinition(identifier, name, moment, source_note="Пользовательский тип", is_builtin=False)
        catalog = {**self._catalog, identifier: definition}
        records = [asdict(item) for item in catalog.values() if not item.is_builtin]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self._catalog = catalog
        return identifier
