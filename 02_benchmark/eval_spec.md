# 评估规范（Eval Spec）

> 这是整个项目的**单一真源**。改动走 PR，业务 lead 签字。  
> 每一次 benchmark 报告都引用一个 spec 版本号。

**当前版本：v1.0（2026-04-24）**

---

## 1. 适用范围

本规范定义"一次 agent 运行"的评估口径。**V1 和 V2 各自维护独立 spec**（同名不同版本），本模板是通用骨架。

## 2. 评估对象

一条 agent trace，包含：
- 用户初始输入
- system prompt / skills_loaded
- 所有 LLM 调用 + 工具调用序列
- 最终状态（success / error）
- 最终输出（如 `submit_final_report`）

## 3. 评估维度

### 3.1 技术维度（自动）

| 维度 | 指标 | 口径 |
|---|---|---|
| 是否完成 | **SuccessRate** | `final_status == expected_status` 的样本占比 |
| 工具调用 | **ToolCallExactMatch** | 调用序列完全匹配 golden |
| 工具调用 | **ToolCallF1** | 调用集合 F1（容忍顺序） |
| 格式 | **JSONValidRate** | tool_call arguments 是合法 JSON 的比例 |
| 格式 | **SchemaValidRate** | tool_call arguments 符合工具声明的 schema |
| 性能 | **LatencyP50/P95** | 端到端耗时 |
| 性能 | **TokensPerCase** | 平均消耗 token |
| 性能 | **CostPerCase** | 按模型计价折算 |

### 3.2 业务维度（LLM-as-Judge）

| 维度 | 指标 | 量表 |
|---|---|---|
| 输出可用性 | **Usability** | 1-5（1=完全不能用，5=直接采纳） |
| 输出相关性 | **Relevance** | 1-5 |
| 输出完整性 | **Completeness** | 1-5 |
| 风格一致性 | **StyleFit** | 1-5 |

**Judge 模型**：Claude 3.5 Sonnet 或 GPT-4o（固定一个，跨批次对比才公平）。  
**Prompt 模板**：见附录 A。

### 3.3 业务维度（人工）

**必须人工的样本**：
- 黄金集 200 条全标（每版模型都标）
- 每批次额外随机抽 30 条（发现 judge bias 用）

**标注量表**（和 LLM-as-Judge 对齐但独立标）：
- 可用性 1-5
- 是否采纳（yes/no/修改后采纳）
- 失败原因分类（见 3.4）
- 自由备注

**标注人**：2 人独立标，分歧进入第三人决。

### 3.4 失败原因分类（标注用）

```
F01  理解错误：误解用户意图
F02  工具调用错误：调错工具 / 少调 / 多调
F03  工具参数错误：参数值/类型/格式不对
F04  工具结果误用：结果读错/漏读
F05  JSON 格式错误
F06  输出内容错误：事实错
F07  输出风格不对
F08  输出不完整：早停/截断
F09  死循环/重复
F10  其他
```

## 4. 评估流程

### 4.1 Benchmark 集构成

- **黄金集**：200 条，人工复核过，贯穿整个项目
- **回放集**：从历史 trace 抽样，用于回归测试（每批 1000 条左右）
- **压测集**：长输入/并发/高负载（阶段 4 灰度用）

三种集都是 `benchmark_golden.jsonl` 同一格式（见 `01_data_pipeline/design.md`）。

### 4.2 每次 benchmark 必做

1. 固定 `seed`（推理用的采样种子）
2. 固定基座模型版本 + adapter 版本
3. 固定 system prompt + tool schema（存 git hash）
4. 固定 spec 版本号
5. 跑完所有维度指标
6. 输出报告 markdown + JSON raw

### 4.3 报告必须包含

- spec 版本号
- 模型版本 + adapter SHA
- benchmark 集版本
- 每维度指标对比表
- 10 条最坏失败 case 示例
- 3 条"judge 打分 vs 人工打分"分歧样本
- 成本、时延分布图（直方图）

## 5. 阈值（示例，按业务调）

| 指标 | 研发阈值 | 上线阈值 |
|---|---|---|
| SuccessRate | ≥ 70% | ≥ 85% |
| ToolCallF1 | ≥ 0.80 | ≥ 0.90 |
| JSONValidRate | ≥ 0.95 | ≥ 0.99 |
| Usability（人工均分） | ≥ 3.5 | ≥ 4.0 |
| LatencyP95 | ≤ 30s | ≤ 15s |
| CostPerCase | ≤ Claude × 0.3 | ≤ Claude × 0.2 |

阈值由业务 lead 签字后生效。改阈值走 PR。

## 6. V1 / V2 隔离规则

- V1 和 V2 用**不同的 spec 文件**：`eval-spec-v1.md` 和 `eval-spec-v2.md`
- 两套 benchmark 集**不共用**
- 报告**必须声明** arch 版本，不做跨 arch 平均
- Dashboard 分开显示

## 7. 评估的边界 / 已知局限

这些事评估测不出来，要靠人工 / 线上监控：
- 用户主观满意度
- 长期会话上下文（我们 benchmark 都是单 task 级别）
- 边缘 case（训练/benchmark 集都覆盖不到的输入）
- 多样性（同 prompt 采样多次输出的丰富度）

所以 benchmark 高分 ≠ 可以上线。灰度 + 线上监控不能省。

---

## 附录 A：LLM-as-Judge Prompt 模板

```text
你是一个严格的营销内容评估专家。

用户输入：
{user_input}

AI 输出：
{ai_output}

标准参考（可选）：
{golden_output}

评估维度（每项 1-5 分，整数）：
1. 可用性（Usability）：输出是否可直接使用
2. 相关性（Relevance）：是否回应了用户意图
3. 完整性（Completeness）：是否覆盖了必要内容
4. 风格一致性（StyleFit）：语气/格式是否符合营销场景

严格要求：
- 每一项打分必须伴随一句话理由
- 如果有严重问题（事实错/格式崩/无法执行），可用性必须 ≤ 2

输出 JSON：
{
  "usability": {"score": N, "reason": "..."},
  "relevance": {"score": N, "reason": "..."},
  "completeness": {"score": N, "reason": "..."},
  "style_fit": {"score": N, "reason": "..."}
}
```

## 附录 B：人工标注界面要求

最低要求：一个带以下字段的 Google Sheet 或 Label Studio：
- case_id
- user_input（只读）
- ai_output（只读）
- usability(1-5)
- adopted(yes/no/modified)
- failure_code（F01-F10 多选）
- notes（自由文本）

不要让标注人看模型名字（避免品牌偏见）。两个标注人独立填完再汇总。

---

## 变更记录

- **v1.0** 2026-04-24：首版
