from .contracts import MagnetDefinition


# Магнитные моменты — приближённые значения в А·м².
MAGNET_CATALOG = {
    "ferrite_y35": MagnetDefinition(
        id="ferrite_y35",
        display_name="Феррит Y35",
        moment_Am2=0.386747,
        material="Ferrite",
        grade="Y35",
    ),
    "ndfeb_n42": MagnetDefinition(
        id="ndfeb_n42",
        display_name="Неодим N42 (средний)",
        moment_Am2=1.038486,
        material="NdFeB",
        grade="N42",
    ),
    "ndfeb_n52": MagnetDefinition(
        id="ndfeb_n52",
        display_name="Неодим N52 (сильный)",
        moment_Am2=4.967544,
        material="NdFeB",
        grade="N52",
    ),
}
