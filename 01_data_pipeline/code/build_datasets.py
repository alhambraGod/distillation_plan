"""
最后一步：SFT 集切 train/val/test，Benchmark 集采样黄金集。

用法：
    python build_datasets.py \
        --sft-in ../../data/datasets/v2_sft_2026Q1.jsonl \
        --bench-in ../../data/datasets/v2_bench_2026Q1.jsonl \
        --out-dir ../../data/datasets/v2/ \
        --seed 42 \
        --golden-n 200
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def stratified_split(
    samples: list[dict],
    ratios: tuple[float, float, float],
    seed: int,
    strata_key: str = "task_type",
) -> tuple[list, list, list]:
    """按 strata_key 分层随机切分。"""
    rng = random.Random(seed)
    buckets: dict[str, list[dict]] = {}
    for s in samples:
        buckets.setdefault(s.get(strata_key, "_"), []).append(s)

    train, val, test = [], [], []
    for k, items in buckets.items():
        rng.shuffle(items)
        n = len(items)
        n_train = int(n * ratios[0])
        n_val = int(n * ratios[1])
        train.extend(items[:n_train])
        val.extend(items[n_train : n_train + n_val])
        test.extend(items[n_train + n_val :])
    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def build_benchmark_case(sample: dict) -> dict:
    """从 SFT 样本反向构造 benchmark case（取 user 首轮作为初始输入）。"""
    first_user = next((m for m in sample["messages"] if m.get("role") == "user"), None)
    expected_tools = []
    for m in sample["messages"]:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                name = tc.get("name") or (tc.get("function") or {}).get("name")
                if name:
                    expected_tools.append(name)
    golden = next(
        (m.get("content") for m in reversed(sample["messages"]) if m.get("role") == "assistant" and m.get("content")),
        "",
    )
    return {
        "case_id": f"bench_{sample['sample_id']}",
        "task_type": sample["task_type"],
        "system": sample["system"],
        "skills_loaded": sample["skills_loaded"],
        "initial_input": first_user or {"role": "user", "content": ""},
        "expected_status": sample["final_status"],
        "expected_tools": expected_tools,
        "expected_tools_strict": False,
        "golden_output": golden,
        "source_sample_id": sample["sample_id"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft-in", required=True)
    ap.add_argument("--bench-in", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--golden-n", type=int, default=200)
    ap.add_argument("--ratios", default="0.9,0.05,0.05", help="train,val,test")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ratios = tuple(float(x) for x in args.ratios.split(","))
    assert len(ratios) == 3 and abs(sum(ratios) - 1.0) < 1e-6, "ratios must sum to 1"

    sft = read_jsonl(Path(args.sft_in))
    print(f"SFT source: {len(sft)}")

    train, val, test = stratified_split(sft, ratios, seed=args.seed)
    write_jsonl(train, out_dir / "sft_train.jsonl")
    write_jsonl(val, out_dir / "sft_val.jsonl")
    write_jsonl(test, out_dir / "sft_test.jsonl")
    print(f"split → train={len(train)} val={len(val)} test={len(test)}")

    # Benchmark：从 bench 候选抽 golden_n 条，分层按 final_status
    bench = read_jsonl(Path(args.bench_in))
    rng = random.Random(args.seed + 1)
    success_cases = [s for s in bench if s["final_status"] == "success"]
    error_cases = [s for s in bench if s["final_status"] != "success"]
    rng.shuffle(success_cases)
    rng.shuffle(error_cases)

    golden = success_cases[: int(args.golden_n * 0.8)] + error_cases[: int(args.golden_n * 0.2)]
    rng.shuffle(golden)
    golden_cases = [build_benchmark_case(s) for s in golden]
    write_jsonl(golden_cases, out_dir / "benchmark_golden.jsonl")
    print(f"golden cases: {len(golden_cases)} → {out_dir / 'benchmark_golden.jsonl'}")

    # 打印一个 manifest 方便追踪
    manifest = {
        "seed": args.seed,
        "ratios": ratios,
        "counts": {
            "sft_train": len(train),
            "sft_val": len(val),
            "sft_test": len(test),
            "benchmark_golden": len(golden_cases),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"manifest → {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
