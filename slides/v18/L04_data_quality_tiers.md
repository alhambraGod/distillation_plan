---
marp: true
theme: default
paginate: true
header: 'L04 · 数据质量分级'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #065F46; border-bottom: 4px solid #065F46; padding-bottom: 8px; }
  h2 { color: #059669; }
  section.cover { background: linear-gradient(135deg, #065F46 0%, #059669 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #065F46; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 16px; }
  .big { font-size: 48px; text-align: center; color: #065F46; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
  .gold-tier { background: #FEF3C7; padding: 8px; border-left: 4px solid #D97706; }
  .silver-tier { background: #F3F4F6; padding: 8px; border-left: 4px solid #6B7280; }
  .bronze-tier { background: #FEF2F2; padding: 8px; border-left: 4px solid #9F1239; }
  .black-tier { background: #1F2937; color: white; padding: 8px; border-left: 4px solid black; }
---

<!-- _class: cover -->

# L04 · 数据质量分级

## 金 / 银 / 铜 / 黑 —— 防幸存者偏差

<br>

📅 **第 4 课 · 60 分钟**
📚 教材：`01_data_pipeline/data_quality_tiers.md`

---

## 🎯 本课目标

- 理解"幸存者偏差"为什么是致命问题
- 掌握金 / 银 / 铜 / 黑四级定义
- 能给样本打 tier
- **动手给 20 条样本标记**

---

## 🚨 问题：你以为你有"好数据"

```
10 万条 LangSmith trace
      │
      ▼
"这就是我的训练数据了！"
      │
      ▼
❌ 幸存者偏差：
  - 只有 Claude 成功的路径
  - 没有"Claude 应该怎么做但没做"的反例
  - Claude 自己的 bug 会被继承
```

<br>

<div class="highlight">
🔑 小模型天花板 = 教师能力 + 数据质量。数据烂，模型也烂。
</div>

---

## 📊 四级分级法

<div class="gold-tier">

**🥇 金数据 (Gold) - 1-5%**
人工标注 + 用户采纳 + 任务闭环完成

</div>

<div class="silver-tier">

**🥈 银数据 (Silver) - 20-40%**
启发式过滤：无 error / 无重试 / submit_final_report 合法

</div>

<div class="bronze-tier">

**🥉 铜数据 (Bronze) - 其余**
原始 trace，有错误、取消、早停 — **不进训练集**

</div>

<div class="black-tier">

**⚫ 黑数据 (Trash) - 少量**
用户 downvote / 已知 bug / 合规违规 — **DPO 的 rejected 来源**

</div>

---

## 🥇 金数据：什么样才算

**全部满足**：
- ✅ 任务**闭环完成**（submit_final_report 被下游接受）
- ✅ **无 error**、无重试
- ✅ 用户**显式采纳** 或 **人工复核通过**
- ✅ 2 人标注一致（Cohen's Kappa ≥ 0.7）

<br>

**用途**：
- SFT 主力训练数据
- 黄金集 benchmark（200 条）
- DPO 的 chosen 来源

---

## 🥈 银数据：启发式过滤

```python
is_silver = (
    row["status"] == "success"
    and not row["has_error"]
    and 200 <= row["total_tokens"] <= 16000
    and row["tool_call_steps"] <= 15
    and row["tool_calls_valid"]
    and row.get("submit_final_report_exists", False)
)
```

<br>

**用途**：和金数据**混用**做 SFT 训练主力。

---

## 🥉 铜数据：**不进训练集**

> 有错误 / 取消 / 重试 / 早停 / 被弃用

**可以用来做**：
- ✅ Benchmark 回放（测失败模式）
- ✅ 归因分析
- ✅ 人工复核后升级

**绝不能做**：
- ❌ 直接进 SFT（会把错误学进去）

---

## ⚫ 黑数据：DPO 的反面教材

**来源**：
- 用户显式 downvote（点踩）
- 复现的 known bug
- 安全 / 合规违规输出
- 人工标注"不可接受"

**用途**：
- ✅ DPO 的 rejected
- ✅ 反例测试集
- ❌ 绝对不进 SFT

---

## 🛠️ 实现：`clean.py` 加 tier 标签

```python
def classify_tier(row) -> str:
    if row.get("user_downvoted") or row.get("known_bug_tag"):
        return "trash"
    if (
        row.get("user_adopted") is True
        and not row["has_error"]
        and row.get("human_verified") is True
    ):
        return "gold"
    if is_silver(row):
        return "silver"
    return "bronze"
```

---

## 📁 分 tier 输出

```bash
data/datasets/v2/
├── sft_gold.jsonl       # 金，全用
├── sft_silver.jsonl     # 银，采样 60%
├── bench_bronze.jsonl   # 铜，只进 benchmark
└── neg_trash.jsonl      # 黑，DPO rejected
```

<br>

**build_datasets.py 配比**：

```yaml
training_mix:
  gold: 1.0
  silver: 0.6
  bronze: 0.0    # 绝不
  general: 0.2   # 通用数据防遗忘
```

---

## 📈 数据量预期

| 层 | 目标 | 来源 |
|---|---|---|
| 🥇 金 | 3-5k | 人工标 + 用户采纳 |
| 🥈 银 | 20-40k | 启发式筛 |
| 🥉 铜 | 50k+ | 剩下全部 |
| ⚫ 黑 | 500-2k | 人工 + 用户 downvote |
| 合成 | 2-5k | CoT / Evol-Instruct 补齐 |

<br>

**SFT 实际用**：金 100% + 银 60% + 合成 + 通用 ≈ 30-50k

---

## 🧑 金数据"制造"方法

现实：金数据**量永远不够**，需要主动造：

| 方法 | 做法 |
|---|---|
| A: 人工标注 | 银数据抽 1000 条 → 2 人打"是否金" |
| B: 用户行为 | "采纳"按钮、"修改后采纳"、"弃用"分档 |
| C: 业务规则 | submit_final_report 被下游消费 = 金 |
| D: 教师预筛 | Claude 对银数据打分，top 20% 交人工 |

---

## 🔬 Cohen's Kappa 入门

两个标注人一致性的指标，不是简单的"一致率"。

```
Kappa < 0.4    一致性差，重新对齐 rubric
0.4 - 0.7      一致性中，分歧样本讨论
≥ 0.7          可上线标注
```

<br>

```python
from sklearn.metrics import cohen_kappa_score
kappa = cohen_kappa_score(annotator_a, annotator_b)
```

---

## 🏋️ 实操（课堂 15 分钟）

**任务**：我发给你 20 条样本的摘要，你给每条打 tier（金 / 银 / 铜 / 黑 / 不确定）。

标注 rubric：
- 🥇 金：我会直接采纳作为"标杆答案"
- 🥈 银：能用，但可能要小改
- 🥉 铜：能反映问题，但不学习
- ⚫ 黑：绝对不能学

标完后：
- 计算小组间 Kappa
- 挑分歧大的 3 条讨论

---

## ⚠️ 常见误区

1. "我们有 10 万条 trace，数据多" → 实际可用 = 金 + 银 = 2-5 万
2. "采纳率自动等于金" → 要 2+ 信号交叉
3. "黑数据也 SFT 当反例" → 大错！SFT 只能学"对"的
4. "分级太麻烦，全训" → 幸存者偏差会让你付出更大代价

---

## 🏠 课后作业

1. 用 `classify_tier` 函数给 200 条样本打 tier
2. 统计各 tier 比例，和预期对比
3. 思考：你们业务 "用户采纳"信号能否接入？

<br>

**下节课**：L05 合规 + V1/V2 隔离

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: 我们数据全是铜怎么办？ → A: 先人工标一批金（成本高但必须）
- Q: 银数据能做 DPO chosen 吗？ → A: 能，和金一起
- Q: 铜里挑精要标多少？ → A: 20-30% 抽检
