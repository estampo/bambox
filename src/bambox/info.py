"""Read printable metadata from an existing ``.gcode.3mf`` archive.

Returns structured ``PrintInfo`` for downstream consumers (CLIs, MCP servers,
cloud upload tools) without making them re-implement zip + XML + g-code header
parsing.

This module owns *reading* metadata from archives.  It must NOT contain
archive construction (lives in ``pack.py``), settings generation
(``settings.py``), validation logic (``validate.py``), or printer
communication.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO

# Layer count is parsed from the gcode header block.  BambuStudio writes
# "; total layer number: N"; older / Cura-style headers use ";LAYER_COUNT:N".
_RE_TOTAL_LAYERS = re.compile(r"; total layer number:\s*(\d+)")
_RE_LAYER_COUNT = re.compile(r";LAYER_COUNT:(\d+)")

# Only the gcode header carries the layer count — no need to read megabytes.
_HEADER_SCAN_BYTES = 4096


@dataclass
class Filament:
    """One filament referenced by a plate in the 3MF.

    ``id`` matches the ``id`` attribute on ``<filament>`` in
    ``Metadata/slice_info.config`` (1-indexed in BambuStudio output).
    ``color`` is the 6-character uppercase hex string with no leading ``#``.
    """

    id: int
    type: str
    color: str
    used_m: float
    used_g: float


@dataclass
class PrintInfo:
    """Metadata extracted from a ``.gcode.3mf`` archive."""

    time_seconds: int = 0
    weight_g: float = 0.0
    layers: int = 0
    bed_type: str | None = None
    printer_model_id: str = ""
    filaments: list[Filament] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """JSON-serializable representation."""
        return {
            "time_seconds": self.time_seconds,
            "weight_g": self.weight_g,
            "layers": self.layers,
            "bed_type": self.bed_type,
            "printer_model_id": self.printer_model_id,
            "filaments": [asdict(f) for f in self.filaments],
        }


def extract_print_info(path: Path) -> PrintInfo:
    """Read print metadata from a ``.gcode.3mf`` archive on disk.

    Returns a ``PrintInfo`` with sensible defaults for any fields that could
    not be read.  Raises ``zipfile.BadZipFile`` if the file is not a valid
    zip archive.
    """
    with open(path, "rb") as fh:
        return extract_print_info_buffer(fh)


def extract_print_info_buffer(buf: IO[bytes]) -> PrintInfo:
    """Read print metadata from a ``.gcode.3mf`` open file-like object."""
    info = PrintInfo()

    with zipfile.ZipFile(buf) as zf:
        slice_info = _safe_read_str(zf, "Metadata/slice_info.config")
        if slice_info is not None:
            _populate_from_slice_info(slice_info, info)

        project_settings = _safe_read_str(zf, "Metadata/project_settings.config")
        if project_settings is not None:
            info.bed_type = _extract_bed_type(project_settings)

        info.layers = _extract_layer_count(zf)

    return info


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_read_str(zf: zipfile.ZipFile, name: str) -> str | None:
    try:
        return zf.read(name).decode(errors="replace")
    except KeyError:
        return None


def _populate_from_slice_info(xml_str: str, info: PrintInfo) -> None:
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return
    plate = root.find("plate")
    if plate is None:
        return

    meta = {el.get("key", ""): el.get("value", "") for el in plate.findall("metadata")}
    info.printer_model_id = meta.get("printer_model_id", "")
    info.time_seconds = _safe_int(meta.get("prediction", "0"))
    info.weight_g = _safe_float(meta.get("weight", "0"))

    for f in plate.findall("filament"):
        fid = _safe_int(f.get("id", "0"))
        if fid <= 0:
            continue
        info.filaments.append(
            Filament(
                id=fid,
                type=f.get("type", ""),
                color=_normalize_color(f.get("color", "")),
                used_m=_safe_float(f.get("used_m", "0")),
                used_g=_safe_float(f.get("used_g", "0")),
            )
        )


def _extract_bed_type(raw: str) -> str | None:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    value = data.get("curr_bed_type")
    return value if isinstance(value, str) and value else None


def _extract_layer_count(zf: zipfile.ZipFile) -> int:
    """Return the layer count from the first plate gcode header, or 0."""
    gcode_name: str | None = None
    for name in zf.namelist():
        if name.startswith("Metadata/plate_") and name.endswith(".gcode"):
            gcode_name = name
            break
    if gcode_name is None:
        return 0
    try:
        head = zf.read(gcode_name)[:_HEADER_SCAN_BYTES].decode(errors="replace")
    except KeyError:
        return 0
    m = _RE_TOTAL_LAYERS.search(head) or _RE_LAYER_COUNT.search(head)
    return int(m.group(1)) if m else 0


def _normalize_color(raw: str) -> str:
    """Strip a leading ``#`` and uppercase, leaving an empty string untouched."""
    return raw.lstrip("#").upper()


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
