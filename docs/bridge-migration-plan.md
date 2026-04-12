# Bridge Migration Plan

This plan supersedes `daemon-bridge-design.md`. The original design proposed a
Python HTTP wrapper around the C++ bridge binary. This plan replaces both the
C++ binary and the Python wrapper with a single Rust binary that calls
`libbambu_networking.so` via FFI and exposes an HTTP API.

It also covers migrating all printer-specific code from estampo into bambu-3mf,
making estampo a pure G-code generation tool.

## Architecture

```
estampo (Python)                    bambu-3mf (Python + Rust)
┌──────────────┐                   ┌─────────────────────────────────┐
│ STL → G-code │──── .gcode ────▶  │ pack (gcode_compat + 3MF)      │
│              │                   │ auth (Bambu Cloud OAuth)        │
│ OrcaSlicer   │                   │ credentials (printer config)    │
│ CuraEngine   │                   │ bridge client (HTTP)            │
│ PrusaSlicer  │                   │ AMS mapping                     │
└──────────────┘                   └───────────┬─────────────────────┘
                                               │ HTTP
                                   ┌───────────▼─────────────────────┐
                                   │ bambu-bridge (Rust binary)      │
                                   │                                 │
                                   │  axum HTTP API (:8765)          │
                                   │  ├── GET  /health               │
                                   │  ├── GET  /status/:device       │
                                   │  ├── GET  /ams/:device          │
                                   │  ├── POST /print                │
                                   │  ├── POST /cancel/:device       │
                                   │  └── WS   /watch/:device        │
                                   │                                 │
                                   │  FFI → shim.cpp → .so           │
                                   │  Persistent MQTT connection     │
                                   │  Cached printer state           │
                                   └─────────────────────────────────┘
```

## Phase 1: Rust bridge daemon (status + watch)

**Goal:** Replace `bambu_cloud_bridge.cpp` with a Rust binary that can
authenticate, connect to MQTT, and stream printer status.

**Scope:** `status` and `watch` subcommands only. No printing, no HTTP API yet.
CLI tool matching the C++ bridge interface for drop-in testing.

### Components

```
bambu-3mf/
└── bridge/
    ├── Cargo.toml
    ├── build.rs              # cc crate compiles shim.cpp
    ├── src/
    │   ├── main.rs           # CLI: status, watch subcommands
    │   ├── agent.rs          # BambuAgent: init, connect, subscribe
    │   ├── ffi.rs            # Raw FFI bindings (extern "C" types)
    │   └── callbacks.rs      # Rust callback handlers
    └── shim/
        └── shim.cpp          # extern "C" wrappers for .so functions
```

### C++ shim (~200 LOC)

The `.so` exports functions using C++ types (`std::string`, `std::function`,
`std::map`). The shim wraps each function with `extern "C"` using C-compatible
types:

```cpp
// shim.cpp — compiled by build.rs via cc crate
extern "C" {
    void* bambu_shim_create_agent(const char* log_dir);
    int   bambu_shim_connect_server(void* agent);
    int   bambu_shim_change_user(void* agent, const char* user_json);
    int   bambu_shim_send_message(void* agent, const char* dev_id,
                                  const char* json, int qos);
    int   bambu_shim_set_on_message_fn(void* agent,
              void (*cb)(const char* dev_id, const char* msg, void* ctx),
              void* ctx);
    // ... ~15 functions total
}
```

### Rust FFI (~100 LOC)

```rust
// ffi.rs
extern "C" {
    fn bambu_shim_create_agent(log_dir: *const c_char) -> *mut c_void;
    fn bambu_shim_connect_server(agent: *mut c_void) -> c_int;
    fn bambu_shim_change_user(agent: *mut c_void, json: *const c_char) -> c_int;
    fn bambu_shim_set_on_message_fn(
        agent: *mut c_void,
        cb: extern "C" fn(*const c_char, *const c_char, *mut c_void),
        ctx: *mut c_void,
    ) -> c_int;
    // ...
}
```

### Deliverables

- [ ] `shim.cpp` wrapping the ~15 `.so` functions used by status/watch
- [ ] `build.rs` compiling the shim and linking `libdl`
- [ ] `BambuAgent` struct managing agent lifecycle
- [ ] `status` subcommand: connect, subscribe, pushall, print JSON, exit
- [ ] `watch` subcommand: connect, subscribe, stream MQTT messages to stdout
- [ ] Credential loading from `~/.config/estampo/credentials.toml`
- [ ] Test against real printer (P1S workshop)

## Phase 2: HTTP API

**Goal:** Add an axum HTTP server so Python clients can talk to the bridge
over HTTP instead of stdin/stdout.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Daemon health + MQTT connection state |
| GET | `/status/{device_id}` | Cached printer status (instant) |
| GET | `/ams/{device_id}` | AMS tray info from cached status |
| POST | `/print` | Upload 3MF + start print job |
| POST | `/cancel/{device_id}` | Cancel current print |
| WS | `/watch/{device_id}` | Live status stream via WebSocket |

### Key design decisions

- **Files via HTTP POST, not filesystem.** 3MF uploaded in request body.
  Eliminates bind-mount issues in DinD, sandboxed, and remote environments.
- **MQTT persists across requests.** Status returns cached data, no 20s wait.
- **Credentials at startup.** Token JSON passed once via `--credentials` flag
  or `BAMBOX_CREDENTIALS` env var.
