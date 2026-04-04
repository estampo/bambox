//! bambu-bridge — Rust CLI for Bambu Lab printer status and monitoring.
//!
//! Phase 1: `status` and `watch` subcommands, replacing the C++ bridge
//! for read-only operations.

mod agent;
mod callbacks;
mod ffi;

use std::io::{self, BufRead, Write};
use std::path::PathBuf;
use std::process;
use std::time::Duration;

use clap::{Parser, Subcommand};

use agent::{BambuAgent, Credentials};

/// Saved original stdout fd, used to restore after suppressing library noise.
static mut SAVED_STDOUT: i32 = -1;

/// Suppress stdout to hide library noise (e.g. "use_count = 4").
/// Logs (tracing) go to stderr and are unaffected.
fn suppress_stdout() {
    unsafe {
        SAVED_STDOUT = libc::dup(1);
        let devnull = libc::open(b"/dev/null\0".as_ptr() as *const _, libc::O_WRONLY);
        if devnull >= 0 {
            libc::dup2(devnull, 1);
            libc::close(devnull);
        }
    }
}

/// Fast exit that skips atexit handlers, avoiding .so MQTT thread cleanup hangs.
fn fast_exit(code: i32) -> ! {
    use std::io::Write;
    let _ = io::stdout().flush();
    let _ = io::stderr().flush();
    unsafe { libc::_exit(code) }
}

#[derive(Parser)]
#[command(name = "bambu-bridge", about = "Bambu Lab printer bridge")]
struct Cli {
    #[command(subcommand)]
    command: Command,

    /// Path to libbambu_networking.so
    #[arg(
        long,
        env = "BAMBU_LIB_PATH",
        default_value = "/tmp/bambu_plugin/libbambu_networking.so"
    )]
    lib_path: String,

    /// Verbose debug output
    #[arg(short, long, global = true)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Command {
    /// Query live printer state via MQTT (JSON output)
    Status {
        /// Bambu device ID
        device_id: String,
        /// Path to token JSON file or credentials TOML
        credentials: PathBuf,
    },
    /// Long-lived mode: login once, accept commands on stdin
    Watch {
        /// Bambu device ID
        device_id: String,
        /// Path to token JSON file or credentials TOML
        credentials: PathBuf,
    },
}

fn load_credentials(path: &PathBuf) -> Credentials {
    // Try TOML first (has [cloud] section), fall back to raw JSON
    if let Some(ext) = path.extension() {
        if ext == "toml" {
            match Credentials::from_toml(path) {
                Ok(c) => return c,
                Err(e) => {
                    eprintln!("error: {e}");
                    process::exit(1);
                }
            }
        }
    }
    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(e) => {
            eprintln!("error: cannot read {}: {e}", path.display());
            process::exit(1);
        }
    };
    match Credentials::from_token_json(&text) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {e}");
            process::exit(1);
        }
    }
}

fn init_agent(lib_path: &str, creds: &Credentials) -> BambuAgent {
    let agent = match BambuAgent::new(lib_path) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("error: {e}");
            process::exit(1);
        }
    };
    if let Err(e) = agent.login_and_connect(creds) {
        eprintln!("error: {e}");
        process::exit(1);
    }
    agent
}

/// Find the best (largest, most complete) message from a set.
fn best_message(messages: &[callbacks::MqttMessage]) -> Option<&callbacks::MqttMessage> {
    messages.iter().max_by_key(|m| m.payload.len())
}

fn cmd_status(agent: &BambuAgent, device_id: &str) {
    if let Err(e) = agent.subscribe_and_pushall(device_id, Duration::from_secs(10)) {
        eprintln!("error: {e}");
        process::exit(1);
    }

    let messages = agent.drain_messages();

    // Restore stdout (was suppressed to hide library noise like "use_count = 4")
    unsafe { libc::dup2(SAVED_STDOUT, 1) };

    match best_message(&messages) {
        Some(msg) => {
            println!("{}", msg.payload);
        }
        None => {
            eprintln!("error: no status received from printer {device_id}");
            fast_exit(2);
        }
    }
}

fn cmd_watch(agent: &BambuAgent, device_id: &str) {
    let dev_c = std::ffi::CString::new(device_id).unwrap();
    let module = std::ffi::CString::new("device").unwrap();

    // Subscribe once
    unsafe {
        ffi::bambu_shim_set_user_selected_machine(agent.agent_ptr(), dev_c.as_ptr());
    }
    agent
        .callback_state()
        .printer_subscribed
        .store(false, std::sync::atomic::Ordering::SeqCst);
    unsafe {
        ffi::bambu_shim_start_subscribe(agent.agent_ptr(), module.as_ptr());
    }

    // Wait for subscription
    let start = std::time::Instant::now();
    while start.elapsed() < Duration::from_secs(3)
        && !agent
            .callback_state()
            .printer_subscribed
            .load(std::sync::atomic::Ordering::SeqCst)
    {
        std::thread::sleep(Duration::from_millis(100));
    }

    // Restore stdout and signal readiness
    unsafe { libc::dup2(SAVED_STDOUT, 1) };
    println!("{{\"ready\":true}}");
    io::stdout().flush().unwrap();

    // Read commands from stdin
    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let line = line.trim().to_string();
        if line.is_empty() {
            continue;
        }
        if line == "quit" || line == "exit" {
            break;
        }

        if line == "status" {
            // Drain any stale messages
            agent.drain_messages();

            // Send pushall
            let pushall = r#"{"pushing":{"sequence_id":"0","command":"pushall","version":1,"push_target":1}}"#;
            agent.send_message(device_id, pushall);

            // Wait for full status
            let start = std::time::Instant::now();
            let timeout = Duration::from_secs(10);
            loop {
                if start.elapsed() >= timeout {
                    break;
                }
                {
                    let msgs = agent.callback_state().messages.lock().unwrap();
                    if msgs
                        .iter()
                        .any(|m| m.payload.len() > 500 && m.payload.contains("gcode_state"))
                    {
                        drop(msgs);
                        std::thread::sleep(Duration::from_millis(300));
                        break;
                    }
                }
                std::thread::sleep(Duration::from_millis(100));
            }

            let messages = agent.drain_messages();
            match best_message(&messages) {
                Some(msg) => println!("{}", msg.payload),
                None => println!("{{\"error\":\"no status received\"}}"),
            }
            io::stdout().flush().unwrap();
        } else {
            println!("{{\"error\":\"unknown command\"}}");
            io::stdout().flush().unwrap();
        }
    }
}

fn main() {
    let cli = Cli::parse();

    // Set up tracing
    let level = if cli.verbose { "debug" } else { "warn" };
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(level)),
        )
        .with_writer(io::stderr)
        .init();

    match &cli.command {
        Command::Status {
            device_id,
            credentials,
        } => {
            suppress_stdout();
            let creds = load_credentials(credentials);
            let agent = init_agent(&cli.lib_path, &creds);
            cmd_status(&agent, device_id);
            // Fast exit — _exit() skips atexit handlers, avoids .so MQTT
            // thread cleanup hangs (same as C++ bridge's fast_exit).
            fast_exit(0);
        }
        Command::Watch {
            device_id,
            credentials,
        } => {
            suppress_stdout();
            let creds = load_credentials(credentials);
            let agent = init_agent(&cli.lib_path, &creds);
            cmd_watch(&agent, device_id);
            fast_exit(0);
        }
    }
}
