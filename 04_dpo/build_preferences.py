"""
构造 DPO 偏好对数据。

三种来源：
A. LangSmith 历史挖掘（同 prompt 不同 trace）
B. SFT 多次采样 + judge 排序
C. Claude vs SFT（慎用，不超过 20%）

输出：datasets/dpo_v2.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


@dataclass
class PrefPair:
    pair_id: str
    prompt: str               # apply_chat_template 后的字符串
    chosen: str               # assistant 完整回复
    rejected: str
    source: str               # "history" | "sampled" | "claude_vs_sft"
    metadata: dict


# ------------------------------------------------------------
# 来源 A：LangSmith 历史挖掘
# ------------------------------------------------------------
def mine_from_history(history_jsonl: Path, n_pairs: int) -> list[PrefPair]:
    """
    从历史 SFT 集里找"同一 prompt 出现多次"的样本，挑更好的作 chosen。

    前提：你已经用 `extract_fields.py` 处理过，历史样本每条带 prompt_hash。
    这里用一个简化策略：按 prompt hash 聚类，组内用 token 长度或成功状态筛选。
    """
    import hashlib
    from collections import defaultdict

    groups: dict[str, list[dict]] = defaultdict(list)
    with history_jsonl.open(encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            user_text = next((m.get("content", "") for m in s["messages"] if m.get("role") == "user"), "")
            h = hashlib.sha256(user_text.encode()).hexdigest()
            groups[h].append(s)

    pairs = []
    for h, items in groups.items():
        if len(items) < 2:
            continue
        # 简化：token 多的 + final_status == success 当 chosen
        items.sort(key=lambda s: (s["final_status"] != "success", -s["metadata"].get("completion_tokens", 0)))
        chosen = items[0]
        rejected = items[-1]
        if chosen == rejected:
            continue
        prompt = next((m.get("content", "") for m in chosen["messages"] if m.get("role") == "user"), "")
        pairs.append(PrefPair(
            pair_id=f"hist_{h[:12]}",
            prompt=prompt,
            chosen=_extract_assistant_text(chosen),
            rejected=_extract_assistant_text(rejected),
            source="history",
            metadata={"group_size": len(items)},
        ))
        if len(pairs) >= n_pairs:
            break
    log.info("mined %d pairs from history", len(pairs))
    return pairs


def _extract_assistant_text(sample: dict) -> str:
    """把最后一条 assistant 消息序列化（含 tool_calls）"""
    asst = next((m for m in reversed(sample["messages"]) if m.get("role") == "assistant"), None)
    if not asst:
        return ""
    parts = [asst.get("content", "") or ""]
    for tc in asst.get("tool_calls") or []:
        name = tc.get("name") or (tc.get("function") or {}).get("name", "")
        args = tc.get("arguments") or (tc.get("function") or {}).get("arguments", {})
        if isinstance(args, dict):
            args = json.dumps(args, ensure_ascii=False)
        parts.append(f"<tool_call>{{\"name\": \"{name}\", \"arguments\": {args}}}</tool_call>")
    return "\n".join(parts).strip()


# ------------------------------------------------------------
# 来源 B：SFT 多次采样 + judge 排序
# ------------------------------------------------------------
def sample_and_rank(
    prompts: list[str],
    sft_client,                   # 实现 .generate(prompt, temperature) 的对象
    judge_client,                 # 实现 .score(prompt, output) 的对象
    k: int = 4,
    n_pairs: int = 2000,
) -> list[PrefPair]:
    pairs = []
    for i, prompt in enumerate(prompts):
        candidates = [sft_client.generate(prompt, temperature=0.8) for _ in range(k)]
        scored = [(c, judge_client.score(prompt, c)) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        chosen = scored[0][0]
        rejected = scored[-1][0]
        if chosen == rejected:
            continue
        pairs.append(PrefPair(
            pair_id=f"smp_{i:06d}",
            prompt=prompt,
            chosen=chosen,
            rejected=rejected,
            source="sampled",
            metadata={"chosen_score": scored[0][1], "rejected_score": scored[-1][1]},
        ))
        if len(pairs) >= n_pairs:
            break
    return pairs


# ------------------------------------------------------------
# 来源 C：Claude vs SFT
# ------------------------------------------------------------
def claude_vs_sft(
    prompts: list[str],
    claude_client,
    sft_client,
    n_pairs: int = 500,
) -> list[PrefPair]:
    pairs = []
    for i, prompt in enumerate(prompts):
        c_out = claude_client.generate(prompt)
        s_out = sft_client.generate(prompt, temperature=0.7)
        if c_out == s_out:
            continue
        pairs.append(PrefPair(
            pair_id=f"cvs_{i:06d}",
            prompt=prompt,
            chosen=c_out,
            rejected=s_out,
            source="claude_vs_sft",
            metadata={},
        ))
        if len(pairs) >= n_pairs:
            break
    return pairs


# ------------------------------------------------------------
# 质量过滤
# ------------------------------------------------------------
def filter_pairs(pairs: list[PrefPair]) -> list[PrefPair]:
    kept = []
    for p in pairs:
        # 1. chosen 和 rejected 不能完全相同
        if p.chosen.strip() == p.rejected.strip():
            continue
        # 2. 长度差异过大（1 比 >3 倍）→ 长度偏差
        lc, lr = len(p.chosen), len(p.rejected)
        if lc and lr and (max(lc, lr) / min(lc, lr) > 3):
            continue
        # 3. 任一为空
        if not p.chosen.strip() or not p.rejected.strip():
            continue
        kept.append(p)
    log.info("kept %d / %d after filter", len(kept), len(pairs))
    return kept


def write_jsonl(pairs: list[PrefPair], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps({
                "pair_id": p.pair_id,
                "prompt": p.prompt,
                "chosen": p.chosen,
                "rejected": p.rejected,
                "source": p.source,
                "metadata": p.metadata,
            }, ensure_ascii=False) + "\n")
    log.info("wrote %d pairs → %s", len(pairs), out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["history", "demo"])
    ap.add_argument("--history-in", help="SFT jsonl for history mode")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-pairs", type=int, default=2000)
    args = ap.parse_args()

    if args.mode == "history":
        pairs = mine_from_history(Path(args.history_in), args.n_pairs)
    elif args.mode == "demo":
        # 示例：只产几条假数据，教学用
        pairs = [
            PrefPair(
                pair_id="demo_001",
                prompt="写一句高端护肤品广告",
                chosen="点燃东方美学——唤醒肌肤本真光泽。",
                rejected="我们的面霜很不错，你应该买。",
                source="demo",
                metadata={},
            ),
        ]
    pairs = filter_pairs(pairs)
    write_jsonl(pairs, Path(args.out))


if __name__ == "__main__":
    main()
