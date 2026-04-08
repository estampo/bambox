"""CuraEngine integration: printer definitions and BAMBOX header parsing.

Provides bundled CuraEngine printer definitions with BAMBOX header comments
that bambox reads to auto-configure packaging. The header contract lets
CuraEngine output carry machine-readable metadata without coupling the
slicer to Bambu Lab specifics.

Header format (emitted as G-code comments by the printer definition)::

    ; BAMBOX_PRINTER=p1s
    ; BAMBOX_EXTRUDERS=4
    ; BAMBOX_BED_TEMP=60
    ; BAMBOX_NOZZLE_TEMP=220
    ; BAMBOX_FILAMENT_SLOT=0
    ; BAMBOX_FILAMENT_TYPE=PLA
    ; BAMBOX_ASSEMBLE=true
    ; BAMBOX_END
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Printer definitions
# ---------------------------------------------------------------------------

_CURA_DIR = Path(__file__).parent / "data" / "cura"


def cura_definitions_dir() -> Path:
    """Return the path to bundled CuraEngine definition files.

    Pass this to CuraEngine's ``-d`` flag so it can resolve
    ``bambox_p1s_ams`` and its extruder definitions.
    """
    return _CURA_DIR


def available_cura_printers() -> list[str]:
    """Return names of bundled CuraEngine printer definitions."""
    return [
        p.name.removesuffix(".def.json")
        for p in sorted(_CURA_DIR.glob("*.def.json"))
        if "extruder" not in p.name
    ]


# ---------------------------------------------------------------------------
# BAMBOX header parsing
# ---------------------------------------------------------------------------


def parse_bambox_headers(gcode: str) -> dict[str, str]:
    """Extract ``; BAMBOX_*`` headers from G-code.

    Returns a dict of key→value pairs. Stops at ``; BAMBOX_END`` or after
    the first 200 lines (headers are always at the top).

    Multi-value keys like ``BAMBOX_FILAMENT_TYPE`` appearing multiple times
    are collected into comma-separated values.
    """
    result: dict[str, str] = {}
    for i, line in enumerate(gcode.splitlines()):
        if i > 200:
            break
        stripped = line.strip()
        if stripped == "; BAMBOX_END":
            break
        if stripped.startswith("; BAMBOX_"):
            # "; BAMBOX_KEY=value" → ("KEY", "value")
            payload = stripped[9:]  # after "; BAMBOX_"
            if "=" in payload:
                key, _, val = payload.partition("=")
                key = key.strip()
                val = val.strip()
                if key in result:
                    result[key] = result[key] + "," + val
                else:
                    result[key] = val
    return result
