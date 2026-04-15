# ADR-003: Remove G-code Assembly and AMS Tool-Change Rewriting

**Status:** Accepted
**Date:** 2026-04-15

## Context

bambox included a G-code post-processing pipeline for CuraEngine output:

1. A multi-extruder CuraEngine printer definition (`bambox_p1s_ams`) that
   emitted `BAMBOX_ASSEMBLE=true` headers instead of real start/end G-code.
2. `assemble_cura_gcode()` which stripped those headers, rendered Jinja2
   start/end G-code templates, and stitched them around the toolpath.
3. `rewrite_tool_changes()` which replaced CuraEngine's bare `T0`/`T1`
   commands with full M620/M621 AMS flush sequences, computing per-transition
   purge volumes from `flush_volumes_matrix`.

This approach worked in testing but had two problems:

- **Safety risk.** The AMS tool-change sequences (nozzle flush, filament
  retract, temperature management, mechanical travel) were validated against
  generated G-code only — never on physical hardware with an AMS unit. An
  incorrect flush sequence, wrong Z height during travel, or bad retraction
  length could damage the printer or cause a filament jam.
- **Unnecessary complexity.** The native CuraEngine printer definition
  (`bambox_p1s`) embeds complete start/end G-code using CuraEngine's own
  `{variable}` substitution. No bambox post-processing is needed — the
  `translate_to_bbl()` pass in `pack_gcode_3mf()` handles firmware progress
  markers (M73/M991/HEADER_BLOCK) automatically.

## Decision

Remove the entire G-code assembly pipeline:

- Delete `bambox_p1s_ams` printer definition and its four extruder definitions.
- Delete `assemble_cura_gcode()`, `strip_bambox_header()`,
  `build_template_context()`, `max_layer_z()`, `first_layer_bbox()` from
  `cura.py`.
- Delete `rewrite_tool_changes()`, `_compute_flush_lengths()` from
  `gcode_compat.py`.
- Delete the P1S Jinja2 G-code templates (start, end, toolchange).
- Remove the `BAMBOX_ASSEMBLE` handling branch from the CLI.

Retain `parse_bambox_headers()` (harmless, still called by CLI for
auto-detection of machine/filament from G-code comments).

Retain `templates.py`, `assemble.py`, and their public API exports — they
are small, tested, and may serve future printer definitions.

## Consequences

- **Single-extruder only.** bambox supports one filament per print via the
  native CuraEngine definition. Multi-filament / AMS support is deferred.
- **No G-code rewriting.** The only G-code modification bambox performs is
  firmware marker injection (`translate_to_bbl()`), which is slicer-agnostic
  and well-tested.
- **Recovery path.** The tool-change rewriting code (flush volume math,
  pulsatile purge staging, per-transition context) is preserved in git
  history. When multi-filament support is revisited, it should be rebuilt
  with hardware-in-the-loop validation on a physical AMS unit.
