# 数据质量分级：金 / 银 / 铜 / 黑

> 与 `01_data_pipeline/design.md`（管线设计）、`00_overview/anthropic_tos_compliance.md`（合规审查）配套使用。
> 核心原则：**不是所有 trace 都能进训练集**

---

## 1. 为什么分级

### 1.1 幸存者偏差

可观测性平台（LangSmith / LangFuse）的 trace 只记录"已完成"的 agent 执行路径。直接拿来训练，小模型只学会：
- 教师模型（Claude）的成功模式（天花板就是 Claude）
- 教师模型的所有错误模式（把 bug 学进去）
- 不学任何"失败路径"（长尾 case 处理不好）

### 1.2 业务专属偏差（社媒推广业务示例）

> **真实数据案例**：以 9 条社媒推广 trace 为例（项目示例数据集）：
>
> | 表面分类 | 真实情况 |
> |---|---|
> | 5 条『成功』V1 trace | 3 真成功 + 2 部分失败被 retry |
> | 4 条『成功』V2 trace | 3 真成功 + 1 SOP 跳步『假成功』 |
> | 业务方说『没问题』 | Claude 视角拒绝过 2 次（道德边界） |

**直接训 →** 学到：
- 跳 SOP 也算成功（铜数据污染）
- 复刻 Claude 道德拒绝（黑数据污染）
- 长尾噪声（银里学的）

**解决**：按质量分级，不同级用不同用途。

---

## 2. 四个等级定义

### 🥇 金数据（Gold） - 1-5%

**4 标准（全部满足）**：
- ✅ 任务**闭环完成**（`submit_final_report` 被采纳）
- ✅ **无 error**、无重试
- ✅ 用户**显式采纳**（点赞 / 复制 / 下载）或 **人工复核通过**
- ✅ 2 人标注一致（Cohen's Kappa ≥ 0.7）

**业务专属补充**（如学员的社媒推广业务）：
- ✅ **SOP 完整执行**（如 Reddit 仿写必经 6 步全跑：fetch → filter → rewrite → select → preflight → publish）
- ✅ 平台合规（如 Reddit karma ≥ 门槛 / X 不触发 CIB）

**用途**：
- ✅ SFT 训练主力
- ✅ 黄金集 benchmark（200 条固定）
- ✅ DPO 的 chosen 来源
- ✅ RL reward 的 ground truth

**真实数据示例**：
- V2-成功 `019dde5e-5051`（Reddit 抢评）：5 trace、68 tool calls、113 秒、$0.12，全 status=success，业务方背书
- V2-成功 `019dde5e-5033`、`019dde42`：同类，紧凑闭环

**数量**：通常 3-5k 条（人工标注 + 采纳信号筛）

### 🥈 银数据（Silver） - 20-40%

**启发式标准（全部满足）**：
- ✅ `final_status == success`
- ✅ 没有 tool_call JSON parse 失败
- ✅ `submit_final_report` 存在且符合 schema
- ✅ 工具调用步骤数在合理范围（业务专属阈值，如学员业务 2-100 步）
- ✅ 总 tokens 在合理范围（200 - 32000，学员业务调宽）
- ✅ 不是 known-bug 复现 case

**用途**：
- ✅ SFT 训练（和金数据混用，采样 60%）
- ✅ 可作 DPO chosen（金数据优先，银数据补量）
- ⚠️ **不进 benchmark 黄金集**

**真实数据示例**：
- V1-成功 `019dfa27`（X KOL 跟评）：12 trace、375 tool calls、805 messages、18 分钟、$0.68
  - status 全部 success，但量大有重复模式 → 银
- V1-成功 `019ddc8d`、`019ddcfd`：同类，量更大

**数量**：通常 10k-50k 条

### 🥉 铜数据（Bronze） - 大多数

**标准**：
- 有错误 / 取消 / 重试 / 早停
- 输出被用户弃用
- 超长或超短
- **业务专属：SOP 跳步**（如学员 V2-部分成功）

**用途**：
- ⚠️ **不进训练集**
- ✅ Benchmark 回放（测失败模式，看小模型是否能复现）
- ✅ 归因分析
- ✅ 铜中挑精（经人工复核后可升级）

**真实数据示例**：
- V2-部分成功 `019dde6d`（Reddit 仿写人设跳步）：11 trace、146 tool calls
  - 表面成功（帖子发出去了）
  - 但**没按 SOP 第 2.1 条做人设匹配检查**——直接选了 karma 最高的号
  - 长期会拉低账号"真实度"信号

### ⚫ 黑数据（Trash / Negative） - 少量

**标准**：
- 用户**显式 downvote**（点踩）
- 复现的 known bug
- 安全/合规违规输出
- 人工标注为"不可接受"
- **业务专属：教师模型道德拒绝**（学员业务真实场景）

**用途**：
- ✅ **DPO 的 rejected 来源**（负样本）
- ✅ 反例测试集（上线前必测不能触发这些）
- ❌ 绝对不进 SFT

