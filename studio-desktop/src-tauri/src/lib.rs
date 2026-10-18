//! PROMETEO Studio · host nativo (Tauri 2)
//!
//! Arranque (CLAUDE-REMEDIATION-001 · PA-001, PA-005, seguridad de tokens):
//! 1. La ventana se crea de inmediato; el frontend muestra el progreso real.
//! 2. El backend Python se lanza en un hilo aparte: el hilo principal nunca espera.
//! 3. La salud se comprueba con GET /api/health (HTTP), no solo con una conexión TCP,
//!    y se vigila si el proceso hijo termina para informar la causa.
//! 4. Los datos mutables viven en la carpeta de datos de la app (PROMETEO_WORKSPACE),
//!    nunca dentro del paquete .app, que puede estar en un DMG de solo lectura.
//! 5. El token de sesión sale de /dev/urandom, se entrega al hijo por stdin y nunca
//!    se escribe en registros ni en argumentos de proceso.
//! 6. Cerrar con trabajo sin guardar pregunta antes (CAMP-002 · F1, `close_guard`).

mod close_guard;
#[cfg(target_os = "macos")]
mod mac_terminate;

use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{Emitter, Manager, State, WindowEvent};

use close_guard::{CloseDecision, UnsavedState, CLOSE_REQUEST_SCRIPT};

const HEALTH_TIMEOUT: Duration = Duration::from_secs(90);
const LOG_ROTATE_BYTES: u64 = 5 * 1024 * 1024;

/// Estado visible para el frontend. Nunca contiene el token.
#[derive(Clone, Debug, Serialize)]
pub struct BackendStatus {
    /// STARTING | BACKEND_READY | DEGRADED | FAILED
    pub state: String,
    pub port: u16,
    pub code: Option<String>,
    pub message: Option<String>,
    pub exit_code: Option<i32>,
    pub log_path: Option<String>,
    pub workspace_path: Option<String>,
    pub elapsed_ms: u64,
}

pub struct AppState {
    pub status: Arc<Mutex<BackendStatus>>,
    pub child: Arc<Mutex<Option<Child>>>,
    /// Mantener stdin abierto es el "salvavidas": al cerrarse, el sidecar termina.
    pub child_stdin: Arc<Mutex<Option<ChildStdin>>>,
    /// Trabajo sin guardar declarado por la interfaz (guarda de cierre).
    pub unsaved: Arc<Mutex<UnsavedState>>,
    /// Escenario de prueba nativa (`PROMETEO_AUTOTEST`); `None` en un arranque normal.
    pub autotest: Option<String>,
}

/// Escenarios de prueba nativa admitidos. Cualquier otro valor se ignora.
const AUTOTEST_SCENARIOS: [&str; 4] = ["unsaved_verified", "unsaved_verified_close_window", "clean_close_window", "unsaved_verified_reload_close"];

/// Solo pruebas nativas: pide el cierre de la ventana por el mismo camino que el botón rojo
/// (`CloseRequested`). Rechazado si la app no se lanzó con `PROMETEO_AUTOTEST`.
#[tauri::command]
fn request_close_for_test(app: tauri::AppHandle, state: State<AppState>) -> Result<(), String> {
    if state.autotest.is_none() {
        return Err("no disponible fuera de las pruebas nativas".into());
    }
    eprintln!("[PROMETEO HOST] prueba: cierre de ventana solicitado");
    if let Some(window) = app.get_webview_window("main") {
        window.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn lock_unsaved(state: &AppState) -> std::sync::MutexGuard<'_, UnsavedState> {
    state.unsaved.lock().unwrap_or_else(|p| p.into_inner())
}

/// La interfaz informa de si hay trabajo que se perdería al cerrar. `seq` crece con cada aviso:
/// un aviso viejo que llegue tarde se ignora.
#[tauri::command]
fn set_unsaved_work(state: State<AppState>, seq: u64, dirty: bool, kind: String, count: u32) {
    lock_unsaved(&state).report(seq, dirty, &kind, count);
}

/// La interfaz confirma que mostró el diálogo de cierre.
#[tauri::command]
fn close_dialog_shown(state: State<AppState>) {
    eprintln!("[PROMETEO HOST] la interfaz mostró el diálogo de cierre");
    lock_unsaved(&state).acknowledge();
}

/// La persona decidió cerrar (guardó o descartó): se cierra sin volver a preguntar.
#[tauri::command]
fn confirm_close(app: tauri::AppHandle, state: State<AppState>) {
    eprintln!("[PROMETEO HOST] cierre confirmado por la interfaz");
    lock_unsaved(&state).allow_close = true;
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.close();
    }
}

