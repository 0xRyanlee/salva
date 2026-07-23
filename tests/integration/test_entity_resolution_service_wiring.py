"""board salva-entity-resolution-nomenklatura-integration：
_resolve_duplicate_entities_if_enabled() 是 resolve_duplicate_entities() 接
進 salva_core/service.py::execute_discovery() 的 opt-in 開關，預設關閉，
比照 enable_query_proposal 的做法——SALVA_ENABLE_ENTITY_RESOLUTION 環境變數
未設定或非真值時，行為必須跟接線前完全一致（同一個 list，不觸發任何
nomenklatura 呼叫）。"""
from __future__ import annotations

from salva_core.schemas import CanonicalEntity
from salva_core.service import _resolve_duplicate_entities_if_enabled


def _entities() -> list[CanonicalEntity]:
    return [
        CanonicalEntity(entity_id="c1", entity_type="company", title="Acme Robotics Inc"),
        CanonicalEntity(entity_id="c2", entity_type="company", title="Acme Robotics Incorporated"),
    ]


def test_disabled_by_default_returns_same_entities_untouched(monkeypatch) -> None:
    monkeypatch.delenv("SALVA_ENABLE_ENTITY_RESOLUTION", raising=False)
    entities = _entities()
    result = _resolve_duplicate_entities_if_enabled(entities)
    assert result is entities


def test_explicitly_falsy_value_stays_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_ENABLE_ENTITY_RESOLUTION", "false")
    entities = _entities()
    result = _resolve_duplicate_entities_if_enabled(entities)
    assert result is entities


def test_enabled_merges_near_duplicate_entities(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_ENABLE_ENTITY_RESOLUTION", "true")
    result = _resolve_duplicate_entities_if_enabled(_entities())
    assert len(result) == 1
