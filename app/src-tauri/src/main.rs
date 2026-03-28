#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, WebviewWindow,
};

const SIDECAR_BASE: &str = "http://localhost:18234";
const OVERLAY_LABEL: &str = "overlay";
const MAIN_LABEL: &str = "main";
const AUTO_INSERT_MS: u64 = 1500;

#[derive(Clone, Serialize, Deserialize)]
struct DictationEvent {
    state: String,
    data: serde_json::Value,
}

static IS_RECORDING: AtomicBool = AtomicBool::new(false);

struct AppState {
    last_text: Mutex<String>,
    raw_text: Mutex<String>,
    detected_language: Mutex<String>,
    auto_insert_handle: Mutex<Option<tauri::async_runtime::JoinHandle<()>>>,
}

// HTTP helpers

fn http_client() -> reqwest::Client {
    reqwest::Client::new()
}

async fn sidecar_post(path: &str, body: Option<serde_json::Value>) -> Result<serde_json::Value, String> {
    let client = http_client();
    let url = format!("{}{}", SIDECAR_BASE, path);
    let req = if let Some(json) = body {
        client.post(&url).json(&json)
    } else {
        client.post(&url)
    };
    let resp = req.send().await.map_err(|e| format!("HTTP request failed: {e}"))?;
    resp.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse response: {e}"))
}

async fn sidecar_get(path: &str) -> Result<serde_json::Value, String> {
    let url = format!("{}{}", SIDECAR_BASE, path);
    let resp = http_client()
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("HTTP request failed: {e}"))?;
    resp.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse response: {e}"))
}

// Overlay helpers

fn show_overlay_near_cursor(window: &WebviewWindow) {
    if let Ok(pos) = window.cursor_position() {
        let x = pos.x as i32;
        let y = pos.y as i32;
        let _ = window.set_position(tauri::Position::Physical(
            tauri::PhysicalPosition { x: x + 16, y: y + 16 },
        ));
    }
    let _ = window.show();
    let _ = window.set_focus();
}

fn hide_overlay(window: &WebviewWindow) {
    let _ = window.hide();
}

// Auto-insert timer management

fn cancel_auto_insert(app: &AppHandle) {
    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut handle) = state.auto_insert_handle.lock() {
            if let Some(h) = handle.take() {
                h.abort();
            }
        }
    }
}

fn restart_auto_insert(app: &AppHandle) {
    cancel_auto_insert(app);
    let app2 = app.clone();
    let handle = tauri::async_runtime::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_millis(AUTO_INSERT_MS)).await;
        if !IS_RECORDING.load(Ordering::SeqCst) {
            insert_and_hide(&app2).await;
        }
    });
    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut h) = state.auto_insert_handle.lock() {
            *h = Some(handle);
        }
    }
}

// Health check

async fn wait_for_sidecar(max_retries: u32, delay_ms: u64) -> Result<serde_json::Value, String> {
    for i in 0..max_retries {
        match sidecar_get("/status").await {
            Ok(resp) => {
                if resp.get("status").and_then(|s| s.as_str()) == Some("ready") {
                    return Ok(resp);
                }
            }
            _ => {}
        }
        if i < max_retries - 1 {
            tokio::time::sleep(std::time::Duration::from_millis(delay_ms)).await;
        }
    }
    Err("Python sidecar not responding".into())
}

// Shortcut toggle handler

