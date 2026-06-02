from __future__ import annotations

import argparse
import json
from pathlib import Path

from salva_core.pricing import normalize_pricing_catalog_payload, save_pricing_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the Salva pricing catalog from a JSON source.")
    parser.add_argument("--source-url", help="URL that returns a JSON pricing payload.")
    parser.add_argument("--input-path", help="Local JSON file to read instead of fetching from URL.")
    parser.add_argument("--output-path", help="Where to write the normalized catalog JSON.")
    parser.add_argument("--source-name", help="Human-readable source name.")
    args = parser.parse_args()

    payload = _load_payload(args.source_url, args.input_path)
    normalized = normalize_pricing_catalog_payload(payload, source_name=args.source_name, source_url=args.source_url)
    target = save_pricing_catalog(normalized, output_path=args.output_path)

    print(json.dumps({
        "output_path": str(target),
        "source_name": normalized.get("source_name"),
        "source_url": normalized.get("source_url"),
        "entries": len(normalized.get("entries", [])),
    }, ensure_ascii=False, indent=2))
    return 0


def _load_payload(source_url: str | None, input_path: str | None):
    if input_path:
        return json.loads(Path(input_path).expanduser().read_text(encoding="utf-8"))
    if source_url:
        from urllib.request import Request, urlopen

        request = Request(source_url, headers={"User-Agent": "SalvaRuntime/1.0"})
        with urlopen(request, timeout=20) as response:  # nosec: runtime-controlled URL
            return json.loads(response.read().decode("utf-8"))
    raise SystemExit("Provide either --source-url or --input-path")


if __name__ == "__main__":
    raise SystemExit(main())
