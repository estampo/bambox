/**
 * shim.cpp — extern "C" wrappers for libbambu_networking.so
 *
 * The .so exports functions using C++ types (std::string, std::function,
 * std::map). This shim wraps each function with extern "C" using C-compatible
 * types so Rust can call them via FFI.
 *
 * The library is loaded at runtime via dlopen — no compile-time linking needed.
 */

#include <cstring>
#include <dlfcn.h>
#include <functional>
#include <map>
#include <string>

// ---------------------------------------------------------------------------
// Type definitions matching bambu_networking.hpp
// ---------------------------------------------------------------------------

typedef std::function<void(int online_login, bool login)> OnUserLoginFn;
typedef std::function<void(std::string topic_str)> OnPrinterConnectedFn;
typedef std::function<void(int return_code, int reason_code)> OnServerConnectedFn;
typedef std::function<void(unsigned http_code, std::string http_body)> OnHttpErrorFn;
typedef std::function<std::string()> GetCountryCodeFn;
typedef std::function<void(std::string topic)> GetSubscribeFailureFn;
typedef std::function<void(std::string dev_id, std::string msg)> OnMessageFn;

// ---------------------------------------------------------------------------
// Function pointer types (resolved via dlsym)
// ---------------------------------------------------------------------------

typedef void* (*fn_create_agent)(std::string);
typedef int (*fn_destroy_agent)(void*);
typedef int (*fn_init_log)(void*);
typedef int (*fn_set_config_dir)(void*, std::string);
typedef int (*fn_set_cert_file)(void*, std::string, std::string);
typedef int (*fn_set_country_code)(void*, std::string);
typedef int (*fn_start)(void*);
typedef int (*fn_connect_server)(void*);
typedef bool (*fn_is_server_connected)(void*);
typedef int (*fn_change_user)(void*, std::string);
typedef bool (*fn_is_user_login)(void*);
typedef int (*fn_set_user_selected_machine)(void*, std::string);
typedef int (*fn_set_on_server_connected_fn)(void*, OnServerConnectedFn);
typedef int (*fn_set_on_http_error_fn)(void*, OnHttpErrorFn);
typedef int (*fn_set_on_message_fn)(void*, OnMessageFn);
typedef int (*fn_set_on_printer_connected_fn)(void*, OnPrinterConnectedFn);
typedef int (*fn_set_get_country_code_fn)(void*, GetCountryCodeFn);
typedef int (*fn_set_on_user_login_fn)(void*, OnUserLoginFn);
typedef int (*fn_set_on_subscribe_failure_fn)(void*, GetSubscribeFailureFn);
typedef int (*fn_set_extra_http_header)(void*, std::map<std::string, std::string>);
typedef int (*fn_send_message)(void*, std::string, std::string, int);
typedef int (*fn_send_message_to_printer)(void*, std::string, std::string, int, int);
typedef int (*fn_start_subscribe)(void*, std::string);

// ---------------------------------------------------------------------------
// Resolved function pointers
// ---------------------------------------------------------------------------

static void* g_lib = nullptr;

static fn_create_agent              fp_create_agent = nullptr;
static fn_destroy_agent             fp_destroy_agent = nullptr;
static fn_init_log                  fp_init_log = nullptr;
static fn_set_config_dir            fp_set_config_dir = nullptr;
static fn_set_cert_file             fp_set_cert_file = nullptr;
static fn_set_country_code          fp_set_country_code = nullptr;
static fn_start                     fp_start = nullptr;
static fn_connect_server            fp_connect_server = nullptr;
static fn_is_server_connected       fp_is_connected = nullptr;
static fn_change_user               fp_change_user = nullptr;
static fn_is_user_login             fp_is_user_login = nullptr;
static fn_set_user_selected_machine fp_set_machine = nullptr;
static fn_set_on_server_connected_fn fp_set_server_cb = nullptr;
static fn_set_on_http_error_fn      fp_set_http_err_cb = nullptr;
static fn_set_on_message_fn         fp_set_message_cb = nullptr;
static fn_set_on_printer_connected_fn fp_set_printer_cb = nullptr;
static fn_set_get_country_code_fn   fp_set_country_cb = nullptr;
static fn_set_on_user_login_fn      fp_set_user_login_cb = nullptr;
static fn_set_on_subscribe_failure_fn fp_set_sub_fail_cb = nullptr;
static fn_set_extra_http_header     fp_set_extra_hdr = nullptr;
static fn_send_message              fp_send_msg = nullptr;
static fn_send_message_to_printer   fp_send_msg_printer = nullptr;
static fn_start_subscribe           fp_start_sub = nullptr;

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