/// Pide a la interfaz que pregunte antes de cerrar (y trae la ventana al frente: si estaba
/// minimizada, el diálogo quedaría invisible).
fn ask_interface_to_confirm(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        let _ = window.eval(CLOSE_REQUEST_SCRIPT);
    }
}

/// Decisión común para todas las vías de salida (ventana, ⌘Q, Dock, cierre de sesión).
pub(crate) fn guard_exit(app: &tauri::AppHandle, via: &str) -> CloseDecision {
    if app.get_webview_window("main").is_none() {
        return CloseDecision::Allow;
    }
    let state: State<AppState> = app.state();
    let decision = lock_unsaved(&state).decide(Instant::now());
    if decision == CloseDecision::AskUser {
        eprintln!("[PROMETEO HOST] {} en espera: hay trabajo sin guardar", via);
        ask_interface_to_confirm(app);
    }
    decision
}

#[tauri::command]
fn get_backend_config(state: State<AppState>) -> BackendStatus {
    state.status.lock().map(|s| s.clone()).unwrap_or_else(|p| p.into_inner().clone())
}

fn find_free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(0)
}

/// 32 bytes aleatorios del sistema operativo en hexadecimal.
fn generate_auth_token() -> String {
    let mut buf = [0u8; 32];
    let mut filled = false;
    if let Ok(mut f) = File::open("/dev/urandom") {
        filled = f.read_exact(&mut buf).is_ok();
    }
    if !filled {
        // Sin /dev/urandom (Windows): RandomState se siembra con aleatoriedad del SO.
        use std::collections::hash_map::RandomState;
        use std::hash::{BuildHasher, Hasher};
        for chunk in buf.chunks_mut(8) {
            let mut h = RandomState::new().build_hasher();
            h.write_u128(Instant::now().elapsed().as_nanos());
            chunk.copy_from_slice(&h.finish().to_le_bytes()[..chunk.len()]);
        }
    }
    buf.iter().map(|b| format!("{:02x}", b)).collect()
}

fn locate_python_and_root(resource_dir: Option<PathBuf>) -> Result<(PathBuf, PathBuf), String> {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(contents_dir) = exe_path.parent().and_then(|p| p.parent()) {
            candidates.push(contents_dir.join("Resources"));
        }
    }
    if let Some(res) = resource_dir {
        candidates.push(res);
    }
    for res_dir in candidates {
        let py3 = res_dir.join("runtime").join("bin").join("python3");
        let py = res_dir.join("runtime").join("bin").join("python");
        let bundled_py = if py3.exists() { py3 } else { py };
        let runner = res_dir.join("studio").join("backend").join("desktop_runner.py");
        if bundled_py.exists() && runner.exists() {
            return Ok((bundled_py, res_dir));
        }
    }
    // Modo desarrollo: repositorio con .venv en el directorio actual.
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let venv_py = cwd.join(".venv").join("bin").join("python");
    let dev_runner = cwd.join("studio").join("backend").join("desktop_runner.py");
    if venv_py.exists() && dev_runner.exists() {
        return Ok((venv_py, cwd));
    }
    if dev_runner.exists() {
        return Ok((PathBuf::from("python3"), cwd));
    }
    Err("No se encontró el runtime empaquetado de PROMETEO.".to_string())
}

