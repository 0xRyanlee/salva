"""docs/reports/pluggable-engine-architecture-research-20260721.md 點名的
quick win：admission_policy 一直是 SalvaController 的建構子參數，但
execute_discovery() 從沒把它傳進去，正式流程永遠吃 default "gate"。
_resolve_admission_policy() 補上這條線，預設仍是 "gate"（不改變既有行為）。
"""
from __future__ import annotations

from salva_core.service import _resolve_admission_policy


def test_unset_defaults_to_gate(monkeypatch) -> None:
    monkeypatch.delenv("SALVA_ADMISSION_POLICY", raising=False)
    assert _resolve_admission_policy() == "gate"


def test_explicit_rank_is_honored(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_ADMISSION_POLICY", "rank")
    assert _resolve_admission_policy() == "rank"


def test_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_ADMISSION_POLICY", "RANK")
    assert _resolve_admission_policy() == "rank"


def test_unrecognized_value_falls_back_to_gate_not_silently_passed_through(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_ADMISSION_POLICY", "typo-value")
    assert _resolve_admission_policy() == "gate"
