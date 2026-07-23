"""salva-llm-backend-cli-passthrough：complete_with_sidecar()(client)與
SidecarServer(server)之間的 socket 協定，以及 BYOK-vs-sidecar 派工邏輯。
CLI runner 是注入的，這些測試從不真的呼叫 claude/codex process。"""
from __future__ import annotations

import json
import socket
import stat
import threading
import time
import uuid

import pytest

from salva_core.llm import LLMPromptBundle
from salva_core.llm_sidecar import (
    SidecarServer,
    _recv_message,
    _send_message,
    _token_path,
    byok_configured,
    complete_with_byok,
    complete_with_sidecar,
    resolve_llm_completion_fn,
    sidecar_reachable,
    sidecar_socket_path,
)


def _bundle(user_prompt: str = "hello") -> LLMPromptBundle:
    return LLMPromptBundle(
        task="output_shaping", system_prompt="system", user_prompt=user_prompt
    )


def _run_server_in_background(instance_id: str, runner) -> SidecarServer:
    server = SidecarServer(instance_id=instance_id, runner=runner)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 2.0
    while not server.socket_path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError("sidecar server did not bind its socket in time")
        time.sleep(0.01)
    return server


@pytest.fixture
def instance_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def test_client_reports_degraded_when_no_server_running(instance_id) -> None:
    result = complete_with_sidecar(_bundle(), instance_id=instance_id)
    assert result.available is False
    assert "sidecar not connected" in result.message
    assert "claude login" in result.message


def test_round_trip_success(instance_id) -> None:
    def fake_runner(prompt: str, model_hint: str | None):
        assert "hello" in prompt
        return '{"kept": []}', None

    _run_server_in_background(instance_id, fake_runner)
    result = complete_with_sidecar(_bundle(), instance_id=instance_id)
    assert result.available is True
    assert result.content == '{"kept": []}'
    assert result.provider_name == "sidecar"


def test_runner_error_surfaces_as_unavailable_not_a_crash(instance_id) -> None:
    def failing_runner(prompt: str, model_hint: str | None):
        return None, "claude: not installed; codex: not installed"

    _run_server_in_background(instance_id, failing_runner)
    result = complete_with_sidecar(_bundle(), instance_id=instance_id)
    assert result.available is False
    assert "not installed" in result.message


def test_socket_path_is_per_instance() -> None:
    assert sidecar_socket_path("a") != sidecar_socket_path("b")
    assert sidecar_socket_path("a") == sidecar_socket_path("a")


def test_sidecar_reachable_false_when_not_running(instance_id) -> None:
    assert sidecar_reachable(instance_id) is False


def test_sidecar_reachable_true_when_running_without_triggering_cli(instance_id) -> None:
    called = {"n": 0}

    def runner(prompt: str, model_hint: str | None):
        called["n"] += 1
        return "should never run for a reachability check", None

    _run_server_in_background(instance_id, runner)
    assert sidecar_reachable(instance_id) is True
    assert called["n"] == 0


def test_socket_and_token_file_are_owner_only(instance_id) -> None:
    """audit finding: socket path is a predictable hash, so file permissions
    (not path secrecy) are what actually keeps a different local user from
    hijacking an already-logged-in claude/codex session."""
    server = _run_server_in_background(instance_id, lambda prompt, model_hint: ("{}", None))
    socket_mode = stat.S_IMODE(server.socket_path.stat().st_mode)
    token_mode = stat.S_IMODE(_token_path(server.socket_path).stat().st_mode)
    assert socket_mode == 0o600
    assert token_mode == 0o600


def test_wrong_token_is_rejected_without_running_the_cli(instance_id) -> None:
    """A raw connection that skips complete_with_sidecar()'s automatic token
    read (simulating a different local user who found the socket path but
    not the 0600 token file) must be refused before the CLI runner fires."""
    called = {"n": 0}

    def runner(prompt: str, model_hint: str | None):
        called["n"] += 1
        return "should never run", None

    server = _run_server_in_background(instance_id, runner)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2.0)
        client.connect(str(server.socket_path))
        _send_message(
            client,
            json.dumps({"system_prompt": "s", "user_prompt": "u", "token": "wrong-token"}),
        )
        raw = _recv_message(client)
    payload = json.loads(raw)
    assert payload["error"] == "invalid token"
    assert called["n"] == 0


def test_dispatcher_prefers_byok_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_BYOK_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("SALVA_BYOK_API_KEY", "test-key")
    assert byok_configured() is True
    assert resolve_llm_completion_fn() is complete_with_byok


def test_dispatcher_falls_back_to_sidecar_when_byok_unset(monkeypatch) -> None:
    monkeypatch.delenv("SALVA_BYOK_BASE_URL", raising=False)
    monkeypatch.delenv("SALVA_BYOK_API_KEY", raising=False)
    assert byok_configured() is False
    assert resolve_llm_completion_fn() is complete_with_sidecar


def test_byok_reports_unavailable_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("SALVA_BYOK_BASE_URL", raising=False)
    monkeypatch.delenv("SALVA_BYOK_API_KEY", raising=False)
    result = complete_with_byok(_bundle())
    assert result.available is False
    assert "SALVA_BYOK_BASE_URL" in result.message


def test_byok_completes_against_openai_compatible_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_BYOK_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("SALVA_BYOK_API_KEY", "test-key")
    monkeypatch.setenv("SALVA_BYOK_MODEL", "some-model")

    import json
    import urllib.request

    captured = {}

    class _FakeResponse:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        body = {"choices": [{"message": {"content": "reranked"}}]}
        return _FakeResponse(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = complete_with_byok(_bundle())

    assert result.available is True
    assert result.content == "reranked"
    assert captured["url"] == "https://example.invalid/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
