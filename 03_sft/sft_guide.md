# SFT 完整指南

> 读本文档前先读：
> - `00_overview/concepts_and_techniques.md` §1.3 和 §2.2（为什么 SFT）
> - `00_overview/base_model_selection.md`（学生基座选哪个）
> - `00_overview/teacher_model_comparison.md`（教师模型选哪个，10 款对比）
> - `distillation_techniques.md`（**SFT 是 7 种蒸馏技术之一**，了解全景）
> - `00_overview/learning_resources.md` §4（SFT 学习资源）

## 0. 本文档定位

SFT 是蒸馏的一种实现（黑盒输出蒸馏）。本指南聚焦**怎么做 SFT**。

如果你需要：
- **白盒 KL 蒸馏**（同家族教师 + 学生）→ 看 `train_kd.py` + `configs/kd_qwen72b_to_7b.yaml`
- **CoT 合成蒸馏** → 看 `build_cot_data.py`
- **黑盒 Claude trace SFT** → `configs/blackbox_claude_to_qwen7b.yaml`（这是当前主线）

## 1. 什么时候进 SFT

前置条件（DP1 通过）：
- [ ] 阶段 1 基线报告出炉
- [ ] 小模型 benchmark 显示"**能做但不稳**"（40-80% 成功率）
- [ ] 主要问题不是"基座根本不够格"，而是格式/流程/偏好

## 2. SFT 流程总览

```
数据准备 → 格式化 → 训练 → 评估 → 迭代
  │          │        │        │       │
  ▼          ▼        ▼        ▼       ▼
 jsonl    apply_    SFTTrainer benchmark 超参扫描
          chat_      + LoRA     对比基线
          template
```

## 3. 数据准备

### 3.1 输入输出格式

来自阶段 1 的 `v2_sft_train.jsonl`（每行一条样本）。核心字段：
```json
{
  "sample_id": "...",
  "task_type": "marketing_ai_v2",
  "system": "...",
  "skills_loaded": [...],
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

### 3.2 格式化成训练字符串

用 tokenizer 的 chat template。**关键**：不同基座模板不同！
- Qwen 2.5：原生支持 `tool` 角色
- Gemma 2：原生不支持 tool，需要自定义模板（见 `format.py`）

### 3.3 Loss mask

**只在 assistant 部分算 loss**，user/tool 部分 mask 掉：
```python
from trl import DataCollatorForCompletionOnlyLM
collator = DataCollatorForCompletionOnlyLM(
    response_template="<|im_start|>assistant",  # Qwen
    tokenizer=tokenizer,
)
```

这一步漏了，训练会让模型连 user 输入都一起"学"，浪费容量、容易退化。

### 3.4 数据配比建议

- **业务数据**：60-70%（从 SFT 集来）
- **通用指令数据**：20-30%（防灾难性遗忘，从开源 SFT 集抽）
- **工具调用合成数据**：5-10%（强化 JSON schema 习惯）

推荐通用数据集：
- `HuggingFaceH4/ultrachat_200k`
- `argilla/ultrafeedback-binarized-preferences-cleaned`（取 chosen 当 SFT）
- 中文：`silk-road/alpaca-data-gpt4-chinese`

## 4. 训练

### 4.1 推荐起步配置

- 基座：Qwen 2.5 7B Instruct（首推）或 Gemma 2 9B Instruct
- 方式：QLoRA 4bit
- LoRA r=16, alpha=32, target all-linear
- Epoch 3, batch 4 × grad_accum 4（eff batch 16）
- Lr 2e-4, warmup 3%, cosine
- Seq len 4096

详见 `configs/sft_v2_base.yaml`。

### 4.2 硬件建议

| 模型 | 方式 | 最低 GPU |
|---|---|---|
| 2B LoRA | fp16 | 1x 3090 24GB |
| 7B LoRA | fp16 | 1x A100 40GB |
| 7B QLoRA | 4bit | 1x 3090 24GB |
| 9B QLoRA | 4bit | 1x A100 40GB（稳）或 3090 24GB（紧） |
| 9B LoRA | fp16 | 1x A100 80GB |

参考 `07_budget/compute_estimate.md` 成本估算。

### 4.3 跑训练

```bash
python training/sft/train.py --config configs/sft_v2_base.yaml
```

训练期间重点看：
- loss 稳定下降（不应该锯齿剧烈或反弹）
- eval loss 不发散（防过拟合）
- lr schedule 符合预期
- grad norm 不爆炸

**出问题立即停**——不要跑完 5 epoch 再看。

### 4.4 实验追踪

配 W&B 后自动记录超参、loss、eval。每次训练：
1. 起一个 run name：`v2_sft_YYYYMMDD_{lr}_{r}_{epoch}`
2. 存 config 文件
3. tag 数据集版本

## 5. 评估

训完必做：
1. 用同一份 benchmark（v2/benchmark_golden.jsonl）跑新 adapter
2. 和上一个 best adapter 对比
3. 关键看：
   - 成功率
   - 工具调用 F1
   - JSON 有效率
   - 人工抽检 20 条（**不能跳**）

填报告用 `02_benchmark/report_template.md`。

## 6. 超参迭代节奏

**一次只动一个变量**，每次跑 2-3 epoch 快试：

```
v1：默认配置
v2：lr 调（1e-4 / 5e-4）
v3：epoch 调（1 / 5）
v4：LoRA r 调（8 / 32）
v5：数据配比（多加/少加通用数据）
v6：target_modules（all-linear vs 仅 attention）
```

维护一份 `experiment_log.md` 跟踪每版的动作和结果。

## 7. 进 DP2 决策

SFT 阶段末要决定：
- 指标是否达到"研发阈值"（`eval_spec.md` §5）
- 如果达到且人工抽检 OK → 可以考虑上线（跳过 DPO）
- 如果技术指标达到但人工反馈"风格/偏好不对" → 进 DPO
- 如果技术指标不达标 → 回炉数据 / 考虑换基座

决策文档：`06_decisions/DP2_sft_enough.md`。

## 8. 常见坑

详见 `troubleshooting.md`。最常见三个：
1. **loss 不降**：多半是 response_template 不对，导致 collator 把所有 token mask 了
2. **过拟合**：eval loss 反弹 → 减 epoch，加 dropout，加通用数据
3. **tool_call 格式崩**：训练数据里 tool_call 序列化格式不一致 → 清洗脚本重跑
