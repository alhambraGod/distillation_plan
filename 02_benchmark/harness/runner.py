"""Benchmark 主循环。"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .case import BenchmarkCase
from .metrics import DEFAULT_METRICS, Metric
from .model_client import build_client
from .reporter import write_report

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_benchmark(
    cases: list[BenchmarkCase],
    model_name: str,
    metrics: list[Metric],
    concurrency: int = 5,
    resume_path: Path | None = None,
) -> list[dict]:
    client = build_client(model_name)
    done_ids: set[str] = set()
    results: list[dict] = []

    if resume_path and resume_path.exists():
        with resume_path.open() as f:
            for line in f:
                r = json.loads(line)
                done_ids.add(r["case_id"])
                results.append(r)
        log.info("resume: %d done", len(done_ids))

    pending = [c for c in cases if c.case_id not in done_ids]
    log.info("running %d new cases", len(pending))

    f_append = resume_path.open("a", encoding="utf-8") if resume_path else None
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futs = {pool.submit(client.run, c): c for c in pending}
            for fut in as_completed(futs):
                case = futs[fut]
                try:
                    trace = fut.result()
                except Exception as e:
                    log.warning("case %s crashed: %s", case.case_id, e)
                    continue
                row = {
                    "case_id": case.case_id,
                    "model": model_name,
                    "trace": trace.to_dict(),
                    "metrics": {m.name: m.compute_single(case, trace) for m in metrics},
                }
                results.append(row)
                if f_append:
                    f_append.write(json.dumps(row, ensure_ascii=False) + "\n")
                    f_append.flush()
                if len(results) % 20 == 0:
                    log.info("progress %d/%d", len(results), len(cases))
    finally:
        if f_append:
            f_append.close()

    return results


def aggregate(results: list[dict], metrics: list[Metric]) -> dict[str, float]:
    out: dict[str, float] = {}
    for m in metrics:
        vals = [r["metrics"].get(m.name, 0.0) for r in results if m.name in r["metrics"]]
        out[m.name] = m.aggregate(vals)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--model", required=True, help="e.g. claude-3-5-sonnet, local-qwen2.5-7b")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--spec-version", default="v1.0")
    ap.add_argument("--concurrency", type=int, default=5)
    args = ap.parse_args()

    cases = BenchmarkCase.from_jsonl(Path(args.cases))
    log.info("loaded %d cases", len(cases))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resume = out_dir / f"raw_{args.model}.jsonl"

    results = run_benchmark(cases, args.model, DEFAULT_METRICS, args.concurrency, resume)
    agg = aggregate(results, DEFAULT_METRICS)
    log.info("aggregate: %s", agg)

    write_report(
        out_path=out_dir / f"report_{args.model}.md",
        model=args.model,
        spec_version=args.spec_version,
        aggregated=agg,
        results=results,
    )


if __name__ == "__main__":
    main()
