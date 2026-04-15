"""Package plain G-code into Bambu Lab .gcode.3mf files."""

from bambox.gcode_compat import is_bbl_gcode, translate_to_bbl
from bambox.pack import (
    FilamentInfo,
    ObjectInfo,
    SliceInfo,
    WarningInfo,
    fixup_project_settings,
    pack_gcode_3mf,
)
from bambox.validate import ValidationResult, validate_3mf

__all__ = [
    "fixup_project_settings",
    "is_bbl_gcode",
    "pack_gcode_3mf",
    "translate_to_bbl",
    "validate_3mf",
    "FilamentInfo",
    "ObjectInfo",
    "SliceInfo",
    "ValidationResult",
    "WarningInfo",
]
