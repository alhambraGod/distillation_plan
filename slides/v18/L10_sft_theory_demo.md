---
marp: true
theme: default
paginate: true
header: 'L10 · SFT 原理 + Demo'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #C2410C; border-bottom: 4px solid #C2410C; padding-bottom: 8px; }
  h2 { color: #EA580C; }
  section.cover { background: linear-gradient(135deg, #C2410C 0%, #EA580C 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #C2410C; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #C2410C; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L10 · SFT 原理 + Demo

## 从 chat template 到 LoRA 训练

<br>

📅 **第 10 课 · 60 分钟**
📚 教材：`sft_guide.md` + `format.py` + `train.py`

---

## 🎯 本课目标

- 理解 SFT loss mask 的核心
- 掌握 chat template（Qwen 与 Gemma 差异）
- 读懂 `train.py` 每一行
- **动手**：5 分钟跑通小 demo

---

## 📖 SFT loss 怎么算

```
一条样本：
  <user> 你好
  <assistant> 您好，有什么可以帮您？<tool_call>...</tool_call>
  <tool> 结果...
  <assistant> 基于结果，...
```

**Loss 只在 assistant 部分算**（user/tool mask 掉）：

```
loss = -∑ log P(y_t | y_<t)  其中 y_t ∈ assistant 部分
```

<br>

<div class="highlight">
⚠️ 漏掉 loss mask = 训练把 user 输入也背下来 = 退化
</div>

---

## 🔑 Chat Template 必须正确

Qwen 2.5:
```
<|im_start|>system\n...<|im_end|>
<|im_start|>user\n...<|im_end|>
<|im_start|>assistant\n...<|im_end|>
```

Gemma 2（不支持 tool role）:
```
<start_of_turn>user\n...<end_of_turn>
<start_of_turn>model\n...<end_of_turn>
```

<br>

**工具调用**：Qwen 原生支持，Gemma 要手动展开 `<tool_call>` 标签

---

## 🎯 DataCollatorForCompletionOnlyLM

```python
from trl import DataCollatorForCompletionOnlyLM

collator = DataCollatorForCompletionOnlyLM(
    response_template="<|im_start|>assistant",  # Qwen
    tokenizer=tokenizer,
)
```

它做什么：
- 找 `response_template` 第一次出现位置
- 之前的 label 设为 -100（mask 掉）
- 之后的保留原 token id

<br>

<div class="highlight">
response_template 错了 → loss 不降或降得诡异
</div>

---

## ⚙️ LoRA + QLoRA 起步配置

```yaml
model: Qwen/Qwen2.5-7B-Instruct
qlora: true

lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules: all-linear

train:
  epochs: 3
  batch_size: 4
  grad_accum: 4        # 等效 batch 16
  lr: 2.0e-4
  warmup_ratio: 0.03
  scheduler: cosine
  max_seq_length: 4096
```

---

## 📝 `train.py` 核心流程

```python
# 1. tokenizer + model
tokenizer = AutoTokenizer.from_pretrained(cfg["model"])
model = AutoModelForCausalLM.from_pretrained(
    cfg["model"],
    quantization_config=bnb,   # QLoRA
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

# 2. LoRA config
lora = LoraConfig(r=16, alpha=32, target_modules="all-linear")

# 3. 数据
train_ds = load_and_format(cfg["train_file"], cfg["model"])

# 4. Trainer
trainer = SFTTrainer(model, args, train_ds,
                    peft_config=lora, data_collator=collator)
trainer.train()
```

---

## 🧪 Sanity Check 必做

**训练前先验证**：

```python
# 看 collator 输出的 labels 是不是只在 assistant 部分非 -100
batch = collator([tokenizer(sample["text"]) for sample in train_ds[:2]])
labels = batch["labels"]
valid_positions = (labels != -100).sum()
print(f"valid tokens for loss: {valid_positions}")
# 应该 > 0，如果是 0 或特别小，template 对不上
```

<br>

<div class="highlight">
先 100 条跑 10 step 看曲线，再上全量
</div>

---

## 📊 Loss 曲线正常长什么样

```
loss
 2.0 ┤●
 1.5 ┤ ●
 1.2 ┤  ●●
 1.0 ┤    ●●●
 0.9 ┤       ●●●●●●
 0.8 ┤              ●●●●●●●●
     └──────────────────────────── step
```

**理想**：前期快速降，后期平稳。

---

## ❌ Loss 曲线**异常**

| 曲线 | 问题 |
|---|---|
| 一直在 3.0 左右 | response_template 不对 |
| 急降到 0.1 以下 | 过拟合，eval 会崩 |
| 剧烈震荡 | lr 太大 |
| 先降后升 | lr schedule 不对 |
| NaN | fp16 精度问题，换 bf16 |

---

## 🎬 实操 Demo（15 分钟）

```bash
# 5 分钟跑 Gemma 2B LoRA
python 03_sft/train.py \
  --config 03_sft/configs/demo_small.yaml
# （配置里：2B 模型 + 100 条数据 + 1 epoch）
```

观察：
- W&B loss 曲线
- GPU 显存占用
- 训完后 inference 效果

---

## 💡 加载 Adapter 推理

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    torch_dtype="bfloat16",
    device_map="auto",
)
model = PeftModel.from_pretrained(base, "adapters/v2_sft_v1/final")
tokenizer = AutoTokenizer.from_pretrained("adapters/v2_sft_v1/final")

out = model.generate(...)
```

---

## 🏠 课后作业

1. 读完 `sft_guide.md`
2. 修改 `sft_v2_base.yaml`，用自己准备的 100 条数据训 1 epoch
3. 看 W&B loss 曲线，判断是否正常

<br>

**下节课**：L11 SFT 调优 + 常见坑

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: LoRA r 怎么选？→ A: 16 默认，简单任务 8，复杂任务 32
- Q: 全参微调 vs LoRA？→ A: 99% 情况 LoRA 够，全参只在迁移学习大改时用
- Q: BF16 vs FP16？→ A: A100 / 3090+ 用 BF16
