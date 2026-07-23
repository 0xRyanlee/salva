"""Sidecar LLM backend: enrichment/rerank completions via a locally logged-in
`claude`/`codex` CLI, instead of a self-hosted omlx model server.

board salva-llm-backend-cli-passthrough. Owner-confirmed design (2026-07-23):
  - No in-app terminal emulator. The user opens their OS's native terminal
    and runs `python -m salva_core.llm_sidecar_run` there (after `claude
    login` / `codex login`) -- that process IS the sidecar.
  - Liveness/close detection: a local Unix domain socket, not a heartbeat
    file. The socket connection itself is the signal -- if the sidecar
    process has exited, connect() fails immediately (ConnectionRefusedError
    / FileNotFoundError), so there is no polling interval to tune.
  - One sidecar per salva instance, not shared machine-wide. Instance
    identity defaults to a stable hash of the discovery-run DB path so a
    single-DB dev setup only needs one login, while genuinely separate
    deployments (different SALVA_DB_PATH) get independent sockets.
  - BYOK: any OpenAI-compatible chat-completions endpoint (env vars below)
    is tried first, since a configured paid API is a stronger signal of
    intent than the local sidecar and shouldn't require the terminal to be
    open at all.

This module intentionally does NOT delete or touch enrichment/omlx.py's
existing OMLXPlugin path (still opt-in via explicit complete=complete_with_omlx).
It adds a new default completion source and changes what "no explicit
complete= passed" resolves to in core/query_proposal.py, enrichment/rerank.py,
and enrichment/omlx.py.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

from salva_core.llm import LLMCompletionResult, LLMPromptBundle, _extract_content

logger = logging.getLogger("salva.llm_sidecar")

SidecarRunner = Callable[[str, str | None], "tuple[str | None, str | None]"]
"""(prompt, model_hint) -> (stdout_content, error_message). Exactly one of
the two return values is not None. Injectable so the socket protocol is
testable without shelling out to a real claude/codex CLI."""

DEFAULT_SOCKET_TIMEOUT = float(os.getenv("SALVA_SIDECAR_TIMEOUT", "60"))
_CLI_ORDER = ("claude", "codex")


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


# ---------------------------------------------------------------------------
# Server (runs inside the user's terminal -- see llm_sidecar_run.py)
# ---------------------------------------------------------------------------

def default_cli_runner(prompt: str, model_hint: str | None) -> tuple[str | None, str | None]:
    """Tries claude (Haiku by default) then codex, in that order -- either
    being logged in is enough. Real subprocess calls; not used in tests."""
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
        return ["claude", "-p", prompt, "--model", model_hint or "haiku"]
    if cli == "codex":
        args = ["codex", "exec", prompt]
        if model_hint:
            args.extend(["-m", model_hint])
        return args
    return None


class SidecarServer:
    """Accept-loop over a Unix domain socket. One request/response per
    connection (the client opens a fresh connection per completion call,
    so a dropped connection cleanly means "the sidecar is not there" rather
    than a half-open stream to reason about)."""

    def __init__(self, instance_id: str | None = None, runner: SidecarRunner = default_cli_runner):
        self.socket_path = sidecar_socket_path(instance_id)
        self.runner = runner
        self._server: socket.socket | None = None

    def serve_forever(self) -> None:
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.socket_path))
        self._server.listen(4)
        logger.info("salva LLM sidecar listening on %s", self.socket_path)
        try:
            while True:
                conn, _ = self._server.accept()
                with conn:
                    self._handle_one(conn)
        finally:
            self.socket_path.unlink(missing_ok=True)

    def _handle_one(self, conn: socket.socket) -> None:
        try:
            raw = _recv_message(conn)
            request = json.loads(raw)
            prompt = f"{request['system_prompt']}\n\n{request['user_prompt']}"
            content, error = self.runner(prompt, request.get("model_name"))
            _send_message(conn, json.dumps({"content": content, "error": error}))
        except Exception as exc:  # noqa: BLE001 -- must never crash the accept loop
            try:
                _send_message(conn, json.dumps({"content": None, "error": str(exc)}))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Client (called from query_proposal.py / rerank.py / omlx.py)
# ---------------------------------------------------------------------------

def complete_with_sidecar(
    bundle: LLMPromptBundle, instance_id: str | None = None
) -> LLMCompletionResult:
    started_at = perf_counter()
    socket_path = sidecar_socket_path(instance_id)
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


# ---------------------------------------------------------------------------
# BYOK: generic OpenAI-compatible chat-completions endpoint
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
    except Exception as exc:  # noqa: BLE001 -- surfaced via LLMCompletionResult, not raised
        return LLMCompletionResult(
            provider_name="byok",
            model_name=model_name or "unknown",
            task=bundle.task,
            available=False,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=str(exc),
        )


def resolve_llm_completion_fn() -> Callable[[LLMPromptBundle], LLMCompletionResult]:
    """The new default completion source for query_proposal/rerank/enrichment:
    BYOK if configured (a deliberately-set paid key beats an ambient local
    login), else the sidecar. Never falls back to local omlx -- that path is
    still reachable by passing complete=complete_with_omlx explicitly."""
    if byok_configured():
        return complete_with_byok
    return complete_with_sidecar


# ---------------------------------------------------------------------------
# Wire protocol: length-prefixed JSON so a single accept()ed connection can't
# short-read a partial message on a busy loopback socket.
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
