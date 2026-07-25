"""Validate task_set_new_tiers.json two ways:

1. Schema: every task's objective/intent constructs a real
   salva_core.schemas.DiscoveryRequest -- same discipline task_set_v1.json
   claims in TASK_SET_README.md.
2. Ground truth (network, opt-in via --live): re-fetch GLEIF/SEC EDGAR and
   diff live membership/counts/reason-codes against what's stored in the
   JSON, so drift (GLEIF re-publishes its golden copy; SEC filings don't
   change but the extraction regex could) is caught, not silently trusted
   forever. Mirrors TASK_SET_README.md's own audit instruction ("follow its
   source_url(s) directly").

Run:
    python -m experiments.salva_v2.harness.validate_new_tiers            # schema only
    python -m experiments.salva_v2.harness.validate_new_tiers --live     # + live re-fetch
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TASK_SET_PATH = Path(__file__).resolve().parent.parent / "task_set_new_tiers.json"
UA = "salva-benchmark-research/1.0 (ryan910814@gmail.com)"


def _validate_schema(tasks: list[dict]) -> list[str]:
    from salva_core.schemas import DiscoveryRequest

    errors = []
    for task in tasks:
        try:
            DiscoveryRequest(objective=task["objective"], intent=task["intent"])
        except Exception as exc:  # noqa: BLE001 -- report every bad task, not just the first
            errors.append(f"{task['task_id']}: {exc}")
    return errors


def _gleif_get(url: str) -> dict:
    headers = {"Accept": "application/vnd.api+json", "User-Agent": UA}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())


def _live_check_gleif_children(lei: str, relation: str, expected_leis: set[str]) -> str | None:
    d = _gleif_get(f"https://api.gleif.org/api/v1/lei-records/{lei}/{relation}")
    live_leis = {r["id"] for r in d.get("data", [])}
    if live_leis != expected_leis:
        return f"{relation} for {lei}: expected {sorted(expected_leis)}, live {sorted(live_leis)}"
    return None


def _live_check_gleif_reason(lei: str, expected_reason: str) -> str | None:
    d = _gleif_get(f"https://api.gleif.org/api/v1/lei-records/{lei}/direct-parent-reporting-exception")
    live_reason = d.get("data", {}).get("attributes", {}).get("reason")
    if live_reason != expected_reason:
        return (
            f"direct-parent-reporting-exception for {lei}: "
            f"expected {expected_reason}, live {live_reason}"
        )
    return None


def _live_check_sec13d(url: str, expected_count: int) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
    import html
    decoded = raw.decode("utf-8", "ignore")
    txt = html.unescape(re.sub(r"<[^>]+>", " ", decoded)).replace("\xa0", " ")
    pattern = (
        r"NAME[S]?\s+OF\s+REPORTING\s+PERSON[S]?\s*[:.]?\s*\n?\s*"
        r"(.{2,80}?)\s*(?:\n|I\.?R\.?S\.?|S\.?S\.? OR)"
    )
    matches = re.findall(pattern, txt, re.I)
    seen = set()
    for m in matches:
        name = re.sub(r"\s+", " ", m).strip().rstrip(".,").lower()
        if len(name) >= 4 and not name.startswith(("see ", "this ", "page", "name")):
            seen.add(name)
    if len(seen) != expected_count:
        return (
            f"SEC 13D {url}: expected {expected_count} reporting persons, "
            f"live parse found {len(seen)}"
        )
    return None


def _validate_live(tasks: list[dict]) -> list[str]:
    errors = []
    for task in tasks:
        tid = task["task_id"]
        if tid.startswith("nary-01") or tid.startswith("nary-03"):
            subject = task["ground_truth_entities"][0]
            expected = {e["lei"] for e in task["ground_truth_entities"][1:]}
            err = _live_check_gleif_children(subject["lei"], "direct-children", expected)
        elif tid.startswith("nary-02"):
            subject = task["ground_truth_entities"][0]
            expected = {e["lei"] for e in task["ground_truth_entities"][1:]}
            err = _live_check_gleif_children(subject["lei"], "ultimate-children", expected)
        elif tid.startswith("nary-04"):
            url = task["ground_truth_entities"][0]["source_url"]
            expected_count = len(task["ground_truth_entities"]) - 1  # excl. subject
            err = _live_check_sec13d(url, expected_count)
        elif task["difficulty_tier"] == "aggregation_count":
            gt = task["ground_truth_entities"][0]
            lei = gt["source_url"].split("/lei-records/")[1].split("/")[0]
            relation = gt["source_url"].rstrip("/").split("/")[-1]
            expected = set(gt["member_leis"])
            err = _live_check_gleif_children(lei, relation, expected)
        elif task["difficulty_tier"] == "negative_absence":
            gt = task["ground_truth_entities"][0]
            lei = gt["source_url"].split("/lei-records/")[1].split("/")[0]
            err = _live_check_gleif_reason(lei, gt["reason_code"])
        else:
            err = None
        if err:
            errors.append(f"{tid}: {err}")
    return errors


def main() -> int:
    tasks = json.loads(TASK_SET_PATH.read_text(encoding="utf-8"))["tasks"]

    schema_errors = _validate_schema(tasks)
    if schema_errors:
        print(f"SCHEMA FAILURES ({len(schema_errors)}):")
        for e in schema_errors:
            print(" -", e)
    else:
        print(f"schema OK: {len(tasks)}/{len(tasks)} tasks construct a valid DiscoveryRequest")

    live_errors: list[str] = []
    if "--live" in sys.argv:
        live_errors = _validate_live(tasks)
        if live_errors:
            print(f"LIVE GROUND-TRUTH DRIFT ({len(live_errors)}):")
            for e in live_errors:
                print(" -", e)
        else:
            print("live re-verification OK: all GLEIF/SEC ground truth matches the JSON")

    return 1 if (schema_errors or live_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
