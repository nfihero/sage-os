//! Sage OS desktop app (W1, D33): a window and a tray icon around the hub.
//!
//! * Finds a running hub on 127.0.0.1:<port> (it answers /api/ping as "sage-os"), or starts one: the bundled
//!   hub next to the app when packaged (F1), else this checkout's Python hub (a developer build).
//! * The window shows the hub's own page, so the hub's security rules apply unchanged; no Tauri command is
//!   exposed to any page. Links to anywhere else open in the default browser.
//! * Closing the window keeps Sage OS running in the tray (digests, game mode and agents carry on); the tray's
//!   Quit stops the hub cleanly (POST /api/quit, which unloads the local model) and then the app.
//! * One copy runs at a time: starting it again shows the window. Start at sign-in is a tray toggle, off by
//!   default; when it starts that way it stays in the tray.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_window_state::{StateFlags, WindowExt};

const HIDDEN_ARG: &str = "--hidden";

struct Hub {
    port: u16,
    child: Mutex<Option<Child>>,
}

impl Hub {
    fn url(&self) -> String {
        format!("http://127.0.0.1:{}/", self.port)
    }
}

fn port() -> u16 {
    std::env::var("SAGE_OS_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8787)
}

/// One plain HTTP request to the hub on localhost. -> (status, body)
fn http(port: u16, method: &str, path: &str, timeout: Duration) -> Option<(u16, String)> {
    let addr: SocketAddr = ([127, 0, 0, 1], port).into();
    let mut s = TcpStream::connect_timeout(&addr, timeout).ok()?;
    s.set_read_timeout(Some(timeout)).ok()?;
    s.set_write_timeout(Some(timeout)).ok()?;
    let req = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Sage-OS: 1\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    );
    s.write_all(req.as_bytes()).ok()?;
    let mut buf = String::new();
    s.read_to_string(&mut buf).ok()?;
    let status = buf.split_whitespace().nth(1)?.parse().ok()?;
    let body = buf.split_once("\r\n\r\n").map(|(_, b)| b.to_string()).unwrap_or_default();
    Some((status, body))
}

/// Is a Sage OS hub (not some other program) answering on the port?
fn hub_up(port: u16) -> bool {
    matches!(http(port, "GET", "/api/ping", Duration::from_millis(800)),
             Some((200, body)) if body.contains("\"app\":\"sage-os\""))
}

/// How to start the hub: the bundled one next to the app (packaged, F1), else this checkout's Python hub.
fn hub_command(log: &PathBuf) -> Option<Command> {
    let exe_dir = std::env::current_exe().ok()?.parent()?.to_path_buf();
    let bundled = exe_dir.join(if cfg!(windows) { "sage-os-hub.exe" } else { "sage-os-hub" });
    let mut cmd = if bundled.is_file() {
        let mut c = Command::new(bundled);
        c.current_dir(&exe_dir);
        c
    } else {
        let root = std::env::var("SAGE_OS_ROOT").map(PathBuf::from).unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
        });
        let python = if cfg!(windows) {
            root.join("hub").join(".venv").join("Scripts").join("python.exe")
        } else {
            root.join("hub").join(".venv").join("bin").join("python")
        };
        if !python.is_file() {
            return None;
        }
        let mut c = Command::new(python);
        c.args(["-m", "sage_os_hub"]).current_dir(root);
        c
    };
    cmd.arg("--log").arg(log);
    // anything the hub prints before its own log is set up (a bad config, a port in use) lands next to it
    if let Ok(out) = std::fs::OpenOptions::new().create(true).append(true).open(log.with_file_name("hub-console.log")) {
        if let Ok(err) = out.try_clone() {
            cmd.stdout(std::process::Stdio::from(out)).stderr(std::process::Stdio::from(err));
        }
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    Some(cmd)
}

fn log_path(app: &AppHandle) -> PathBuf {
    let dir = app.path().data_dir().map(|d| d.join("Sage OS").join("logs")).unwrap_or_else(|_| std::env::temp_dir());
    let _ = std::fs::create_dir_all(&dir);
    dir.join("hub.log")
}

