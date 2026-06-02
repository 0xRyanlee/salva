from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Literal
import json
import os
import urllib.error
import urllib.request

from pydantic import BaseModel, Field


LLMTask = Literal["expansion", "extraction", "summarization", "output_shaping"]

DEFAULT_OMLX_BASE_URL = os.getenv("OMLX_BASE_URL", "http://127.0.0.1:8140")
DEFAULT_OMLX_TOKEN = os.getenv("OMLX_AUTH_TOKEN", "")
DEFAULT_OMLX_MODEL = os.getenv("OMLX_MODEL", "gemma-4-e2b-it-4bit")
DEFAULT_OMLX_TIMEOUT = float(os.getenv("SALVA_OMLX_TIMEOUT", "30"))


class LLMPromptBundle(BaseModel):
    task: LLMTask
    system_prompt: str
    user_prompt: str
    model_name: str | None = None
    max_tokens: int = 500
    temperature: float = 0.3


class LLMCompletionResult(BaseModel):
    provider_name: str
    model_name: str
    task: LLMTask
    content: str | None = None
    available: bool = False
    latency_ms: float = 0.0
    message: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LLMProviderDescriptor(BaseModel):
    name: str
    kind: Literal["omlx"]
    description: str
    default_model: str | None = None
    supports_custom_endpoint: bool = True
    supports_health_check: bool = True
    env_vars: list[str] = Field(default_factory=list)


class LLMProviderHealth(BaseModel):
    name: str
    available: bool
    base_url: str | None = None
    model_name: str | None = None
    latency_ms: float | None = None
    message: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class OmlxProviderAdapter:
    base_url: str = DEFAULT_OMLX_BASE_URL
    token: str = DEFAULT_OMLX_TOKEN
    default_model: str = DEFAULT_OMLX_MODEL
    timeout: float = DEFAULT_OMLX_TIMEOUT

    name: str = "omlx"
    kind: str = "omlx"

    def descriptor(self) -> LLMProviderDescriptor:
        return LLMProviderDescriptor(
            name=self.name,
            kind="omlx",
            description="Local OpenAI-compatible LLM provider used for bounded summarization, extraction, expansion, and output shaping.",
            default_model=self.default_model,
            supports_custom_endpoint=True,
            supports_health_check=True,
            env_vars=["OMLX_BASE_URL", "OMLX_AUTH_TOKEN", "OMLX_MODEL", "SALVA_OMLX_TIMEOUT"],
        )

    def is_available(self) -> bool:
        return bool(self.base_url)

    def health_check(self, model_name: str | None = None) -> LLMProviderHealth:
        started_at = perf_counter()
        message = None
        available = False
        try:
            self._request_json(f"{self.base_url.rstrip('/')}/v1/models", None, method="GET")
            available = True
        except Exception as exc:
            message = str(exc)
            try:
                self._request_json(f"{self.base_url.rstrip('/')}/health", None, method="GET")
                available = True
                message = None
            except Exception as second_exc:
                message = f"{message}; {second_exc}" if message else str(second_exc)
        return LLMProviderHealth(
            name=self.name,
            available=available,
            base_url=self.base_url,
            model_name=model_name or self.default_model,
            latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            message=message,
        )

    def complete(self, bundle: LLMPromptBundle) -> LLMCompletionResult:
        started_at = perf_counter()
        model_name = bundle.model_name or self.default_model
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": _bound_text(bundle.system_prompt, 1800)},
                {"role": "user", "content": _bound_text(bundle.user_prompt, 3200)},
            ],
            "stream": False,
            "max_tokens": bundle.max_tokens,
            "temperature": bundle.temperature,
        }
        try:
            data = self._request_json(
                f"{self.base_url.rstrip('/')}/v1/chat/completions",
                payload,
            )
            content = _extract_content(data)
            return LLMCompletionResult(
                provider_name=self.name,
                model_name=model_name or self.default_model,
                task=bundle.task,
                content=content,
                available=True,
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
            )
        except Exception as exc:
            return LLMCompletionResult(
                provider_name=self.name,
                model_name=model_name or self.default_model,
                task=bundle.task,
                available=False,
                latency_ms=round((perf_counter() - started_at) * 1000.0, 2),
                message=str(exc),
            )

    def _request_json(
        self,
        url: str,
        payload: dict | None,
        method: str = "POST",
    ) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def build_bounded_prompt(
    task: LLMTask,
    system_prompt: str,
    user_prompt: str,
    model_name: str | None = None,
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> LLMPromptBundle:
    return LLMPromptBundle(
        task=task,
        system_prompt=_bound_text(system_prompt, 2200),
        user_prompt=_bound_text(user_prompt, 4200),
        model_name=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def list_llm_provider_descriptors() -> list[LLMProviderDescriptor]:
    return [OmlxProviderAdapter().descriptor()]


def probe_omlx_health(model_name: str | None = None) -> LLMProviderHealth:
    return OmlxProviderAdapter().health_check(model_name=model_name)


def complete_with_omlx(bundle: LLMPromptBundle, timeout: float | None = None) -> LLMCompletionResult:
    if timeout is not None:
        adapter = OmlxProviderAdapter(timeout=timeout)
        return adapter.complete(bundle)
    return OmlxProviderAdapter().complete(bundle)


def _bound_text(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(limit - 1, 1)] + "…"


def _extract_content(payload: dict) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    return text if isinstance(text, str) else None
