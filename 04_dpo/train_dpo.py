"""
DPO 训练脚本。

关键：
1. lr 比 SFT 小 100-1000 倍
2. reference model 必须 freeze（DPOTrainer 自动处理）
3. 在 SFT 后的 adapter 基础上继续训

运行：
    python train_dpo.py --config configs/dpo_v2.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig, PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import DPOConfig, DPOTrainer


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_preferences(jsonl_path: str) -> Dataset:
    records = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            records.append({
                "prompt": d["prompt"],
                "chosen": d["chosen"],
                "rejected": d["rejected"],
            })
    return Dataset.from_list(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    print(f"config: {cfg}")

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4bit 量化（DPO 比 SFT 更吃显存：2 个模型 + 激活）
    bnb = None
    if cfg.get("qlora", True):
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    # 基座 + SFT adapter
    base = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"],
        quantization_config=bnb,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    # 加载 SFT adapter 作为起点
    model = PeftModel.from_pretrained(base, cfg["sft_adapter"], is_trainable=True)
    model.config.use_cache = False
    print(f"loaded SFT adapter: {cfg['sft_adapter']}")

    # DPO 加新 LoRA adapter 训练（或继续训已有 adapter）
    lora = LoraConfig(
        r=cfg["lora"]["r"],
        lora_alpha=cfg["lora"]["alpha"],
        lora_dropout=cfg["lora"].get("dropout", 0.05),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=cfg["lora"].get("target_modules", "all-linear"),
    )

    # 数据
    train_ds = load_preferences(cfg["train_file"])
    eval_ds = load_preferences(cfg["eval_file"]) if cfg.get("eval_file") else None
    print(f"train pairs: {len(train_ds)}")

    # DPO config
    dpo_args = DPOConfig(
        output_dir=str(out_dir),
        beta=cfg["dpo"]["beta"],
        num_train_epochs=cfg["train"]["epochs"],
        per_device_train_batch_size=cfg["train"]["batch_size"],
        per_device_eval_batch_size=cfg["train"].get("eval_batch_size", cfg["train"]["batch_size"]),
        gradient_accumulation_steps=cfg["train"]["grad_accum"],
        learning_rate=cfg["train"]["lr"],
        warmup_ratio=cfg["train"].get("warmup_ratio", 0.05),
        lr_scheduler_type=cfg["train"].get("scheduler", "cosine"),
        logging_steps=cfg["train"].get("logging_steps", 10),
        save_steps=cfg["train"].get("save_steps", 100),
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=cfg["train"].get("eval_steps", 100) if eval_ds else None,
        bf16=True,
        gradient_checkpointing=True,
        max_length=cfg["train"].get("max_length", 4096),
        max_prompt_length=cfg["train"].get("max_prompt_length", 2048),
        report_to=cfg.get("report_to", "wandb"),
        run_name=cfg.get("run_name", "dpo_run"),
        seed=cfg.get("seed", 42),
        # DPO 专属：生成 reference logps 后 freeze
        remove_unused_columns=False,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,  # None 时会自动用 peft adapter disabled 状态作 ref（省显存）
        args=dpo_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        peft_config=lora,
    )

    trainer.train(resume_from_checkpoint=cfg.get("resume_from_checkpoint"))
    trainer.save_model(str(out_dir / "final"))
    tokenizer.save_pretrained(str(out_dir / "final"))
    print(f"saved to {out_dir / 'final'}")


if __name__ == "__main__":
    main()
