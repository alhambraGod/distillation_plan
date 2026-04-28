"""
清洗 + 脱敏。每条规则独立函数，便于单测和 A/B。

用法：
    python clean.py --in ../../data/raw/v2_traces_2026Q1.parquet \
                    --out ../../data/processed/v2_clean_2026Q1.parquet \
                    --report ../../data/processed/v2_clean_report.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# ---------- PII 正则 ----------
PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone_cn": re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)"),
    "phone_intl": re.compile(r"\+\d{1,3}[-\s]?\d{4,14}"),
    "id_cn": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "credit_card": re.compile(r"(?<!\d)\d{13,19}(?!\d)"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
}

REDACT = "[REDACTED_{tag}]"


# ---------- 过滤规则 ----------
@dataclass
class Rule:
    id: str
    desc: str
    keep_for_benchmark: bool  # 是否保留进 benchmark
    keep_for_training: bool   # 是否保留进训练集


RULES: list[Rule] = [
    Rule("R01", "error != null", keep_for_benchmark=True, keep_for_training=False),
    Rule("R02", "status == cancelled", keep_for_benchmark=False, keep_for_training=False),
    Rule("R03", "tool_call JSON invalid", keep_for_benchmark=False, keep_for_training=False),
    Rule("R05_short", "total tokens < 50", keep_for_benchmark=False, keep_for_training=False),
    Rule("R05_long", "total tokens > 32000", keep_for_benchmark=True, keep_for_training=False),
    Rule("R06", "duplicate prompt (keep latest)", keep_for_benchmark=False, keep_for_training=False),
    Rule("R08", "no assistant message", keep_for_benchmark=False, keep_for_training=False),
]


def redact_pii(text: str) -> tuple[str, Counter]:
    hits: Counter = Counter()
    if not text:
        return text, hits
    for tag, pat in PII_PATTERNS.items():
        def _sub(m):
            hits[tag] += 1
            return REDACT.format(tag=tag.upper())
        text = pat.sub(_sub, text)
    return text, hits


def _parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


def classify_arch(project: str) -> str:
    """按项目名粗分 V1 / V2。根据实际项目名改这个映射。"""
    p = (project or "").lower()
    if "v2" in p or "deerflow" in p or "marketing-ai" in p:
        return "v2"
    if "v1" in p or "agent-service" in p:
        return "v1"
    return "unknown"


def validate_tool_calls(outputs) -> bool:
    """outputs 里如果有 tool_calls，检查每个都能被 parse 且有 name / arguments."""
    if not outputs:
        return True
    msgs = outputs if isinstance(outputs, list) else outputs.get("messages", []) if isinstance(outputs, dict) else []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        for tc in m.get("tool_calls", []) or []:
            if not tc.get("name"):
                return False
            args = tc.get("arguments") or tc.get("args")
            if isinstance(args, str):
                if _parse_json(args) is None:
                    return False
    return True


def has_assistant_message(outputs) -> bool:
    if not outputs:
        return False
    msgs = outputs if isinstance(outputs, list) else outputs.get("messages", []) if isinstance(outputs, dict) else []
    return any(isinstance(m, dict) and m.get("role") == "assistant" for m in msgs)


def normalize_for_dedup(text: str) -> str:
    import hashlib
    stripped = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(stripped.encode()).hexdigest()


# ---------- 主流程 ----------
def clean(in_path: Path, out_path: Path, report_path: Path) -> None:
    df = pd.read_parquet(in_path)
    print(f"loaded {len(df)} raw runs")

    df["arch"] = df["project"].apply(classify_arch)

    # parse json columns
    df["inputs_obj"] = df["inputs"].apply(_parse_json)
    df["outputs_obj"] = df["outputs"].apply(_parse_json)

    report = {"total_in": len(df), "dropped": Counter(), "arch_dist": Counter(), "pii_hits": Counter()}

    # Rule R01: 错误的，打 tag
    df["has_error"] = df["error"].notna()

    # R02: cancelled
    before = len(df)
    df = df[df["status"].str.lower() != "cancelled"].copy()
    report["dropped"]["R02_cancelled"] = before - len(df)

    # R03: tool_call JSON 无效
    before = len(df)
    df["tool_calls_valid"] = df["outputs_obj"].apply(validate_tool_calls)
    df = df[df["tool_calls_valid"]].copy()
    report["dropped"]["R03_invalid_tool_calls"] = before - len(df)

    # R05: 长度过滤
    df["total_tokens"] = df["total_tokens"].fillna(0).astype(int)
    before = len(df)
    df = df[df["total_tokens"] >= 50].copy()
    report["dropped"]["R05_too_short"] = before - len(df)

    df["too_long"] = df["total_tokens"] > 32000  # 长的只在 benchmark 用

    # R08: 无 assistant
    before = len(df)
    df["has_assistant"] = df["outputs_obj"].apply(has_assistant_message)
    df = df[df["has_assistant"]].copy()
    report["dropped"]["R08_no_assistant"] = before - len(df)

    # R06: 去重（保留 end_time 最新）
    df["prompt_hash"] = df["inputs"].apply(normalize_for_dedup)
    before = len(df)
    df = df.sort_values("end_time").drop_duplicates("prompt_hash", keep="last").copy()
    report["dropped"]["R06_duplicates"] = before - len(df)

    # R04: PII 脱敏
    pii_counter: Counter = Counter()
    def _redact_row(s):
        r, hits = redact_pii(s)
        for k, v in hits.items():
            pii_counter[k] += v
        return r

    df["inputs"] = df["inputs"].apply(_redact_row)
    df["outputs"] = df["outputs"].apply(_redact_row)
    report["pii_hits"].update(pii_counter)

    # arch 分布
    report["arch_dist"].update(df["arch"].value_counts().to_dict())

    # 落盘
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 丢弃辅助列，保留原始 + 标签
    df_out = df.drop(columns=["inputs_obj", "outputs_obj", "prompt_hash", "tool_calls_valid", "has_assistant"])
    df_out.to_parquet(out_path, index=False)
    print(f"written {len(df_out)} rows to {out_path}")

    report["total_out"] = len(df_out)
    report["dropped"] = dict(report["dropped"])
    report["arch_dist"] = dict(report["arch_dist"])
    report["pii_hits"] = dict(report["pii_hits"])
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"report → {report_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    clean(Path(args.inp), Path(args.out), Path(args.report))


if __name__ == "__main__":
    main()
