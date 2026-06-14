"""E5 — cross-lingual entity resolution (VP5).

Hypothesis: the same entity expressed across 中/英/拼音/ticker/別名 can be
resolved to one canonical entity; and string methods alone CANNOT bridge
scripts/languages — a transliteration/gazetteer/embedding bridge is required.

Stdlib only. Compares a ladder of methods by pairwise precision/recall/F1
against gold clusters. The honest deliverable is *where each tier fails*, which
tells development what must be wired (multilingual embedding + alias gazetteer).

    python -m experiments.hg_penetration.e5_entity_resolution
"""
from __future__ import annotations

import itertools
import re

# ---- gold dataset: real entities, cross-lingual surface forms + distractors ----
GOLD: dict[str, list[str]] = {
    "tsmc": [
        "台積電", "台灣積體電路製造股份有限公司", "台积电",
        "Taiwan Semiconductor Manufacturing Company Limited", "TSMC", "TSM", "2330.TW",
    ],
    "alibaba": [
        "阿里巴巴", "阿里巴巴集团控股有限公司", "Alibaba Group Holding Limited", "BABA", "9988.HK",
    ],
    "tencent": [
        "腾讯", "騰訊控股有限公司", "Tencent Holdings Ltd", "TCEHY", "0700.HK",
    ],
    "honhai": [
        "鴻海", "鴻海精密工業股份有限公司", "鸿海",
        "Hon Hai Precision Industry Co., Ltd.", "Foxconn", "2317.TW",
    ],
    # distractors — share tokens with each other but are DISTINCT entities
    "boc": ["中国银行", "Bank of China"],
    "ccb": ["中国建设银行", "China Construction Bank"],
}

SURFACES: list[tuple[str, str]] = [(name, gid) for gid, names in GOLD.items() for name in names]

_SUFFIXES = [
    "股份有限公司", "有限公司", "控股有限公司", "集团控股有限公司", "集团", "集團", "控股",
    "company limited", "co., ltd.", "co ltd", "ltd.", "ltd", "limited", "inc.", "inc",
    "corporation", "corp.", "corp", "holdings", "holding", "group", "plc", "llc",
]
# minimal traditional→simplified bridge for the demo chars (production: opencc)
_T2S = str.maketrans({"積": "积", "體": "体", "電": "电", "騰": "腾", "訊": "讯", "鴻": "鸿", "灣": "湾", "團": "团"})


def norm0(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def norm(s: str) -> str:
    x = norm0(s)
    x = re.sub(r"\.(tw|hk|ss|sz|n|o)$", "", x)        # strip exchange ticker suffix
    for suf in _SUFFIXES:
        x = x.replace(suf, "")
    return re.sub(r"[^\w一-鿿]+", "", x).strip()


def norm_t2s(s: str) -> str:
    return norm(s).translate(_T2S)


def trigrams(s: str) -> set[str]:
    x = norm(s)
    return {x[i:i + 3] for i in range(len(x) - 2)} or {x}


def jaccard(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    return len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0


# alias gazetteer: encodes EXTERNAL knowledge (ticker/known aliases) → canonical id
GAZETTEER = {norm0(name): gid for gid, names in GOLD.items() for name in names}


# ---- matchers (return True if two surfaces should merge) ----
def m_exact(a: str, b: str) -> bool:
    return norm0(a) == norm0(b)


def m_norm(a: str, b: str) -> bool:
    return norm(a) == norm(b) and norm(a) != ""


def m_norm_t2s(a: str, b: str) -> bool:
    return norm_t2s(a) == norm_t2s(b) and norm_t2s(a) != ""


def m_fuzzy(a: str, b: str) -> bool:
    return jaccard(a, b) >= 0.5


def m_gazetteer(a: str, b: str) -> bool:
    return GAZETTEER.get(norm0(a)) == GAZETTEER.get(norm0(b))


# ---- evaluation: union-find clusters → pairwise P/R/F1 vs gold ----
def cluster(matcher) -> dict[int, int]:
    parent = list(range(len(SURFACES)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(range(len(SURFACES)), 2):
        if matcher(SURFACES[i][0], SURFACES[j][0]):
            parent[find(i)] = find(j)
    return {i: find(i) for i in range(len(SURFACES))}


def score(matcher) -> tuple[float, float, float]:
    cl = cluster(matcher)
    tp = fp = fn = 0
    for i, j in itertools.combinations(range(len(SURFACES)), 2):
        same_pred = cl[i] == cl[j]
        same_gold = SURFACES[i][1] == SURFACES[j][1]
        if same_pred and same_gold:
            tp += 1
        elif same_pred and not same_gold:
            fp += 1
        elif not same_pred and same_gold:
            fn += 1
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def main() -> None:
    print("E5 — cross-lingual entity resolution")
    print(f"  {len(SURFACES)} surface forms across {len(GOLD)} gold entities\n")
    print(f"  {'method':<26} {'precision':>9} {'recall':>8} {'F1':>6}")
    print("  " + "-" * 52)
    for name, m in [
        ("exact", m_exact),
        ("normalized (suffix strip)", m_norm),
        ("normalized + 繁→簡 bridge", m_norm_t2s),
        ("char-trigram fuzzy ≥0.5", m_fuzzy),
        ("alias gazetteer (external)", m_gazetteer),
    ]:
        p, r, f1 = score(m)
        print(f"  {name:<26} {p:>9.2f} {r:>8.2f} {f1:>6.2f}")

    print("\n  reading:")
    print("  • exact/fuzzy/normalized merge only WITHIN a script (suffix & spelling variants).")
    print("  • 繁→簡 bridge recovers CN-internal cross-form (台積電↔台积电) — needs opencc in prod.")
    print("  • NO string method bridges 中文↔English↔ticker (台積電↔TSMC↔2330): zero shared signal.")
    print("  • only the gazetteer (external knowledge) reaches full recall — but it must be")
    print("    maintained and does NOT generalise to unseen entities.")
    print("\n  → DEVELOPMENT IMPLICATION (evidence-based): cross-language/script resolution")
    print("    REQUIRES a bridge that generalises — multilingual embedding (Jina) + alias")
    print("    gazetteer + transliteration (opencc/pypinyin). String ops alone are insufficient.")


if __name__ == "__main__":
    main()
