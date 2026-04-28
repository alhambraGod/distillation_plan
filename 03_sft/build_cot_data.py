"""
CoT 合成数据生成。让教师对每条 case 产出"<think>...</think>final_answer"，加入训练集。

用法：
    python build_cot_data.py \
        --teacher Qwen/Qwen2.5-72B-Instruct \
        --in ../../data/datasets/v2/sft_train.jsonl \
        --out ../../data/datasets/v2/sft_train_cot.jsonl \
        --filter complex   # 只对复杂 case 加 CoT
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tqdm import tqdm


COT_PROMPT_TEMPLATE = """请先在 <think> 标签内详细推理，再给出最终答案。

任务：
{user_prompt}

要求：
1. <think> 标签内列出推理步骤（识别意图、拆解任务、选择工具、参数推导、风险评估）
2. </think> 后给出最终答案 / 工具调用
"""


def is_complex(sample: dict) -> bool:
    """判定是否为复杂 case：多工具调用、长 prompt、长 horizon。"""
    n_tool_calls = sum(
        len(m.get("tool_calls") or []) for m in sample["messages"] if m.get("role") == "assistant"
    )
    n_messages = len(sample["messages"])
    return n_tool_calls >= 2 or n_messages >= 6


def get_user_prompt(sample: dict) -> str:
    return next((m.get("content", "") for m in sample["messages"] if m.get("role") == "user"), "")


def get_final_answer(sample: dict) -> str:
    """提取最后一条 assistant 消息（含 tool_calls 序列化）"""
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


def call_teacher_local(prompt: str, model, tokenizer, max_new_tokens: int = 1024) -> str:
    """本地大模型调用。"""
    import torch
    enc = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        return_tensors="pt", add_generation_prompt=True,
    ).to(model.device)
    with torch.no_grad():
        out = model.generate(enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=0.0)
    text = tokenizer.decode(out[0][enc.shape[1]:], skip_special_tokens=True)
    return text


def call_teacher_api(prompt: str, client, model_name: str) -> str:
    """OpenAI 兼容 API 调用（DeepSeek / Qwen API / vLLM）。"""
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.0,
    )
    return resp.choices[0].message.content


def make_cot_sample(orig_sample: dict, cot_text: str) -> dict:
    """把 CoT 包进新的 assistant 输出。"""
    new_sample = json.loads(json.dumps(orig_sample))  # deep copy
    user_msg = next((m for m in new_sample["messages"] if m.get("role") == "user"), None)
    if user_msg is None:
        return None
    final = get_final_answer(orig_sample)
    new_sample["messages"] = [
        user_msg,
        {"role": "assistant", "content": f"<think>\n{cot_text}\n</think>\n\n{final}"},
    ]
    new_sample["sample_id"] = orig_sample["sample_id"] + "_cot"
    new_sample["metadata"] = dict(orig_sample.get("metadata", {}))
    new_sample["metadata"]["augmented"] = "cot"
    return new_sample


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True, help="HF model name or API model name")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--filter", default="complex", choices=["all", "complex"])
    ap.add_argument("--mode", default="local", choices=["local", "api"])
    ap.add_argument("--api-base", default=None)
    args = ap.parse_args()

    samples = []
    with open(args.inp, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    print(f"input: {len(samples)} samples")

    if args.filter == "complex":
        samples = [s for s in samples if is_complex(s)]
        print(f"after complex filter: {len(samples)}")

    if args.mode == "local":
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        tokenizer = AutoTokenizer.from_pretrained(args.teacher, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.teacher, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
        )
        caller = lambda p: call_teacher_local(p, model, tokenizer)
    else:
        from openai import OpenAI
        client = OpenAI(base_url=args.api_base, api_key="EMPTY")
        caller = lambda p: call_teacher_api(p, client, args.teacher)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_out = 0
    with out_path.open("w", encoding="utf-8") as f_out:
        for sample in tqdm(samples):
            user_prompt = get_user_prompt(sample)
            if not user_prompt:
                continue
            cot_input = COT_PROMPT_TEMPLATE.format(user_prompt=user_prompt)
            try:
                resp = caller(cot_input)
                # 抽 <think> 内容
                if "<think>" in resp and "</think>" in resp:
                    cot = resp.split("<think>", 1)[1].split("</think>", 1)[0].strip()
                else:
                    cot = resp.strip()  # 教师没按格式来，整段当推理
                cot_sample = make_cot_sample(sample, cot)
                if cot_sample:
                    f_out.write(json.dumps(cot_sample, ensure_ascii=False) + "\n")
                    f_out.flush()
                    n_out += 1
            except Exception as e:
                print(f"failed: {e}")
                continue
    print(f"written {n_out} CoT samples → {out_path}")


if __name__ == "__main__":
    main()
