from .contracts import MagnetDefinition


BUILTIN_MAGNETS: dict[str, MagnetDefinition] = {
    "ferrite": MagnetDefinition(
        id="ferrite",
        display_name="Ферритовый",
        moment_Am2=0.08,
        material="Ferrite",
        source_note="Учебный прототип",
    ),
    "ndfeb_medium": MagnetDefinition(
        id="ndfeb_medium",
        display_name="Неодимовый, средний",
        moment_Am2=0.35,
        material="NdFeB",
        grade="N35",
        source_note="Учебный прототип",
    ),
    "ndfeb_strong": MagnetDefinition(
        id="ndfeb_strong",
        display_name="Неодимовый, сильный",
        moment_Am2=0.8,
        material="NdFeB",
        grade="N52",
        source_note="Учебный прототип",
    ),
}
