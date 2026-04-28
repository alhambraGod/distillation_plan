"""
GRPO (Group Relative Policy Optimization) - POC 起步脚本

用途：验证 RL 能否在工具参数调用场景带来额外收益（超过 SFT）

前置：
- 已有 SFT 后的 adapter（不要从基座直接跑 RL）
- 已定义 reward 函数
- 已准备 prompt 池

本脚本是**最简骨架**，用于教学/POC，不是生产级实现。
生产级推荐用 TRL GRPOTrainer 或 OpenRLHF。

用法：
    python train_rl_grpo.py --config configs/grpo_tool_params.yaml

参考：
- DeepSeek R1 论文
- TRL GRPOTrainer docs
- open-r1 项目
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Callable

import torch
import torch.nn.functional as F
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


# ============================================================
# Reward 函数示例（可验证奖励 - POC 1）
# ============================================================

def reward_tool_call_exact(output: str, expected_tool_call: dict) -> float:
    """
    工具调用参数正确性 reward.

    设计：
    - 解析不出 tool_call → 0
    - name 错 → 0
    - name 对但 args 错 → 0.3
    - name + args 的 key 都对 → 0.7
    - name + args 的 key + value 都对 → 1.0
    """
    # 找 <tool_call>{...}</tool_call> 模式
    m = re.search(r"<tool_call>(.+?)</tool_call>", output, re.DOTALL)
    if not m:
        return 0.0
    try:
        tc = json.loads(m.group(1).strip())
    except Exception:
        return 0.0
    if tc.get("name") != expected_tool_call["name"]:
        return 0.0
    actual_args = tc.get("arguments", {}) or {}
    expected_args = expected_tool_call.get("arguments", {}) or {}
    if not isinstance(actual_args, dict):
        return 0.3
    actual_keys = set(actual_args.keys())
    expected_keys = set(expected_args.keys())
    if actual_keys != expected_keys:
        return 0.3
    # 比对 value
    n_match = sum(actual_args.get(k) == expected_args.get(k) for k in expected_keys)
    if n_match == len(expected_keys):
        return 1.0
    return 0.7 * (n_match / max(len(expected_keys), 1)) + 0.3


def reward_json_valid(output: str, expected) -> float:
    """JSON 合法性 reward."""
    try:
        json.loads(output)
        return 1.0
    except Exception:
        return 0.0


def build_reward_fn(name: str) -> Callable:
    mapping = {
        "tool_call_exact": reward_tool_call_exact,
        "json_valid": reward_json_valid,
    }
    if name not in mapping:
        raise ValueError(f"unknown reward: {name}")
    return mapping[name]


# ============================================================
# GRPO 训练最简实现（教学用）
# ============================================================

def sample_k_generations(model, tokenizer, prompt: str, k: int, max_new: int, temperature: float = 1.0):
    """同一 prompt 采 k 个输出"""
    outputs = []
    enc = tokenizer(prompt, return_tensors="pt").to(model.device)
    for _ in range(k):
        with torch.no_grad():
            out = model.generate(
                **enc,
                max_new_tokens=max_new,
                do_sample=True,
                temperature=temperature,
                top_p=0.95,
            )
        text = tokenizer.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        outputs.append((text, out[0]))
    return outputs


def compute_grpo_loss(
    model,
    ref_model,
    tokenizer,
    prompt: str,
    expected,
    reward_fn,
    k: int = 8,
    kl_coef: float = 0.04,
    max_new: int = 256,
):
    """
    最简 GRPO loss 计算（单 prompt 版本）。

    步骤：
    1. 采 K 个输出
    2. 计算每个 reward
    3. 归一化得 advantage
    4. 对每个输出，计算 logprob diff vs ref
    5. loss = -advantage * logprob + kl_coef * KL(policy || ref)
    """
    samples = sample_k_generations(model, tokenizer, prompt, k, max_new)
    texts = [s[0] for s in samples]
    seqs = [s[1] for s in samples]
    rewards = torch.tensor([reward_fn(t, expected) for t in texts], device=model.device)

    # group-relative advantage
    if rewards.std() > 1e-6:
        adv = (rewards - rewards.mean()) / (rewards.std() + 1e-6)
    else:
        adv = rewards - rewards.mean()

    total_loss = 0.0
    for seq, a in zip(seqs, adv):
        # policy logprob
        inputs = seq.unsqueeze(0)
        with torch.no_grad():
            ref_logits = ref_model(inputs).logits
        policy_logits = model(inputs).logits

        # 只算生成部分的 loss
        prompt_len = tokenizer(prompt, return_tensors="pt")["input_ids"].shape[1]
        gen_logits_p = policy_logits[:, prompt_len - 1 : -1, :]
        gen_logits_r = ref_logits[:, prompt_len - 1 : -1, :]
        gen_labels = inputs[:, prompt_len:]

        log_p_policy = F.log_softmax(gen_logits_p, dim=-1).gather(-1, gen_labels.unsqueeze(-1)).squeeze(-1)
        log_p_ref = F.log_softmax(gen_logits_r, dim=-1).gather(-1, gen_labels.unsqueeze(-1)).squeeze(-1)

        ratio = (log_p_policy - log_p_ref).exp()
        pg_loss = -a * ratio.mean()
        kl = (log_p_policy - log_p_ref).mean()

        total_loss = total_loss + pg_loss + kl_coef * kl

    return total_loss / k, rewards.mean().item(), rewards.std().item()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))

    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"], torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    # 从 SFT adapter 起步
    model = PeftModel.from_pretrained(base, cfg["sft_adapter"], is_trainable=True)

    # ref 用 SFT adapter 的冻结版本（disabled 时自动就是 ref）
    ref_model = PeftModel.from_pretrained(
        AutoModelForCausalLM.from_pretrained(
            cfg["base_model"], torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
        ),
        cfg["sft_adapter"],
    )
    ref_model.eval()
    for p in ref_model.parameters():
        p.requires_grad_(False)

    reward_fn = build_reward_fn(cfg["reward"]["fn"])

    # 读数据：每条 {prompt, expected}
    data = [json.loads(l) for l in open(cfg["train_file"]) if l.strip()]
    print(f"samples: {len(data)}")

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg["train"]["lr"])

    for step, sample in enumerate(data[: cfg["train"]["max_steps"]]):
        optimizer.zero_grad()
        loss, r_mean, r_std = compute_grpo_loss(
            model, ref_model, tokenizer,
            prompt=sample["prompt"],
            expected=sample["expected"],
            reward_fn=reward_fn,
            k=cfg["grpo"]["num_generations"],
            kl_coef=cfg["grpo"]["kl_coef"],
            max_new=cfg["grpo"]["max_new_tokens"],
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        optimizer.step()

        if step % 10 == 0:
            print(f"step {step} loss={loss.item():.4f} reward_mean={r_mean:.3f} reward_std={r_std:.3f}")

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir / "final"))
    print(f"saved → {out_dir / 'final'}")


if __name__ == "__main__":
    main()
