# 实施方案总览

## 系统架构

```
┌────────────────────────────────────────────────────────────────┐
│                     LangSmith（数据源）                         │
└──────────────────┬─────────────────────────────────────────────┘
                   │ trace export
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  1. 数据管线 (01_data_pipeline/)                              │
│    trace 拉取 → 清洗 → 字段抽取 → 数据集构建                  │
│    产出：SFT 集 / 偏好对 / benchmark 回放集                    │
└──────────────────┬───────────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   SFT 数据    偏好数据    Benchmark 集
        │          │          │
        ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────┐
│  2. 训练 (03_sft/ + 04_dpo/)                                  │
│    LoRA/QLoRA 适配器；基座 Gemma 2/3 或 Qwen 2.5              │
└──────────────────┬───────────────────────────────────────────┘
                   │ adapter
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  3. 推理服务 (05_serving/)                                    │
│    vLLM + OpenAI 兼容接口                                      │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  4. 路由层                                                    │
│    规则路由 + Claude fallback + 超时降级                       │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
           DeerFlow / V1 agent-service
```

## 分阶段路线

| 阶段 | 时长 | 核心产出 | 退出条件 | 决策点 |
|---|---|---|---|---|
| 0. 准备 | 1 周 | 环境、仓库骨架 | 能本地跑通 HF 推理 demo | — |
| 1. 数据+Benchmark | 2-3 周 | 两套 benchmark + 基线报告 | V1/V2 对比表出炉 | **DP1** 是否训练 |
| 2. SFT（条件） | 3-4 周 | Gemma LoRA adapter | 关键指标 ≥ 阈值 | **DP2** DPO 必要性 |
| 3. DPO/ORPO（条件） | 2-3 周 | 偏好对齐 adapter | 人工评分显著提升 | **DP3** 回滚 or 上线 |
| 4. 灰度 | 2 周 | 路由+监控+线上服务 | 线上指标达标 | **DP4** 全量 |
| 5. RL | 暂缓 | 仅前置调研 | — | **DP5** 未来评估 |

## 技术栈选型表

| 层 | 选型 | 理由 |
|---|---|---|
| 数据存储 | Parquet + DuckDB | trace 嵌套大，列存省空间+SQL 查询方便 |
| 数据 SDK | `langsmith` Python SDK | 官方 |
| 数据处理 | `pandas` / `polars` | polars 对大文件更快 |
| 评估 harness | 自研 Python framework | 工具调用场景现成框架不合用 |
| LLM-as-Judge | Claude 3.5 Sonnet / GPT-4o | 作为裁判质量够 |
| 基座模型 | **Gemma 2 9B IT** 主；Qwen 2.5 7B 备 | 需求明确"Gemma 级别" |
| 微调框架 | `transformers` + `peft` + `trl` | 行业标准 |
| 量化 | `bitsandbytes`（QLoRA 4bit） | 单 A100 能跑 9B |
| 推理 | `vLLM`（线上）+ `ollama`（开发） | vLLM 吞吐好；Ollama 开发体验好 |
| 实验追踪 | Weights & Biases | 免费层够用 |
| 路由 | LiteLLM 或自写 FastAPI | LiteLLM 支持多模型+fallback |

## 目录结构（生产仓库建议）

```
small-model-distill/
├── data/
│   ├── raw/                 # LangSmith 原始 trace (parquet)
│   ├── processed/           # 清洗后（V1/V2 分开）
│   └── datasets/            # 最终训练集 (jsonl)
├── benchmark/
│   ├── harness/             # 本 distill_plan/02_benchmark/harness 的生产版本
│   ├── cases/               # benchmark 样本
│   └── reports/             # markdown 报告
├── training/
│   ├── sft/
│   ├── dpo/
│   └── configs/             # YAML 超参
├── inference/
│   ├── serve.py
│   └── router.py
└── docs/
    ├── eval-spec.md         # 评估口径（唯一真源）
    └── runbook.md
```

## 关键风险与应对

| 风险 | 应对 |
|---|---|
| 历史数据噪声高 | 阶段 1 留 40% 时间做清洗；人工标注 200 条黄金集 |
| V1/V2 混测 | 物理隔离 dataset、benchmark、dashboard |
| 评估口径漂移 | `eval-spec.md` 唯一真源，改动走 PR |
| 工具调用 JSON 失效 | SFT 阶段起步就 track JSON 有效率；必要时约束解码 |
| 业务方评分标准不稳 | 强制 2 人标注+争议第三人；记录分歧用例 |
