---
marp: true
theme: default
paginate: true
header: 'L13 · 白盒 KL + CoT'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #7C2D12; border-bottom: 4px solid #7C2D12; padding-bottom: 8px; }
  h2 { color: #B45309; }
  section.cover { background: linear-gradient(135deg, #7C2D12 0%, #B45309 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #7C2D12; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #7C2D12; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L13 · 白盒 KL + CoT 蒸馏

## SFT 之外的进阶蒸馏手段

<br>

📅 **第 13 课 · 60 分钟**
📚 教材：`distillation_techniques.md` + `train_kd.py` + `build_cot_data.py`

---

## 🎯 本课目标

- 掌握白盒 KL 蒸馏原理（logit 对齐）
- 理解 CoT 合成（DeepSeek R1 的看家技术）
- 知道什么时候叠加、什么时候不叠
- **动手**：跑教师 logits 预计算

---

## 🗺️ 回顾：7 种蒸馏方法

```
教师信号粒度：
  粗 ─────────────────────────── 富
  
  文字      →    概率     →    隐状态
 (black-box)  (white-box)    (feature)
    │             │              │
    ▼             ▼              ▼
  Method 1     Method 2-3     Method 7
  SFT         KL / Seq KD    Feature Match
             + CoT (Method 4)
             + On-policy (Method 5)
             + Reverse KL (Method 6)
```

今天聚焦 Method 2（KL）+ Method 4（CoT）

---

## 🥇 白盒 KL 蒸馏原理

```
Loss = α · CE(student, label) + β · KL(student || teacher_logits)
            ↑ 硬标签               ↑ 软标签（每 token 的分布）
```

**直觉**：教师不只说"答案是 X"，而是告诉学生"X 概率 0.65，Y 概率 0.2，Z 概率 0.1..."

**关键约束**：教师和学生必须**同 tokenizer**
- Qwen 72B → Qwen 7B ✅
- Llama 70B → Qwen 7B ❌

---

## 📊 白盒 vs 黑盒 收益

| 维度 | 黑盒 SFT | 白盒 KL | 差距 |
|---|---|---|---|
| 信号粒度 | 只学 top-1 | 学整个分布 | 5-15% 成功率提升 |
| 数据成本 | 现有 trace | 教师跑一遍 | +教师推理 |
| 训练速度 | 1x | 1.5x | 稍慢 |
| 实施难度 | 🟢 | 🟡 | 需预计算 |

<br>

<div class="highlight">
🎯 同家族最佳：Qwen 72B → Qwen 7B 配对
</div>

---

## 🛠️ 白盒 KL 两步走

```bash
# Step 1: 预计算教师 logits (一次性)
python 03_sft/precompute_teacher_logits.py \
  --teacher Qwen/Qwen2.5-72B-Instruct \
  --data data/datasets/v2/sft_train.jsonl \
  --out data/datasets/v2/sft_train_with_teacher.jsonl \
  --topk 64

# Step 2: KD 训练
python 03_sft/train_kd.py \
  --config 03_sft/configs/kd_qwen72b_to_7b.yaml
```

---

## 💾 Top-K 压缩 logits

每 token 的 logit 向量有 vocab-size 维（几万）。全存太浪费：

```python
# 只存 top-100，其他视为接近 0
top_logits, top_indices = teacher_logits.topk(100, dim=-1)
```

**效果**：
- 磁盘从 vocab × 4 bytes → 100 × 8 bytes
- 压缩 **95%+**
- 训练时 gather 回来做 KL

---

## 📝 `train_kd.py` 核心

```python
class KDTrainer(Trainer):
    def compute_loss(self, model, inputs, ...):
        teacher_idx = inputs.pop("teacher_topk_indices")
        teacher_val = inputs.pop("teacher_topk_values")
        
        outputs = model(...)
        ce_loss = outputs.loss
        
        # 只取 teacher top-k 位置的 student logits
        student_topk = torch.gather(outputs.logits, -1, teacher_idx)
        
        kl = F.kl_div(
            F.log_softmax(student_topk / T, dim=-1),
            F.softmax(teacher_val / T, dim=-1),
        )
        
        loss = α * ce_loss + β * kl * (T * T)
```

---

## 🧠 CoT（Chain-of-Thought）合成蒸馏

**原理**：让教师输出"思考过程"，学生学推理链。

```
用户输入：分析品牌 X 的增长

教师输出：
<think>
  步骤 1: 识别 X 所在行业...
  步骤 2: 拆解增长指标...
  步骤 3: 对比竞品...
</think>
结论: X 在 Q3 增长 23%...
```

<br>

学生学**整个 reasoning**，不只是结论。

---

## 📚 CoT 适合什么任务

| 任务 | 要加 CoT 吗 |
|---|:---:|
| 数学 / 逻辑推理 | ✅ 强烈推荐 |
| 复杂多工具决策 | ✅ |
| 长 horizon agent 任务 | ✅ |
| 简单格式化 JSON 生成 | ❌ 浪费 token |
| tool args 填充 | ❌ |
| 分类 / 抽取 | ❌ |

<br>

<div class="highlight">
只对"复杂 case"加 CoT —— 看 `is_complex()` 过滤
</div>

---

## 🛠️ CoT 生成脚本

```bash
python 03_sft/build_cot_data.py \
  --teacher Qwen/Qwen2.5-72B-Instruct \
  --in data/datasets/v2/sft_train.jsonl \
  --out data/datasets/v2/sft_train_cot.jsonl \
  --filter complex     # 只加到复杂 case
```

输出样本：
```json
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant",
     "content": "<think>\n步骤...\n</think>\n\n结论..."}
  ]
}
```

---

## 📊 三种蒸馏叠加效果（假设）

| 方法 | 成功率 | 相对成本 |
|---|---|---|
| 纯 SFT（baseline） | 75% | 1x |
| + 白盒 KL | 82% | 3-4x |
| + CoT（叠加） | 85% | 5x |
| + DPO（叠加） | 88% | 7x |
| + RL POC（叠加） | 89% | 10x |

<br>

**建议路径**：先 SFT，不够加 KL，再加 CoT，最后 DPO。

---

## ⚠️ 白盒 KL 常见坑

| 坑 | 解决 |
|---|---|
| Tokenizer 不同 | 退化到黑盒 |
| 预计算 logits 磁盘爆 | Top-K 压缩 |
| 教师 OOM（72B 太大） | 量化教师 / 多卡 |
| KL 权重调错 | 从 β=0.5 起步 |
| Temperature 调错 | T=2.0 起步 |

---

## 📋 DeepSeek R1 范本

DeepSeek R1 官方蒸馏版：
- **R1-Distill-Qwen-7B** / 14B / 32B
- **R1-Distill-Llama-8B** / 70B

做法 = **CoT 蒸馏**（R1 产生的推理链作为训练信号）

<br>

<div class="highlight">
💡 阶段 1 benchmark 必测 R1-Distill — 可能已经够用，省训
</div>

---

## 🏋️ 实操（20 分钟）

```bash
# 用小教师 (14B) + 小数据演示
python 03_sft/precompute_teacher_logits.py \
  --teacher Qwen/Qwen2.5-14B-Instruct \
  --data data/pilot_100.jsonl \
  --out data/pilot_100_with_teacher.jsonl \
  --topk 32

# 看输出文件大小
ls -lh data/pilot_100_with_teacher.jsonl

# 抽一条样本看 teacher_logits 字段
python -c "import json; d=json.loads(open('data/pilot_100_with_teacher.jsonl').readline()); print(d['teacher_logits']['indices'][:2])"
```

---

## 🏠 课后作业

1. 读完 `distillation_techniques.md`
2. 跑一次教师 logits 预计算（小教师 + 50 条）
3. 思考：我们项目该不该加 KL？算力够吗？

<br>

**下节课**：L14 RL 理论

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: 不同家族的 tokenizer 能映射吗？→ A: 近似方法有，损失大，不如黑盒
- Q: CoT 会让推理变慢 5 倍？→ A: 是，所以只对复杂 case 加
- Q: R1-Distill 开箱能用吗？→ A: 必测！可能省整个训练阶段