/// GET /api/health por HTTP/1.1 sin dependencias externas.
/// Devuelve Some(json) si el servidor respondió 200 con un cuerpo JSON.
fn http_health(port: u16) -> Option<serde_json::Value> {
    let addr: SocketAddr = format!("127.0.0.1:{}", port).parse().ok()?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(500)).ok()?;
    stream.set_read_timeout(Some(Duration::from_secs(3))).ok()?;
    stream.set_write_timeout(Some(Duration::from_secs(2))).ok()?;
    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\nAccept: application/json\r\n\r\n",
        port
    );
    stream.write_all(req.as_bytes()).ok()?;
    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).ok()?;
    let text = String::from_utf8_lossy(&raw);
    let (head, body) = text.split_once("\r\n\r\n")?;
    let status_line = head.lines().next()?;
    if !status_line.contains(" 200 ") {
        return None;
    }
    // Uvicorn puede usar chunked encoding: tomar el primer objeto JSON del cuerpo.
    let start = body.find('{')?;
    let end = body.rfind('}')?;
    serde_json::from_str(&body[start..=end]).ok()
}

fn open_backend_log(log_dir: &Path) -> Option<(File, PathBuf)> {
    std::fs::create_dir_all(log_dir).ok()?;
    let path = log_dir.join("backend.log");
    if let Ok(meta) = std::fs::metadata(&path) {
        if meta.len() > LOG_ROTATE_BYTES {
            let _ = std::fs::rename(&path, log_dir.join("backend.log.1"));
        }
    }
    let file = OpenOptions::new().create(true).append(true).open(&path).ok()?;
    Some((file, path))
}

fn set_status(app: &tauri::AppHandle, status: &Arc<Mutex<BackendStatus>>, update: impl FnOnce(&mut BackendStatus)) {
    let snapshot = {
        let mut s = match status.lock() {
            Ok(g) => g,
            Err(p) => p.into_inner(),
        };
        update(&mut s);
        s.clone()
    };
    eprintln!(
        "[PROMETEO HOST] backend {} code={:?} ({} ms)",
        snapshot.state, snapshot.code, snapshot.elapsed_ms
    );
    let _ = app.emit("backend-status", snapshot);
}