- **Localhost only.** Binds to `127.0.0.1:8765`. No auth needed.

### Dependencies

```toml
[dependencies]
axum = "0.8"
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
clap = { version = "4", features = ["derive"] }
tracing = "0.1"
tracing-subscriber = "0.3"
```

## Phase 3: Migrate printer code from estampo

**Goal:** Move all Bambu-specific code from estampo into bambu-3mf. estampo
becomes a pure slicing tool (STL → G-code).

### Code to move from estampo

| Source (estampo) | Destination (bambu-3mf) | Description |
|------------------|------------------------|-------------|
| `src/estampo/cloud/bridge.py` | `src/bambu_3mf/bridge.py` | Bridge wrapper (rewritten as HTTP client) |
| `src/estampo/cloud/ams.py` | `src/bambu_3mf/ams.py` | AMS tray parsing + mapping |
| `src/estampo/auth.py` | `src/bambu_3mf/auth.py` | Bambu Cloud OAuth login |
| `src/estampo/credentials.py` | `src/bambu_3mf/credentials.py` | Printer credential management |
| `src/estampo/printer.py` | `src/bambu_3mf/printer.py` | Print dispatch (cloud, LAN, Moonraker) |
| `scripts/bambu_cloud_bridge.cpp` | (deleted — replaced by Rust) | C++ bridge binary |
| `Dockerfile.cloud-bridge` | `bridge/Dockerfile` | Bridge Docker image |
| `tests/test_cloud.py` | `tests/test_bridge.py` | Bridge + AMS tests |
| `tests/test_printer.py` | `tests/test_printer.py` | Print dispatch tests |
| `tests/test_credentials.py` | `tests/test_credentials.py` | Credential tests |
| `tests/test_auth.py` | `tests/test_auth.py` | Auth tests |

### Code to remove from estampo

| File | Action |
|------|--------|
| `src/estampo/cloud/` | Delete entire directory |
| `src/estampo/auth.py` | Delete |
| `src/estampo/credentials.py` | Delete |
| `src/estampo/printer.py` | Delete |
| `scripts/bambu_cloud_bridge.cpp` | Delete |
| `scripts/bambu_cloud_login.py` | Delete |
| `scripts/test_cloud_print.py` | Delete |
| `Dockerfile.cloud-bridge` | Delete |
| CLI: `status` command | Remove |
| CLI: `--upload-only` flag | Remove |
| Pipeline: `print_result` node | Remove |
| `config.py`: `[printer]` section | Remove |
| `init.py`: printer wizard steps | Remove |

### Code to keep in estampo

| File | Description |
|------|-------------|
| `slicer.py` | OrcaSlicer Docker execution |
| `cura.py` | CuraEngine execution |
| `pipeline.py` | Slicing pipeline (STL → G-code only) |
| `config.py` | Slicer config (`[slicer]` section only) |
| `init.py` | Profile setup wizard (slicer profiles only) |
| `cli.py` | `run` (slice only) and `init` commands |
| `profiles.py` | Slicer profile management |

### bambu-3mf CLI

After migration, bambu-3mf gets its own CLI for printing:

```bash
# Bridge daemon
bambu-3mf daemon start
bambu-3mf daemon stop
bambu-3mf daemon status

# Printing
bambu-3mf print file.gcode --printer workshop
bambu-3mf status --printer workshop --watch
bambu-3mf cancel --printer workshop

# Setup
bambu-3mf login
bambu-3mf add-printer
```

### Migration strategy

1. Copy code into bambu-3mf, adapt imports, get tests passing
2. bambu-3mf publishes a release with the new modules
3. estampo drops its printer code, adds optional `bambu-3mf` dependency
4. estampo CLI can offer a convenience `print` that delegates to bambu-3mf

## Phase 4: Docker packaging

**Goal:** Ship the Rust bridge daemon in a Docker image for users who don't
want to install the `.so` and cert locally.

```dockerfile
FROM debian:bookworm-slim
COPY libbambu_networking.so /usr/lib/
COPY slicer_base64.cer /etc/bambu/cert/
COPY bambu-bridge /usr/local/bin/
EXPOSE 8765
ENTRYPOINT ["bambu-bridge", "daemon"]
```

Final image: ~20MB (Rust static binary + `.so` + cert + minimal base).

Users run:
```bash
docker run -d --name bambu-bridge \
  -p 8765:8765 \
  -e BAMBOX_CREDENTIALS='{"token":"..."}' \
  estampo/bambu-bridge:latest
```

## Timeline

| Phase | Scope | Depends on |
|-------|-------|------------|
| 1 | Rust CLI: status + watch | Nothing |
| 2 | HTTP API (axum) | Phase 1 |
| 3 | Migrate printer code from estampo | Phase 2 |
| 4 | Docker image | Phase 2 |

Phases 1-2 are the critical path. Phase 3 can happen in parallel once the
bridge HTTP API is stable. Phase 4 is packaging.

## Open questions

1. **Moonraker support** — Move to bambu-3mf or drop? It's not Bambu-specific
   but it is printer-specific. Could become a separate `moonraker-print` package
   or stay in bambu-3mf as a generic printer backend.
2. **LAN printing** — Currently uses `bambulabs_api` Python package. Move as-is
   or rewrite in Rust alongside cloud printing?
3. **Credential storage** — Keep `~/.config/estampo/credentials.toml` or move
   to `~/.config/bambu-3mf/`? Or support both with a migration path?
