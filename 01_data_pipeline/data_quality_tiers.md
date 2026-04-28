# 数据质量分级：金 / 银 / 铜 / 黑

> 对应 `project_critique_and_fixes.md` 问题 2 的详细方案。
> 核心原则：**不是所有 trace 都能进训练集**。

---

## 1. 为什么分级

**幸存者偏差**：LangSmith trace 只记录"已完成"的 agent 执行路径。如果直接拿来训练，小模型只学会：
- Claude 成功模式（天花板就是 Claude）
- Claude 所有错误模式（把 bug 学进去）
- 不学任何"失败路径"（长尾 case 处理不好）

**解决**：按质量分级，不同级用不同用途。

---

## 2. 四个等级定义

### 🥇 金数据（Gold） - 1-5%

**标准**（全部满足）：
- ✅ 任务**闭环完成**（submit_final_report 被采纳）
- ✅ **无 error**、无重试
- ✅ 用户**显式采纳**（点赞 / 复制 / 下载）或 **人工复核通过**
- ✅ 2 人标注一致（Cohen's Kappa ≥ 0.7）

**用途**：
- ✅ SFT 训练主力
- ✅ 黄金集 benchmark（200 条固定）
- ✅ DPO 的 chosen 来源
- ✅ RL reward 的 ground truth

**数量**：通常 3-5k 条（人工标注 + 采纳信号筛）

### 🥈 银数据（Silver） - 20-40%

**标准**（启发式，全部满足）：
- ✅ `final_status == success`
- ✅ 没有 tool_call JSON parse 失败
- ✅ `submit_final_report` 存在且符合 schema
- ✅ 工具调用步骤数在合理范围（2-15 步，不极端）
- ✅ 总 tokens 在合理范围（200 - 16000）
- ✅ 不是 known-bug 复现 case

**用途**：
- ✅ SFT 训练（和金数据混用）
- ✅ 可作 DPO chosen（和金数据合并）
- ⚠️ 不进 benchmark 黄金集

**数量**：通常 10k-50k 条

### 🥉 铜数据（Bronze） - 其余大部分

**标准**：
- 有错误 / 取消 / 重试 / 早停
- 输出被用户弃用
- 超长或超短
- 规则过滤疑似质量问题

**用途**：
- ⚠️ **不进训练集**
- ✅ Benchmark 回放（测失败模式，看小模型是否能复现）
- ✅ 归因分析
- ✅ 铜中挑精（经人工复核后可升级）

### ⚫ 黑数据（Trash / Negative） - 少量

**标准**：
- 用户**显式 downvote**（点踩）
- 复现的 known bug
- 安全/合规违规输出
- 人工标注为"不可接受"

**用途**：
- ✅ **DPO 的 rejected 来源**（负样本）
- ✅ 反例测试集（上线前必测不能触发这些）
- ❌ 绝对不进 SFT

---

## 3. 分级 Pipeline 实现

### 3.1 在清洗阶段打标

修改 `01_data_pipeline/code/clean.py`：

```python
def classify_tier(row) -> str:
    # 黑数据：explicit downvote / known bug
    if row.get("user_downvoted") or row.get("known_bug_tag"):
        return "trash"

    # 金数据条件：采纳 + 无错 + 人工通过
    if (
        row.get("user_adopted") is True
        and not row["has_error"]
        and row.get("human_verified") is True
    ):
        return "gold"

    # 银数据：启发式
    if (
        row["status"] == "success"
        and not row["has_error"]
        and 200 <= row["total_tokens"] <= 16000
        and row["tool_call_steps"] <= 15
        and row["tool_calls_valid"]
        and row.get("submit_final_report_exists", False)
    ):
        return "silver"

    # 铜数据：其他
    return "bronze"
```

### 3.2 分 tier 输出

修改 `extract_fields.py`：

```python
# 按 tier 分文件
gold_path = out_dir / "sft_gold.jsonl"
silver_path = out_dir / "sft_silver.jsonl"
bronze_path = out_dir / "bench_bronze.jsonl"  # 只进 benchmark
trash_path = out_dir / "neg_trash.jsonl"      # DPO rejected 来源
```

### 3.3 构建训练集

修改 `build_datasets.py`：

