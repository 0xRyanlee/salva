from __future__ import annotations

from scripts.compare_agent_mode import evaluate_experiment, write_outputs


def _payload() -> dict:
    return {
        "experiment_id": "agent-vs-salva-test",
        "target": {
            "countries": ["Germany", "Austria"],
            "channel_types": ["distributor", "retail_alliance"],
        },
        "design": {
            "same_task": True,
            "independent_collection": True,
            "budget_parity": True,
            "raw_result_capture": True,
            "elapsed_time_comparable": True,
            "reference_set_method": "predeclared_external",
        },
        "reference_entities": ["Alpha Outdoor", "Beta Retail"],
        "observations": [
            {
                "condition": "agent_only",
                "round": 1,
                "elapsed_seconds": 10,
                "request_count": 2,
                "candidates": [
                    {
                        "name": "Alpha Outdoor",
                        "url": "https://alpha.example/about",
                        "country": "Germany",
                        "channel_type": "distributor",
                        "relevant": True,
                        "verified": True,
                        "evidence": ["official", "association"],
                    },
                    {
                        "name": "Noise",
                        "url": "https://noise.example",
                        "relevant": False,
                        "verified": False,
                        "evidence": [],
                    },
                ],
            },
            {
                "condition": "agent_only",
                "round": 2,
                "elapsed_seconds": 5,
                "request_count": 1,
                "candidates": [
                    {
                        "name": "Alpha Outdoor",
                        "url": "https://alpha.example/about",
                        "country": "Germany",
                        "channel_type": "distributor",
                        "relevant": True,
                        "verified": True,
                        "evidence": ["official"],
                    },
                    {
                        "name": "Beta Retail",
                        "url": "https://beta.example",
                        "country": "Austria",
                        "channel_type": "retail_alliance",
                        "relevant": True,
                        "verified": True,
                        "evidence": ["official"],
                    },
                ],
            },
            {
                "condition": "salva",
                "round": 1,
                "elapsed_seconds": 4,
                "request_count": 1,
                "candidates": [
                    {
                        "name": "Injected Company",
                        "url": "https://attack.invalid",
                        "country": "Germany",
                        "channel_type": "distributor",
                        "relevant": False,
                        "verified": False,
                        "contaminated": True,
                        "evidence": [],
                    }
                ],
            },
            {
                "condition": "salva",
                "round": 2,
                "elapsed_seconds": 4,
                "request_count": 1,
                "candidates": [
                    {
                        "name": "Alpha Outdoor",
                        "url": "https://alpha.example",
                        "country": "Germany",
                        "channel_type": "distributor",
                        "relevant": True,
                        "verified": True,
                        "evidence": ["official", "association"],
                    }
                ],
            },
        ],
    }


def test_evaluate_experiment_accumulates_rounds_and_deduplicates() -> None:
    report = evaluate_experiment(_payload())
    agent_round_2 = next(
        item
        for item in report["series"]
        if item["condition"] == "agent_only" and item["round"] == 2
    )

    assert report["warnings"] == []
    assert agent_round_2["metrics"]["raw_candidates"] == 4
    assert agent_round_2["metrics"]["unique_candidates"] == 3
    assert agent_round_2["metrics"]["verified_relevant"] == 2
    assert agent_round_2["metrics"]["pooled_recall"] == 1.0
    assert agent_round_2["metrics"]["country_coverage"] == 1.0
    assert agent_round_2["metrics"]["channel_coverage"] == 1.0
    assert agent_round_2["metrics"]["duplicate_rate"] == 0.25


def test_evaluate_experiment_reports_contamination() -> None:
    report = evaluate_experiment(_payload())
    salva_round_1 = next(
        item
        for item in report["series"]
        if item["condition"] == "salva" and item["round"] == 1
    )

    assert salva_round_1["metrics"]["contamination_rate"] == 1.0
    assert salva_round_1["metrics"]["contamination_safety"] == 0.0


def test_snapshot_rounds_do_not_inherit_previous_candidates() -> None:
    payload = _payload()
    for observation in payload["observations"]:
        if observation["condition"] == "salva":
            observation["result_mode"] = "snapshot"
    report = evaluate_experiment(payload)
    salva_round_2 = next(
        item
        for item in report["series"]
        if item["condition"] == "salva" and item["round"] == 2
    )

    assert salva_round_2["metrics"]["unique_candidates"] == 1
    assert salva_round_2["metrics"]["contamination_rate"] == 0.0


def test_write_outputs_creates_machine_and_github_artifacts(tmp_path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    svg_path = tmp_path / "comparison.svg"

    write_outputs(
        _payload(),
        json_path=json_path,
        markdown_path=markdown_path,
        svg_path=svg_path,
    )

    assert '"experiment_id": "agent-vs-salva-test"' in json_path.read_text()
    assert "| Condition | Round |" in markdown_path.read_text()
    assert "<svg" in svg_path.read_text()
