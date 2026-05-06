# 项目方案反思与改进 —— 6 大问题逐项对策

> 客户/Reviewer 提出的 6 条核心问题，本文档**总分结构**：先给整体观点，再逐条详解解决方案。
> 这些问题比"选哪个算法"更决定项目成败。

---

## 总览：一句话总结 6 大问题

| # | 问题 | 核心要害 | 优先级 |
|---|---|---|---|
| 1 | 目标定义模糊 | 没锁尺寸、没定任务切片、没量化 KPI | 🔴 P0 |
| 2 | 数据源单一 + 幸存者偏差 | 只学成功，没学失败 | 🔴 P0 |
| 3 | Benchmark 设计缺关键维度 | 没诊断指标、没对照组、人工评分无 rubric | 🔴 P0 |
| 4 | 训练路线存在逻辑漏洞 | SFT→DPO→RL 不是线性修复 | 🟡 P1 |
| 5 | 工程与回退机制缺失 | "保留 Claude fallback"只是一句话 | 🔴 P0 |
| 6 | 风险评估不完整 | 缺合规 / 模型迭代 / tool schema 漂移 / TCO 反直觉 | 🟡 P1 |

**共性问题**：方案在"做什么"层面清晰，但"**能落地吗**"层面缺具体抓手。

---

## 问题 1：目标定义模糊

### 1.1 原方案的问题

- ❌ "Gemma 级别"未锁定参数规模（2B/7B/9B/27B 差距巨大）
- ❌ "替代部分 Claude 能力"未定义哪部分
- ❌ 没量化成功标准（成本、质量、覆盖比例）

### 1.2 改进方案：按**任务切片**定 KPI

**不再说"替代 Claude"，而是列出具体替代点**：

| 任务切片 | 描述 | 替代优先级 | KPI |
|---|---|---|---|
| `progress_report` 生成 | agent 中间进度文本 | 🟢 高（低风险） | 成本 ≤ Claude 15%，业务评分 ≥ 4.0/5 |
| `skill_routing` 路由 | 选用哪个 skill | 🟢 高 | 准确率 ≥ 95%，P95 ≤ 500ms |
| 工具参数构造 | 生成 tool_call arguments | 🟡 中 | JSON 合法率 ≥ 99%，字段命中 ≥ 90% |
| 简单查询应答 | 单工具 + 短输出 | 🟡 中 | 成功率 ≥ 85% |
| `submit_final_report` 写作 | 长文本合成 | 🔴 低（风险大） | 人工 4.0/5 |
| 复杂多步规划 | 10+ 轮 agent | ⚫ 不替代 | 保留 Claude |

### 1.3 具体改动

**修改**：`06_decisions/DP1_train_or_not.md`
- 加"任务切片列表"
- 每个切片单独定 KPI（成本上限 / 质量下限 / 时延 P95）

**修改**：`02_benchmark/eval_spec.md`
- 按切片分报告
- 每切片独立阈值

**修改**：学生基座选型
- **锁定 Qwen 2.5 7B** 为首选（`base_model_selection.md` 已改）
- 或根据切片分配不同基座（进阶）

---

## 问题 2：数据源单一 + 幸存者偏差

### 2.1 原方案的问题

- ❌ 只用 LangSmith trace = 只有 Claude "成功路径"
- ❌ 小模型天花板 ≤ Claude
- ❌ 继承 Claude 所有错误模式
- ❌ 没有 trace 的**质量过滤机制**
- ❌ V1 / V2 schema 不同

### 2.2 改进方案：三层数据分级 + 分布补齐

**核心洞察**：不是所有 trace 都能进训练集。

#### 三层分级

```
金数据 (Gold) - 1-5%
  - 人工标注 / 用户显式采纳 / 任务闭环完成
  - 用于：SFT 训练 + 黄金 benchmark
  - 认证：2 人标注一致

银数据 (Silver) - 20-40%
  - 启发式过滤：无 error、无重试、submit_final_report 被采纳
  - 用于：SFT 训练（混入金数据后）
  - 去重 + 规则清洗

铜数据 (Bronze) - 其余
  - 原始 trace，有错误、有取消
  - 用于：benchmark 回放（测失败模式）
  - **不进训练集**

黑数据 (Trash)
  - 用户显式 downvote / 复现的 bug case
  - 用于：负样本（DPO rejected）/ 反例测试
  - 不直接进 SFT
```