/// Lanza el sidecar y vigila su salud. Corre fuera del hilo principal.
fn launch_backend(
    app: tauri::AppHandle,
    status: Arc<Mutex<BackendStatus>>,
    child_slot: Arc<Mutex<Option<Child>>>,
    stdin_slot: Arc<Mutex<Option<ChildStdin>>>,
    port: u16,
    token: String,
) {
    let started = Instant::now();
    let ms = |t: Instant| t.elapsed().as_millis() as u64;

    let (python_bin, root) = match locate_python_and_root(app.path().resource_dir().ok()) {
        Ok(pair) => pair,
        Err(e) => {
            set_status(&app, &status, |s| {
                s.state = "FAILED".into();
                s.code = Some("RUNTIME_NOT_FOUND".into());
                s.message = Some(e);
                s.elapsed_ms = ms(started);
            });
            return;
        }
    };

    // Datos mutables: carpeta de datos de la app, nunca dentro del paquete.
    let workspace = app
        .path()
        .app_data_dir()
        .map(|d| d.join("workspace"))
        .unwrap_or_else(|_| std::env::temp_dir().join("prometeo-studio").join("workspace"));
    let log_dir = app
        .path()
        .app_log_dir()
        .unwrap_or_else(|_| std::env::temp_dir().join("prometeo-studio-logs"));
    let log = open_backend_log(&log_dir);
    let log_path = log.as_ref().map(|(_, p)| p.display().to_string());
    set_status(&app, &status, |s| {
        s.log_path = log_path.clone();
        s.workspace_path = Some(workspace.display().to_string());
    });

    let runner = root.join("studio").join("backend").join("desktop_runner.py");
    let mut cmd = Command::new(&python_bin);
    cmd.arg(&runner)
        .arg("--port")
        .arg(port.to_string())
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--token-stdin")
        .arg("--parent-pid")
        .arg(std::process::id().to_string())
        .arg("--watch-stdin")
        .current_dir(&root)
        .env("PYTHONPATH", format!("{}:{}", root.display(), root.join("fase0").display()))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("PROMETEO_WORKSPACE", &workspace)
        .env("PROMETEO_APP_DIR", &root)
        .stdin(Stdio::piped());

    let tess_dir = root.join("ocr");
    if tess_dir.join("tessdata").exists() {
        cmd.env("TESSDATA_PREFIX", tess_dir.join("tessdata"));
    }
    if tess_dir.join("bin").exists() {
        let cur = std::env::var("PATH").unwrap_or_else(|_| "/usr/bin:/bin".to_string());
        cmd.env("PATH", format!("{}:{}", tess_dir.join("bin").display(), cur));
        cmd.env("PROMETEO_TESSERACT_PATH", tess_dir.join("bin").join("tesseract"));
    }
    match log.as_ref().and_then(|(f, _)| Some((f.try_clone().ok()?, f.try_clone().ok()?))) {
        Some((out, err)) => {
            cmd.stdout(Stdio::from(out)).stderr(Stdio::from(err));
        }
        None => {
            cmd.stdout(Stdio::null()).stderr(Stdio::null());
        }
    }

    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            set_status(&app, &status, |s| {
                s.state = "FAILED".into();
                s.code = Some("SPAWN_FAILED".into());
                s.message = Some(format!("No se pudo iniciar el motor: {}", e.kind()));
                s.elapsed_ms = ms(started);
            });
            return;
        }
    };

    // Entregar el token por stdin y conservar el descriptor abierto (salvavidas).
    if let Some(mut stdin) = child.stdin.take() {
        let _ = stdin.write_all(format!("TOKEN {}\n", token).as_bytes());
        let _ = stdin.flush();
        if let Ok(mut slot) = stdin_slot.lock() {
            *slot = Some(stdin);
        }
    }
    if let Ok(mut slot) = child_slot.lock() {
        *slot = Some(child);
    }

    let mut announced: Option<String> = None;
    loop {
        // Si el host ya detuvo el motor (ventana cerrada), terminar la vigilancia.
        if child_slot.lock().map(|g| g.is_none()).unwrap_or(true) {
            return;
        }
        // ¿Terminó el proceso hijo?
        let exited = child_slot
            .lock()
            .ok()
            .and_then(|mut g| g.as_mut().and_then(|c| c.try_wait().ok().flatten()));
        if let Some(exit) = exited {
            set_status(&app, &status, |s| {
                s.state = "FAILED".into();
                s.code = Some("BACKEND_EXITED".into());
                s.exit_code = exit.code();
                s.message = Some("El motor de PROMETEO terminó inesperadamente.".into());
                s.elapsed_ms = ms(started);
            });
            return;
        }

        if let Some(health) = http_health(port) {
            let ready = health.get("ready").and_then(|v| v.as_bool()).unwrap_or(false);
            let state = if ready { "BACKEND_READY" } else { "DEGRADED" };
            if announced.as_deref() != Some(state) {
                let code = health
                    .get("workspace")
                    .and_then(|w| w.get("error_code"))
                    .and_then(|c| c.as_str())
                    .map(|c| c.to_string());
                set_status(&app, &status, |s| {
                    s.state = state.into();
                    s.code = if ready { None } else { code.or(Some("BACKEND_DEGRADED".into())) };
                    s.message = None;
                    s.elapsed_ms = ms(started);
                });
                announced = Some(state.to_string());
            }
            // Una vez sano, seguir vigilando con menos frecuencia por si el proceso muere.
            std::thread::sleep(Duration::from_millis(5000));
            continue;
        }

        if announced.is_none() && started.elapsed() > HEALTH_TIMEOUT {
            set_status(&app, &status, |s| {
                s.state = "FAILED".into();
                s.code = Some("HEALTH_TIMEOUT".into());
                s.message = Some("El motor no respondió a tiempo.".into());
                s.elapsed_ms = ms(started);
            });
            announced = Some("FAILED".into());
        }
        std::thread::sleep(Duration::from_millis(if announced.is_some() { 1500 } else { 150 }));
    }
}