fn show(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

fn say(app: &AppHandle, text: &str) {
    if let Some(w) = app.get_webview_window("main") {
        let js = format!(
            "var m=document.getElementById('msg'); if (m) {{ m.textContent = {}; m.className = 'err'; }}",
            serde_json_string(text)
        );
        let _ = w.eval(&js);
    }
}

fn serde_json_string(s: &str) -> String {
    let mut out = String::from("\"");
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// Start the hub if it isn't running, wait until it answers, then show it in the window.
fn connect(app: AppHandle) {
    std::thread::spawn(move || {
        let hub = app.state::<Hub>();
        let port = hub.port;
        if !hub_up(port) {
            let log = log_path(&app);
            match hub_command(&log).map(|mut c| c.spawn()) {
                Some(Ok(child)) => *hub.child.lock().unwrap() = Some(child),
                Some(Err(e)) => return say(&app, &format!("Couldn't start Sage OS's hub: {e}")),
                None => return say(&app, "Couldn't find Sage OS's hub next to the app or in the checkout (set SAGE_OS_ROOT)."),
            }
            let started = Instant::now();
            while !hub_up(port) {
                let exited = hub.child.lock().unwrap().as_mut().and_then(|c| c.try_wait().ok().flatten());
                if let Some(status) = exited {
                    return say(&app, &format!("Sage OS's hub stopped while starting ({status}). See {} and hub-console.log next to it.", log.display()));
                }
                if started.elapsed() > Duration::from_secs(90) {
                    return say(&app, &format!("Sage OS's hub didn't answer within 90 s. Its log: {}", log.display()));
                }
                std::thread::sleep(Duration::from_millis(300));
            }
        }
        let url = tauri::Url::parse(&hub.url()).expect("hub url");
        let handle = app.clone();
        let _ = app.run_on_main_thread(move || {
            if let Some(w) = handle.get_webview_window("main") {
                let _ = w.navigate(url);
            }
        });
    });
}

/// Quit: stop the hub cleanly (it unloads the local model on the way out), then the app.
fn quit(app: &AppHandle) {
    let hub = app.state::<Hub>();
    let port = hub.port;
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
    }
    let _ = http(port, "POST", "/api/quit", Duration::from_secs(3));
    let deadline = Instant::now() + Duration::from_secs(20);
    let mut child = hub.child.lock().unwrap().take();
    loop {
        let done = match child.as_mut() {
            Some(c) => c.try_wait().ok().flatten().is_some(),
            None => !hub_up(port),
        };
        if done || Instant::now() > deadline {
            break;
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    if let Some(mut c) = child {
        if c.try_wait().ok().flatten().is_none() {
            let _ = c.kill(); // it didn't stop in time; the next hub start stops any model it left loaded
        }
    }
    app.exit(0);
}

fn allowed(url: &tauri::Url, port: u16) -> bool {
    let host = url.host_str().unwrap_or("");
    url.scheme() == "tauri"
        || host == "tauri.localhost"
        || (host == "127.0.0.1" || host == "localhost") && url.port_or_known_default() == Some(port)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let hidden = std::env::args().any(|a| a == HIDDEN_ARG);
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show(app)))
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, Some(vec![HIDDEN_ARG])))
        .plugin(tauri_plugin_window_state::Builder::default().with_state_flags(StateFlags::all() & !StateFlags::VISIBLE).build())
        .plugin(tauri_plugin_opener::init())
        .manage(Hub { port: port(), child: Mutex::new(None) })
        .setup(move |app| {
            let port = app.state::<Hub>().port;
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Sage OS")
                .inner_size(1440.0, 900.0)
                .min_inner_size(375.0, 560.0)
                .visible(false)
                .on_navigation(move |url| {
                    if allowed(url, port) {
                        return true;
                    }
                    if matches!(url.scheme(), "http" | "https" | "mailto") {
                        let _ = tauri_plugin_opener::open_url(url.as_str(), None::<&str>);
                    }
                    false
                })
                // Links meant for a new tab (note links, chat links, Google sign-in) open in the default browser;
                // the app never opens a second window of its own. A blank tab opened first (Google sign-in does
                // that) is refused, and the page then navigates itself, which on_navigation sends to the browser.
                .on_new_window(|url, _features| {
                    if matches!(url.scheme(), "http" | "https" | "mailto") {
                        let _ = tauri_plugin_opener::open_url(url.as_str(), None::<&str>);
                    }
                    tauri::webview::NewWindowResponse::Deny
                })
                .build()?;
            let _ = window.restore_state(StateFlags::all() & !StateFlags::VISIBLE);
            if !hidden {
                let _ = window.show();
            }

            let handle = app.handle();
            let open = MenuItem::with_id(handle, "open", "Open Sage OS", true, None::<&str>)?;
            let at_login = CheckMenuItem::with_id(handle, "autostart", "Start at sign-in", true,
                                                  handle.autolaunch().is_enabled().unwrap_or(false), None::<&str>)?;
            let quit_item = MenuItem::with_id(handle, "quit", "Quit Sage OS", true, None::<&str>)?;
            let menu = Menu::with_items(handle, &[&open, &PredefinedMenuItem::separator(handle)?, &at_login,
                                                 &PredefinedMenuItem::separator(handle)?, &quit_item])?;
            let toggle = at_login.clone();
            TrayIconBuilder::with_id("tray")
                .icon(app.default_window_icon().cloned().expect("app icon"))
                .tooltip("Sage OS")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(move |app, event| match event.id.as_ref() {
                    "open" => show(app),
                    "autostart" => {
                        let al = app.autolaunch();
                        let on = al.is_enabled().unwrap_or(false);
                        let _ = if on { al.disable() } else { al.enable() };
                        let _ = toggle.set_checked(al.is_enabled().unwrap_or(false));
                    }
                    "quit" => {
                        let app = app.clone();
                        std::thread::spawn(move || quit(&app));
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                        show(tray.app_handle());
                    }
                })
                .build(app)?;

            connect(app.handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close(); // closing keeps Sage OS in the tray; Quit is in the tray menu
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("couldn't start the Sage OS app");
    app.run(|_app, event| {
        if let RunEvent::ExitRequested { code: None, api, .. } = event {
            api.prevent_exit(); // windows closing never ends the app; only Quit does
        }
    });
}