#### 分布补齐

- 光靠 trace 会偏向"已见过的"分布
- **加合成数据**（CoT / Evol-Instruct）扩展分布
- **加失败样本人工构造**补齐长尾

### 2.3 具体改动

**新文档**：`01_data_pipeline/data_quality_tiers.md` - 金/银/铜/黑分级的具体规则和代码

**修改**：`01_data_pipeline/clean.py`
- 加 `tier` 字段打标
- 输出按 tier 分文件

**修改**：`01_data_pipeline/extract_fields.py`
- 导出训练集时只用金 + 银
- 铜/黑只进 benchmark

**修改**：`build_datasets.py`
- 加 tier 配比参数

---

## 问题 3：Benchmark 设计缺关键维度

### 3.1 原方案的问题

- ❌ 只有结果指标（成功率、工具调用率），缺诊断指标
- ❌ 没 baseline 对比组（Claude-Haiku / GPT-4o-mini / Gemma-base）
- ❌ "人工业务评分"无 rubric，不可复现

### 3.2 改进方案：三层指标 + 三组对照 + Rubric 化

#### 三层指标

| 层 | 指标例 | 用途 |
|---|---|---|
| **结果** | 成功率、工具调用 F1 | 总结表现 |
| **诊断** | 首 token 延迟、JSON 合法率、步骤数分布、幻觉率、指令遵循率 | 定位问题 |
| **业务** | 采纳率、NPS、时延 P95 | 真实价值 |

#### 三组对照组

| 组 | 角色 | 作用 |
|---|---|---|
| Claude 3.5 Sonnet | 上限 | 目标 |
| Claude-Haiku / GPT-4o-mini | 同价位竞品 | 横向 |
| Gemma-base / Qwen-base（未训） | 下限 | 训练增益量化 |

#### Rubric 化人工评分

**双盲**：标注人不知道哪个是小模型 / Claude。

**Rubric**：每维度明确 1-5 分的**行为描述**，不是"感觉好不好"。例：
```
可用性（Usability）
5: 输出可直接采纳，无需修改
4: 轻微调整（换 1-2 个词）即可采纳
3: 中等修改（改结构或补充 1 段）可采纳
2: 重写主要部分才能用
1: 完全不可用
```

**一致性**：计算 Cohen's Kappa ≥ 0.7，否则重培训标注人。

### 3.3 具体改动

**修改**：`02_benchmark/eval_spec.md`
- 拆"结果/诊断/业务"三层
- 加对照组列表
- Rubric 详细化（附录）

**修改**：`02_benchmark/harness/metrics.py`
- 加诊断指标实现：`FirstTokenLatency` / `StepsDistribution` / `HallucinationRate`

**新文档**：`02_benchmark/annotation_guide.md`
- 标注规程
- Rubric 细则
- Kappa 计算脚本

---

## 问题 4：训练路线存在逻辑漏洞

### 4.1 原方案的问题

- ❌ 假设 SFT → DPO → RL 线性"修复前阶段问题"
- ❌ SFT 噪声 DPO 无法修复（DPO 放大偏好）
- ❌ 没说明 DPO 偏好对从哪来
- ❌ 没提灾难性遗忘
- ❌ "Gemma 同量级"— Gemma tool-calling 弱

### 4.2 改进方案

#### 4.2.1 SFT 前增加"数据配比实验"

在正式 SFT 前，先跑 5 组小实验：

| 实验 | 业务数据 : 通用数据 | 目标 |
|---|---|---|
| A | 100% : 0% | 最激进，看有没有灾难性遗忘 |
| B | 90% : 10% | |
| C | 70% : 30% | 推荐起点 |
| D | 50% : 50% | 保守 |
| E | 0% : 100% | 对照（应无业务能力） |

每组跑 1 epoch，看业务 benchmark + 通用 benchmark（MMLU / C-Eval）变化。

#### 4.2.2 明确 DPO 偏好对来源