fn stop_backend(state: &AppState, reason: &str) {
    if let Ok(mut slot) = state.child_stdin.lock() {
        slot.take(); // cerrar stdin: el sidecar limpia y termina por sí mismo
    }
    if let Ok(mut lock) = state.child.lock() {
        if let Some(mut child) = lock.take() {
            eprintln!("[PROMETEO HOST] deteniendo motor ({})", reason);
            let deadline = Instant::now() + Duration::from_secs(3);
            while Instant::now() < deadline {
                if let Ok(Some(_)) = child.try_wait() {
                    return;
                }
                std::thread::sleep(Duration::from_millis(50));
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .setup(|app| {
            let port = find_free_port();
            let token = generate_auth_token();
            let status = Arc::new(Mutex::new(BackendStatus {
                state: "STARTING".into(),
                port,
                code: None,
                message: None,
                exit_code: None,
                log_path: None,
                workspace_path: None,
                elapsed_ms: 0,
            }));
            let child = Arc::new(Mutex::new(None));
            let child_stdin = Arc::new(Mutex::new(None));
            app.manage(AppState {
                status: status.clone(),
                child: child.clone(),
                child_stdin: child_stdin.clone(),
                unsaved: Arc::new(Mutex::new(UnsavedState::default())),
                autotest: std::env::var("PROMETEO_AUTOTEST").ok().filter(|v| AUTOTEST_SCENARIOS.contains(&v.as_str())),
            });

            // 1. Motor en segundo plano, lanzado ANTES de construir la ventana: crear el
            //    WKWebView tarda varios segundos y no debe retrasar el arranque del motor.
            let handle = app.handle().clone();
            let token_for_backend = token.clone();
            std::thread::spawn(move || launch_backend(handle, status, child, child_stdin, port, token_for_backend));
            // 2. Ventana. El script se inyecta antes de cualquier código de la página.
            // Solo para pruebas nativas: `open --env PROMETEO_AUTOOPEN_SAMPLE=case_a` abre una muestra.
            let auto_open = std::env::var("PROMETEO_AUTOOPEN_SAMPLE")
                .ok()
                .filter(|v| !v.is_empty() && v.len() <= 32 && v.chars().all(|c| c.is_ascii_alphanumeric() || c == '_'))
                .map(|v| format!("'{}'", v))
                .unwrap_or_else(|| "null".to_string());
            let auto_test = app
                .state::<AppState>()
                .autotest
                .as_ref()
                .map(|v| format!("'{}'", v))
                .unwrap_or_else(|| "null".to_string());
            let script = format!(
                "window.__PROMETEO_BACKEND__ = Object.freeze({{ port: {}, token: '{}', autoOpenSample: {}, autoTest: {} }});",
                port, token, auto_open, auto_test
            );
            tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::default())
                .title("PROMETEO Studio")
                .inner_size(1360.0, 860.0)
                .min_inner_size(960.0, 620.0)
                .resizable(true)
                // Fondo de la app desde el primer instante (sin destello gris antes del primer pintado).
                .background_color(tauri::window::Color(15, 15, 17, 255))
                // Sin suspensión en segundo plano: una verificación larga con la app oculta no se congela.
                .background_throttling(tauri::utils::config::BackgroundThrottlingPolicy::Disabled)
                .initialization_script(&script)
                .build()?;

            // ⌘Q, «Salir» del Dock y el cierre de sesión llegan por applicationShouldTerminate:,
            // que Tauri/tao no exponen: se añade al delegado para que pasen por la guarda.
            #[cfg(target_os = "macos")]
            mac_terminate::install(app.handle());

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_config, set_unsaved_work, close_dialog_shown, confirm_close, request_close_for_test])
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                if guard_exit(window.app_handle(), "cierre") == CloseDecision::AskUser {
                    api.prevent_close();
                }
            }
            WindowEvent::Destroyed => {
                let state: State<AppState> = window.state();
                stop_backend(&state, "ventana cerrada");
            }
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| match event {
            // ⌘Q o «Salir»: mientras la ventana exista y haya trabajo sin guardar, preguntar antes.
            tauri::RunEvent::ExitRequested { api, .. } => {
                if guard_exit(app_handle, "salida") == CloseDecision::AskUser {
                    api.prevent_exit();
                }
            }
            tauri::RunEvent::Exit => {
                let state: State<AppState> = app_handle.state();
                stop_backend(&state, "salida de la app");
            }
            _ => {}
        });
}
