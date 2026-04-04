//! Callback state shared between the shim and Rust code.
//!
//! The .so library invokes callbacks on its own threads. We use atomics and
//! a mutex-protected message buffer to safely communicate with the main thread.

use std::ffi::CStr;
use std::os::raw::{c_char, c_int, c_uint, c_void};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

/// Shared state for all callbacks. Allocated on the heap and passed as the
/// `void* ctx` to every shim callback setter.
pub struct CallbackState {
    pub server_connected: AtomicBool,
    pub user_logged_in: AtomicBool,
    pub printer_subscribed: AtomicBool,
    pub messages: Mutex<Vec<MqttMessage>>,
}

pub struct MqttMessage {
    pub dev_id: String,
    pub payload: String,
}

impl CallbackState {
    pub fn new() -> Self {
        Self {
            server_connected: AtomicBool::new(false),
            user_logged_in: AtomicBool::new(false),
            printer_subscribed: AtomicBool::new(false),
            messages: Mutex::new(Vec::new()),
        }
    }

    /// Take all accumulated messages, leaving the buffer empty.
    pub fn drain_messages(&self) -> Vec<MqttMessage> {
        let mut lock = self.messages.lock().unwrap();
        std::mem::take(&mut *lock)
    }
}

// ---------------------------------------------------------------------------
// extern "C" callback functions passed to the shim
// ---------------------------------------------------------------------------

/// Cast `ctx` back to `&CallbackState`. Caller must guarantee lifetime.
unsafe fn state(ctx: *mut c_void) -> &'static CallbackState {
    &*(ctx as *const CallbackState)
}

unsafe fn cstr_to_str(ptr: *const c_char) -> &'static str {
    if ptr.is_null() {
        return "";
    }
    CStr::from_ptr(ptr).to_str().unwrap_or("")
}

pub extern "C" fn on_server_connected(rc: c_int, _reason: c_int, ctx: *mut c_void) {
    let s = unsafe { state(ctx) };
    if rc == 0 {
        s.server_connected.store(true, Ordering::SeqCst);
    }
    tracing::debug!(rc, _reason, "server_connected callback");
}

pub extern "C" fn on_message(dev_id: *const c_char, msg: *const c_char, ctx: *mut c_void) {
    let s = unsafe { state(ctx) };
    let dev = unsafe { cstr_to_str(dev_id) };
    let payload = unsafe { cstr_to_str(msg) };
    if payload.is_empty() || payload == "{}" {
        return;
    }
    tracing::trace!(dev_id = dev, len = payload.len(), "mqtt message");
    let mut lock = s.messages.lock().unwrap();
    lock.push(MqttMessage {
        dev_id: dev.to_owned(),
        payload: payload.to_owned(),
    });
}

pub extern "C" fn on_printer_connected(topic: *const c_char, ctx: *mut c_void) {
    let s = unsafe { state(ctx) };
    s.printer_subscribed.store(true, Ordering::SeqCst);
    let t = unsafe { cstr_to_str(topic) };
    tracing::debug!(topic = t, "printer_connected callback");
}

pub extern "C" fn on_user_login(_online: c_int, login: c_int, ctx: *mut c_void) {
    let s = unsafe { state(ctx) };
    if login != 0 {
        s.user_logged_in.store(true, Ordering::SeqCst);
    }
    tracing::debug!(_online, login, "user_login callback");
}

pub extern "C" fn on_http_error(code: c_uint, body: *const c_char, _ctx: *mut c_void) {
    let b = unsafe { cstr_to_str(body) };
    tracing::warn!(code, body = &b[..b.len().min(200)], "http_error callback");
}

pub extern "C" fn on_subscribe_failure(topic: *const c_char, _ctx: *mut c_void) {
    let t = unsafe { cstr_to_str(topic) };
    tracing::warn!(topic = t, "subscribe_failure callback");
}
