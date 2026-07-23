"""在單一 discovery run 內，用 nomenklatura 的打分+judgement 模型合併重複
的 CanonicalEntity 記錄（experiments/salva_v2/ENTITY_RESOLUTION_INTEGRATION_
EVAL.md 的 step 3-4）。

Step 3 發現：core/controller.py 目前完全沒有 entity-level 合併呼叫點——
salva_core/service.py 對每個倖存的搜尋結果各自建一個 CanonicalEntity，
沒有後續去重。這個模組是全新能力，不是取代既有邏輯。刻意還沒 wire 進
service.py（見 board salva-entity-resolution-nomenklatura-integration）——
因為接線會改變使用者可見的輸出，值得有自己的 opt-in flag 決策，比照
enable_query_proposal 一開始就預設關閉的做法。

只比較同一 FtM schema 的實體（經 ftm_adapter 的映射）——例如拿 Person 跟
Company 比對絕不會是合法的重複配對，只會浪費一次 nomenklatura.matching
呼叫。
"""
from __future__ import annotations

from itertools import combinations

from nomenklatura.db import get_engine, get_metadata, make_session
from nomenklatura.judgement import Judgement
from nomenklatura.matching import DefaultAlgorithm
from nomenklatura.resolver import Resolver

from salva_core.resolvers.ftm_adapter import canonical_entity_to_proxy
from salva_core.schemas import CanonicalEntity

DEFAULT_MERGE_THRESHOLD = 0.7


def make_ephemeral_resolver(db_url: str = "sqlite:///:memory:") -> Resolver:
    """一個由全新 in-memory judgement store 支撐的 resolver，範圍限定在
    這一次呼叫。judgement 是否該跨 run 持久化（一個機器等級常駐的
    nomenklatura DB，還是每次 run 都全新一份）是另一個尚未拍板的接線決策
    ——這是安全預設，不會在那個決策定案前就意外開始累積一份永久的跨 run
    儲存。"""
    engine = get_engine(db_url)
    get_metadata().create_all(bind=engine)
    return Resolver(make_session(db_url), create=True)


def resolve_duplicate_entities(
    entities: list[CanonicalEntity],
    resolver: Resolver | None = None,
    threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> list[CanonicalEntity]:
    """回傳一個新 list，score>=threshold 的配對合併成一個 CanonicalEntity
    （輸入順序較早的那個存活；被合併掉的 entity 的 source_urls/tags/
    evidence 會併進去，不會靜默丟失）。在每個 schema 群組內是 O(n^2)——
    單一 run 的實體數量（幾十筆，非千筆等級）下沒問題；若這個假設不再
    成立，改用 nomenklatura 的 Index/blocking 機制。"""
    if len(entities) < 2:
        return list(entities)

    active_resolver = resolver if resolver is not None else make_ephemeral_resolver()
    proxies = {entity.entity_id: canonical_entity_to_proxy(entity) for entity in entities}
    config = DefaultAlgorithm.default_config()

    parent: dict[str, str] = {entity.entity_id: entity.entity_id for entity in entities}

    def find(entity_id: str) -> str:
        while parent[entity_id] != entity_id:
            parent[entity_id] = parent[parent[entity_id]]
            entity_id = parent[entity_id]
        return entity_id

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    by_schema: dict[str, list[CanonicalEntity]] = {}
    for entity in entities:
        by_schema.setdefault(entity.entity_type, []).append(entity)

    for group in by_schema.values():
        for left, right in combinations(group, 2):
            left_proxy, right_proxy = proxies[left.entity_id], proxies[right.entity_id]
            result = DefaultAlgorithm.compare(left_proxy, right_proxy, config)
            if result.score >= threshold:
                active_resolver.decide(
                    left.entity_id, right.entity_id, Judgement.POSITIVE, score=result.score
                )
                union(left.entity_id, right.entity_id)

    groups: dict[str, list[CanonicalEntity]] = {}
    for entity in entities:
        groups.setdefault(find(entity.entity_id), []).append(entity)

    return [_merge_group(group) for group in groups.values()]


def _merge_group(group: list[CanonicalEntity]) -> CanonicalEntity:
    if len(group) == 1:
        return group[0]
    survivor = group[0].model_copy(deep=True)
    seen_urls = set(survivor.source_urls)
    seen_tags = set(survivor.tags)
    for duplicate in group[1:]:
        for url in duplicate.source_urls:
            if url not in seen_urls:
                survivor.source_urls.append(url)
                seen_urls.add(url)
        for tag in duplicate.tags:
            if tag not in seen_tags:
                survivor.tags.append(tag)
                seen_tags.add(tag)
        survivor.evidence.extend(duplicate.evidence)
        for key, value in duplicate.attributes.items():
            survivor.attributes.setdefault(key, value)
        survivor.confidence = max(survivor.confidence, duplicate.confidence)
        survivor.score = max(survivor.score, duplicate.score)
    return survivor
