use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

// desktop/src-tauri -> desktop -> salva repo root（Python core 所在位置）。
// CARGO_MANIFEST_DIR 在編譯期固定指向 desktop/src-tauri，往上兩層即可。
fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("desktop/src-tauri 應該有兩層父目錄（desktop、repo root）")
        .to_path_buf()
}

struct CoreProcess(Mutex<Option<Child>>);

fn spawn_core(repo_root: &PathBuf) -> std::io::Result<Child> {
    Command::new("uv")
        .args(["run", "uvicorn", "apps.api.main:app", "--port", "8765"])
        .current_dir(repo_root)
        .spawn()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let root = repo_root();
            match spawn_core(&root) {
                Ok(child) => {
                    app.manage(CoreProcess(Mutex::new(Some(child))));
                }
                Err(err) => {
                    // core 沒起來不阻擋視窗開啟——前端的健康檢查會顯示 core
                    // offline，使用者至少能看到畫面、知道要去手動排查。
                    eprintln!("無法啟動 salva core（{root:?} 下 `uv run uvicorn ...`）：{err}");
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<CoreProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
