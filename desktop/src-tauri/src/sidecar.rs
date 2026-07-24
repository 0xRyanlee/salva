// App-managed LLM sidecar 行程：consent gate → preflight（PATH/登入檢查）→
// spawn → 存活監控 → crash 後有上限的自動重啟。設計文件：
// docs/spec/sidecar-managed-process.md。
//
// 刻意不與 lib.rs 的 core-process 邏輯共用一個 process-supervisor
// 抽象（spec §7 open item 3）——兩邊各自的 spawn/kill/liveness 保持顯式
// 重複，方便之後追某個 process 是怎麼死的時不用先猜共用邏輯藏了什麼。

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Emitter, Manager, State};

use crate::{augmented_path, forward_and_capture, repo_root, resolve_uv_binary};

const CLI_ORDER: [&str; 2] = ["claude", "codex"];
const LOGIN_POLL_INTERVAL: Duration = Duration::from_secs(5);
const LOGIN_POLL_TIMEOUT: Duration = Duration::from_secs(600);
const CRASH_MONITOR_POLL_INTERVAL: Duration = Duration::from_millis(1000);
const LIVENESS_CHECK_DELAY: Duration = Duration::from_millis(1500);
const AUTO_RESTART_BACKOFF: Duration = Duration::from_secs(5);
const MAX_AUTO_RESTARTS: u32 = 2;

#[derive(Clone, Debug, PartialEq)]
pub(crate) enum SidecarState {
    Disabled,
    Probing,
    AwaitingLogin { detail: String },
    Starting,
    Running,
    External,
    Failed { detail: String },
    Byok,
}

impl SidecarState {
    fn as_str(&self) -> &'static str {
        match self {
            SidecarState::Disabled => "disabled",
            SidecarState::Probing => "probing",
            SidecarState::AwaitingLogin { .. } => "awaiting_login",
            SidecarState::Starting => "starting",
            SidecarState::Running => "running",
            SidecarState::External => "external",
            SidecarState::Failed { .. } => "failed",
            SidecarState::Byok => "byok",
        }
    }

    fn detail(&self) -> Option<String> {
        match self {
            SidecarState::AwaitingLogin { detail } | SidecarState::Failed { detail } => {
                Some(detail.clone())
            }
            _ => None,
        }
    }
}

pub(crate) struct SidecarManager {
    state: Mutex<SidecarState>,
    child: Mutex<Option<Child>>,
    restart_count: Mutex<u32>,
}

impl SidecarManager {
    pub(crate) fn new() -> Self {
        Self {
            state: Mutex::new(SidecarState::Disabled),
            child: Mutex::new(None),
            restart_count: Mutex::new(0),
        }
    }
}

#[derive(serde::Serialize)]
pub(crate) struct SidecarStatusDto {
    state: String,
    detail: Option<String>,
}

#[derive(serde::Deserialize)]
struct PreflightEntry {
    status: String,
    path: Option<String>,
}

type PreflightResult = HashMap<String, PreflightEntry>;

pub(crate) fn byok_configured() -> bool {
    let base = std::env::var("SALVA_BYOK_BASE_URL").unwrap_or_default();
    let key = std::env::var("SALVA_BYOK_API_KEY").unwrap_or_default();
    !base.is_empty() && !key.is_empty()
}

fn emit_sidecar_status(app: &AppHandle, state: &SidecarState) {
    let _ = app.emit(
        "sidecar-managed-status",
        serde_json::json!({ "state": state.as_str(), "detail": state.detail() }),
    );
}

pub(crate) fn set_state(app: &AppHandle, manager: &SidecarManager, new_state: SidecarState) {
    if let Ok(mut guard) = manager.state.lock() {
        *guard = new_state.clone();
    }
    emit_sidecar_status(app, &new_state);
}

// App 退出時的清理——鏡射 lib.rs CoreProcess 的關窗處理，但多一個例外：
// exit-3 偵測到的 External 狀態代表這個 socket 是別的（手動 terminal 或
// 另一個 app instance）process 在管，app 沒有這個 child 的所有權，關窗
// 什麼都不做（spec §4）。
pub(crate) fn kill_on_close(manager: &SidecarManager) {
    let is_external = matches!(
        manager.state.lock().map(|g| g.clone()),
        Ok(SidecarState::External)
    );
    if is_external {
        return;
    }
    if let Ok(mut guard) = manager.child.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
        }
    }
}

