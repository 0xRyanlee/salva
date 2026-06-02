from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from salva_core.worker import default_worker_id, run_job, run_worker_loop


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Salva queued-job worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Seconds between queue polls.")
    parser.add_argument("--worker-id", default=default_worker_id(), help="Stable worker identifier.")
    parser.add_argument("--db-path", default=None, help="Optional SQLite path override.")
    parser.add_argument("--job-id", default=None, help="Run one specific job immediately.")
    args = parser.parse_args()

    if args.job_id:
        run_job(args.job_id, path=args.db_path, execution_mode="worker")
        print("processed_jobs=1")
        return 0

    processed = run_worker_loop(worker_id=args.worker_id, poll_interval=args.poll_interval, once=args.once, path=args.db_path)
    print(f"processed_jobs={processed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
