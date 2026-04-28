# 学生基座（Student Base）模型选型

> 对应需求文档 "建议：初始模型选 Gemma 同量级基座"。  
> 本文档讨论**学生模型**（被蒸馏出来上线的小模型）选型。  
>
> 配套文档：
> - **教师模型选型**：[`teacher_model_comparison.md`](./teacher_model_comparison.md) - 选谁教（10 款大模型对比）
> - **蒸馏技术选择**：[`../03_sft/distillation_techniques.md`](../03_sft/distillation_techniques.md) - 黑盒/白盒/CoT/On-policy

## 我们的场景特征（选型的约束）

1. **Agent 任务**：多轮对话 + 工具调用（function calling）为主
2. **营销 AI + 研究类输出**：长文本生成、结构化 JSON 并存
3. **中文为主 or 中英混合**（假设 marketing-ai 面向中文场景，如果错请在此文档注明）
4. **成本导向**：主目标就是便宜
5. **LoRA 可微调**：需要活跃的 fine-tuning 生态
6. **Claude fallback 保底**：模型不用 100% 完美

这些约束决定了评分维度——不是"哪个模型最强"，而是"哪个最适合这几个约束"。

## 候选模型总览

| 模型 | 大小 | 许可证 | 发布时间（版本） | 中文 | 工具调用原生 | 社区活跃度 |
|---|---|---|---|---|---|---|
| Gemma 2 | 2B / 9B / 27B | Gemma License | 2024-06 | 中等 | 不原生 | 高 |
| Gemma 3 | 1B / 4B / 12B / 27B | Gemma License | 2025 | 较好（多语言加强） | 有限支持 | 中高 |
| Qwen 2.5 | 0.5B–72B | Apache 2.0（≤7B） / 自有（14B+） | 2024-09 | **强** | **原生支持** | 高 |
| Qwen 2.5-Coder | 1.5B/7B/14B/32B | Apache 2.0 | 2024-09 | 好 | 好 | 高 |
| Qwen 3 | 0.6B–235B（含 MoE） | Apache 2.0（dense）/ 自有（MoE） | 2025-04 | **强** | **原生+思考模式** | 高 |
| Llama 3.1 | 8B / 70B / 405B | Llama Community | 2024-07 | 中等 | 原生（8B 起） | 极高 |
| Llama 3.2 | 1B / 3B | Llama Community | 2024-09 | 中等 | 有限 | 高 |
| Mistral / Ministral | 3B / 7B / 8B | Apache 2.0 / 自有 | 2024 | 一般 | 原生 | 中高 |
| DeepSeek V2-Lite / V3 | 16B MoE（2.4B 激活）/ 大 | 自有宽松 | 2024-2025 | **强** | 原生 | 高 |

## 逐个模型深度分析

### 1. Gemma 2 / Gemma 3（Google）

**优势**
- Google 出品，训练数据质量高，知识覆盖广
- Gemma 2 9B 在同量级英文 benchmark 领先（MMLU / HumanEval）
- PEFT/TRL 社区 LoRA 配置最稳，**教程最多、踩坑少**（适合初学者）
- Gemma 3 多模态 + 更长上下文（最长 128k）+ 多语言加强
- 推理生态成熟：vLLM、Ollama、llama.cpp 都支持

**问题**
- ⚠️ **原生不支持 tool calling 格式**。需要在 SFT 数据中自己定义 `<tool_call>...</tool_call>` 标签，或迁移到有 tool 角色的 chat template
- ⚠️ **中文能力中等**：Gemma 2 的中文训练语料比例低，在纯中文场景会比 Qwen 弱
- ⚠️ **许可证**（Gemma License）：比 Apache 2.0 严格，商用要读条款；禁止特定用途（见 Prohibited Use Policy）
- Gemma 3 发布时间较近，fine-tuning 最佳实践还在沉淀

**适合场景**
- 英文为主的场景
- 团队初次做微调（学习资料最多）
- 工具调用需求不复杂

### 2. Qwen 2.5（阿里）

**优势**
- ✅ **中文能力 top-tier**：预训练数据中文比例高
- ✅ **原生 tool calling**：chat template 内置 `<tool_call>` 和 `tool` 角色
- ✅ **尺寸齐全**：0.5B / 1.5B / 3B / 7B / 14B / 32B / 72B 覆盖所有算力预算
- ✅ **Apache 2.0 许可证**（≤7B 版本）：商用无忧
- 代码版 Qwen 2.5-Coder 在 JSON/结构化输出上非常强
- 长上下文原生 128k

**问题**
- ⚠️ 英文 benchmark 略弱于 Gemma 2 9B（但差距已经很小）
- ⚠️ 14B 及以上版本许可证非 Apache 2.0，要逐个确认
- 7B 的工具调用稳定性在复杂场景下仍需要 SFT 加固

**适合场景**
- **中文场景的首选**
- 需要原生工具调用、JSON 输出稳定
- 对许可证敏感（可选 Apache 2.0 版本）

### 3. Qwen 3（阿里，2025）

