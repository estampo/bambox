# CuraEngine + bambox: Printing on a Bambu P1S with AMS

This guide walks through using CuraEngine (the open-source slicer engine) with
bambox to produce printer-ready `.gcode.3mf` archives for the Bambu Lab P1S
with the AMS (Automatic Material System).

> **This workflow is experimental.** bambox generates G-code and firmware
> settings that talk directly to Bambu printer firmware. Incorrect settings
> can cause failed prints, nozzle clogs, or physical damage. Always review
> output before sending to hardware, and start with small test prints.

## Overview

Bambu printers only accept `.gcode.3mf` archives — not raw G-code. These
archives contain the G-code plus ~544 slicer settings, metadata, thumbnails,
and MD5 checksums. Normally OrcaSlicer or BambuStudio produces these archives,
but bambox can build them from any G-code source.

The workflow is:

```
CuraEngine  ──→  raw G-code  ──→  bambox pack  ──→  .gcode.3mf  ──→  printer
                (with BAMBOX         (assemble,        (ready to
                 headers)             settings,          print)
                                      package)
```

For multi-filament prints, bambox rewrites CuraEngine's bare tool change
commands (`T0`, `T1`, ...) into the M620/M621 AMS sequences that Bambu
firmware requires, and wraps the toolpath with machine-specific start/end
G-code templates.

## Prerequisites