**真实数据示例**：
- V1-拒绝执行 `019defa4`（『针对 AI 话题对引流号执行养号闭环』）：
  - Claude 自己拒绝执行，引用『Coordinated Inauthentic Behavior』
  - **不在 Anthropic ToS 里**，是 Claude 训练时学到的道德边界
- V1-拒绝内容 `019dd263`：内容生成阶段被中止

---

## 3. 分级 Pipeline 实现

### 3.1 在清洗阶段打标

修改 `01_data_pipeline/code/clean.py`：

```python
def classify_tier(row, business_rules: BusinessRules) -> str:
    # ⚫ 黑数据：教师模型道德拒绝（业务专属）
    if business_rules.has_moral_rejection(row):
        return "trash"
    
    # ⚫ 黑数据：explicit downvote / known bug
    if row.get("user_downvoted") or row.get("known_bug_tag"):
        return "trash"

    # 🥇 金数据：4 标准
    if (row.get("user_adopted") is True
        and not row["has_error"]
        and row.get("human_verified") is True
        and business_rules.sop_followed(row)):  # 业务专属
        return "gold"

    # 🥈 银数据：启发式
    if (row["status"] == "success"
        and not row["has_error"]
        and 200 <= row["total_tokens"] <= business_rules.max_tokens
        and row["tool_call_steps"] <= business_rules.max_tool_calls
        and row["tool_calls_valid"]
        and row.get("submit_final_report_exists", False)):
        return "silver"

    # 🥉 铜数据：其他
    return "bronze"


class BusinessRules:
    """业务专属规则（按业务实例化）"""
    
    def __init__(self, business_id: str):
        # 学员业务（社媒推广）
        if business_id == "social_media_growth":
            self.max_tokens = 32000
            self.max_tool_calls = 100
            self.required_sop_steps = {
                "loop-86771bc5": {"profile_check", "search_posts",
                                  "comment", "report"},
                "loop-54ee005d": {"persona_match", "fetch_posts",
                                  "rewrite", "publish"},
            }
            self.moral_rejection_signals = [
                "Coordinated Inauthentic Behavior",
                "manipulate engagement metrics",
                "operate online systems",
                "拒绝执行",
                "I cannot assist with",
            ]
        # 通用客服 chatbot 业务
        elif business_id == "customer_service":
            self.max_tokens = 8000
            self.max_tool_calls = 5
            self.required_sop_steps = {}
            self.moral_rejection_signals = []
        # ... 其他业务
    
    def has_moral_rejection(self, row) -> bool:
        for msg in row.get("messages", []):
            content = str(msg.get("content", ""))
            if any(sig in content for sig in self.moral_rejection_signals):
                return True
        return False
    
    def sop_followed(self, row) -> bool:
        skill_id = row.get("skill_id")
        if skill_id not in self.required_sop_steps:
            return True  # 无 SOP 要求
        required = self.required_sop_steps[skill_id]
        actual = {step["name"] for step in row.get("plan_steps", [])}
        return required.issubset(actual)
```

### 3.2 分 tier 输出

修改 `extract_fields.py`：

```python
# 按 tier 分文件 + 按平台分文件夹
data/datasets/v1/             # X(Twitter) 业务
├── sft_gold.jsonl
├── sft_silver.jsonl
├── bench_bronze.jsonl
└── neg_trash.jsonl

data/datasets/v2/             # Reddit 业务（独立！）
├── sft_gold.jsonl
└── ...
```

### 3.3 构建训练集

修改 `build_datasets.py`：

```yaml
# config（每个业务一份独立 yaml）
training_mix:
  gold: 1.0           # 金数据全用
  silver: 0.6         # 银数据采样 60%
  bronze: 0.0         # 不用
  general_huggingface: 0.2   # 通用 HF 数据混入比例

benchmark_mix:
  gold: 1.0           # 黄金 benchmark 全用金数据
  silver: 0.0         # 不用
  bronze: 0.1         # 回放集抽 10% 铜数据（测失败模式）
  trash_red_line: 1.0 # 黑数据全部进风险红线 benchmark
```

---

## 4. 数据量规划

### 4.1 通用项目典型数据量（12 周跑完）

| 层 | 目标数量 | 来源 |
|---|---|---|
| 金 | 3-5k | 人工标注 + 用户采纳 |
| 银 | 20-40k | 启发式过滤 |
| 铜 | 50k+ | 剩下的 |
| 黑 | 500-2k | 人工标 + 用户 downvote |
| 合成（增强） | 2-5k | CoT 合成 / Evol-Instruct |

### 4.2 学员业务（社媒推广）数据量参考

| 层 | V1 (X) | V2 (Reddit) |
|---|---:|---:|
| 金 | ~500 | ~2k（事件触发量大） |
| 银 | ~3k | ~5k |
| 铜 | ~5k | ~3k |
| 黑（道德拒绝） | ~200 | ~50 |
| HF 通用补充 | ~10k | ~10k |
| **总训练集** | **~15k** | **~17k** |

### 4.3 训练集构成（典型 30-50k 总量）