已在 `04_dpo/build_preferences.py` 实现三种来源：
- 来源 A：LangSmith 历史挖掘
- 来源 B：SFT 采样 + Claude-as-judge 排序
- 来源 C：合规教师 vs SFT 对比（Claude 仅限书面许可后）

**补强**：
- Claude-as-judge 的 prompt **必须稳定版本化**
- **人工抽检 10%** 双轨（必须加，防 judge bias）

#### 4.2.3 基座选型做 Pilot

不预设 Gemma。跑 pilot：

| 候选 | 量级 | 评分维度 |
|---|---|---|
| Qwen 2.5 7B | 7B | 中文强、tool-calling 原生 |
| Llama 3.1 8B | 8B | 英文强 |
| Gemma 2 9B | 9B | Google 出品 |
| DeepSeek-R1-Distill-Qwen-7B | 7B | 已蒸馏，直接测 |
| Qwen 2.5 14B | 14B | 大一号 |

**Pilot 方法**（见 `00_overview/base_model_pilot.md`）：
- 用黄金集 500 条
- 每个基座做 zero-shot + few-shot + LoRA 训 200 条的小实验
- 用同样 benchmark 打分

#### 4.2.4 灾难性遗忘检测

每版 adapter 训完必测：
- 业务 benchmark（本项目的）
- 通用 benchmark：MMLU / CMMLU / GSM8K / HumanEval 抽样
- 如果通用掉 > 5% → 回滚 / 加通用数据

### 4.3 具体改动

**修改**：`03_sft/sft_guide.md` §4 加"配比实验"小节
**新文档**：`00_overview/base_model_pilot.md` - Pilot 方法论
**修改**：`04_dpo/build_preferences.py` 加"10% 人工抽检"步骤
**修改**：`02_benchmark/harness/metrics.py` 加通用能力抽样测试

---

## 问题 5：工程与回退机制缺失

### 5.1 原方案的问题

- ❌ "保留 Claude fallback" 一句话，没说**怎么触发**
- ❌ 没有 shadow / canary 细则
- ❌ 没有线上持续评估 + 数据回流

### 5.2 改进方案：回退触发器 + 三阶上线 + 在线评估

#### 5.2.1 Fallback 触发条件（5 条任一）

| 触发器 | 阈值 | 动作 |
|---|---|---|
| **置信度** | top-1 logprob < 阈值 | fallback |
| **Schema 校验失败** | tool_call JSON 不合法 | fallback |
| **重试失败** | 同 prompt 重试 N 次还错 | fallback |
| **超时** | 小模型推理 > 15s | fallback |
| **业务规则** | 任务 tag ∈ CRITICAL_SET | 强制 Claude |

#### 5.2.2 三阶上线路径

```
1. Offline benchmark      ── 离线通过阈值
2. Shadow evaluation      ── 小模型跑但不用结果，每天对比
3. 5% Canary              ── 真实用小模型响应 5% 流量
4. 20% → 50% → 100%       ── 逐步放量
```

**每阶段守门**：关键指标不降 + P0 事故 = 0

#### 5.2.3 在线评估与数据回流

- **每日采样 5%** 流量双跑 Claude + 小模型，自动存差异
- **业务方每周 review** 10 条差异大的 case
- **采纳率追踪**：小模型输出被用户采纳 / 修改 / 弃用的比例
- **数据回流**：采纳 → 金数据；弃用 → 黑数据

### 5.3 具体改动

**新文档**：`05_serving/fallback_engineering.md` - 完整回退工程化
**修改**：`05_serving/router.py` - 加 logprob 置信度 / schema 校验 / 重试
**修改**：`05_serving/rollout_plan.md` - 加 shadow evaluation 阶段
**新文档**：`05_serving/online_evaluation.md` - 线上双跑与数据回流

---

## 问题 6：风险评估不完整

### 6.1 原方案的问题

- ❌ 合规：Claude 蒸馏可能违反 Anthropic ToS
- ❌ 模型迭代：Claude 升级后数据过期
- ❌ Tool schema 漂移：业务工具签名变了
- ❌ 成本反直觉：QPS 低时自托管 TCO 反而高

### 6.2 改进方案：四大隐性风险专项

#### 6.2.1 Anthropic ToS 合规

**新文档**：`00_overview/anthropic_tos_compliance.md`

