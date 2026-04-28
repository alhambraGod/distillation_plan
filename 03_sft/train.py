"""
SFT 训练脚本。使用 HuggingFace TRL 的 SFTTrainer + LoRA。

运行：
    python train.py --config configs/sft_v2_base.yaml
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import DataCollatorForCompletionOnlyLM, SFTConfig, SFTTrainer

from format import load_and_format


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_bnb_config(use_qlora: bool):
    if not use_qlora:
        return None
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )


def build_response_template(model_name: str, tokenizer) -> list[int] | str:
    """
    给 DataCollatorForCompletionOnlyLM 用的 response template。
    只在 assistant 部分算 loss。
    """
    n = model_name.lower()
    if "qwen" in n:
        return "<|im_start|>assistant"
    if "gemma" in n:
        return "<start_of_turn>model"
    # fallback: 用 tokenizer 自带
    return tokenizer.decode(tokenizer.encode("", add_special_tokens=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    print(f"config: {cfg}")

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------- tokenizer ----------
    tokenizer = AutoTokenizer.from_pretrained(cfg["model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ---------- model ----------
    bnb = build_bnb_config(cfg.get("qlora", False))
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model"],
        quantization_config=bnb,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation=cfg.get("attn_implementation", "sdpa"),
    )
    model.config.use_cache = False

    # ---------- LoRA ----------
    lora = LoraConfig(
        r=cfg["lora"]["r"],
        lora_alpha=cfg["lora"]["alpha"],
        lora_dropout=cfg["lora"].get("dropout", 0.05),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=cfg["lora"].get("target_modules", "all-linear"),
    )

    # ---------- data ----------
    train_ds = load_and_format(cfg["train_file"], cfg["model"])
    eval_ds = load_and_format(cfg["eval_file"], cfg["model"]) if cfg.get("eval_file") else None

    # 可选：混入通用数据
    if cfg.get("general_data_file"):
        general = load_and_format(cfg["general_data_file"], cfg["model"])
        ratio = cfg.get("general_ratio", 0.2)
        n_general = int(len(train_ds) * ratio)
        general = general.shuffle(seed=42).select(range(min(n_general, len(general))))
        train_ds = Dataset.from_dict({
            "text": list(train_ds["text"]) + list(general["text"])
        }).shuffle(seed=42)
        print(f"mixed with general data: total {len(train_ds)}")

    # ---------- collator ----------
    resp_template = build_response_template(cfg["model"], tokenizer)
    collator = DataCollatorForCompletionOnlyLM(
        response_template=resp_template,
        tokenizer=tokenizer,
    )

    # ---------- trainer ----------
    sft_args = SFTConfig(
        output_dir=str(out_dir),
        num_train_epochs=cfg["train"]["epochs"],
        per_device_train_batch_size=cfg["train"]["batch_size"],
        per_device_eval_batch_size=cfg["train"].get("eval_batch_size", cfg["train"]["batch_size"]),
        gradient_accumulation_steps=cfg["train"]["grad_accum"],
        learning_rate=cfg["train"]["lr"],
        warmup_ratio=cfg["train"].get("warmup_ratio", 0.03),
        lr_scheduler_type=cfg["train"].get("scheduler", "cosine"),
        logging_steps=cfg["train"].get("logging_steps", 10),
        save_steps=cfg["train"].get("save_steps", 200),
        eval_strategy="steps" if eval_ds else "no",
        eval_steps=cfg["train"].get("eval_steps", 200) if eval_ds else None,
        bf16=True,
        gradient_checkpointing=True,
        max_seq_length=cfg["train"].get("max_seq_length", 4096),
        packing=False,  # 和 completion-only collator 不兼容
        report_to=cfg.get("report_to", "wandb"),
        run_name=cfg.get("run_name", "sft_run"),
        save_total_limit=3,
        seed=cfg.get("seed", 42),
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        peft_config=lora,
        data_collator=collator,
        tokenizer=tokenizer,
    )

    trainer.train(resume_from_checkpoint=cfg.get("resume_from_checkpoint"))
    trainer.save_model(str(out_dir / "final"))
    tokenizer.save_pretrained(str(out_dir / "final"))
    print(f"saved to {out_dir / 'final'}")


if __name__ == "__main__":
    main()
