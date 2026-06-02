from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from salva_core.benchmark import build_benchmark_report, write_benchmark_bundle
from salva_core.schemas import BenchmarkRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Salva benchmark artifacts.")
    parser.add_argument("--run-id", action="append", dest="run_ids", required=True, help="Run ID to include. Repeatable.")
    parser.add_argument("--label", default=None, help="Optional benchmark label.")
    parser.add_argument("--output-dir", default=None, help="Directory for JSON and Markdown artifacts.")
    parser.add_argument("--db-path", default=None, help="Optional SQLite path override.")
    parser.add_argument("--markdown-only", action="store_true", help="Write only Markdown summary to stdout.")
    args = parser.parse_args()

    payload = BenchmarkRequest(run_ids=args.run_ids, label=args.label)

    if args.markdown_only:
        report = build_benchmark_report(payload, path=args.db_path)
        from salva_core.benchmark import render_benchmark_markdown

        print(render_benchmark_markdown(report))
        return 0

    report, json_path, md_path = write_benchmark_bundle(payload, output_dir=args.output_dir, path=args.db_path)
    print(f"benchmark_runs={report.total_runs}")
    print(f"json_path={json_path}")
    print(f"markdown_path={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
