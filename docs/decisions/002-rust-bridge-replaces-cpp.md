# ADR-002: Rust `bambox-bridge` Replaces C++ `estampo/cloud-bridge`

**Status:** Accepted (migration in progress)
**Date:** 2026-04-11
**Supersedes:** `docs/daemon-bridge-design.md` (Python-HTTP-over-C++ design)
**Tracking issue:** estampo/bambox#143

## Context

bambox communicates with Bambu Lab cloud printers through a "bridge" — a
binary that loads `libbambu_networking.so`, authenticates with Bambu Cloud,
subscribes to the printer's MQTT topics, and handles status queries and
print dispatch.

Two bridge implementations currently exist in this repository, and the
project is mid-migration between them:

1. **Legacy C++ bridge.** Distributed as the Docker image
   `estampo/cloud-bridge:bambu-02.05.00.00`. Built from
   `scripts/bambu_cloud_bridge.cpp` in the estampo repository. Subcommands
   `status`, `print`, `cancel` with the credentials token passed as a
   positional argument. This is what `src/bambox/bridge.py:34` currently
   targets.
2. **Rust `bambox-bridge`.** Source in `bridge/` in this repository. Calls
   `libbambu_networking.so` via a thin C++ shim (`shim/shim.cpp`) and FFI.
   Implements `status`, `watch`, and `daemon` subcommands today. Credentials
   are passed via a global `-c/--credentials` flag. A Docker image
   (`bambox/bridge`) is built from `bridge/Dockerfile` but nothing in Python
   references it yet.

Phase 1 and Phase 2 of the migration (Rust binary + HTTP API skeleton) were
implemented on top of the plan in `docs/bridge-migration-plan.md`. The plan
originated on branch `plan/bridge-migration` (commit `434b73c`) but was
never merged to main, so for a period the Rust bridge existed without any
merged documentation of intent. This ADR closes that gap.

The immediate trigger for writing this ADR: a user installed the Rust
`bambox-bridge` locally, `_find_local_bridge()` in `bridge.py` picked it up,
and `bambox status` crashed because Python passed the token file
positionally (the C++ CLI shape) while the Rust CLI expects `-c`. The two
bridges are not drop-in compatible, and nothing in the codebase made that
obvious.

## Decision

**The Rust `bambox-bridge` is the only bridge. The C++ bridge is deprecated
and will be removed.**

Concretely:

1. `bambox-bridge` (Rust, in `bridge/`) is the single source of truth for
   Bambu cloud communication going forward. All new bridge functionality
   lands in the Rust crate.
2. The Python client (`src/bambox/bridge.py`) will stop referencing
   `estampo/cloud-bridge`. The Docker fallback path will target the Rust
   `bambox/bridge` image built from `bridge/Dockerfile`.
3. The Python↔bridge transport unifies: Python calls `bambox-bridge` with a
   single CLI contract regardless of whether the binary runs locally or
   inside Docker. Long term, Python talks to the bridge over the HTTP
   daemon API (`axum`, port 8765) rather than stdout JSON — this
   eliminates the bind-mount/baked-image fallback dance and the 20-second
   MQTT-per-call cost.
4. The Rust bridge must reach CLI parity with what Python expects before
   the C++ image can be deleted: `Print` and `Cancel` subcommands must be
   added to `bridge/src/main.rs`.
5. Until parity is reached, `_run_bridge_local()` must not claim coverage
   it doesn't have — it should only take over for subcommands the Rust
   bridge actually implements, and fall through to the legacy Docker path
   for the rest. This is the stopgap, not the destination.
6. Phase 3 of the migration plan (absorbing estampo's printer code into
   bambox) continues to target v0.4.0, per the existing roadmap.

The full implementation plan — including the FFI shim design, HTTP API
endpoints, module-by-module move from estampo, and Docker packaging — lives
in `docs/bridge-migration-plan.md`. This ADR records the decision; the plan
records the mechanics.

## Consequences

### Benefits

- **One bridge, one CLI contract.** Eliminates the class of bug that
  triggered this ADR: Python can no longer silently route to a bridge with
  an incompatible CLI.
- **No bind-mount gymnastics.** Uploading 3MFs over HTTP removes the baked-
  Docker-image fallback in `_run_bridge_baked()` and all the sandbox
  workarounds around it.
- **Persistent MQTT connection.** Status queries return cached state
  instantly instead of paying a ~20s MQTT connect+subscribe cost per call.
- **Memory-safe bridge.** The C++ binary is replaced by a Rust binary that
  wraps the `.so` behind a narrow FFI surface.
- **Self-contained repo.** The bridge source lives in bambox, not in
  estampo. estampo becomes a pure slicing tool.

### Costs

- **Rust toolchain in CI.** The bridge build already requires this — the
  Dockerfile uses `rust:1.88-bookworm`. Contributors touching the bridge
  need Rust installed locally.
- **FFI fragility.** The `.so` exports C++ types; the shim wraps each
  function in `extern "C"`. ABI drift in a future Bambu Studio release
  could break the shim. This risk existed with the C++ bridge too.
- **Migration window.** Until `Print` and `Cancel` land in the Rust bridge,
  the legacy C++ image remains in the tree and `_run_bridge_local()` has
  to be selective about what it handles. This is a known transitional
  hazard.
- **Print/cancel parity gap.** The Rust bridge currently only implements
  `status`, `watch`, `daemon`. Closing this gap is the critical-path work
  for removing the C++ image.

### Non-goals

- This ADR does not decide between "Python shells out to `bambox-bridge`
  CLI" and "Python talks to the bridge HTTP daemon." The destination is
  HTTP (per the migration plan), but the CLI path remains supported for
  one-shot invocations and tests.
- This ADR does not cover LAN printing or Moonraker. Those are tracked
  separately (issue #91 for LAN) and are out of scope for the C++→Rust
  migration.

## Alternatives considered

### Keep the C++ bridge, wrap it in a Python HTTP daemon

This was the original design in `docs/daemon-bridge-design.md`. Rejected
because it leaves two languages in the critical path (C++ binary + Python
HTTP wrapper) and doesn't address the bind-mount issues — it just moves
them into the daemon container.

### Rewrite Python `bridge.py` to match the C++ CLI more faithfully and drop the Rust work

Rejected. The C++ binary depends on estampo's build system, is hard to
distribute (no static binary, no Homebrew tap), and carries the bind-mount
failure modes that motivated the migration in the first place. The Rust
work is already past Phase 2; throwing it away would cost more than
finishing it.

### Keep both bridges long-term, select by config

Rejected. Two CLI contracts, two test matrices, two release pipelines.
The bug that triggered this ADR is exactly what happens when "two bridges
coexist" meets reality.

## References

- `docs/bridge-migration-plan.md` — full 4-phase implementation plan
- Plan commit: `434b73c` (branch `plan/bridge-migration`, unmerged until
  this ADR)
- `bridge/src/main.rs` — Rust bridge entry point
- `bridge/Dockerfile` — Rust bridge Docker image (`bambox/bridge`)
- `src/bambox/bridge.py` — Python client (currently straddles both bridges)
- estampo ADR-005 — v0.4.0 printer-code absorption
