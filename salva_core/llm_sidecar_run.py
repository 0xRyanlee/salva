"""使用者在自己的 terminal 執行來架設 sidecar LLM 後端的進入點：
`python -m salva_core.llm_sidecar_run`。

保持這個 terminal 開著——關掉它就是進程結束，而這正是
salva_core.llm_sidecar.complete_with_sidecar() 偵測到的訊號（下一次連線
會拿到 ConnectionRefusedError，或 socket 檔案已經消失）。

執行前需要在同一環境先跑過 `claude login` 或 `codex login`；本腳本不做
登入這件事本身。
"""
from __future__ import annotations

import sys

from salva_core.llm_sidecar import SidecarServer, resolve_instance_id


def main() -> None:
    instance_id = resolve_instance_id()
    print(f"salva LLM sidecar 啟動中（instance={instance_id}）。Ctrl-C 停止。")
    print("需要 `claude login` 或 `codex login` 已經完成登入驗證。")
    server = SidecarServer(instance_id=instance_id)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nsalva LLM sidecar 已停止。")
        sys.exit(0)


if __name__ == "__main__":
    main()
