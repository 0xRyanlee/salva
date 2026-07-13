"""Shared Hyphen feedback client (Python) — for Salva and any CLI/runtime app.

    from feedback import send_feedback
    send_feedback("salva", "discover() returned 0 results for X", env={"run_id": rid})

Or wire a CLI subcommand: `salva feedback "message"`.
Reports to the same Worker as the GUI apps; the `app` field drives triage.
"""
from __future__ import annotations
import json
import platform
import urllib.request
from typing import Any

DEFAULT_FEEDBACK_ENDPOINT = "https://feedback.hyphen-network.com/report"


def default_env(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    env: dict[str, Any] = {"os": platform.platform(), "python": platform.python_version()}
    if extra:
        env.update(extra)
    return env


def send_feedback(
    app: str,
    message: str,
    env: dict[str, Any] | None = None,
    type: str = "feedback",
    endpoint: str | None = None,
    submit_token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    payload = {
        "app": app,
        "message": (message or "").strip(),
        "type": type,
        "env": env if env is not None else default_env(),
    }
    # Cloudflare's bot-fight rules block the default "Python-urllib/x.y" UA outright
    # (403, error code 1010) before the request ever reaches the Worker — every caller
    # of this client needs a real UA or every send silently fails.
    headers = {"Content-Type": "application/json", "User-Agent": f"hyphen-feedback-client/{app}"}
    if submit_token:
        headers["x-submit-token"] = submit_token
    req = urllib.request.Request(
        endpoint or DEFAULT_FEEDBACK_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted endpoint)
        return json.loads(resp.read().decode("utf-8"))
