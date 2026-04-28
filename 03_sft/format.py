"""
把 jsonl 样本转成模型可训练的 chat 字符串。

关键点：
1. 不同基座 chat template 不同
2. Gemma 不支持 tool role，需要自定义模板
3. Qwen 2.5 原生支持 tool role，最省心
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer
from datasets import Dataset


# ------------------------------------------------------------
# Qwen 2.5 / Qwen 3：原生 chat template 即可
# ------------------------------------------------------------
def format_qwen_sample(sample: dict, tokenizer) -> dict:
    """
    Qwen 2.5 / 3 的 chat template 原生支持 tool_calls + tool role。
    """
    messages = [{"role": "system", "content": sample["system"] or ""}]
    messages.extend(sample["messages"])
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


# ------------------------------------------------------------
# Gemma 2：原生模板不含 tool role，手动展开
# ------------------------------------------------------------
def _gemma_render_message(m: dict) -> str:
    role = m["role"]
    content = m.get("content", "")
    if role == "user":
        return f"<start_of_turn>user\n{content}<end_of_turn>\n"
    if role == "assistant":
        body = content or ""
        # 把 tool_calls 序列化成文本放进 assistant content
        for tc in m.get("tool_calls", []) or []:
            name = tc.get("name") or (tc.get("function") or {}).get("name", "")
            args = tc.get("arguments") or (tc.get("function") or {}).get("arguments", {})
            args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
            body += f"\n<tool_call>{{\"name\": \"{name}\", \"arguments\": {args_str}}}</tool_call>"
        return f"<start_of_turn>model\n{body}<end_of_turn>\n"
    if role == "tool":
        tc_id = m.get("tool_call_id", "")
        return f"<start_of_turn>user\n<tool_response id=\"{tc_id}\">{content}</tool_response><end_of_turn>\n"
    return ""


def format_gemma_sample(sample: dict, tokenizer) -> dict:
    parts = []
    sys = sample.get("system") or ""
    if sys:
        # Gemma 推荐把 system 合进第一个 user 消息
        first_user_idx = next((i for i, m in enumerate(sample["messages"]) if m["role"] == "user"), None)
        if first_user_idx is not None:
            sample = dict(sample)
            sample["messages"] = list(sample["messages"])
            first = dict(sample["messages"][first_user_idx])
            first["content"] = f"{sys}\n\n{first['content']}"
            sample["messages"][first_user_idx] = first
    for m in sample["messages"]:
        parts.append(_gemma_render_message(m))
    text = tokenizer.bos_token + "".join(parts)
    return {"text": text}


# ------------------------------------------------------------
# 分发
# ------------------------------------------------------------
def build_formatter(model_name: str, tokenizer):
    n = model_name.lower()
    if "qwen" in n:
        return lambda s: format_qwen_sample(s, tokenizer)
    if "gemma" in n:
        return lambda s: format_gemma_sample(s, tokenizer)
    # 其他模型尝试通用 chat_template
    def _generic(s):
        return {
            "text": tokenizer.apply_chat_template(
                ([{"role": "system", "content": s["system"]}] if s.get("system") else []) + s["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
        }
    return _generic


# ------------------------------------------------------------
# 入口：从 jsonl 到 Dataset
# ------------------------------------------------------------
def load_and_format(jsonl_path: str, model_name: str, tokenizer_name: str | None = None) -> Dataset:
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name or model_name)
    formatter = build_formatter(model_name, tokenizer)

    def _iter():
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)

    raw = list(_iter())
    ds = Dataset.from_list(raw).map(formatter, remove_columns=[c for c in raw[0].keys() if c != "text"] if raw else None)
    return ds


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--preview", type=int, default=2)
    args = ap.parse_args()
    ds = load_and_format(args.inp, args.model)
    print(f"loaded {len(ds)} samples")
    for i in range(min(args.preview, len(ds))):
        print(f"\n===== sample {i} =====")
        print(ds[i]["text"][:2000])