fn on_shortcut_toggle(app: &AppHandle) {
    let was_recording = IS_RECORDING.fetch_xor(true, Ordering::SeqCst);

    if !was_recording {
        // Start recording
        cancel_auto_insert(app);

        let overlay = match app.get_webview_window(OVERLAY_LABEL) {
            Some(w) => w,
            None => return,
        };

        let _ = overlay.emit(
            "dictation-state",
            DictationEvent {
                state: "recording".into(),
                data: serde_json::json!({}),
            },
        );

        show_overlay_near_cursor(&overlay);

        let app_handle = app.clone();
        tauri::async_runtime::spawn(async move {
            if let Err(e) = sidecar_post("/start_recording", None).await {
                eprintln!("[DictateMe] start_recording failed: {e}");
                IS_RECORDING.store(false, Ordering::SeqCst);
                if let Some(w) = app_handle.get_webview_window(OVERLAY_LABEL) {
                    let _ = w.emit(
                        "dictation-state",
                        DictationEvent {
                            state: "error".into(),
                            data: serde_json::json!({"message": format!("Failed to start recording: {e}")}),
                        },
                    );
                    // Auto-hide after 3s on error
                    let app3 = app_handle.clone();
                    tauri::async_runtime::spawn(async move {
                        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                        if let Some(w) = app3.get_webview_window(OVERLAY_LABEL) {
                            let _ = w.emit("dictation-state", DictationEvent {
                                state: "hidden".into(),
                                data: serde_json::json!({}),
                            });
                            hide_overlay(&w);
                        }
                    });
                }
            }
        });
    } else {
        // Stop recording -> process -> ready
        let app_handle = app.clone();
        tauri::async_runtime::spawn(async move {
            let overlay = match app_handle.get_webview_window(OVERLAY_LABEL) {
                Some(w) => w,
                None => return,
            };

            let _ = overlay.emit(
                "dictation-state",
                DictationEvent {
                    state: "processing".into(),
                    data: serde_json::json!({}),
                },
            );

            match sidecar_post("/stop_recording", None).await {
                Ok(resp) => {
                    let cleaned = resp.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let raw = resp.get("raw").and_then(|v| v.as_str()).unwrap_or("").to_string();
                    let lang = resp.get("language").and_then(|v| v.as_str()).unwrap_or("en").to_string();

                    if let Some(state) = app_handle.try_state::<AppState>() {
                        if let Ok(mut t) = state.last_text.lock() { *t = cleaned.clone(); }
                        if let Ok(mut r) = state.raw_text.lock() { *r = raw; }
                        if let Ok(mut l) = state.detected_language.lock() { *l = lang.clone(); }
                    }

                    if cleaned.is_empty() {
                        let _ = overlay.emit("dictation-state", DictationEvent {
                            state: "hidden".into(),
                            data: serde_json::json!({}),
                        });
                        hide_overlay(&overlay);
                        return;
                    }

                    // Show text with format pills - user can press 1-8 to pick format
                    let _ = overlay.emit(
                        "dictation-state",
                        DictationEvent {
                            state: "ready".into(),
                            data: serde_json::json!({
                                "text": cleaned,
                                "language": lang,
                                "show_formats": true,
                                "auto_insert_ms": AUTO_INSERT_MS
                            }),
                        },
                    );

                    restart_auto_insert(&app_handle);
                }
                Err(e) => {
                    eprintln!("[DictateMe] stop_recording failed: {e}");
                    let _ = overlay.emit(
                        "dictation-state",
                        DictationEvent {
                            state: "error".into(),
                            data: serde_json::json!({"message": format!("Transcription failed: {e}")}),
                        },
                    );
                    // Auto-hide after 3s
                    let app3 = app_handle.clone();
                    tauri::async_runtime::spawn(async move {
                        tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                        if let Some(w) = app3.get_webview_window(OVERLAY_LABEL) {
                            let _ = w.emit("dictation-state", DictationEvent {
                                state: "hidden".into(),
                                data: serde_json::json!({}),
                            });
                            hide_overlay(&w);
                        }
                    });
                }
            }
        });
    }
}

async fn insert_and_hide(app: &AppHandle) {
    let text = app
        .try_state::<AppState>()
        .and_then(|s| s.last_text.lock().ok().map(|t| t.clone()))
        .unwrap_or_default();

    // Hide overlay FIRST so Windows returns focus to the previous app
    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit(
            "dictation-state",
            DictationEvent {
                state: "hidden".into(),
                data: serde_json::json!({}),
            },
        );
        hide_overlay(&w);
    }

    // Wait for OS to process the focus change back to the original window
    tokio::time::sleep(std::time::Duration::from_millis(150)).await;

    // Now paste into the previously focused window (which now has focus again)
    if !text.is_empty() {
        let _ = sidecar_post("/insert", Some(serde_json::json!({ "text": text }))).await;
    }
}

// Tauri commands

#[tauri::command]
async fn select_format(app: AppHandle, format_key: String) -> Result<serde_json::Value, String> {
    let current_text = app
        .try_state::<AppState>()
        .and_then(|s| s.last_text.lock().ok().map(|t| t.clone()))
        .unwrap_or_default();

    let language = app
        .try_state::<AppState>()
        .and_then(|s| s.detected_language.lock().ok().map(|l| l.clone()))
        .unwrap_or_else(|| "en".into());

    if current_text.is_empty() {
        return Err("No text to reformat".into());
    }

    cancel_auto_insert(&app);

    // "as_is" = no reformat needed
    if format_key == "as_is" {
        restart_auto_insert(&app);
        return Ok(serde_json::json!({"text": current_text}));
    }

    // Emit processing state while reformatting
    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit("dictation-state", DictationEvent {
            state: "reformatting".into(),
            data: serde_json::json!({}),
        });
    }

    let resp = sidecar_post(
        "/reformat",
        Some(serde_json::json!({
            "text": current_text,
            "format": format_key,
            "language": language,
        })),
    ).await?;

    let reformatted = resp.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();

    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut t) = state.last_text.lock() {
            *t = reformatted.clone();
        }
    }

    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit("dictation-state", DictationEvent {
            state: "ready".into(),
            data: serde_json::json!({
                "text": reformatted,
                "show_formats": true,
                "auto_insert_ms": AUTO_INSERT_MS
            }),
        });
    }

    restart_auto_insert(&app);
    Ok(resp)
}

