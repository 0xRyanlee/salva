"""One-off: derive task_set_v2.json from task_set_v1.json.

Adds a normalized `source_url` field (singular, the ORIGINAL/primary source
for the claim -- not a mirror or secondary re-citation) to every
ground_truth_entities entry:
  - multi_hop entries already carry `source_url` -- kept as-is.
  - single_entity/cross_language entries carry `source_urls` (list) -- the
    first element is taken as the primary source, `source_urls` is kept
    alongside it as supplementary corroboration.
  - if no source is known, `source_url` is set to null (still present as a
    key, so downstream code can rely on the field existing).

This is what makes failure modes like multihop-01-cncf-founders' "found a
secondhand mis-citing list, not the original CNCF announcement" measurable:
a result can now be checked against the single canonical source_url, not
just fuzzy-matched against a name.

Run: python -m experiments.salva_v2.harness.build_task_set_v2
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

V1_PATH = Path(__file__).resolve().parent.parent / "task_set_v1.json"
V2_PATH = Path(__file__).resolve().parent.parent / "task_set_v2.json"


def _normalize_entity(entity: dict[str, Any]) -> dict[str, Any]:
    entity = dict(entity)
    if "source_url" in entity:
        return entity
    source_urls = entity.get("source_urls")
    entity["source_url"] = source_urls[0] if source_urls else None
    return entity


def build_v2(v1: dict[str, Any]) -> dict[str, Any]:
    v2 = dict(v1)
    v2["version"] = "v2"
    v2["derived_from"] = "task_set_v1.json"
    v2["changes"] = (
        "Normalized a singular `source_url` field onto every "
        "ground_truth_entities entry (primary/original source, distinct "
        "from `source_urls`/other supplementary fields) -- see "
        "experiments/salva_v2/harness/build_task_set_v2.py for the derivation."
    )
    v2["tasks"] = [
        {
            **task,
            "ground_truth_entities": [
                _normalize_entity(e) for e in task["ground_truth_entities"]
            ],
        }
        for task in v1["tasks"]
    ]
    return v2


def main() -> None:
    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
    v2 = build_v2(v1)
    V2_PATH.write_text(json.dumps(v2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {V2_PATH}")


if __name__ == "__main__":
    main()
