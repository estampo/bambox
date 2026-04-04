//! Raw FFI bindings to the C++ shim layer.
//!
//! These map 1:1 to the `extern "C"` functions in `shim/shim.cpp`.
//! Higher-level Rust wrappers live in `agent.rs`.

use std::os::raw::{c_char, c_int, c_uint, c_void};

// Callback function pointer types matching shim.cpp typedefs
pub type OnServerConnectedFn = extern "C" fn(rc: c_int, reason: c_int, ctx: *mut c_void);
pub type OnMessageFn = extern "C" fn(dev_id: *const c_char, msg: *const c_char, ctx: *mut c_void);
pub type OnPrinterConnectedFn = extern "C" fn(topic: *const c_char, ctx: *mut c_void);
pub type OnUserLoginFn = extern "C" fn(online: c_int, login: c_int, ctx: *mut c_void);
pub type OnHttpErrorFn = extern "C" fn(code: c_uint, body: *const c_char, ctx: *mut c_void);
pub type OnSubscribeFailureFn = extern "C" fn(topic: *const c_char, ctx: *mut c_void);

extern "C" {
    // Library loading
    pub fn bambu_shim_load(lib_path: *const c_char) -> c_int;
    pub fn bambu_shim_load_error() -> *const c_char;

    // Agent lifecycle
    pub fn bambu_shim_create_agent(log_dir: *const c_char) -> *mut c_void;
    pub fn bambu_shim_destroy_agent(agent: *mut c_void) -> c_int;

    // Setup
    pub fn bambu_shim_init_log(agent: *mut c_void) -> c_int;
    pub fn bambu_shim_set_config_dir(agent: *mut c_void, dir: *const c_char) -> c_int;
    pub fn bambu_shim_set_cert_file(
        agent: *mut c_void,
        dir: *const c_char,
        name: *const c_char,
    ) -> c_int;
    pub fn bambu_shim_set_country_code(agent: *mut c_void, code: *const c_char) -> c_int;
    pub fn bambu_shim_start(agent: *mut c_void) -> c_int;
    pub fn bambu_shim_set_extra_http_header(
        agent: *mut c_void,
        keys: *const *const c_char,
        vals: *const *const c_char,
        count: c_int,
    ) -> c_int;

    // Auth
    pub fn bambu_shim_change_user(agent: *mut c_void, json: *const c_char) -> c_int;
    pub fn bambu_shim_is_user_login(agent: *mut c_void) -> c_int;

    // Connection
    pub fn bambu_shim_connect_server(agent: *mut c_void) -> c_int;
    pub fn bambu_shim_is_server_connected(agent: *mut c_void) -> c_int;

    // Subscribe + messaging
    pub fn bambu_shim_set_user_selected_machine(
        agent: *mut c_void,
        dev_id: *const c_char,
    ) -> c_int;
    pub fn bambu_shim_start_subscribe(agent: *mut c_void, module: *const c_char) -> c_int;
    pub fn bambu_shim_send_message(
        agent: *mut c_void,
        dev_id: *const c_char,
        json: *const c_char,
        qos: c_int,
    ) -> c_int;
    pub fn bambu_shim_send_message_to_printer(
        agent: *mut c_void,
        dev_id: *const c_char,
        json: *const c_char,
        qos: c_int,
        timeout: c_int,
    ) -> c_int;

    // Callback setters
    pub fn bambu_shim_set_on_server_connected_fn(
        agent: *mut c_void,
        cb: OnServerConnectedFn,
        ctx: *mut c_void,
    ) -> c_int;
    pub fn bambu_shim_set_on_message_fn(
        agent: *mut c_void,
        cb: OnMessageFn,
        ctx: *mut c_void,
    ) -> c_int;
    pub fn bambu_shim_set_on_printer_connected_fn(
        agent: *mut c_void,
        cb: OnPrinterConnectedFn,
        ctx: *mut c_void,
    ) -> c_int;
    pub fn bambu_shim_set_on_user_login_fn(
        agent: *mut c_void,
        cb: OnUserLoginFn,
        ctx: *mut c_void,
    ) -> c_int;
    pub fn bambu_shim_set_on_http_error_fn(
        agent: *mut c_void,
        cb: OnHttpErrorFn,
        ctx: *mut c_void,
    ) -> c_int;
    pub fn bambu_shim_set_get_country_code_fn(
        agent: *mut c_void,
        code: *const c_char,
    ) -> c_int;
    pub fn bambu_shim_set_on_subscribe_failure_fn(
        agent: *mut c_void,
        cb: OnSubscribeFailureFn,
        ctx: *mut c_void,
    ) -> c_int;
}
