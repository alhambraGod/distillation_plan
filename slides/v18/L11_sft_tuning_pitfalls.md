---
marp: true
theme: default
paginate: true
header: 'L11 · SFT 调优 + 常见坑'
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

# L11 · SFT 调优 + 坑

## 9 种常见症状 + 灾难性遗忘防护

<br>

📅 **第 11 课 · 60 分钟**
📚 教材：`sft_guide.md` + `troubleshooting.md`

---

## 🎯 本课目标

- 掌握单变量实验原则
- 熟悉 9 种常见症状和解法
- 理解 **灾难性遗忘** 和配比实验
- **动手**：小数据集训一次，分析 loss

---

## 🧪 单变量实验原则

<div class="big">
一次只改一个变量
</div>

<br>

❌ 错：一次改 lr + epoch + r + 数据量，结果好了 → 不知道谁的功劳

✅ 对：每次一个变量，带版本号保存

```
v1: baseline
v2: 只改 lr = 1e-4
v3: 只改 epoch = 5
v4: 只改 LoRA r = 32
```

---

## 📋 超参扫描顺序建议

| 优先级 | 超参 | 常用范围 |
|---|---|---|
| 1 | lr | 1e-4 / 2e-4 / 5e-4 |
| 2 | epochs | 1 / 3 / 5 |
| 3 | LoRA r | 8 / 16 / 32 |
| 4 | target_modules | all-linear / attention |
| 5 | 数据配比 | 80/20, 70/30, 50/50 |

**每次跑 2-3 epoch 快试**，不到效果就 early stop。

---

## 🔍 9 种常见症状（上）

| 症状 | 原因 | 解法 |
|---|---|---|
| 1. Loss 不降 (卡 ~0) | response_template 不对 | 看 collator mask 位置 |
| 2. Loss 降太快 (<0.3) | 过拟合 | 减 epoch / 加 dropout |
| 3. OOM | 显存不够 | QLoRA + grad_checkpoint + 减 batch |
| 4. tool_call JSON 崩 | 数据格式不统一 | 清洗脚本重跑 + 约束解码 |

---

## 🔍 9 种常见症状（下）

| 症状 | 原因 | 解法 |
|---|---|---|
| 5. 通用能力崩 | **灾难性遗忘** | 混 20-30% 通用数据 |
| 6. 模型重复输出 | eos 没学对 / 数据重复模式 | rep_penalty / 去重 |
| 7. 训练很慢 | gradient_checkpoint + 无 flash-attn | 换 Unsloth / 开 flash-attn 2 |
| 8. Adapter 加载不了 | 版本不匹配 | `pip list` 对版本 |
| 9. W&B 没显示 | API key 或 report_to 错 | `wandb login` |

---

## 🧟 灾难性遗忘（最坑的一个）

**现象**：业务任务训好了，让它写诗 / 数学 / 通用对话全废了。

```
训练前：MMLU 70%
训练后：MMLU 45%  ← 退化 25 分！
```

<br>

<div class="highlight">
本项目会有这个问题，如果只用业务数据训
</div>

---

## 💊 配比实验（解决灾难性遗忘）

在正式训练前跑 5 组小实验：

| 实验 | 业务 : 通用 | 观察 |
|---|---|---|
| A | 100% : 0% | 极端，看是否遗忘 |
| B | 90% : 10% | |
| C | 70% : 30% | **推荐起点** |
| D | 50% : 50% | 保守 |
| E | 0% : 100% | 对照 |

**每组跑 1 epoch**，看业务 + 通用两个 benchmark。

---

## 📊 配比实验结果（假设）

| 实验 | 业务成功率 | MMLU | 结论 |
|---|---|---|---|
| A (100:0) | 88% | 48% ❌ | 遗忘严重 |
| B (90:10) | 85% | 58% ⚠️ | 有改善 |
| C (70:30) | 82% | 68% ✅ | **平衡** |
| D (50:50) | 75% | 72% | 业务退步 |

**选 C**：业务稍降但通用能力保住。

---

## 🎯 通用指令数据选什么

| 数据集 | 规模 | 用途 |
|---|---|---|
| `HuggingFaceH4/ultrachat_200k` | 200k | 通用对话 |
| `argilla/ultrafeedback` | 60k | 偏好对（取 chosen） |
| `silk-road/alpaca-data-gpt4-chinese` | 52k | 中文指令 |
| `BelleGroup/train_1M_CN` | 1M | 中文大量 |

<br>

**混入比例**：20-30%，随机打散到 train set。

---

## 🧰 避免过拟合的三招

```yaml
# 1. 加 dropout
lora:
  dropout: 0.1   # 默认 0.05 太小

# 2. Early stopping
train:
  load_best_model_at_end: true
  metric_for_best_model: eval_loss
  early_stopping_patience: 3

# 3. 减 epoch
train:
  epochs: 1-2    # 而不是 5
```

---

## 💾 版本化 adapter

```
adapters/
├── v2_sft_v1/                 # 起步
├── v2_sft_v2_lr1e-4/          # 实验：lr
├── v2_sft_v3_epoch5/          # 实验：epoch
├── v2_sft_v4_r32/             # 实验：r
├── v2_sft_v5_mix7030/         # 实验：配比
├── v2_sft_best -> v2_sft_v5/  # 软链接
```

<br>

配合 W&B run name + config 文件 git 版本化。

---

## 🏋️ 实操（20 分钟）

```bash
# 小数据 1 epoch 快速跑
python 03_sft/train.py \
  --config configs/sft_v2_demo.yaml
  # (100 条数据, 1 epoch, LoRA r=8)

# 训完后 benchmark
python -m benchmark.harness.runner \
  --cases data/pilot_100.jsonl \
  --model local-qwen-with-adapter \
  --out-dir reports/sft_demo/
```

分析：
- Loss 曲线正常吗？
- 基线 vs 训后：提升多少？

---

## 🏠 课后作业

1. 读完 `troubleshooting.md`
2. 用真实数据跑 SFT 一版，选 1 个超参做扫描（比如 lr）
3. 写 150 字：这一版的优化理由

<br>

**下节课**：L12 DPO

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Unsloth 真的快 2x 吗？→ A: 是，但有些特性不支持，先 demo
- Q: gradient_checkpointing 开还是关？→ A: 显存够就关（慢 30%）
- Q: 我怎么知道 overfit 了？→ A: train_loss 降但 eval_loss 升
