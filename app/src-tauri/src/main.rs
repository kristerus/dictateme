#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{
    menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, WebviewWindow,
};

// Constants
const SIDECAR_BASE: &str = "http://localhost:18234";
const OVERLAY_LABEL: &str = "overlay";
const SETTINGS_LABEL: &str = "settings";

// Dictation state event payload
#[derive(Clone, Serialize, Deserialize)]
struct DictationEvent {
    state: String,
    data: serde_json::Value,
}

// Global toggle shared across shortcut presses
static IS_RECORDING: AtomicBool = AtomicBool::new(false);

struct AppState {
    last_text: Mutex<String>,
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

// Overlay window helpers

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

// Shortcut toggle handler

fn on_shortcut_toggle(app: &AppHandle) {
    let was_recording = IS_RECORDING.fetch_xor(true, Ordering::SeqCst);

    if !was_recording {
        // Start recording
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
                            state: "hidden".into(),
                            data: serde_json::json!({}),
                        },
                    );
                    hide_overlay(&w);
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
                    let transcribed = resp
                        .get("text")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();

                    if let Some(state) = app_handle.try_state::<AppState>() {
                        if let Ok(mut t) = state.last_text.lock() {
                            *t = transcribed.clone();
                        }
                    }

                    let _ = overlay.emit(
                        "dictation-state",
                        DictationEvent {
                            state: "ready".into(),
                            data: serde_json::json!({
                                "text": transcribed,
                                "show_formats": true,
                                "auto_insert_ms": 1500
                            }),
                        },
                    );

                    let app2 = app_handle.clone();
                    tauri::async_runtime::spawn(async move {
                        tokio::time::sleep(std::time::Duration::from_millis(1500)).await;
                        if !IS_RECORDING.load(Ordering::SeqCst) {
                            insert_and_hide(&app2).await;
                        }
                    });
                }
                Err(e) => {
                    eprintln!("[DictateMe] stop_recording failed: {e}");
                    let _ = overlay.emit(
                        "dictation-state",
                        DictationEvent {
                            state: "hidden".into(),
                            data: serde_json::json!({"error": e}),
                        },
                    );
                    hide_overlay(&overlay);
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

    let _ = sidecar_post(
        "/insert",
        Some(serde_json::json!({ "text": text })),
    )
    .await;

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
}

// Tauri commands (callable from JS)

#[tauri::command]
async fn select_format(app: AppHandle, index: u32) -> Result<serde_json::Value, String> {
    let resp = sidecar_post(
        "/reformat",
        Some(serde_json::json!({ "index": index })),
    )
    .await?;

    let reformatted = resp
        .get("text")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut t) = state.last_text.lock() {
            *t = reformatted.clone();
        }
    }

    if let Some(w) = app.get_webview_window(OVERLAY_LABEL) {
        let _ = w.emit(
            "dictation-state",
            DictationEvent {
                state: "ready".into(),
                data: serde_json::json!({
                    "text": reformatted,
                    "show_formats": true,
                    "auto_insert_ms": 1500
                }),
            },
        );
    }

    let app2 = app.clone();
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_millis(1500)).await;
        if !IS_RECORDING.load(Ordering::SeqCst) {
            insert_and_hide(&app2).await;
        }
    });

    Ok(resp)
}

#[tauri::command]
async fn get_settings() -> Result<serde_json::Value, String> {
    sidecar_get("/settings").await
}

#[tauri::command]
async fn save_settings(config: serde_json::Value) -> Result<serde_json::Value, String> {
    sidecar_post("/settings", Some(config)).await
}

// Entry point

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            last_text: Mutex::new(String::new()),
        })
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            // Tray icon
            let settings_item = MenuItemBuilder::with_id("settings", "Settings").build(app)?;
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
                        if let Some(w) = app.get_webview_window(SETTINGS_LABEL) {
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

            // Global shortcut (Ctrl + Super as toggle)
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

            let shortcut = Shortcut::new(
                Some(Modifiers::CONTROL | Modifiers::SUPER),
                Code::Space,
            );

            app.global_shortcut().on_shortcut(shortcut, move |app, _shortcut, _event| {
                on_shortcut_toggle(app);
            })?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            select_format,
            get_settings,
            save_settings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running DictateMe");
}

