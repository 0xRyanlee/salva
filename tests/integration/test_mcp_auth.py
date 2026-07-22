from __future__ import annotations

import pytest

from apps.mcp.server import validate_auth_environment


def test_mcp_http_auth_requires_matching_env(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_API_KEY", "api-secret")
    monkeypatch.delenv("SALVA_MCP_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SALVA_MCP_API_KEY must be set"):
        validate_auth_environment("http")


def test_mcp_http_auth_accepts_matching_env(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_API_KEY", "api-secret")
    monkeypatch.setenv("SALVA_MCP_API_KEY", "api-secret")

    validate_auth_environment("http")


def test_mcp_stdio_auth_is_not_enforced(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_API_KEY", "api-secret")
    monkeypatch.delenv("SALVA_MCP_API_KEY", raising=False)

    validate_auth_environment("stdio")
