"""
预计算教师 logits（用于白盒 KL 蒸馏）。

只存 top-k logits，节省磁盘 95%+。

用法：
    python precompute_teacher_logits.py \
        --teacher Qwen/Qwen2.5-72B-Instruct \
        --data ../../data/datasets/v2/sft_train.jsonl \
        --out ../../data/datasets/v2/sft_train_with_teacher.jsonl \
        --topk 64

输出 schema 加字段：
    {
      ... 原 SFT 样本 ...,
      "teacher_logits": {
        "indices": [[token_id_1, ..., token_id_k], ...],   # [seq_len, k]
        "values":  [[logit_1, ..., logit_k], ...],         # [seq_len, k]
      }
    }

注意：
- 教师必须与学生同 tokenizer！
- topk 推荐 32-128
- 这一步耗时长，跑完一次后训练时反复用
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from tqdm import tqdm


def precompute(
    teacher_model: str,
    data_path: Path,
    out_path: Path,
    topk: int = 64,
    max_len: int = 4096,
    batch_size: int = 1,
    device: str = "cuda",
):
    tokenizer = AutoTokenizer.from_pretrained(teacher_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"loading teacher: {teacher_model}")
    model = AutoModelForCausalLM.from_pretrained(
        teacher_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    # 读样本
    samples = []
    with data_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    print(f"samples: {len(samples)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    f_out = out_path.open("w", encoding="utf-8")

    with torch.no_grad():
        for sample in tqdm(samples, desc="precomputing"):
            messages = []
            if sample.get("system"):
                messages.append({"role": "system", "content": sample["system"]})
            messages.extend(sample["messages"])
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_len).to(device)
            out = model(**enc)
            logits = out.logits[0]  # [seq_len, vocab]
            top_v, top_i = logits.topk(topk, dim=-1)  # [seq_len, k]
            sample["teacher_logits"] = {
                "indices": top_i.cpu().to(torch.int32).tolist(),
                "values": top_v.cpu().to(torch.float16).tolist(),
            }
            f_out.write(json.dumps(sample, ensure_ascii=False) + "\n")
            f_out.flush()

    f_out.close()
    print(f"done → {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topk", type=int, default=64)
    ap.add_argument("--max-len", type=int, default=4096)
    args = ap.parse_args()
    precompute(
        teacher_model=args.teacher,
        data_path=Path(args.data),
        out_path=Path(args.out),
        topk=args.topk,
        max_len=args.max_len,
    )


if __name__ == "__main__":
    main()
