"""报告生成。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _fmt(val: float, metric_name: str) -> str:
    if "rate" in metric_name or "success" in metric_name or "f1" in metric_name or "exact" in metric_name:
        return f"{val * 100:.1f}%"
    if "latency" in metric_name:
        return f"{val:.0f} ms"
    if "cost" in metric_name:
        return f"${val:.4f}"
    return f"{val:.2f}"


def _top_failures(results: list[dict], n: int = 10) -> list[dict]:
    failed = [r for r in results if r["metrics"].get("success_rate", 0) < 1.0]
    failed.sort(key=lambda r: sum(r["metrics"].values()))
    return failed[:n]


def write_report(out_path: Path, model: str, spec_version: str, aggregated: dict, results: list[dict]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    total = len(results)
    failures = _top_failures(results)

    lines = []
    lines.append(f"# Benchmark Report: {model}")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Eval Spec: {spec_version}")
    lines.append(f"- Total cases: {total}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for name, val in aggregated.items():
        lines.append(f"| {name} | {_fmt(val, name)} |")
    lines.append("")

    lines.append("## Top Failures")
    lines.append("")
    for f in failures[:10]:
        tr = f["trace"]
        lines.append(f"### {f['case_id']}")
        lines.append(f"- final_status: `{tr['final_status']}`")
        if tr.get("error_message"):
            lines.append(f"- error: {tr['error_message'][:300]}")
        lines.append(f"- metrics: `{json.dumps(f['metrics'])}`")
        lines.append(f"- output: {tr['final_output'][:300]}")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Human evaluation on golden set NOT included here — see separate human-review doc.")
    lines.append("- This report is auto-generated; hand-written analysis section should be appended below.")
    lines.append("")
    lines.append("## Analysis (to be filled)")
    lines.append("")
    lines.append("_Team lead to fill in observations and next-step decisions here._")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"report → {out_path}")
