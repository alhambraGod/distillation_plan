"""
白盒 KL 蒸馏训练脚本。

Loss = α · CE(student, label) + β · KL(student || teacher_topk)

教师 logits 必须先用 precompute_teacher_logits.py 预计算好，
存在每条样本的 teacher_logits 字段。

要求：教师和学生同 tokenizer。

用法：
    python train_kd.py --config configs/kd_qwen72b_to_7b.yaml
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F
import yaml
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
)


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_data_with_teacher(path: str) -> Dataset:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return Dataset.from_list(rows)


class KDDataCollator:
    """
    把样本（含 teacher_logits 字段）打包成 batch。

    输出：
      - input_ids, attention_mask, labels（标准 SFT）
      - teacher_topk_indices, teacher_topk_values（白盒蒸馏额外）
    """

    def __init__(self, tokenizer, max_len: int = 4096, response_template: str = None):
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.response_template = response_template

    def __call__(self, batch):
        # 把每条样本转 input_ids
        input_ids_list, label_list = [], []
        teacher_indices, teacher_values = [], []

        for sample in batch:
            messages = []
            if sample.get("system"):
                messages.append({"role": "system", "content": sample["system"]})
            messages.extend(sample["messages"])
            text = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
            enc = self.tokenizer(text, truncation=True, max_length=self.max_len, return_tensors="pt")
            input_ids = enc["input_ids"][0]
            labels = input_ids.clone()

            # mask response_template 之前的 token（只算 assistant 部分 loss）
            if self.response_template:
                tmpl_ids = self.tokenizer.encode(self.response_template, add_special_tokens=False)
                # 简化处理：找第一次出现位置之前都 mask
                for i in range(len(input_ids) - len(tmpl_ids)):
                    if input_ids[i : i + len(tmpl_ids)].tolist() == tmpl_ids:
                        labels[: i + len(tmpl_ids)] = -100
                        break

            input_ids_list.append(input_ids)
            label_list.append(labels)

            # 教师 logits
            t = sample["teacher_logits"]
            t_idx = torch.tensor(t["indices"][: len(input_ids)], dtype=torch.long)
            t_val = torch.tensor(t["values"][: len(input_ids)], dtype=torch.float32)
            teacher_indices.append(t_idx)
            teacher_values.append(t_val)

        # padding
        max_len_b = max(x.size(0) for x in input_ids_list)
        pad_id = self.tokenizer.pad_token_id
        topk = teacher_indices[0].size(-1)

        def _pad(t, max_len, pad_value=0, dim=0):
            if t.size(dim) < max_len:
                shape = list(t.shape)
                shape[dim] = max_len - t.size(dim)
                pad = torch.full(shape, pad_value, dtype=t.dtype)
                return torch.cat([t, pad], dim=dim)
            return t[:max_len]

        input_ids = torch.stack([_pad(x, max_len_b, pad_id) for x in input_ids_list])
        labels = torch.stack([_pad(x, max_len_b, -100) for x in label_list])
        attention_mask = (input_ids != pad_id).long()
        teacher_idx = torch.stack([_pad(x, max_len_b, 0) for x in teacher_indices])
        teacher_val = torch.stack([_pad(x, max_len_b, 0.0) for x in teacher_values])

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
            "teacher_topk_indices": teacher_idx,
            "teacher_topk_values": teacher_val,
        }


class KDTrainer(Trainer):
    """混合 CE + KL loss 的 Trainer。"""

    def __init__(self, *args, kd_alpha: float = 0.5, kd_beta: float = 0.5, kd_temperature: float = 2.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.kd_alpha = kd_alpha
        self.kd_beta = kd_beta
        self.kd_T = kd_temperature

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        teacher_idx = inputs.pop("teacher_topk_indices")
        teacher_val = inputs.pop("teacher_topk_values")
        labels = inputs["labels"]

        outputs = model(**{k: v for k, v in inputs.items() if k != "labels"}, labels=labels)
        ce_loss = outputs.loss
        student_logits = outputs.logits  # [B, L, V]

        # 取出对应教师 topk 位置的学生 logits
        # student_topk[b, l, k] = student_logits[b, l, teacher_idx[b, l, k]]
        student_topk = torch.gather(student_logits, dim=-1, index=teacher_idx)

        # 计算 KL，注意 mask 掉 -100 位置
        T = self.kd_T
        student_log_p = F.log_softmax(student_topk / T, dim=-1)
        teacher_p = F.softmax(teacher_val / T, dim=-1)
        kl = F.kl_div(student_log_p, teacher_p, reduction="none").sum(-1)  # [B, L]

        loss_mask = (labels != -100).float()
        kl_loss = (kl * loss_mask).sum() / loss_mask.sum().clamp(min=1.0)
        kl_loss = kl_loss * (T * T)  # standard KD scaling

        loss = self.kd_alpha * ce_loss + self.kd_beta * kl_loss
        if return_outputs:
            return loss, outputs
        return loss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(cfg["student_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = None
    if cfg.get("qlora", False):
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        cfg["student_model"],
        quantization_config=bnb,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.config.use_cache = False

    lora = LoraConfig(
        r=cfg["lora"]["r"],
        lora_alpha=cfg["lora"]["alpha"],
        lora_dropout=cfg["lora"].get("dropout", 0.05),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=cfg["lora"].get("target_modules", "all-linear"),
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    train_ds = load_data_with_teacher(cfg["train_file"])
    eval_ds = load_data_with_teacher(cfg["eval_file"]) if cfg.get("eval_file") else None

    response_template = cfg.get("response_template")  # 例如 "<|im_start|>assistant"
    collator = KDDataCollator(tokenizer, max_len=cfg["train"].get("max_seq_length", 4096), response_template=response_template)

    targs = TrainingArguments(
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
        report_to=cfg.get("report_to", "wandb"),
        run_name=cfg.get("run_name", "kd_run"),
        save_total_limit=3,
        seed=cfg.get("seed", 42),
        remove_unused_columns=False,
    )

    trainer = KDTrainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        tokenizer=tokenizer,
        kd_alpha=cfg["kd"]["alpha"],
        kd_beta=cfg["kd"]["beta"],
        kd_temperature=cfg["kd"].get("temperature", 2.0),
    )

    trainer.train(resume_from_checkpoint=cfg.get("resume_from_checkpoint"))
    trainer.save_model(str(out_dir / "final"))
    tokenizer.save_pretrained(str(out_dir / "final"))
    print(f"saved to {out_dir / 'final'}")


if __name__ == "__main__":
    main()