template<typename T>
static T load_fn(const char* name) {
    void* ptr = dlsym(g_lib, name);
    return reinterpret_cast<T>(ptr);
}

// ---------------------------------------------------------------------------
// extern "C" API for Rust
// ---------------------------------------------------------------------------

extern "C" {

int bambu_shim_load(const char* lib_path) {
    if (g_lib) return 0; // already loaded

    g_lib = dlopen(lib_path, RTLD_LAZY);
    if (!g_lib) return -1;

    fp_create_agent    = load_fn<fn_create_agent>("bambu_network_create_agent");
    fp_destroy_agent   = load_fn<fn_destroy_agent>("bambu_network_destroy_agent");
    fp_init_log        = load_fn<fn_init_log>("bambu_network_init_log");
    fp_set_config_dir  = load_fn<fn_set_config_dir>("bambu_network_set_config_dir");
    fp_set_cert_file   = load_fn<fn_set_cert_file>("bambu_network_set_cert_file");
    fp_set_country_code = load_fn<fn_set_country_code>("bambu_network_set_country_code");
    fp_start           = load_fn<fn_start>("bambu_network_start");
    fp_connect_server  = load_fn<fn_connect_server>("bambu_network_connect_server");
    fp_is_connected    = load_fn<fn_is_server_connected>("bambu_network_is_server_connected");
    fp_change_user     = load_fn<fn_change_user>("bambu_network_change_user");
    fp_is_user_login   = load_fn<fn_is_user_login>("bambu_network_is_user_login");
    fp_set_machine     = load_fn<fn_set_user_selected_machine>("bambu_network_set_user_selected_machine");
    fp_set_server_cb   = load_fn<fn_set_on_server_connected_fn>("bambu_network_set_on_server_connected_fn");
    fp_set_http_err_cb = load_fn<fn_set_on_http_error_fn>("bambu_network_set_on_http_error_fn");
    fp_set_message_cb  = load_fn<fn_set_on_message_fn>("bambu_network_set_on_message_fn");
    fp_set_printer_cb  = load_fn<fn_set_on_printer_connected_fn>("bambu_network_set_on_printer_connected_fn");
    fp_set_country_cb  = load_fn<fn_set_get_country_code_fn>("bambu_network_set_get_country_code_fn");
    fp_set_user_login_cb = load_fn<fn_set_on_user_login_fn>("bambu_network_set_on_user_login_fn");
    fp_set_sub_fail_cb = load_fn<fn_set_on_subscribe_failure_fn>("bambu_network_set_on_subscribe_failure_fn");
    fp_set_extra_hdr   = load_fn<fn_set_extra_http_header>("bambu_network_set_extra_http_header");
    fp_send_msg        = load_fn<fn_send_message>("bambu_network_send_message");
    fp_send_msg_printer = load_fn<fn_send_message_to_printer>("bambu_network_send_message_to_printer");
    fp_start_sub       = load_fn<fn_start_subscribe>("bambu_network_start_subscribe");

    if (!fp_create_agent || !fp_change_user || !fp_connect_server) {
        dlclose(g_lib);
        g_lib = nullptr;
        return -2;
    }
    return 0;
}

const char* bambu_shim_load_error() {
    return dlerror();
}

void* bambu_shim_create_agent(const char* log_dir) {
    if (!fp_create_agent) return nullptr;
    return fp_create_agent(std::string(log_dir));
}

int bambu_shim_destroy_agent(void* agent) {
    if (!fp_destroy_agent) return -1;
    return fp_destroy_agent(agent);
}

int bambu_shim_init_log(void* agent) {
    if (!fp_init_log) return -1;
    return fp_init_log(agent);
}

int bambu_shim_set_config_dir(void* agent, const char* dir) {
    if (!fp_set_config_dir) return -1;
    return fp_set_config_dir(agent, std::string(dir));
}

int bambu_shim_set_cert_file(void* agent, const char* dir, const char* name) {
    if (!fp_set_cert_file) return -1;
    return fp_set_cert_file(agent, std::string(dir), std::string(name));
}

int bambu_shim_set_country_code(void* agent, const char* code) {
    if (!fp_set_country_code) return -1;
    return fp_set_country_code(agent, std::string(code));
}

int bambu_shim_start(void* agent) {
    if (!fp_start) return -1;
    return fp_start(agent);
}

int bambu_shim_set_extra_http_header(
    void* agent, const char** keys, const char** vals, int count
) {
    if (!fp_set_extra_hdr) return -1;
    std::map<std::string, std::string> hdrs;
    for (int i = 0; i < count; i++) {
        hdrs[std::string(keys[i])] = std::string(vals[i]);
    }
    return fp_set_extra_hdr(agent, hdrs);
}

int bambu_shim_change_user(void* agent, const char* json) {
    if (!fp_change_user) return -1;
    return fp_change_user(agent, std::string(json));
}

int bambu_shim_is_user_login(void* agent) {
    if (!fp_is_user_login) return 0;
    return fp_is_user_login(agent) ? 1 : 0;
}

int bambu_shim_connect_server(void* agent) {
    if (!fp_connect_server) return -1;
    return fp_connect_server(agent);
}

int bambu_shim_is_server_connected(void* agent) {
    if (!fp_is_connected) return 0;
    return fp_is_connected(agent) ? 1 : 0;
}

int bambu_shim_set_user_selected_machine(void* agent, const char* dev_id) {
    if (!fp_set_machine) return -1;
    return fp_set_machine(agent, std::string(dev_id));
}

int bambu_shim_start_subscribe(void* agent, const char* module) {
    if (!fp_start_sub) return -1;
    return fp_start_sub(agent, std::string(module));
}

int bambu_shim_send_message(void* agent, const char* dev_id, const char* json, int qos) {
    if (!fp_send_msg) return -1;
    return fp_send_msg(agent, std::string(dev_id), std::string(json), qos);
}

int bambu_shim_send_message_to_printer(
    void* agent, const char* dev_id, const char* json, int qos, int timeout
) {
    if (!fp_send_msg_printer) return -1;
    return fp_send_msg_printer(
        agent, std::string(dev_id), std::string(json), qos, timeout
    );
}

// ---------------------------------------------------------------------------
// Callback setters
//
// Each stores a C function pointer + void* context, wraps it in a
// std::function, and passes it to the real .so function.
// ---------------------------------------------------------------------------

// on_server_connected(int rc, int reason)
typedef void (*shim_on_server_connected_fn)(int, int, void*);
static shim_on_server_connected_fn g_server_cb = nullptr;
static void* g_server_cb_ctx = nullptr;

int bambu_shim_set_on_server_connected_fn(
    void* agent, shim_on_server_connected_fn cb, void* ctx
) {
    if (!fp_set_server_cb) return -1;
    g_server_cb = cb;
    g_server_cb_ctx = ctx;
    OnServerConnectedFn wrapper = [](int rc, int reason) {
        if (g_server_cb) g_server_cb(rc, reason, g_server_cb_ctx);
    };
    return fp_set_server_cb(agent, wrapper);
}

// on_message(dev_id, msg)
typedef void (*shim_on_message_fn)(const char*, const char*, void*);
static shim_on_message_fn g_message_cb = nullptr;
static void* g_message_cb_ctx = nullptr;

int bambu_shim_set_on_message_fn(
    void* agent, shim_on_message_fn cb, void* ctx
) {
    if (!fp_set_message_cb) return -1;
    g_message_cb = cb;
    g_message_cb_ctx = ctx;
    OnMessageFn wrapper = [](std::string dev_id, std::string msg) {
        if (g_message_cb) g_message_cb(dev_id.c_str(), msg.c_str(), g_message_cb_ctx);
    };
    return fp_set_message_cb(agent, wrapper);
}

// on_printer_connected(topic)
typedef void (*shim_on_printer_connected_fn)(const char*, void*);
static shim_on_printer_connected_fn g_printer_cb = nullptr;
static void* g_printer_cb_ctx = nullptr;

int bambu_shim_set_on_printer_connected_fn(
    void* agent, shim_on_printer_connected_fn cb, void* ctx
) {
    if (!fp_set_printer_cb) return -1;
    g_printer_cb = cb;
    g_printer_cb_ctx = ctx;
    OnPrinterConnectedFn wrapper = [](std::string topic) {
        if (g_printer_cb) g_printer_cb(topic.c_str(), g_printer_cb_ctx);
    };
    return fp_set_printer_cb(agent, wrapper);
}

// on_user_login(online, login)
typedef void (*shim_on_user_login_fn)(int, int, void*);
static shim_on_user_login_fn g_user_login_cb = nullptr;
static void* g_user_login_cb_ctx = nullptr;

int bambu_shim_set_on_user_login_fn(
    void* agent, shim_on_user_login_fn cb, void* ctx
) {
    if (!fp_set_user_login_cb) return -1;
    g_user_login_cb = cb;
    g_user_login_cb_ctx = ctx;
    OnUserLoginFn wrapper = [](int online, bool login) {
        if (g_user_login_cb) g_user_login_cb(online, login ? 1 : 0, g_user_login_cb_ctx);
    };
    return fp_set_user_login_cb(agent, wrapper);
}

// on_http_error(code, body)
typedef void (*shim_on_http_error_fn)(unsigned, const char*, void*);
static shim_on_http_error_fn g_http_err_cb = nullptr;
static void* g_http_err_cb_ctx = nullptr;

int bambu_shim_set_on_http_error_fn(
    void* agent, shim_on_http_error_fn cb, void* ctx
) {
    if (!fp_set_http_err_cb) return -1;
    g_http_err_cb = cb;
    g_http_err_cb_ctx = ctx;
    OnHttpErrorFn wrapper = [](unsigned code, std::string body) {
        if (g_http_err_cb) g_http_err_cb(code, body.c_str(), g_http_err_cb_ctx);
    };
    return fp_set_http_err_cb(agent, wrapper);
}

// get_country_code — simplified: just store a string
static std::string g_country_code = "US";

int bambu_shim_set_get_country_code_fn(void* agent, const char* code) {
    if (!fp_set_country_cb) return -1;
    g_country_code = std::string(code);
    GetCountryCodeFn wrapper = []() -> std::string {
        return g_country_code;
    };
    return fp_set_country_cb(agent, wrapper);
}

// on_subscribe_failure(topic)
typedef void (*shim_on_subscribe_failure_fn)(const char*, void*);
static shim_on_subscribe_failure_fn g_sub_fail_cb = nullptr;
static void* g_sub_fail_cb_ctx = nullptr;

int bambu_shim_set_on_subscribe_failure_fn(
    void* agent, shim_on_subscribe_failure_fn cb, void* ctx
) {
    if (!fp_set_sub_fail_cb) return -1;
    g_sub_fail_cb = cb;
    g_sub_fail_cb_ctx = ctx;
    GetSubscribeFailureFn wrapper = [](std::string topic) {
        if (g_sub_fail_cb) g_sub_fail_cb(topic.c_str(), g_sub_fail_cb_ctx);
    };
    return fp_set_sub_fail_cb(agent, wrapper);
}

} // extern "C"
