"""
把清洗后的 parquet 抽成统一 SFT schema。

用法：
    python extract_fields.py --in ../../data/processed/v2_clean_2026Q1.parquet \
                             --out-sft ../../data/datasets/v2_sft_2026Q1.jsonl \
                             --out-bench ../../data/datasets/v2_bench_2026Q1.jsonl \
                             --arch v2

两个产出：
1. SFT 集：只含 success + 长度合规 + 无错误的样本
2. Benchmark 候选：包含 has_error 或 too_long 的样本（能被复现/测失败模式）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def to_std_messages(raw_inputs: dict, raw_outputs) -> tuple[list, str, list[str]]:
    """
    把 LangSmith 的 inputs/outputs 展开成标准 messages + system + skills_loaded。

    注意：具体展开逻辑强依赖你们 agent 的 trace 结构。
    下面是一个通用骨架，需要根据实际 inputs/outputs 形状调整。
    """
    system = ""
    skills: list[str] = []
    messages: list[dict] = []

    # 1. 从 inputs 里拿 system / skills
    if isinstance(raw_inputs, dict):
        system = raw_inputs.get("system", "") or raw_inputs.get("system_prompt", "") or ""
        skills = raw_inputs.get("skills_loaded", []) or raw_inputs.get("skills", []) or []
        user_content = raw_inputs.get("input") or raw_inputs.get("user_input") or raw_inputs.get("messages")
        if isinstance(user_content, str):
            messages.append({"role": "user", "content": user_content})
        elif isinstance(user_content, list):
            # messages-style inputs
            for m in user_content:
                if isinstance(m, dict) and "role" in m:
                    messages.append(m)

    # 2. outputs
    if isinstance(raw_outputs, dict):
        out_msgs = raw_outputs.get("messages") or raw_outputs.get("output")
        if isinstance(out_msgs, list):
            messages.extend([m for m in out_msgs if isinstance(m, dict)])
        elif isinstance(out_msgs, str):
            messages.append({"role": "assistant", "content": out_msgs})
    elif isinstance(raw_outputs, list):
        messages.extend([m for m in raw_outputs if isinstance(m, dict)])

    return messages, system, skills


def derive_status(row) -> str:
    if row.get("has_error"):
        return "error"
    return "success"


def sample_from_row(row, arch: str) -> dict:
    raw_inputs = json.loads(row["inputs"]) if row["inputs"] else {}
    raw_outputs = json.loads(row["outputs"]) if row["outputs"] else {}
    messages, system, skills = to_std_messages(raw_inputs, raw_outputs)
    return {
        "sample_id": f"{arch}_{row['start_time'][:10].replace('-', '')}_{row['run_id'][:8]}",
        "task_type": f"marketing_ai_{arch}",
        "system": system,
        "skills_loaded": skills,
        "messages": messages,
        "final_status": derive_status(row),
        "metadata": {
            "run_id": row["run_id"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "total_tokens": int(row.get("total_tokens") or 0),
            "prompt_tokens": int(row.get("prompt_tokens") or 0),
            "completion_tokens": int(row.get("completion_tokens") or 0),
            "too_long": bool(row.get("too_long", False)),
            "has_error": bool(row.get("has_error", False)),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out-sft", required=True)
    ap.add_argument("--out-bench", required=True)
    ap.add_argument("--arch", required=True, choices=["v1", "v2"])
    args = ap.parse_args()

    df = pd.read_parquet(args.inp)
    df = df[df["arch"] == args.arch].copy()
    print(f"loaded {len(df)} rows for arch={args.arch}")

    out_sft = Path(args.out_sft)
    out_bench = Path(args.out_bench)
    out_sft.parent.mkdir(parents=True, exist_ok=True)
    out_bench.parent.mkdir(parents=True, exist_ok=True)

    n_sft = n_bench = 0
    with out_sft.open("w", encoding="utf-8") as f_sft, out_bench.open("w", encoding="utf-8") as f_bench:
        for _, row in df.iterrows():
            sample = sample_from_row(row, args.arch)
            # SFT 集：纯净 success + 非超长 + 有至少一对 user/assistant
            if (
                sample["final_status"] == "success"
                and not sample["metadata"]["too_long"]
                and any(m.get("role") == "user" for m in sample["messages"])
                and any(m.get("role") == "assistant" for m in sample["messages"])
            ):
                f_sft.write(json.dumps(sample, ensure_ascii=False) + "\n")
                n_sft += 1
            # Benchmark 候选：全部保留（包括错误/超长）
            f_bench.write(json.dumps(sample, ensure_ascii=False) + "\n")
            n_bench += 1

    print(f"SFT: {n_sft} → {out_sft}")
    print(f"Bench candidates: {n_bench} → {out_bench}")


if __name__ == "__main__":
    main()
