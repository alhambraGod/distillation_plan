"""
L07 配套：DPO 偏好对合并 + 抽检报告生成

把 history / sampled / cross-model 三种来源按比例合并，
并随机抽 10% 生成人工 review 报告。

用法：
    python 04_dpo/merge_and_audit.py \
        --sources history,sampled,cross_model \
        --inputs data/datasets/v2/dpo_history.jsonl,data/datasets/v2/dpo_sampled.jsonl,data/datasets/v2/dpo_cross.jsonl \
        --ratios 0.3,0.5,0.2 \
        --out data/datasets/v2/dpo_merged.jsonl \
        --audit-out data/datasets/v2/dpo_audit_review.md \
        --audit-sample 0.1
"""
from __future__ import annotations
import argparse
import json
import random
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open() if l.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True,
                    help="逗号分隔的来源标签：history,sampled,cross_model")
    ap.add_argument("--inputs", required=True,
                    help="逗号分隔的输入 jsonl 路径")
    ap.add_argument("--ratios", required=True,
                    help="逗号分隔的比例，如 0.3,0.5,0.2")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--audit-out", type=Path, required=True)
    ap.add_argument("--audit-sample", type=float, default=0.1)
    ap.add_argument("--total", type=int, default=10000,
                    help="合并后目标总量")
    args = ap.parse_args()

    sources = args.sources.split(",")
    inputs = [Path(p.strip()) for p in args.inputs.split(",")]
    ratios = [float(r) for r in args.ratios.split(",")]

    if not (len(sources) == len(inputs) == len(ratios)):
        raise SystemExit("sources / inputs / ratios 长度必须一致")

    if abs(sum(ratios) - 1.0) > 0.01:
        print(f"⚠️ 比例之和 {sum(ratios)} ≠ 1.0，按相对值归一")
        s = sum(ratios)
        ratios = [r / s for r in ratios]

    print("=" * 60)
    print(" 偏好对合并")
    print("=" * 60)

    merged = []
    src_counts = {}
    for src, path, ratio in zip(sources, inputs, ratios):
        if not path.exists():
            print(f"  ⚠️ {path} 不存在，跳过")
            continue
        all_pairs = load_jsonl(path)
        n_target = int(args.total * ratio)
        n_actual = min(n_target, len(all_pairs))
        selected = random.sample(all_pairs, n_actual)
        for s in selected:
            s["_merge_source"] = src
        merged.extend(selected)
        src_counts[src] = n_actual
        print(f"  [{src}] 目标 {n_target}, "
              f"实际取 {n_actual}（来源 {len(all_pairs)} 总）")

    random.shuffle(merged)
    write_jsonl(args.out, merged)
    print(f"\n✅ 合并后 {len(merged)} 对 → {args.out}")
    print(f"📊 来源分布：{src_counts}")

    print("\n" + "=" * 60)
    print(" 长度分布检查（防 reward hacking）")
    print("=" * 60)
    chosen_lens = [len(p["chosen"]) if isinstance(p["chosen"], str)
                   else len(json.dumps(p["chosen"]))
                   for p in merged]
    rejected_lens = [len(p["rejected"]) if isinstance(p["rejected"], str)
                     else len(json.dumps(p["rejected"]))
                     for p in merged]
    diffs = [c - r for c, r in zip(chosen_lens, rejected_lens)]

    print(f"  chosen avg:    {sum(chosen_lens) / len(chosen_lens):.0f}")
    print(f"  rejected avg:  {sum(rejected_lens) / len(rejected_lens):.0f}")
    print(f"  mean diff:     {sum(diffs) / len(diffs):+.0f}")
    print(f"  max abs diff:  {max(abs(d) for d in diffs)}")

    if abs(sum(diffs) / len(diffs)) > 100:
        print("  ⚠️ 长度偏差大！chosen 平均比 rejected 长很多")
        print("     建议：用 SimPO 或在采样时长度均衡")

    print("\n" + "=" * 60)
    print(" 抽检报告生成")
    print("=" * 60)
    sample_n = max(20, int(len(merged) * args.audit_sample))
    sample = random.sample(merged, min(sample_n, len(merged)))

    args.audit_out.parent.mkdir(parents=True, exist_ok=True)
    with args.audit_out.open("w") as f:
        f.write("# 偏好对抽检报告\n\n")
        f.write(f"- 合并总量：{len(merged)} 对\n")
        f.write(f"- 抽检：{len(sample)} 对（{args.audit_sample:.0%}）\n")
        f.write(f"- 来源分布：{src_counts}\n\n")

        f.write("## 检查规则\n\n")
        f.write("- ✅ chosen 明显比 rejected 好\n")
        f.write("- ⚠️ 差不多 / 看不出区别\n")
        f.write("- ❌ rejected 反而更好（标错了）\n\n")
        f.write("**通过标准**：✅ 比例 ≥ 80%，否则数据质量不达标\n\n")

        for i, p in enumerate(sample):
            f.write(f"## #{i + 1} (来源: {p.get('_merge_source', 'n/a')})\n\n")
            prompt = p.get("prompt", "")
            if isinstance(prompt, dict):
                prompt = json.dumps(prompt, ensure_ascii=False)
            f.write(f"**Prompt**: {prompt[:400]}\n\n")

            chosen = p["chosen"]
            if isinstance(chosen, dict):
                chosen = json.dumps(chosen, ensure_ascii=False, indent=2)
            f.write(f"**Chosen**:\n```\n{chosen[:800]}\n```\n\n")

            rejected = p["rejected"]
            if isinstance(rejected, dict):
                rejected = json.dumps(rejected, ensure_ascii=False, indent=2)
            f.write(f"**Rejected**:\n```\n{rejected[:800]}\n```\n\n")

            f.write(f"**判断**：[ ] ✅ / [ ] ⚠️ / [ ] ❌\n\n")
            f.write("**理由**：\n\n---\n\n")

    print(f"✅ 抽检报告 → {args.audit_out}")
    print(f"   让业务方人工 review 后统计通过率")


if __name__ == "__main__":
    main()