- 金 100% = 5k
- 银 60% = 20k（from 33k）
- 合成 = 3k
- 通用指令数据（HuggingFace）= 8k（防遗忘）
- **总计 ~36k**

---

## 5. 金数据的"制造"方法

金数据通常量不够，需要主动制造：

### 方法 A：人工标注

- 从银数据里随机抽 1000 条
- 2 人独立打"是否可作为金样本"
- 一致的进金库
- **学员业务建议**：从 V1 成功 trace 里挑闭环最干净的 1000 条

### 方法 B：用户行为信号

- 接入"采纳"按钮 → 采纳的 trace 自动标金
- 接入"修改后采纳" → 按修改量分级
- 接入"弃用" → 标黑
- **学员业务建议**：Reddit 帖子 24h 后 score 增长 > 50 → 自动金

### 方法 C：业务规则自动

- 金：完整 `submit_final_report` 被下游接口消费
- 黑：任务 timeout / 用户 5 分钟内再次发起同请求
- **学员业务建议**：业务方 dashboard 真实展示了 = 金

### 方法 D：教师 judge 预筛

- Claude 对银数据打分，top 20% 交人工复核 → 金
- **学员业务建议**：可以在 1 周内造出 500-1000 条金

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
| **道德拒绝率（业务专属）** | < 1%（学员业务） |
| **SOP 跳步率（业务专属）** | < 3%（学员业务） |

---

## 8. 给新人/标注人的培训材料

**"什么算金数据"** 一页纸（放 `docs/` 或 Notion）：

### 通用模板
- 5 个正例：完整 / 采纳 / 无错 / 闭环 / 业务方认可
- 5 个反例：长但空 / 无错但答非所问 / tool 调对了但结果误用
- 标注流程：看 prompt → 读完整 trace → 打分 → 一句话理由

### 学员业务定制
**正例（学员社媒推广业务）**：
1. Reddit 抢评 SOP 6 步全过 + 评论被点赞
2. X 跟评 60 秒内完成 + 业务方点采纳
3. 投票裂变 24h 互动达 5000+
4. KOL 跟评抢前 3 楼 + 引流到主号
5. submit_final_report 被业务 dashboard 引用

**反例**：
1. SOP 跳步（如不做人设匹配直接选号）
2. 工具返回 stack trace 但任务标 success
3. Claude 拒绝执行（CIB / 内容违规）
4. 单号在 60s 内同动作 5+ 次（CIB 高风险）
5. 评论文案重复模式（同一 thread 内『很有道理』出现 3 次以上）

**Cohen's Kappa 培训**：
- 2 人各标 50 条
- 计算 Kappa
- < 0.5 → 重新对齐 rubric
- 0.5-0.7 → 分歧样本讨论
- ≥ 0.7 → 可上线标注

---

## 9. 部分成功 trace 的『前后切分』

学员业务真实场景：V1-拒绝内容 `019dd263` 这类 trace **前 70% 是好的，后 30% 被拒绝**。

```python
def split_trace_by_status(trace, business_rules):
    """切分部分成功的 trace
    
    返回 (success_part, rejected_part)：
    - success_part 进 SFT 银数据
    - rejected_part 进 DPO rejected
    """
    success_msgs, rejected_msgs = [], []
    rejected = False
    for msg in trace.messages:
        if msg.type == "tool":
            content = str(msg.get("content", ""))
            if any(sig in content for sig in business_rules.moral_rejection_signals):
                rejected = True
        if rejected:
            rejected_msgs.append(msg)
        else:
            success_msgs.append(msg)
    return success_msgs, rejected_msgs
```

**关键**：成功部分**带上原 trace 的 `source_run_id`**，便于业务方后续 review 时追溯。

---

## 10. 常见误区

### ❌ "我们有 N 万条 trace，数据很多"
实际可用 = 银 + 金 = 2-5 万，剩下大半不能进训练集。

### ❌ "用用户采纳率自动标金"
采纳率只是**一维信号**，可能用户只是"懒得改"。要 2+ 信号交叉。

### ❌ "黑数据也拿来 SFT 当反例"
SFT 学到"错也要学"。黑数据必须通过 DPO 的 rejected 或 RL 的负奖励进。

### ❌ "分级太麻烦，全量训"
**幸存者偏差 + 噪声**会让小模型训出一堆问题。分级是 ROI 最高的工程投入。

### ❌ "教师拒绝当 bug 看"（学员业务必学）
**Claude 道德拒绝是合规信号，是金矿数据**——它告诉你业务方哪些操作是边界 case。

---

## 11. 相关文档

- `01_data_pipeline/design.md` — 数据管线设计（清洗规则 + 双 schema）
- `04_dpo/build_preferences.py` — DPO 数据构造（用 tier 字段过滤）
- `00_overview/anthropic_tos_compliance.md` — 合规审查模板
- `00_overview/project_critique_and_fixes.md` §2 — 数据质量问题背景

---

## 变更记录

- 2026-04-24：首版（通用模板）
- 2026-05-06：增加业务专属规则、PII、SOP 检查、教师道德拒绝处理；用真实数据案例替换通用例子
