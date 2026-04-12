"""Shared test fixtures and constants for bambox tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal valid 3MF archive data
# ---------------------------------------------------------------------------

MINIMAL_GCODE = """\
; HEADER_BLOCK_START
; total layer number: 3
; total estimated time: 2m 30s
; HEADER_BLOCK_END
M73 P0 R2
;LAYER_CHANGE
;Z:0.2
;HEIGHT:0.2
M73 L1
M991 S0 P1
M73 P33 R2
G1 X10 Y10 E1 F600
;LAYER_CHANGE
;Z:0.4
;HEIGHT:0.2
M73 L2
M991 S0 P2
M73 P66 R1
G1 X20 Y20 E2 F600
;LAYER_CHANGE
;Z:0.6
;HEIGHT:0.2
M73 L3
M991 S0 P3
M73 P100 R0
G1 X30 Y30 E3 F600
"""

MINIMAL_SLICE_INFO = """\
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value=""/>
  </header>
  <plate>
    <metadata key="index" value="1"/>
    <metadata key="printer_model_id" value="C12"/>
    <metadata key="nozzle_diameters" value="0.4"/>
    <metadata key="prediction" value="150"/>
    <metadata key="weight" value="5.00"/>
    <metadata key="outside" value="false"/>
    <metadata key="support_used" value="false"/>
    <metadata key="label_object_enabled" value="true"/>
    <metadata key="timelapse_type" value="0"/>
    <metadata key="filament_maps" value="1"/>
    <filament id="1" tray_info_idx="GFL99" type="PLA" color="#F2754E" used_m="1.00" used_g="3.00" />
  </plate>
</config>
"""

MINIMAL_SETTINGS = json.dumps(
    {
        "filament_type": ["PLA", "PLA", "PLA", "PLA", "PLA"],
        "filament_colour": ["#F2754E", "#F2754E", "#F2754E", "#F2754E", "#F2754E"],
        "nozzle_temperature": ["220", "220", "220", "220", "220"],
        "nozzle_temperature_initial_layer": ["220", "220", "220", "220", "220"],
        "bed_temperature": ["60", "60", "60", "60", "60"],
        "filament_max_volumetric_speed": ["12", "12", "12", "12", "12"],
    }
)


def build_valid_3mf(
    tmp_path: Path,
    gcode: str = MINIMAL_GCODE,
    slice_info: str = MINIMAL_SLICE_INFO,
    settings: str = MINIMAL_SETTINGS,
) -> Path:
    """Build a minimal valid .gcode.3mf for testing."""
    out = tmp_path / "test.gcode.3mf"
    gcode_bytes = gcode.encode()
    md5 = hashlib.md5(gcode_bytes).hexdigest().upper()

    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("_rels/.rels", "<Relationships/>")
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode_bytes)
        zf.writestr("Metadata/plate_1.gcode.md5", md5)
        zf.writestr("Metadata/model_settings.config", "{}")
        zf.writestr("Metadata/_rels/model_settings.config.rels", "<Relationships/>")
        zf.writestr("Metadata/slice_info.config", slice_info)
        zf.writestr("Metadata/project_settings.config", settings)
        zf.writestr("Metadata/plate_1.json", "{}")
        zf.writestr("Metadata/plate_1.png", b"\x89PNG\r\n\x1a\n")
        zf.writestr("Metadata/plate_no_light_1.png", b"\x89PNG\r\n\x1a\n")
        zf.writestr("Metadata/plate_1_small.png", b"\x89PNG\r\n\x1a\n")
        zf.writestr("Metadata/top_1.png", b"\x89PNG\r\n\x1a\n")
        zf.writestr("Metadata/pick_1.png", b"\x89PNG\r\n\x1a\n")
    return out