fn spawn_sidecar(repo_root: &PathBuf) -> std::io::Result<Child> {
    Command::new(resolve_uv_binary())
        .args(["run", "python", "-m", "salva_core.llm_sidecar_run"])
        .current_dir(repo_root)
        .env("PATH", augmented_path())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
}

fn run_preflight(repo_root: &PathBuf) -> Result<PreflightResult, String> {
    let output = Command::new(resolve_uv_binary())
        .args([
            "run",
            "python",
            "-m",
            "salva_core.llm_sidecar_run",
            "--preflight",
        ])
        .current_dir(repo_root)
        .env("PATH", augmented_path())
        .output()
        .map_err(|err| format!("preflight 執行失敗：{err}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let line = stdout.lines().last().unwrap_or("").trim();
    serde_json::from_str(line).map_err(|err| format!("preflight 輸出格式錯誤：{err}（{line}）"))
}

fn summarize_preflight(result: &PreflightResult) -> String {
    CLI_ORDER
        .iter()
        .map(|cli| {
            let status = result
                .get(*cli)
                .map(|entry| entry.status.as_str())
                .unwrap_or("unknown");
            format!("{cli}: {status}")
        })
        .collect::<Vec<_>>()
        .join("; ")
}

// consent 通過（或 launch 時 consent 已持久化）後的入口：BYOK 已經在
// setup() 裡直接處理過，這裡只剩「probe 再 spawn」這條路——不管是第一次
// consent、每次啟動的重跑，還是崩潰後的自動/手動重啟，都走同一條路徑。
pub(crate) fn start_probe_and_spawn(app: AppHandle) {
    thread::spawn(move || {
        let manager = app.state::<SidecarManager>();
        let Some(root) = repo_root() else {
            set_state(
                &app,
                &manager,
                SidecarState::Failed {
                    detail: "找不到 salva core 原始碼位置（需設定 SALVA_REPO_ROOT）".to_string(),
                },
            );
            return;
        };

        set_state(&app, &manager, SidecarState::Probing);
        match run_preflight(&root) {
            Ok(result) => {
                if result.values().any(|entry| entry.status == "ok") {
                    do_spawn(&app, &manager, &root);
                } else {
                    set_state(
                        &app,
                        &manager,
                        SidecarState::AwaitingLogin {
                            detail: summarize_preflight(&result),
                        },
                    );
                }
            }
            Err(detail) => {
                set_state(&app, &manager, SidecarState::Failed { detail });
            }
        }
    });
}

fn do_spawn(app: &AppHandle, manager: &SidecarManager, root: &PathBuf) {
    set_state(app, manager, SidecarState::Starting);
    match spawn_sidecar(root) {
        Ok(mut child) => {
            let stdout = child.stdout.take();
            let stderr = child.stderr.take();
            let stderr_tail = stderr.map(|s| forward_and_capture(s, "sidecar:stderr"));
            if let Some(stdout) = stdout {
                forward_and_capture(stdout, "sidecar:stdout");
            }

            // 立刻 manage，理由跟 lib.rs 的 core spawn 一樣：關窗清理邏輯要
            // 在存活檢查跑完之前就抓得到這個 child，避免孤兒進程。
            if let Ok(mut guard) = manager.child.lock() {
                *guard = Some(child);
            }

            let app_for_check = app.clone();
            let root_for_monitor = root.clone();
            thread::spawn(move || {
                thread::sleep(LIVENESS_CHECK_DELAY);
                let manager = app_for_check.state::<SidecarManager>();
                let wait_result = {
                    let Ok(mut guard) = manager.child.lock() else {
                        return;
                    };
                    match guard.as_mut() {
                        Some(child) => child.try_wait(),
                        None => return,
                    }
                };
                match wait_result {
                    Ok(Some(status)) => {
                        let tail = stderr_tail
                            .clone()
                            .and_then(|t| t.lock().ok().map(|v| v.join("\n")))
                            .unwrap_or_default();
                        if let Ok(mut guard) = manager.child.lock() {
                            *guard = None; // 已經死了，別讓關窗邏輯再 kill 一次
                        }
                        if status.code() == Some(3) {
                            set_state(&app_for_check, &manager, SidecarState::External);
                        } else {
                            set_state(
                                &app_for_check,
                                &manager,
                                SidecarState::Failed {
                                    detail: format!(
                                        "sidecar 啟動後立刻結束（exit={status}）。\
                                         最後幾行輸出：\n{tail}"
                                    ),
                                },
                            );
                        }
                    }
                    Ok(None) => {
                        set_state(&app_for_check, &manager, SidecarState::Running);
                        spawn_crash_monitor(app_for_check.clone(), root_for_monitor);
                    }
                    Err(err) => {
                        set_state(
                            &app_for_check,
                            &manager,
                            SidecarState::Failed {
                                detail: format!("無法確認 sidecar 存活狀態：{err}"),
                            },
                        );
                    }
                }
            });
        }
        Err(err) => {
            set_state(
                app,
                manager,
                SidecarState::Failed {
                    detail: format!("無法啟動 sidecar：{err}"),
                },
            );
        }
    }
}

// 用 try_wait() 輪詢而不是 spec 描述的一次性 blocking child.wait()：這個
// child handle 跟關窗清理共用同一個 Mutex<Option<Child>>，如果在這裡
// blocking wait 同時持有鎖，關窗時 kill_on_close() 會永遠拿不到鎖（而
// wait() 又只有等 kill 後才會返回）——經典死鎖。輪詢版本行為等價（照樣能
// 偵測非預期結束），且跟 lib.rs 既有的 core 存活檢查用同一種 try_wait()
// 風格，不是新發明一套。
fn spawn_crash_monitor(app: AppHandle, root: PathBuf) {
    thread::spawn(move || loop {
        thread::sleep(CRASH_MONITOR_POLL_INTERVAL);
        let manager = app.state::<SidecarManager>();
        let wait_result = {
            let Ok(mut guard) = manager.child.lock() else {
                return;
            };
            match guard.as_mut() {
                Some(child) => child.try_wait(),
                None => return, // child 已經被關窗邏輯 take 並 kill，監控結束
            }
        };
        match wait_result {
            Ok(None) => continue,
            Ok(Some(status)) => {
                if let Ok(mut guard) = manager.child.lock() {
                    *guard = None;
                }
                if status.code() == Some(3) {
                    set_state(&app, &manager, SidecarState::External);
                } else {
                    set_state(
                        &app,
                        &manager,
                        SidecarState::Failed {
                            detail: format!("sidecar 非預期結束（exit={status}）"),
                        },
                    );
                    attempt_auto_restart(app.clone(), root.clone());
                }
                return;
            }
            Err(err) => {
                set_state(
                    &app,
                    &manager,
                    SidecarState::Failed {
                        detail: format!("無法確認 sidecar 存活狀態：{err}"),
                    },
                );
                return;
            }
        }
    });
}

// 最多自動重啟 2 次，每次先重跑 preflight（崩潰原因可能就是登入被撤銷）。
// 超過上限後停在 Failed，交給使用者手動點「重試」——避免無聲 crash-loop
// 一直燒 CPU。sidecar_restart command 會把計數器歸零。
fn attempt_auto_restart(app: AppHandle, root: PathBuf) {
    let manager = app.state::<SidecarManager>();
    let count = {
        let Ok(mut guard) = manager.restart_count.lock() else {
            return;
        };
        *guard += 1;
        *guard
    };
    if count > MAX_AUTO_RESTARTS {
        return;
    }
    thread::spawn(move || {
        thread::sleep(AUTO_RESTART_BACKOFF);
        let manager = app.state::<SidecarManager>();
        match run_preflight(&root) {
            Ok(result) if result.values().any(|entry| entry.status == "ok") => {
                do_spawn(&app, &manager, &root);
            }
            Ok(result) => {
                set_state(
                    &app,
                    &manager,
                    SidecarState::AwaitingLogin {
                        detail: summarize_preflight(&result),
                    },
                );
            }
            Err(detail) => {
                set_state(&app, &manager, SidecarState::Failed { detail });
            }
        }
    });
}

/// 把路徑包成 shell 安全的單引號字串（macOS 允許使用者家目錄含空格，如
/// `/Users/John Doe/.local/bin/claude`，不加引號會被 Terminal 逐字拆開執行失敗）。
fn shell_single_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', r"'\''"))
}

/// 把 shell 指令字串跳脫成可以安全塞進 AppleScript 雙引號字串字面值的形式。
fn applescript_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

#[cfg(target_os = "macos")]
fn open_login_terminal(cli_path: &str) -> Result<(), String> {
    let shell_cmd = format!("{} login", shell_single_quote(cli_path));
    let do_script = format!(
        r#"tell application "Terminal" to do script "{}""#,
        applescript_escape(&shell_cmd)
    );
    Command::new("/usr/bin/osascript")
        .args([
            "-e",
            r#"tell application "Terminal" to activate"#,
            "-e",
            &do_script,
        ])
        .spawn()
        .map(|_| ())
        .map_err(|err| format!("無法開啟 Terminal.app：{err}"))
}

#[cfg(not(target_os = "macos"))]
fn open_login_terminal(_cli_path: &str) -> Result<(), String> {
    Err("登入流程目前僅支援 macOS".to_string())
}

// 登入視窗（Terminal.app）不是 app 的 child，app 從不 kill 它、它的視窗
// 關掉對狀態機也沒有意義——只有下一次 preflight 的結果算數（spec §3）。
fn poll_login(app: AppHandle, root: PathBuf, cli: String) {
    thread::spawn(move || {
        let manager = app.state::<SidecarManager>();
        let deadline = Instant::now() + LOGIN_POLL_TIMEOUT;
        loop {
            thread::sleep(LOGIN_POLL_INTERVAL);
            {
                let Ok(guard) = manager.state.lock() else {
                    return;
                };
                if !matches!(*guard, SidecarState::AwaitingLogin { .. }) {
                    return; // 使用者在等待期間關掉 consent 或手動重試了,不搶
                }
            }
            if let Ok(result) = run_preflight(&root) {
                if result
                    .get(cli.as_str())
                    .map(|entry| entry.status == "ok")
                    .unwrap_or(false)
                {
                    do_spawn(&app, &manager, &root);
                    return;
                }
            }
            if Instant::now() >= deadline {
                set_state(
                    &app,
                    &manager,
                    SidecarState::Failed {
                        detail: "登入未完成（10 分鐘逾時）".to_string(),
                    },
                );
                return;
            }
        }
    });
}

#[tauri::command]
pub(crate) fn sidecar_consent(app: AppHandle, enabled: bool) -> Result<(), String> {
    let manager = app.state::<SidecarManager>();
    if !enabled {
        set_state(&app, &manager, SidecarState::Disabled);
        return Ok(());
    }
    if byok_configured() {
        set_state(&app, &manager, SidecarState::Byok);
        return Ok(());
    }
    start_probe_and_spawn(app.clone());
    Ok(())
}

#[tauri::command]
pub(crate) fn sidecar_status(manager: State<'_, SidecarManager>) -> SidecarStatusDto {
    let guard = manager.state.lock().unwrap();
    SidecarStatusDto {
        state: guard.as_str().to_string(),
        detail: guard.detail(),
    }
}

#[tauri::command]
pub(crate) fn sidecar_restart(app: AppHandle) -> Result<(), String> {
    let manager = app.state::<SidecarManager>();
    if let Ok(mut guard) = manager.child.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
        }
    }
    if let Ok(mut count) = manager.restart_count.lock() {
        *count = 0;
    }
    start_probe_and_spawn(app.clone());
    Ok(())
}

#[tauri::command]
pub(crate) fn sidecar_open_login(app: AppHandle, cli: String) -> Result<(), String> {
    let manager = app.state::<SidecarManager>();
    let root = repo_root().ok_or_else(|| "找不到 salva core 原始碼位置".to_string())?;

    let preflight = run_preflight(&root)?;
    let entry = preflight
        .get(cli.as_str())
        .ok_or_else(|| format!("未知的 CLI：{cli}"))?;
    // 用 preflight 給的絕對路徑，不要用裸名——Terminal.app 的 login shell
    // PATH 通常有，但絕對路徑才是這個 codebase 已經踩過一次 PATH 雷後該有
    // 的審計基準（spec §3）。
    let path = entry
        .path
        .clone()
        .ok_or_else(|| format!("{cli} 未安裝，找不到可登入的路徑"))?;

    open_login_terminal(&path)?;

    set_state(
        &app,
        &manager,
        SidecarState::AwaitingLogin {
            detail: format!("正在等待 {cli} 登入…"),
        },
    );
    poll_login(app.clone(), root, cli);
    Ok(())
}
