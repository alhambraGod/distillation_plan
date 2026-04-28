---
marp: true
theme: default
paginate: true
header: 'L12 · DPO 偏好对齐'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #BE185D; border-bottom: 4px solid #BE185D; padding-bottom: 8px; }
  h2 { color: #DB2777; }
  section.cover { background: linear-gradient(135deg, #BE185D 0%, #DB2777 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #BE185D; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #BE185D; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L12 · DPO 偏好对齐

## SFT 后"风格不对"的救命稻草

<br>

📅 **第 12 课 · 60 分钟**
📚 教材：`dpo_guide.md` + `build_preferences.py`

---

## 🎯 本课目标

- 理解 DPO 原理 + 为什么比 RLHF 简单
- 掌握偏好对构造的 3 种方法 + 10% 人工抽检
- 熟悉 DPO 的 3 个致命坑
- **动手**：构造 50 条偏好对

---

## 🤔 什么时候用 DPO

<div class="big">
SFT 后技术 OK，但人工评分 3.2<br>
→ DPO 救场
</div>

<br>

**典型症状**：
- 工具调用对、JSON 合法 → SFT 搞定
- 但文案生硬、不打动人心 → SFT 搞不定
- 用户说"就是差点意思"

---

## 📖 DPO 原理 (30 秒版)

给定偏好对 `(x, y_w, y_l)` 让 y_w 概率高于 y_l：

```
L = -log σ(β · [log(π(y_w)/π_ref(y_w)) 
                - log(π(y_l)/π_ref(y_l))])
```

**直觉**：让模型更倾向 chosen，但被参考模型拉住不跑太远。

<br>

论文点：原本要 RM + PPO 两步，DPO 证明一步就行。

---

## 🔑 DPO vs SFT 区别

| 维度 | SFT | DPO |
|---|---|---|
| 数据 | (x, y) | (x, y_w, y_l) |
| 学什么 | "y 是对的" | "y_w 比 y_l 好" |
| lr | 2e-4 | **5e-7** (小 400x) |
| epoch | 1-3 | 1-2 |
| 需要参考模型 | ❌ | ✅ |

---

## 📚 偏好对三种来源

| 来源 | 做法 | 比例 |
|---|---|---|
| **A: 历史挖掘** | 同 prompt 不同 trace 里挑一对 | 30% |
| **B: 采样排序** | SFT 采 K 个，Claude 或人工排序 | **50%** |
| **C: Claude vs SFT** | Claude 当 chosen，SFT 当 rejected | 20% (慎用) |

<br>

<div class="highlight">
⚠️ 来源 C 会让学生变"Claude 影子"，比例控制在 20% 以下
</div>

---

## 🧑 关键补强：10% 人工抽检

业务方从生成的偏好对里抽 10%，判断：
- chosen 真的比 rejected 好吗？
- 分歧理由合理吗？

**抽检通过率**：
- < 80% → 数据质量差，回炉
- ≥ 80% → 可训

<br>

<div class="highlight">
原方案没这步 → 修复的关键
</div>

---

## ⚙️ DPO 配置起步

```yaml
base_model: Qwen/Qwen2.5-7B-Instruct
sft_adapter: adapters/v2_sft_best   # SFT 后的

dpo:
  beta: 0.1             # 0.1-0.5，越大越保守

train:
  epochs: 1             # ⚠️ 容易过拟合
  lr: 5.0e-7            # ⚠️ 比 SFT 小 400x
  batch_size: 2
  grad_accum: 8
  max_length: 4096
  max_prompt_length: 2048
```

---

## 🚨 DPO 三大致命坑

| 坑 | 症状 | 防范 |
|---|---|---|
| **lr 太大** | 模型崩，输出乱码 | 5e-7 起步，一半一半调 |
| **Reward hacking** | margin 飙高但 benchmark 掉 | 监控 benchmark + 降 lr + 加 beta |
| **长度偏差** | 输出变冗长 | 构造偏好对时长度匹配 |

---

## 🔍 Reward Hacking 识别

**症状**：
- `rewards/margin` 飞快上升到 10+
- `rewards/accuracies` = 100%
- 但 eval 分数降

**原因**：模型找 reward 函数漏洞，拉大差值但实际输出不行。

**解决**：
- 降 lr
- 降 epoch（0.3-0.5 epoch 就停）
- 加 beta

---

## 📏 长度偏差检查

训练前必做：

```python
import json
lengths = []
with open("dpo_train.jsonl") as f:
    for l in f:
        d = json.loads(l)
        lengths.append((len(d["chosen"]), len(d["rejected"])))

diffs = [c - r for c, r in lengths]
print(f"mean diff: {np.mean(diffs):.0f}")
# 如果 > 200 字符，就是长度偏差
```

<br>

**修正**：筛选或改用 SimPO（原生长度归一化）。

---

## 🧰 构造偏好对脚本

```bash
# 来源 A: 历史挖掘
python 04_dpo/build_preferences.py \
  --mode history \
  --history-in data/datasets/v2/sft_train.jsonl \
  --out data/datasets/v2/dpo_from_history.jsonl \
  --n-pairs 1000

# 来源 B: SFT 采样 + judge
# (需要先有 SFT adapter + judge prompt)

# 合并 + 抽检
python 04_dpo/merge_and_audit.py \
  --sources history,sampled,claude_vs_sft \
  --ratios 0.3,0.5,0.2 \
  --audit-sample 0.1
```

---

## 📊 DPO 训练监控

W&B 上关键曲线：

| 曲线 | 正常 | 异常 |
|---|---|---|
| `loss` | 缓慢下降 | 震荡或 NaN → lr 大 |
| `rewards/chosen` | 缓慢上升 | — |
| `rewards/rejected` | 缓慢下降 | — |
| `rewards/margin` | 逐步增大 | 暴涨到 10+ → hacking |
| `rewards/accuracies` | 60-90% | 100% 持续 → hacking |

---

## 🔄 DPO 评估

训完比较 SFT vs DPO：

- 技术指标：**不能降**（否则 DPO 有问题）
- Usability 人工分：**必须升**（≥ 0.3 分）
- 通用能力：抽测 MMLU / CMMLU 不崩

<br>

三个都过 → 上线
任一不过 → 回滚 SFT 版本

---

## 🆚 DPO vs ORPO vs SimPO

| 情况 | 选 |
|---|---|
| 有 SFT + 想稳 | DPO |
| 显存紧 | ORPO (不要 ref) |
| 长度偏差严重 | SimPO |

<br>

**本项目**：先 DPO，不稳再 SimPO。

---

## 🏋️ 实操（20 分钟）

**任务**：构造 50 条偏好对

```bash
# Option A: 从 SFT 历史采样
python 04_dpo/build_preferences.py \
  --mode history \
  --history-in data/datasets/v2/sft_train_small.jsonl \
  --out data/datasets/v2/dpo_demo.jsonl \
  --n-pairs 50
```

然后人工 review 5 条：
- chosen 真的更好？
- 长度差别大吗？

---

## 🏠 课后作业

1. 读完 `dpo_guide.md` + `troubleshooting.md`
2. 构造 200 条偏好对（任选来源）
3. 做 10% 人工抽检，计算通过率

<br>

**下节课**：L13 白盒 KL + CoT

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: 不做 SFT 直接 DPO 行吗？→ A: 不行，DPO 放大错误
- Q: β 调大还是调小？→ A: 训崩就调大（更保守）
- Q: 一定要人工抽检吗？→ A: 对，否则 Judge bias 会放大
