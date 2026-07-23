use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager};

// desktop/src-tauri -> desktop -> salva repo root（Python core 所在位置）。
#[cfg(debug_assertions)]
fn repo_root() -> Option<PathBuf> {
    // CARGO_MANIFEST_DIR 是編譯期巨集，把編譯當下這台機器的絕對路徑烤進
    // 執行檔——只在「開發者用 `pnpm tauri dev` 從原始碼跑」時成立，release
    // build 完全不該走這條（見下面 not(debug_assertions) 分支）。
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.to_path_buf())
}

#[cfg(not(debug_assertions))]
fn repo_root() -> Option<PathBuf> {
    // 正式打包版本尚未把 Python core 一起 bundle 進 .app（tauri.conf.json
    // 目前沒有 externalBin/resources 設定，這是已知的後續工作，見 board 卡
    // salva-desktop-tauri-core-carrier 的 environment-parity 審計發現）。
    // SALVA_REPO_ROOT 是給早期測試者手動指向原始碼位置的 escape hatch，
    // 長期解法是把 Python runtime 打進 .app Resources。
    std::env::var("SALVA_REPO_ROOT").ok().map(PathBuf::from)
}

// `uv` 裸名呼叫依賴呼叫端繼承的 PATH。從終端機（`pnpm tauri dev`）啟動時
// PATH 通常有 shell rc 檔追加的路徑；但從 Finder/Dock/launchd 啟動的 GUI
// process 拿到的是精簡過的系統 PATH，官方安裝（~/.local/bin）或 Homebrew
// （/opt/homebrew/bin，Apple Silicon）裝的 uv 都不在裡面。依序試已知安裝
// 位置，最後才退回裸名讓 PATH 有機會解析。
fn resolve_uv_binary() -> PathBuf {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Some(home) = std::env::var_os("HOME") {
        candidates.push(PathBuf::from(&home).join(".local/bin/uv"));
        candidates.push(PathBuf::from(&home).join(".cargo/bin/uv"));
    }
    candidates.push(PathBuf::from("/opt/homebrew/bin/uv"));
    candidates.push(PathBuf::from("/usr/local/bin/uv"));

    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .unwrap_or_else(|| PathBuf::from("uv"))
}

struct CoreProcess(Mutex<Option<Child>>);

fn spawn_core(repo_root: &PathBuf) -> std::io::Result<Child> {
    Command::new(resolve_uv_binary())
        .args(["run", "uvicorn", "apps.api.main:app", "--port", "8765"])
        .current_dir(repo_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
}

// 轉發子進程輸出到本進程的 stdout/stderr 並記錄下來，讓「spawn() 成功但
// process 隨後立刻死掉」（找不到 pyproject.toml、venv 壞掉等）不會是完全
// 沉默的失敗——至少終端機/log 看得到，且會被下面的存活檢查讀到最後幾行。
fn forward_and_capture(
    reader: impl std::io::Read + Send + 'static,
    prefix: &'static str,
) -> std::sync::Arc<Mutex<Vec<String>>> {
    let captured = std::sync::Arc::new(Mutex::new(Vec::new()));
    let captured_clone = captured.clone();
    thread::spawn(move || {
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            eprintln!("[core:{prefix}] {line}");
            if let Ok(mut buf) = captured_clone.lock() {
                buf.push(line);
                if buf.len() > 50 {
                    buf.remove(0);
                }
            }
        }
    });
    captured
}

fn emit_core_status(app: &AppHandle, online: bool, error: Option<String>) {
    let _ = app.emit("core-status", serde_json::json!({ "online": online, "error": error }));
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let handle = app.handle().clone();
            let Some(root) = repo_root() else {
                emit_core_status(
                    &handle,
                    false,
                    Some(
                        "找不到 salva core 原始碼位置（正式打包版本尚未內建 Python \
                         core，需設定 SALVA_REPO_ROOT 環境變數指向 repo 根目錄）"
                            .to_string(),
                    ),
                );
                return Ok(());
            };

            match spawn_core(&root) {
                Ok(mut child) => {
                    let stdout = child.stdout.take();
                    let stderr = child.stderr.take();
                    let stderr_tail = stderr.map(|s| forward_and_capture(s, "stderr"));
                    if let Some(stdout) = stdout {
                        forward_and_capture(stdout, "stdout");
                    }

                    // 立刻 manage，讓視窗關閉時的清理邏輯一開始就抓得到這個
                    // child——不要等下面的存活檢查完才交出去，否則使用者在
                    // 檢查完成前關窗，這個 process 就沒人 kill（孤兒進程）。
                    app.manage(CoreProcess(Mutex::new(Some(child))));

                    // spawn() 只保證 process 起得來，不保證跑得動——例如
                    // repo_root 算錯、找不到 pyproject.toml，uv 會很快自己
                    // 退出。短暫等待後透過 managed state 檢查一次，把這類
                    // 「看起來成功其實已死」的情況也回報給前端，而不是讓
                    // 使用者永遠卡在健康燈號沒有理由的 offline。
                    let handle_for_check = handle.clone();
                    thread::spawn(move || {
                        thread::sleep(Duration::from_millis(1500));
                        let Some(state) = handle_for_check.try_state::<CoreProcess>() else {
                            return;
                        };
                        let Ok(mut guard) = state.0.lock() else { return };
                        // try_wait() 的 &mut Child 借用必須在 `*guard = None`
                        // 之前結束，所以先算出結果存起來，離開這個 match
                        // 的借用範圍後才動 guard 本身。
                        let wait_result = match guard.as_mut() {
                            Some(child) => child.try_wait(),
                            None => return,
                        };
                        match wait_result {
                            Ok(Some(status)) => {
                                let tail = stderr_tail
                                    .and_then(|t| t.lock().ok().map(|v| v.join("\n")))
                                    .unwrap_or_default();
                                *guard = None; // 已經死了，別讓關窗邏輯再 kill 一次
                                emit_core_status(
                                    &handle_for_check,
                                    false,
                                    Some(format!(
                                        "salva core 啟動後立刻結束（exit={status}）。\
                                         最後幾行輸出：\n{tail}"
                                    )),
                                );
                            }
                            Ok(None) => emit_core_status(&handle_for_check, true, None),
                            Err(err) => emit_core_status(
                                &handle_for_check,
                                false,
                                Some(format!("無法確認 salva core 存活狀態：{err}")),
                            ),
                        }
                    });
                }
                Err(err) => {
                    emit_core_status(
                        &handle,
                        false,
                        Some(format!(
                            "無法啟動 salva core（{root:?} 下執行 `uv run uvicorn ...`）：\
                             {err}（確認 uv 已安裝，或設定 SALVA_REPO_ROOT）"
                        )),
                    );
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