- **CuraEngine** — the CLI slicer (not the Cura GUI). Install from your
  package manager or build from source:
  [github.com/Ultimaker/CuraEngine](https://github.com/Ultimaker/CuraEngine)
- **bambox** — `pip install bambox` or `uv pip install bambox`
- **Docker** or **bambox-bridge** — only needed if you want to send prints
  directly to the printer (see the main README for bridge setup)

## Step 1: Locate the Printer Definitions

bambox bundles CuraEngine printer definitions for the P1S with 4-slot AMS.
Find the definitions directory:

```bash
python -c "from bambox.cura import cura_definitions_dir; print(cura_definitions_dir())"
```

This prints a path like:

```
/path/to/site-packages/bambox/data/cura
```

That directory contains:

| File | Purpose |
|------|---------|
| `bambox_p1s_ams.def.json` | P1S machine definition (4 extruders, AMS) |
| `bambox_p1s_ams_extruder_0.def.json` | AMS slot 1 extruder definition |
| `bambox_p1s_ams_extruder_1.def.json` | AMS slot 2 extruder definition |
| `bambox_p1s_ams_extruder_2.def.json` | AMS slot 3 extruder definition |
| `bambox_p1s_ams_extruder_3.def.json` | AMS slot 4 extruder definition |

The machine definition injects `BAMBOX_*` headers into the G-code start
section. These headers tell `bambox pack` how to process the output —
which machine, which filaments, and whether to assemble start/end G-code
from templates.

## Step 2: Slice with CuraEngine

### Single filament

```bash
CuraEngine slice \
  -j "$(python -c 'from bambox.cura import cura_definitions_dir; print(cura_definitions_dir())')/bambox_p1s_ams.def.json" \
  -o plate_1.gcode \
  -s material_print_temperature=220 \
  -s material_bed_temperature_layer_0=60 \
  -s material_type=PLA \
  -l model.stl
```

### Multi-filament (AMS)

For multi-filament prints, use CuraEngine's `-e` flag to configure each
extruder and assign STL objects to extruders with `-e N`:

```bash
DEFS="$(python -c 'from bambox.cura import cura_definitions_dir; print(cura_definitions_dir())')"

CuraEngine slice \
  -j "$DEFS/bambox_p1s_ams.def.json" \
  -o plate_1.gcode \
  -e0 -s material_print_temperature=220 -s material_type=PLA \
  -e1 -s material_print_temperature=230 -s material_type=PETG \
  -e0 -l body.stl \
  -e1 -l accent.stl
```

CuraEngine emits `T0` / `T1` commands in the toolpath for tool changes.
bambox will rewrite these into proper M620/M621 AMS sequences during packing.

## Step 3: Pack with bambox

### Single filament

```bash
bambox pack plate_1.gcode -o output.gcode.3mf
```

When the G-code contains BAMBOX headers (from the bundled printer definition),
bambox auto-detects the machine and filament type. You can also specify
explicitly:

```bash
bambox pack plate_1.gcode -o output.gcode.3mf -m p1s -f PLA
```

### Multi-filament

```bash
bambox pack plate_1.gcode -o output.gcode.3mf -m p1s \
  -f 1:PLA:#FF0000 \
  -f 2:PETG:#2850E0
```

The `-f` flag accepts `[SLOT:]TYPE[:COLOR]`:

| Format | Meaning |
|--------|---------|
| `PLA` | PLA in the next available slot |
| `2:PETG` | PETG in AMS slot 2 |
| `1:PLA:#FF0000` | Red PLA in AMS slot 1 |
| `PETG-CF:#2850E0` | Blue PETG-CF in the next slot |

Slots are 1-indexed (matching the AMS tray numbers on the printer).

### What happens during packing

When `BAMBOX_ASSEMBLE=true` is set in the G-code headers (which it is with
the bundled printer definitions), `bambox pack` does the following:

1. **Strips the BAMBOX header block** from the raw G-code, leaving just the
   toolpath
2. **Rewrites tool changes** — bare `T0`/`T1` commands become M620/M621
   sequences with temperature management, filament retraction, and purge
   cycles
3. **Renders start/end templates** — machine-specific initialization
   (homing, bed leveling, nozzle cleaning) and shutdown sequences
4. **Assembles the full G-code** — start template + rewritten toolpath +
   end template
5. **Generates 544-key project settings** — the `project_settings.config`
   that Bambu firmware requires, built from machine and filament profiles
6. **Packages the archive** — creates the `.gcode.3mf` ZIP with metadata,
   thumbnails, and MD5 checksums

## Step 4: Validate (recommended)

Before sending to the printer, validate the archive:

```bash
bambox validate output.gcode.3mf
```

This checks for common issues: missing metadata, incorrect checksums,
temperature ranges, tool change sequences, and more.

For CI pipelines:

```bash
bambox validate output.gcode.3mf --json --strict
```

## Step 5: Print (optional)

If you have the bridge set up, send directly to the printer:

```bash
# By device serial
bambox print output.gcode.3mf -d YOUR_SERIAL

# By named printer (from bambox login)
bambox print output.gcode.3mf -p my_p1s

# Dry run first — shows AMS mapping without sending
bambox print output.gcode.3mf -d YOUR_SERIAL -n
```

Or transfer the `.gcode.3mf` to the printer via SD card, Bambu Handy, or
BambuStudio's network send.

## Supported Filament Types

bambox includes profiles for common filament types. Use these names with `-f`:

| Type | Description |
|------|-------------|
| `PLA` | Standard PLA |
| `PLA-CF` | Carbon fiber PLA |
| `PETG` | Standard PETG |
| `PETG-CF` | Carbon fiber PETG |
| `ABS` | ABS |
| `ASA` | ASA |
| `TPU` | TPU flexible |
| `PA` | Nylon / Polyamide |
| `PA-CF` | Carbon fiber nylon |
| `PC` | Polycarbonate |
| `PVA` | PVA support material |

Run `bambox pack --help` for the full list.

## Troubleshooting

### "Bare tool command outside M620/M621 block"

This validation warning means the G-code has a `T` command that isn't wrapped
in the AMS sequence. If you're using the bambox printer definitions with
`BAMBOX_ASSEMBLE=true`, tool changes are rewritten automatically. If you see
this on bambox-generated archives, it's likely a harmless initial extruder
select — update to the latest bambox version.

### Settings not accepted by printer

Bambu firmware is strict about `project_settings.config`. If the printer
rejects an archive, try `bambox repack` to regenerate settings:

```bash
bambox repack output.gcode.3mf -m p1s -f PLA
```

### CuraEngine not finding definitions

Make sure you pass the full path to the `.def.json` file with `-j`, not
just the machine name. CuraEngine resolves extruder definitions relative to
the definition file's directory.

## Python API

For scripting or integration into other tools:

```python
from pathlib import Path
from bambox.cura import (
    cura_definitions_dir,
    parse_bambox_headers,
    build_template_context,
    extract_slice_stats,
)
from bambox.gcode_compat import rewrite_tool_changes
from bambox.templates import render_template
from bambox.assemble import assemble_gcode
from bambox.settings import build_project_settings
from bambox.pack import pack_gcode_3mf, SliceInfo, FilamentInfo

# After slicing with CuraEngine...
gcode = Path("plate_1.gcode").read_text()
headers = parse_bambox_headers(gcode)

# Build settings
settings = build_project_settings(
    filaments=["PLA", "PETG"],
    machine="p1s",
)

# Rewrite tool changes and assemble
from bambox.cura import strip_bambox_header
toolpath = strip_bambox_header(gcode)
toolpath = rewrite_tool_changes(toolpath, settings, "p1s")

ctx = build_template_context(headers, settings)
start = render_template("p1s_start.gcode.j2", ctx)
end = render_template("p1s_end.gcode.j2", ctx)
final_gcode = assemble_gcode(start, toolpath, end)

# Package
info = SliceInfo(
    nozzle_diameter=0.4,
    filaments=[
        FilamentInfo(filament_type="PLA", color="FF0000"),
        FilamentInfo(filament_type="PETG", color="2850E0"),
    ],
)
pack_gcode_3mf(
    final_gcode.encode(),
    Path("output.gcode.3mf"),
    slice_info=info,
    project_settings=settings,
)
```
