"""使用者在自己的 terminal 執行來架設 sidecar LLM 後端的進入點：
`python -m salva_core.llm_sidecar_run`。

保持這個 terminal 開著——關掉它就是進程結束，而這正是
salva_core.llm_sidecar.complete_with_sidecar() 偵測到的訊號（下一次連線
會拿到 ConnectionRefusedError，或 socket 檔案已經消失）。

執行前需要在同一環境先跑過 `claude login` 或 `codex login`；本腳本不做
登入這件事本身。
"""
from __future__ import annotations

import argparse
import json
import sys

from salva_core.llm_sidecar import (
    SidecarAlreadyRunning,
    SidecarServer,
    resolve_instance_id,
    run_preflight,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="不啟動 sidecar，只印一行 JSON 回報每個 CLI 的 PATH/登入狀態後結束（exit 0）",
    )
    args = parser.parse_args()

    if args.preflight:
        print(json.dumps(run_preflight()))
        sys.exit(0)

    instance_id = resolve_instance_id()
    print(f"salva LLM sidecar 啟動中（instance={instance_id}）。Ctrl-C 停止。")
    print("需要 `claude login` 或 `codex login` 已經完成登入驗證。")
    server = SidecarServer(instance_id=instance_id)
    try:
        server.serve_forever()
    except SidecarAlreadyRunning as exc:
        print(f"ALREADY_RUNNING：socket 已有活著的 process 在聽（{exc}），不搶占。")
        sys.exit(3)
    except KeyboardInterrupt:
        print("\nsalva LLM sidecar 已停止。")
        sys.exit(0)


if __name__ == "__main__":
    main()