**优势**
- ✅ 在 Qwen 2.5 基础上进一步加强推理（引入"thinking"模式，类 o1/R1）
- ✅ MoE 架构版本（如 Qwen3-30B-A3B）激活参数小、推理成本低
- ✅ 原生工具调用 + 思考模式融合，复杂 agent 任务上表现强
- ✅ 中英文都强

**问题**
- ⚠️ **发布较新（2025）**：LoRA/QLoRA 调参最佳实践**不如 Qwen 2.5 稳**
- ⚠️ **思考模式不是所有任务都需要**：对简单 tool calling 任务反而增加 token 开销
- ⚠️ MoE 版本对推理框架兼容性要求高（vLLM 支持还在演进中）
- ⚠️ 社区教程、Kaggle 讨论比 Qwen 2.5 少

**适合场景**
- 复杂 agent 多步推理任务
- 能接受较新生态的团队
- 对 MoE 推理成本敏感且基建允许

### 4. Llama 3.1 8B / Llama 3.2

**优势**
- ✅ 社区**最活跃**，几乎所有 ML 工具都优先支持
- ✅ Llama 3.1 8B 综合能力强，tool calling 官方支持
- ✅ 海量衍生版本（Hermes、OpenChat、WizardLM 等）

**问题**
- ⚠️ **中文能力弱**：预训练语料以英文为主
- ⚠️ Llama Community License：不是 Apache 2.0，月活用户 > 7 亿需要单独授权（大厂要注意）
- ⚠️ Llama 3.2 1B/3B 在复杂工具调用上能力不足

**适合场景**
- 英文场景 + 海量社区插件需求
- 团队已有 Llama 生态

### 5. Mistral / Ministral

**优势**
- Apache 2.0 许可证宽松
- 推理速度快
- 部分衍生版本（Mistral-Small-Instruct）综合能力不错

**问题**
- ⚠️ 中文能力**较弱**
- ⚠️ 更新节奏不如 Qwen/Llama
- ⚠️ 工具调用生态不如 Qwen 2.5

**适合场景**
- 纯英文场景；追求部署速度

### 6. DeepSeek V2-Lite / V3

**优势**
- ✅ MoE 架构激活参数小，推理便宜
- ✅ 中文强、代码强
- ✅ 许可证相对宽松

**问题**
- ⚠️ 模型架构非主流 transformer，LoRA 训练配置要单独调
- ⚠️ 社区 fine-tuning 教程偏少
- ⚠️ V3 参数量大，不完全匹配"Gemma 同量级"的需求描述

**适合场景**
- 团队有 MoE 推理经验
- 需要强中文 + 强代码

---

## 我们场景的推荐

> 前提：面向中文营销 AI，需要 tool calling，团队新手多。

### 主线：Qwen 2.5 7B Instruct（推荐）

**理由**：
1. 中文能力是当前所有开源模型里最好的之一
2. **原生工具调用 chat template**，避免 Gemma 那种要自己"造 schema"的麻烦
3. Apache 2.0，商用无顾虑
4. LoRA / QLoRA 的社区配置非常成熟
5. 模型尺寸 7B 刚好卡在"单卡 A100 80G 能训 LoRA + 单卡 A10/3090 能推理"的甜点

**起步配置**（把这行写进 `03_sft/configs/sft_v2_base.yaml`）：
```yaml
model: Qwen/Qwen2.5-7B-Instruct
tokenizer: Qwen/Qwen2.5-7B-Instruct
```

### 备选 A：Gemma 2 9B Instruct

如果场景以英文为主，或团队坚持"Gemma 级别"这个描述字面理解，用 Gemma 2 9B。
需要额外做：
- 自定义 chat template 支持 tool calling
- SFT 数据里显式构造 `<tool_call>...</tool_call>` 标签
- 人工加入更多中文指令数据以弥补

### 备选 B：Qwen 3 7B（或 MoE 版本）

团队技术储备较强、能接受较新生态，可以直接上 Qwen 3。
**注意**：一定要关闭 thinking 模式做 baseline 对比，再决定是否开启。

### 阶段 1 Benchmark 建议同时测 3 个

```
Claude 3.5 Sonnet (baseline)
├─ Qwen 2.5 7B Instruct       ← 推荐起步
├─ Gemma 2 9B Instruct        ← 需求文档指定的参考
└─ Qwen 3 7B Instruct         ← 探索上限
```

这样阶段 1 末的 DP1 决策文档里有横向数据支持选型。

---

## 选型决策 checklist

填完下面这张表再定型：

- [ ] 主要业务语种是？（中文/英文/混合）
- [ ] 团队有没有调过 Qwen 或 Gemma？
- [ ] 商用许可证是否必须 Apache 2.0？
- [ ] 上线推理的 GPU 是什么？（决定模型尺寸上限）
- [ ] tool calling 场景复杂度？（简单工具查询 vs 多轮 agent）
- [ ] 是否需要思考模式（CoT）？
- [ ] 训练机器是什么？（决定能跑多大的模型 + LoRA/QLoRA）

填完表，回到上面的"推荐"小节二次确认。

## 更新记录
- 2026-04-24：首版，加入 Qwen 2.5 / Qwen 3 / Llama 3.1-3.2 / Mistral / DeepSeek 对比