#[tauri::command]
async fn cancel_recording(app: AppHandle) -> Result<(), String> {
    if IS_RECORDING.load(Ordering::SeqCst) {
        IS_RECORDING.store(false, Ordering::SeqCst);
        let _ = sidecar_post("/cancel_recording", None).await;
    }
    cancel_auto_insert(&app);
    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit("dictation-state", DictationEvent {
            state: "hidden".into(),
            data: serde_json::json!({}),
        });
        hide_overlay(&w);
    }
    Ok(())
}

#[tauri::command]
async fn dismiss_overlay(app: AppHandle) -> Result<(), String> {
    cancel_auto_insert(&app);
    IS_RECORDING.store(false, Ordering::SeqCst);
    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit("dictation-state", DictationEvent {
            state: "hidden".into(),
            data: serde_json::json!({}),
        });
        hide_overlay(&w);
    }
    Ok(())
}

#[tauri::command]
async fn insert_now(app: AppHandle) -> Result<(), String> {
    cancel_auto_insert(&app);
    insert_and_hide(&app).await;
    Ok(())
}

#[tauri::command]
async fn get_settings() -> Result<serde_json::Value, String> {
    sidecar_get("/settings").await
}

#[tauri::command]
async fn save_settings(config: serde_json::Value) -> Result<serde_json::Value, String> {
    sidecar_post("/settings", Some(config)).await
}

#[tauri::command]
async fn get_status() -> Result<serde_json::Value, String> {
    sidecar_get("/status").await
}

#[tauri::command]
async fn get_audio_devices() -> Result<serde_json::Value, String> {
    sidecar_get("/audio_devices").await
}

// Entry point

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            last_text: Mutex::new(String::new()),
            raw_text: Mutex::new(String::new()),
            detected_language: Mutex::new("en".into()),
            auto_insert_handle: Mutex::new(None),
        })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            // Tray icon
            let settings_item = MenuItemBuilder::with_id("settings", "Open DictateMe").build(app)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Quit").build(app)?;

            let tray_menu = MenuBuilder::new(app)
                .item(&settings_item)
                .item(&separator)
                .item(&quit_item)
                .build()?;

            TrayIconBuilder::new()
                .tooltip("DictateMe")
                .menu(&tray_menu)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "settings" => {
                        if let Some(w) = app.get_webview_window(MAIN_LABEL) {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // Set window icon (needed for dev mode taskbar/titlebar)
            if let Some(w) = app.get_webview_window(MAIN_LABEL) {
                let png_data = include_bytes!("../icons/128x128.png");
                if let Ok(img) = png::Decoder::new(std::io::Cursor::new(png_data)).read_info().and_then(|mut reader| {
                    let mut buf = vec![0u8; reader.output_buffer_size()];
                    let info = reader.next_frame(&mut buf)?;
                    buf.truncate(info.buffer_size());
                    Ok((buf, info.width, info.height))
                }) {
                    let icon = tauri::image::Image::new_owned(img.0, img.1, img.2);
                    let _ = w.set_icon(icon);
                }
            }

            // Global shortcut
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

            let shortcut = Shortcut::new(
                Some(Modifiers::CONTROL | Modifiers::SHIFT),
                Code::KeyD,
            );

            app.global_shortcut().on_shortcut(shortcut, move |app, _shortcut, _event| {
                on_shortcut_toggle(app);
            })?;

            // Health check sidecar in background
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Some(w) = app_handle.get_webview_window(OVERLAY_LABEL) {
                    let _ = w.emit("sidecar-status", serde_json::json!({"status": "connecting"}));
                }
                if let Some(w) = app_handle.get_webview_window(MAIN_LABEL) {
                    let _ = w.emit("sidecar-status", serde_json::json!({"status": "connecting"}));
                }

                match wait_for_sidecar(30, 1000).await {
                    Ok(status) => {
                        let model_loaded = status.get("model_loaded").and_then(|v| v.as_bool()).unwrap_or(false);
                        let payload = serde_json::json!({
                            "status": "ready",
                            "model_loaded": model_loaded
                        });
                        if let Some(w) = app_handle.get_webview_window(OVERLAY_LABEL) {
                            let _ = w.emit("sidecar-status", payload.clone());
                        }
                        if let Some(w) = app_handle.get_webview_window(MAIN_LABEL) {
                            let _ = w.emit("sidecar-status", payload);
                        }
                    }
                    Err(e) => {
                        eprintln!("[DictateMe] Sidecar check failed: {e}");
                        let payload = serde_json::json!({"status": "error", "message": e});
                        if let Some(w) = app_handle.get_webview_window(OVERLAY_LABEL) {
                            let _ = w.emit("sidecar-status", payload.clone());
                        }
                        if let Some(w) = app_handle.get_webview_window(MAIN_LABEL) {
                            let _ = w.emit("sidecar-status", payload);
                        }
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            select_format,
            get_settings,
            save_settings,
            cancel_recording,
            dismiss_overlay,
            insert_now,
            get_status,
            get_audio_devices,
        ])
        .run(tauri::generate_context!())
        .expect("error while running DictateMe");
}
