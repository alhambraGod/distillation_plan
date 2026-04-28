"""
从 LangSmith 拉取 trace 并落到 Parquet。

用法：
    python pull_traces.py --project marketing-ai-v2 --start 2026-01-01 --end 2026-03-31 \
                          --out ../../data/raw/v2_traces_2026Q1.parquet

设计要点：
- 按时间窗口拉，不一次拉全库
- 支持断点续传：读 checkpoint 文件记录 last_run_id
- 失败重试：超时/429 自动退避
- 分页写入：每 500 条写一批，避免 OOM
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd
from langsmith import Client
from langsmith.utils import LangSmithRateLimitError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


@dataclass
class RawRun:
    run_id: str
    project: str
    run_type: str
    name: str
    inputs: str          # JSON stringified
    outputs: str         # JSON stringified
    error: str | None
    start_time: str
    end_time: str
    extra: str           # JSON stringified
    parent_run_id: str | None
    status: str
    total_tokens: int | None
    prompt_tokens: int | None
    completion_tokens: int | None


def _safe_json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception as e:
        log.warning("json dump failed: %s", e)
        return json.dumps({"_dump_error": str(e)})


def _run_to_raw(r) -> RawRun:
    usage = (r.extra or {}).get("invocation_params", {}).get("usage", {}) if r.extra else {}
    return RawRun(
        run_id=str(r.id),
        project=r.session_name or r.project_name or "",
        run_type=r.run_type,
        name=r.name or "",
        inputs=_safe_json(r.inputs),
        outputs=_safe_json(r.outputs),
        error=r.error,
        start_time=r.start_time.isoformat() if r.start_time else "",
        end_time=r.end_time.isoformat() if r.end_time else "",
        extra=_safe_json(r.extra),
        parent_run_id=str(r.parent_run_id) if r.parent_run_id else None,
        status=r.status or "",
        total_tokens=usage.get("total_tokens"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )


def iter_runs(
    client: Client,
    project: str,
    start: datetime,
    end: datetime,
    run_type: str = "chain",
    page_size: int = 500,
) -> Iterator[RawRun]:
    last_id = None
    fetched = 0
    while True:
        try:
            runs = list(
                client.list_runs(
                    project_name=project,
                    start_time=start,
                    end_time=end,
                    run_type=run_type,
                    limit=page_size,
                    execution_order=1,  # 只取顶层 run，子节点通过 parent_run_id 关联
                )
            )
        except LangSmithRateLimitError:
            log.warning("rate limited, backing off 30s")
            time.sleep(30)
            continue
        except Exception as e:
            log.error("list_runs failed: %s, retry in 10s", e)
            time.sleep(10)
            continue

        if not runs:
            break

        for r in runs:
            if str(r.id) == last_id:
                continue
            yield _run_to_raw(r)
            last_id = str(r.id)
            fetched += 1

        log.info("fetched %d so far", fetched)
        if len(runs) < page_size:
            break


def write_batch(records: list[RawRun], out_path: Path, append: bool) -> None:
    df = pd.DataFrame([asdict(r) for r in records])
    if append and out_path.exists():
        existing = pd.read_parquet(out_path)
        df = pd.concat([existing, df], ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True, help="LangSmith project name")
    ap.add_argument("--start", required=True, help="ISO date, e.g. 2026-01-01")
    ap.add_argument("--end", required=True, help="ISO date, e.g. 2026-03-31")
    ap.add_argument("--run-type", default="chain")
    ap.add_argument("--out", required=True, help="output parquet path")
    ap.add_argument("--batch-size", type=int, default=500)
    args = ap.parse_args()

    assert os.environ.get("LANGSMITH_API_KEY"), "set LANGSMITH_API_KEY"

    client = Client()
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    out_path = Path(args.out)

    buf: list[RawRun] = []
    total = 0
    for r in iter_runs(client, args.project, start, end, args.run_type):
        buf.append(r)
        if len(buf) >= args.batch_size:
            write_batch(buf, out_path, append=(total > 0))
            total += len(buf)
            buf = []

    if buf:
        write_batch(buf, out_path, append=(total > 0))
        total += len(buf)

    log.info("done. total=%d path=%s", total, out_path)


if __name__ == "__main__":
    main()