```yaml
# config
training_mix:
  gold: 1.0           # 金数据全用
  silver: 0.6         # 银数据采样 60%
  bronze: 0.0         # 不用
  general: 0.2        # 通用数据比例（对总训练集）

benchmark_mix:
  gold: 1.0           # 黄金 benchmark 全用金数据
  silver: 0.0         # 不用
  bronze: 0.1         # 回放集抽 10% 铜数据（测失败模式）
```

---

## 4. 数据量规划

典型项目数据量（12 周跑完）：

| 层 | 目标数量 | 来源 |
|---|---|---|
| 金 | 3-5k | 人工标注 + 用户采纳 |
| 银 | 20-40k | 启发式过滤 |
| 铜 | 50k+ | 剩下的 |
| 黑 | 500-2k | 人工标 + 用户 downvote |
| 合成（增强） | 2-5k | CoT 合成 / Evol-Instruct |

**训练集构成（典型 30-50k 总量）**：
- 金 100% = 5k
- 银 60% = 20k（from 33k）
- 合成 = 3k
- 通用指令数据 = 8k（防遗忘）
- **总计 ~36k**

---

## 5. 金数据的"制造"方法

金数据通常量不够，需要主动制造：

### 方法 A：人工标注
- 从银数据里随机抽 1000 条
- 2 人独立打"是否可作为金样本"
- 一致的进金库

### 方法 B：用户行为信号
- 接入"采纳"按钮 → 采纳的 trace 自动标金
- 接入"修改后采纳" → 按修改量分级
- 接入"弃用" → 标黑

### 方法 C：业务规则自动
- 金：完整 `submit_final_report` 被下游接口消费
- 黑：任务 timeout / 用户 5 分钟内再次发起同请求

### 方法 D：教师 judge 预筛
- Claude 对银数据打分，top 20% 交人工复核 → 金

---

## 6. 分级后的训练策略

### 6.1 标准策略（推荐起步）

- SFT：金 + 银（60-70%） + 通用（20-30%）
- DPO：chosen 从金 + 银采，rejected 从黑 + 负采样

### 6.2 激进策略（金质量高时）

- SFT：只用金 + 合成 + 通用
- 看基础指标，不够再加银

### 6.3 长尾补齐策略

如果银/金都不够覆盖某类 case：
- 主动合成（让教师针对特定 prompt 生成）
- 业务方**人造**case 喂进来

---

## 7. 质量监控指标

上线后持续追踪每批数据的质量漂移：

| 指标 | 健康范围 |
|---|---|
| 金数据占比 | 3-5% |
| 银数据占比 | 20-40% |
| Kappa 一致性（金） | ≥ 0.7 |
| 采纳率（实时） | 业务阈值 |
| 黑数据新增率 | 不应超过 2% / 周 |

---

## 8. 给新人/标注人的培训材料

**"什么算金数据"** 一页纸（放 `docs/` 或 Notion）：
- 5 个正例：完整 / 采纳 / 无错 / 闭环 / 业务方认可
- 5 个反例：长但空 / 无错但答非所问 / tool 调对了但结果误用
- 标注流程：看 prompt → 读完整 trace → 打分 → 一句话理由

**Cohen's Kappa 培训**：
- 2 人各标 50 条
- 计算 Kappa
- < 0.5 → 重新对齐 rubric
- 0.5-0.7 → 分歧样本讨论
- ≥ 0.7 → 可上线标注

---

## 9. 常见误区

### ❌ "我们有 10 万条 trace，数据很多"
实际可用 = 银 + 金 = 2-5 万，剩下大半不能进训练集。

### ❌ "用用户采纳率自动标金"
采纳率只是**一维信号**，可能用户只是"懒得改"。要 2+ 信号交叉。

### ❌ "黑数据也拿来 SFT 当反例"
SFT 学到"错也要学"。黑数据必须通过 DPO 的 rejected 或 RL 的负奖励进。

### ❌ "分级太麻烦，全量训"
**幸存者偏差 + 噪声**会让小模型训出一堆问题。分级是 ROI 最高的工程投入。

---

## 10. 相关文档

- `project_critique_and_fixes.md` §2（问题背景）
- `01_data_pipeline/design.md`（清洗规则）
- `04_dpo/build_preferences.py`（DPO 数据构造）

---

## 变更记录
- 2026-04-24：首版
