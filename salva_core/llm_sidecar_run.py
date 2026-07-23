"""Entrypoint the user runs in their own terminal to host the sidecar LLM
backend: `python -m salva_core.llm_sidecar_run`.

Keep this terminal open -- closing it ends the process, which is exactly
the signal salva_core.llm_sidecar.complete_with_sidecar() detects (the next
connection attempt gets ConnectionRefusedError / the socket file is gone).

Requires `claude login` or `codex login` to have been run beforehand in
this same environment; this script does not perform login itself.
"""
from __future__ import annotations

import sys

from salva_core.llm_sidecar import SidecarServer, resolve_instance_id


def main() -> None:
    instance_id = resolve_instance_id()
    print(f"salva LLM sidecar starting (instance={instance_id}). Ctrl-C to stop.")
    print("Requires `claude login` or `codex login` to already be authenticated.")
    server = SidecarServer(instance_id=instance_id)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nsalva LLM sidecar stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
