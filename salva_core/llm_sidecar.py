"""Sidecar LLM 後端：透過本機已登入的 `claude`/`codex` CLI 提供
enrichment/rerank 的 completion，取代自架的 omlx 模型伺服器。

board salva-llm-backend-cli-passthrough。owner 確認的設計（2026-07-23）：
  - 不做 app 內建 terminal 模擬器。使用者在自己 OS 的原生 terminal 執行
    `python -m salva_core.llm_sidecar_run`（先跑過 `claude login`/
    `codex login`）——那個進程本身就是 sidecar。
  - 存活/關閉偵測：本機 Unix domain socket，不是心跳檔案。socket 連線本身
    就是訊號——sidecar 進程一旦退出，connect() 會立即失敗
    （ConnectionRefusedError/FileNotFoundError），不需要調校 polling 間隔。
  - 每個 salva instance 各自一個 sidecar，不跨機器共用。instance 身份預設
    用 discovery-run DB path 的穩定 hash，單一 DB 的開發環境只需登入一次，
    不同部署（不同 SALVA_SQLITE_PATH）各自獨立 socket——注意這代表「同一份
    SALVA_SQLITE_PATH 底下的多個 process」預設會共用同一個 sidecar，不是
    每個 process 各自獨立；真的要每個 process 隔離需明確設 SALVA_INSTANCE_ID。
  - BYOK：任何 OpenAI-compatible 的 chat-completions 端點（見下方環境變數）
    優先於 sidecar 嘗試——刻意設定的付費 API 比環境裡剛好登入的本機 CLI
    意圖更明確，也不需要 terminal 一直開著。

本模組刻意不刪除、不動 enrichment/omlx.py 既有的 OMLXPlugin 路徑（仍可用
明確傳 complete=complete_with_omlx 選用）。它新增一個預設 completion 來源，
改變 core/query_proposal.py、enrichment/rerank.py、enrichment/omlx.py 裡
「沒明確傳 complete=」時會解析到的對象。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from salva_core.llm import LLMCompletionResult, LLMPromptBundle, _extract_content

logger = logging.getLogger("salva.llm_sidecar")

SidecarRunner = Callable[[str, str | None], "tuple[str | None, str | None]"]
"""(prompt, model_hint) -> (stdout_content, error_message)。兩個回傳值恰好
一個非 None。可注入，讓 socket 協定能測試而不需真的呼叫 claude/codex CLI。"""

DEFAULT_SOCKET_TIMEOUT = float(os.getenv("SALVA_SIDECAR_TIMEOUT", "60"))
_CLI_ORDER = ("claude", "codex")
PREFLIGHT_TIMEOUT = float(os.getenv("SALVA_SIDECAR_PREFLIGHT_TIMEOUT", "10"))


def resolve_instance_id() -> str:
    explicit = os.getenv("SALVA_INSTANCE_ID")
    if explicit:
        return explicit
    from salva_core.persistence.db import DEFAULT_DB_PATH

    digest = hashlib.sha256(DEFAULT_DB_PATH.encode("utf-8")).hexdigest()
    return digest[:12]


def sidecar_socket_path(instance_id: str | None = None) -> Path:
    resolved = instance_id or resolve_instance_id()
    return Path(tempfile.gettempdir()) / f"salva-llm-sidecar-{resolved}.sock"


def _token_path(socket_path: Path) -> Path:
    return socket_path.with_suffix(socket_path.suffix + ".token")


def _read_token(socket_path: Path) -> str | None:
    try:
        return _token_path(socket_path).read_text().strip()
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Server（跑在使用者的 terminal 裡——見 llm_sidecar_run.py）
# ---------------------------------------------------------------------------

def default_cli_runner(prompt: str, model_hint: str | None) -> tuple[str | None, str | None]:
    """依序試 claude（預設 Haiku）再試 codex——任一個登入即可。真的會呼叫
    subprocess，測試不會用到這個函式。"""
    errors: list[str] = []
    for cli in _CLI_ORDER:
        args = _cli_invocation(cli, prompt, model_hint)
        if args is None:
            continue
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=DEFAULT_SOCKET_TIMEOUT
            )
        except FileNotFoundError:
            errors.append(f"{cli}: not installed")
            continue
        except subprocess.TimeoutExpired:
            errors.append(f"{cli}: timed out after {DEFAULT_SOCKET_TIMEOUT}s")
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip(), None
        errors.append(f"{cli}: exit {result.returncode}: {result.stderr.strip()[:300]}")
    return None, "; ".join(errors) or "no CLI runner available"


def _cli_invocation(cli: str, prompt: str, model_hint: str | None) -> list[str] | None:
    if cli == "claude":
        # prompt 是 -p 的 flag-argument，不是獨立 positional，一般 CLI
        # 解析器不會把它誤判成另一個 flag，就算內容以 "-" 開頭也一樣。
        return ["claude", "-p", prompt, "--model", model_hint or "haiku"]
    if cli == "codex":
        # prompt 這裡是 positional（見 `codex exec [OPTIONS] [PROMPT]`），
        # 內容來自搜尋/爬蟲資料，攻擊者可能讓它以 "-" 開頭。用 "--" 明確
        # 標記後面全部當 positional，避免被誤解成 flag。
        args = ["codex", "exec"]
        if model_hint:
            args.extend(["-m", model_hint])
        args.extend(["--", prompt])
        return args
    return None


class SidecarAlreadyRunning(Exception):
    """`serve_forever()` 發現 socket path 已經有活著的 process 在聽——
    不可以 unlink 偷走它（app-managed spawn 下可能是 leftover 的
    manual-terminal sidecar，或另一個 app instance）。"""


def _probe_existing_socket(socket_path: Path, timeout: float = 0.5) -> bool:
    """短逾時 connect() 既有 socket 檔案，只用來判斷「有沒有活的 process
    在聽」，不送任何請求。"""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(socket_path))
        return True
    except OSError:
        return False


def _check_claude_auth(cli_path: str) -> str:
    """`claude auth status --json` 是非互動、快（實測 ~0.2s）、不打真的
    API 的官方指令，直接回傳 loggedIn 布林——不需要 credentials 檔案位置
    heuristic，也不需要用真的 completion 呼叫去試探。"""
    try:
        result = subprocess.run(
            [cli_path, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=PREFLIGHT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "error"
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return "error"
    return "ok" if payload.get("loggedIn") else "not_logged_in"


def _check_codex_auth(cli_path: str) -> str:
    """`codex login status` 沒有 --json，登入時以 exit 0 印出「Logged in
    using ...」——但實測（2026-07）這行是寫到 stderr，不是 stdout，兩個都要
    檢查才不會誤判成 not_logged_in。"""
    try:
        result = subprocess.run(
            [cli_path, "login", "status"],
            capture_output=True,
            text=True,
            timeout=PREFLIGHT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return "error"
    combined = (result.stdout + result.stderr).lower()
    if result.returncode == 0 and "logged in" in combined:
        return "ok"
    return "not_logged_in"


_AUTH_CHECKERS: dict[str, Callable[[str], str]] = {
    "claude": _check_claude_auth,
    "codex": _check_codex_auth,
}


def run_preflight() -> dict[str, dict[str, str | None]]:
    """`--preflight` 模式用：對 `_CLI_ORDER` 每個 CLI 檢查 (a) PATH 上找不找
    得到、(b) 有沒有登入。回傳 {cli: {"status": ..., "path": ...}}——path 用
    絕對路徑，給 Rust 端 §3 的登入流程直接拿去開 terminal，不用再自己找一次。"""
    results: dict[str, dict[str, str | None]] = {}
    for cli in _CLI_ORDER:
        path = shutil.which(cli)
        if path is None:
            results[cli] = {"status": "missing", "path": None}
            continue
        status = _AUTH_CHECKERS[cli](path)
        results[cli] = {"status": status, "path": path}
    return results


class SidecarServer:
    """在 Unix domain socket 上跑 accept-loop。一次 connection 對應一次
    請求/回應（client 每次 completion 呼叫都開新連線，連線斷掉乾脆地
    代表「sidecar 不在了」，不用去推理半開的 stream 狀態）。

    socket path 是 DB path 的 hash 衍生，同機器上知道這個 repo checkout
    路徑的人都能算出來——單靠路徑不可預測性不算身份驗證。所以另外生成一個
    隨機 token，寫進權限收緊到 0600 的 sibling 檔案；同帳號的其他 process
    理論上還是讀得到（本機開發工具的既定信任邊界），但機器上的其他帳號
    讀不到，且無法在不知道 token 的情況下冒用已登入的 claude/codex 額度。"""

    def __init__(self, instance_id: str | None = None, runner: SidecarRunner = default_cli_runner):
        self.socket_path = sidecar_socket_path(instance_id)
        self.runner = runner
        self._server: socket.socket | None = None
        self._token = secrets.token_hex(32)

    def serve_forever(self) -> None:
        if self.socket_path.exists():
            if _probe_existing_socket(self.socket_path):
                raise SidecarAlreadyRunning(str(self.socket_path))
            self.socket_path.unlink()
        token_path = _token_path(self.socket_path)
        token_path.write_text(self._token)
        os.chmod(token_path, 0o600)

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self._server.listen(4)
        logger.info("salva LLM sidecar listening on %s", self.socket_path)
        try:
            while True:
                conn, _ = self._server.accept()
                conn.settimeout(DEFAULT_SOCKET_TIMEOUT)
                with conn:
                    self._handle_one(conn)
        finally:
            self.socket_path.unlink(missing_ok=True)
            token_path.unlink(missing_ok=True)

    def _handle_one(self, conn: socket.socket) -> None:
        try:
            raw = _recv_message(conn)
            request = json.loads(raw)
            if request.get("token") != self._token:
                _send_message(conn, json.dumps({"content": None, "error": "invalid token"}))
                return
            prompt = f"{request['system_prompt']}\n\n{request['user_prompt']}"
            content, error = self.runner(prompt, request.get("model_name"))
            _send_message(conn, json.dumps({"content": content, "error": error}))
        except TimeoutError:
            pass  # 客戶端沒在 timeout 內送完整訊息 -- 放棄這個連線，accept-loop 不受影響
        except Exception as exc:  # noqa: BLE001 -- accept loop 絕不能被這裡的例外打斷
            try:
                _send_message(conn, json.dumps({"content": None, "error": str(exc)}))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Client（從 query_proposal.py / rerank.py / omlx.py 呼叫）
# ---------------------------------------------------------------------------

def complete_with_sidecar(
    bundle: LLMPromptBundle, instance_id: str | None = None
) -> LLMCompletionResult:
    started_at = perf_counter()
    socket_path = sidecar_socket_path(instance_id)
    token = _read_token(socket_path)
    if token is None:
        return LLMCompletionResult(
            provider_name="sidecar",
            model_name=bundle.model_name or "unknown",
            task=bundle.task,
            available=False,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=(
                "sidecar not connected -- start it with "
                "`python -m salva_core.llm_sidecar_run` in a terminal after "
                "`claude login` or `codex login` (no auth token file found)"
            ),
        )
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(DEFAULT_SOCKET_TIMEOUT)
            client.connect(str(socket_path))
            _send_message(
                client,
                json.dumps({
                    "system_prompt": bundle.system_prompt,
                    "user_prompt": bundle.user_prompt,
                    "model_name": bundle.model_name,
                    "token": token,
                }),
            )
            raw = _recv_message(client)
    except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
        return LLMCompletionResult(
            provider_name="sidecar",
            model_name=bundle.model_name or "unknown",
            task=bundle.task,
            available=False,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=(
                "sidecar not connected -- start it with "
                "`python -m salva_core.llm_sidecar_run` in a terminal after "
                f"`claude login` or `codex login` ({exc})"
            ),
        )

    payload = json.loads(raw)
    if payload.get("error"):
        return LLMCompletionResult(
            provider_name="sidecar",
            model_name=bundle.model_name or "unknown",
            task=bundle.task,
            available=False,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=payload["error"],
        )
    return LLMCompletionResult(
        provider_name="sidecar",
        model_name=bundle.model_name or "unknown",
        task=bundle.task,
        content=payload.get("content"),
        available=True,
        latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
    )


def sidecar_reachable(instance_id: str | None = None) -> bool:
    """輕量存活檢查：只 connect() 不送任何請求，不會觸發真的 CLI 呼叫。
    給 UI 顯示「LLM 後端可用嗎」用，不要拿 complete_with_sidecar() 做這件
    事——那會真的付一次 claude/codex 呼叫的代價。"""
    socket_path = sidecar_socket_path(instance_id)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(str(socket_path))
        return True
    except (FileNotFoundError, ConnectionRefusedError, OSError):
        return False


# ---------------------------------------------------------------------------
# BYOK：通用 OpenAI-compatible chat-completions 端點
# ---------------------------------------------------------------------------

def byok_configured() -> bool:
    return bool(os.getenv("SALVA_BYOK_BASE_URL") and os.getenv("SALVA_BYOK_API_KEY"))


def complete_with_byok(bundle: LLMPromptBundle) -> LLMCompletionResult:
    import urllib.request

    started_at = perf_counter()
    base_url = os.getenv("SALVA_BYOK_BASE_URL", "")
    token = os.getenv("SALVA_BYOK_API_KEY", "")
    model_name = bundle.model_name or os.getenv("SALVA_BYOK_MODEL", "")
    if not base_url or not token:
        return LLMCompletionResult(
            provider_name="byok",
            model_name=model_name or "unknown",
            task=bundle.task,
            available=False,
            message="SALVA_BYOK_BASE_URL / SALVA_BYOK_API_KEY not set",
        )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": bundle.system_prompt},
            {"role": "user", "content": bundle.user_prompt},
        ],
        "stream": False,
        "max_tokens": bundle.max_tokens,
        "temperature": bundle.temperature,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_SOCKET_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return LLMCompletionResult(
            provider_name="byok",
            model_name=model_name or "unknown",
            task=bundle.task,
            content=_extract_content(data),
            available=True,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
        )
    except Exception as exc:  # noqa: BLE001 -- 透過 LLMCompletionResult 回報，不往外拋
        return LLMCompletionResult(
            provider_name="byok",
            model_name=model_name or "unknown",
            task=bundle.task,
            available=False,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=str(exc),
        )


def resolve_llm_completion_fn() -> Callable[[LLMPromptBundle], LLMCompletionResult]:
    """query_proposal/rerank/enrichment 的新預設 completion 來源：BYOK 若
    有設定就優先（刻意設定的付費 key 比環境裡剛好登入的本機更明確），否則
    走 sidecar。不再 fallback 回本機 omlx——那條路徑仍可用，但要呼叫方明確
    傳 complete=complete_with_omlx 才會用到。"""
    if byok_configured():
        return complete_with_byok
    return complete_with_sidecar


# ---------------------------------------------------------------------------
# Wire protocol：長度前綴 JSON，確保單一 accept() 到的連線在忙碌的 loopback
# socket 上不會把訊息讀到一半
# ---------------------------------------------------------------------------

def _send_message(conn: socket.socket, text: str) -> None:
    body = text.encode("utf-8")
    conn.sendall(len(body).to_bytes(4, "big") + body)


def _recv_message(conn: socket.socket) -> str:
    header = _recv_exact(conn, 4)
    length = int.from_bytes(header, "big")
    return _recv_exact(conn, length).decode("utf-8")


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            raise ConnectionError("sidecar connection closed mid-message")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
