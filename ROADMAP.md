# bambox Roadmap

This is a living document updated at each release. It captures what's done, what's in scope for the next milestone, and what's explicitly deferred.

---

## v0.1.x — Done

Core packaging library with Bambu Connect compatibility.

- Core `.gcode.3mf` archive construction with MD5 checksums
- Template-driven 544-key `project_settings.config` generation
- Machine base profiles (P1S) with filament overlays (PLA, ASA, PETG-CF)
- Automatic array padding and missing-key fixup for Bambu Connect firmware
- Cloud printing via Docker bridge with bind-mount and baked fallback
- AMS tray mapping and printer status querying
- OrcaSlicer-to-Jinja2 template conversion and rendering
- G-code component assembly (start + toolpath + end)
- CuraEngine Docker slicer backend prototype
- CLI with `pack`, `print`, and `status` commands
- G-code-to-PNG thumbnail rendering

---

## v0.2.0 — In Progress

**Theme: Rust FFI bridge daemon replacing the C++ binary.**

### Done (prototype working)
- [x] C++ shim wrapping `libbambu_networking.so` functions via dlopen
- [x] `build.rs` compiling shim as C++17 and linking `libdl`
- [x] `BambuAgent` struct managing agent lifecycle with Drop cleanup
- [x] Thread-safe callback state (atomics + Mutex)
- [x] `status` subcommand: connect, query, print JSON, exit
- [x] `watch` subcommand: stdin-driven MQTT message streaming
- [x] `daemon` subcommand: axum HTTP server
- [x] Credential loading from `~/.config/estampo/credentials.toml` and JSON
- [x] HTTP endpoints: `/ping`, `/health`, `/status/{device}`, `/ams/{device}`, `/print`, `/cancel/{device}`, `/shutdown`
- [x] 3MF upload via multipart POST (eliminates bind-mount issues)
- [x] Cached printer state with 30s TTL
- [x] Full print pipeline: AMS mapping, color patching, config 3MF stripping
- [x] Retry logic for `-3140` enc flag failures (15s backoff, 5 retries)
- [x] Unit tests for credential parsing, callbacks, 3MF processing, HTTP handlers

### Remaining for v0.2.0 release (#28 — high priority)
- [ ] Replace `CString::new().unwrap()` with error propagation (~20 call sites)
- [ ] Move agent to dedicated thread with command channel (unblock HTTP during MQTT queries)
- [ ] Wire up print cancellation (`WasCancelledFn` → `AtomicBool`)
- [ ] Replace `static mut SAVED_STDOUT` with `AtomicI32`
- [ ] Dockerfile for building and running the Rust bridge

### Out of scope for v0.2.0
- WebSocket `/watch/{device}` endpoint (Phase 2b)
- LAN printing mode
- Migrating code from estampo

---

## v0.3.0 — Planned

**Theme: Absorb printer code from estampo. Complete the split.**

Per estampo ADR-005, bambox becomes the standalone Bambu packaging + communication library. This release coordinates with estampo v0.4.0.

- Migrate `cloud/bridge.py` from estampo (rewrite as HTTP client to Rust daemon)
- Migrate `cloud/ams.py`, `auth.py`, `credentials.py`, `printer.py` from estampo
- Migrate `thumbnails.py`, `bambu_connect_fixup()` from estampo
- Migrate associated tests
- Send print completion (100%) command to printer (#381 on estampo)
- bambox publishes release with new modules
- estampo drops printer code, adds optional `bambox` dependency
- WebSocket `/watch/{device}` endpoint
- LAN printing mode

---

## v1.0 — Sketch

**Theme: Stable public API.**

- Public API freeze for `pack_gcode_3mf()`, `build_project_settings()`, `fixup_project_settings()`
- Comprehensive API documentation
- Support for additional Bambu printer models (X1C, A1, A1 Mini)

---

## Deferred / Backlog

- Moonraker (non-Bambu) printer support
- Multi-extruder CuraEngine output packaging
- Profile editing or merging UI

---

## Architecture North Star

Two projects, each owning one concern:

```
estampo          → pipeline orchestrator, slicer-agnostic
bambox           → BBL packaging + G-code templates + printer communication (Python lib + Rust bridge daemon)
```

Every feature decision should move toward this split, not away from it.