核心问题：
- Anthropic ToS 是否明确禁止用 Claude 输出训小模型？
- "竞品"定义？对**内部业务**使用是否豁免？
- 数据用途声明是否需更新？

**行动**：
1. Legal 第 1 周内出具白皮书
2. 替代方案准备：若被禁止，改用 Qwen 72B 教师（`teacher_model_comparison.md` 备选方案 A）
3. 风险等级定档：法律风险 vs 成本收益

#### 6.2.2 模型迭代追踪

**机制**：
- Claude 每次升级（3.5 → 4 等），**评估是否需要重训**
- 建立"数据版本 vs Claude 版本"矩阵
- 定期 benchmark：新 Claude 对 benchmark 分数是否变化大 → 触发重训

**频率**：每 3-6 月重评估。

#### 6.2.3 Tool Schema 漂移

**风险**：业务方改了 `search` 工具参数，小模型还在用旧格式 → 线上错误率飙升。

**对策**：
1. **工具 schema 版本化**：在 DB 存 schema 版本号
2. **训练时记录 schema hash**：adapter 和 schema 绑定
3. **上线前 schema diff 检查**：新 schema 和 adapter 训练时的 schema 不一致 → 告警
4. **灰度时双路径**：工具 schema 改了先灰度再全量

#### 6.2.4 TCO 反直觉

**风险**：自托管 GPU 成本 vs Claude API 成本，QPS 低时可能**自托管反而贵**。

**分析**：
```
Claude: $0.0135 / 次 × 日 N 次 = 月成本 (按量)
自托管 A100 40G: $1500/月（固定）
盈亏平衡点：N = 1500 / 30 / 0.0135 = ~3700 次/日
```

**结论**：
- 日调用 < 3700 次：Claude 更便宜
- 日调用 > 3700 次：自托管开始省钱
- 日调用 > 50000 次：自托管大幅省钱

**对策**：
- 方案 ROI 分析（`07_budget/cost_breakdown.md`）加"盈亏平衡点"
- 灰度上线前先确认 QPS 达到盈亏点
- 不达标 → **先用 API 调用开源模型**（硅基流动 / 阿里云 / AWS Bedrock），QPS 上来了再自托管

### 6.3 具体改动

**新文档**：
- `00_overview/anthropic_tos_compliance.md`
- `05_serving/schema_version_management.md`

**修改**：
- `00_overview/compliance_and_safety.md` - 加 ToS 专章
- `07_budget/cost_breakdown.md` - 加盈亏分析
- `06_decisions/DP1` - 加合规审查项

---

## 优先级与行动计划

### P0（必须立即做）

1. **Anthropic ToS 合规审查**（第 1 周）
2. **锁定 1-2 个低风险子任务做 POC**（不是全盘开训）
3. **数据三层分级 + V1/V2 物理隔离**（第 2 周前）
4. **Benchmark rubric 化 + Kappa 验证**（第 3 周前）
5. **Fallback 触发器工程化**（上线前必须）

### P1（第一阶段跑通后补）

1. 基座 Pilot 对比（第 3-4 周）
2. Shadow evaluation 机制（阶段 4 前）
3. 配比实验 + 灾难性遗忘防护（阶段 2 中）
4. 在线双跑 + 数据回流（灰度期间）

### P2（稳态后持续）

1. Claude 版本追踪
2. Tool schema 版本管理
3. TCO 季度 review

---

## 给客户/老板的口头版

**客户**："我怎么知道你们这方案不会踩坑？"

**我们**：
> 6 个关键风险我们都识别了：
>
> - **目标太宽**：我们按任务切片定 KPI，不是大而全替代
> - **数据偏差**：三层分级，只有金 + 银进训练集
> - **评估不稳**：加诊断指标 + 3 组对照 + rubric 人工评分
> - **训练路线坑**：每阶段做配比实验 + 灾难性遗忘检测
> - **上线出事**：5 条 fallback 触发器 + 三阶灰度 + 在线双跑
> - **合规/成本**：Anthropic ToS 第 1 周审查 + TCO 盈亏分析
>
> 这 6 条比选 SFT / DPO 更关键，我们已经在方案里每条都有对应文档和对策。

---

## 变更记录
- 2026-04-24：首版，对应客户 6 问
