# 速查词汇表

> 一页搞定所有术语。细节见 `concepts_and_techniques.md`。

## 🔤 按字母排

| 术语 | 缩写 | 一句话解释 | 深入 |
|---|---|---|---|
| Adapter | — | 微调产出的增量参数，挂在基座上使用 | [PEFT](https://huggingface.co/docs/peft) |
| Batch | — | 一次前向的样本数 | ml_fundamentals §3 |
| BF16 | — | 16bit 浮点，训练首选 | ml_fundamentals §4 |
| Chat Template | — | 把 messages 转成 token 的模板 | `transformers` chat_templating |
| Chosen / Rejected | — | DPO 偏好对里的胜者 / 败者 | concepts §1.4 |
| Constitutional AI | CAI | 用规则集做自我批判的 RL 方法 | concepts §1.7 Anthropic |
| Context Window | — | 模型能处理的最大 token 数 | — |
| Continual Pre-training | CPT | 在基座上继续预训练 | — |
| DPO | Direct Preference Optimization | 用偏好对直接训练，不需要奖励模型 | concepts §1.4 |
| Epoch | — | 数据集过一遍完整训练 | ml_fundamentals |
| Eval Loss | — | 验证集上的 loss，看过拟合 | ml_fundamentals §11 |
| Fallback | — | 主模型失败时退到备用模型 | serving |
| Few-shot | — | prompt 里给几个例子 | — |
| Flash Attention | — | 加速 attention 计算的实现 | ml_fundamentals §7 |
| FSDP | Fully Sharded Data Parallel | PyTorch 原生的分布式训练 | ml_fundamentals §8 |
| Function Calling | Tool Calling | 模型调用工具的能力 | — |
| Golden Set | 黄金集 | 200 条人工精标的基准 | eval_spec |
| Gradient Accumulation | grad_accum | 累积多步梯度再 update | ml_fundamentals §3 |
| Gradient Checkpointing | — | 省显存但慢 | ml_fundamentals §5 |
| GRPO | Group Relative Policy Optimization | DeepSeek R1 用的 RL | concepts §1.8 |
| HF | Hugging Face | 模型 / 数据集社区 | huggingface.co |
| Judge / LLM-as-Judge | — | 用强模型给弱模型打分 | concepts §1.7 |
| KTO | Kahneman-Tversky Optimization | 不要成对偏好，只要 good/bad 标签 | concepts §1.9 |
| LangSmith | — | LangChain 的观测平台 | concepts §1.1 |
| Latency | — | 时延 | — |
| Learning Rate | lr | 梯度更新的步长 | ml_fundamentals §2 |
| LoRA | Low-Rank Adaptation | 低秩旁路微调 | concepts §1.2 |
| Loss Mask | — | 只在 assistant 部分算 loss | sft_guide §3.3 |
| Middleware | — | 横向注入 agent 的中间件 | v2_benchmark |
| Mixed Precision | — | bf16/fp16 混合训练 | ml_fundamentals §4 |
| ORPO | Odds Ratio Preference Optimization | SFT+DPO 合成一步 | concepts §1.5 |
| Overfitting | 过拟合 | 训好测差 | ml_fundamentals §11 |
| PagedAttention | — | vLLM 的内存管理技术 | vLLM docs |
| PEFT | Parameter-Efficient Fine-Tuning | LoRA 等参数高效方法的总称 | HF PEFT |
| Perplexity | PPL | exp(loss)，困惑度 | ml_fundamentals §10 |
| PPO | Proximal Policy Optimization | RL 算法，ChatGPT 用的 | concepts §1.6 |
| PRM | Process Reward Model | 过程奖励模型 | 08_rl_future |
| QLoRA | — | 4bit 量化 + LoRA | concepts §1.2 |
| Quantization | 量化 | fp16 → int8/int4 | — |
| Reference Model | ref_model | DPO 的参考模型（冻结） | concepts §1.4 |
| Report Progress | — | V2 agent 报告进度的工具 | v2_benchmark |
| Reward Hacking | — | 模型找到 reward 漏洞 | concepts §1.6 |
| RLHF | RL from Human Feedback | 人类反馈强化学习 | concepts §1.6 |
| RLAIF | RL from AI Feedback | AI 反馈强化学习 | concepts §1.7 |
| Router | 路由 | 选择哪个模型处理请求 | serving |
| Sampling | 采样 | 从概率分布里抽 token | ml_fundamentals §12 |
| Schema | — | JSON 结构定义 | — |
| Self-consistency | — | 多次采样投票 | — |
| SFT | Supervised Fine-Tuning | 监督微调 | concepts §1.3 |
| SimPO | Simple Preference Optimization | 不要 ref model 的 DPO 变体 | concepts §1.10 |
| Skill | — | V2 agent 加载的工具集合 | v2_benchmark |
| Submit Final Report | — | V2 agent 提交最终结果的工具 | v2_benchmark |
| System Prompt | — | 给模型的角色和约束说明 | — |
| Temperature | — | 采样温度，0 贪心，>1 随机 | ml_fundamentals §12 |
| TensorRT-LLM | — | NVIDIA 的 LLM 推理库 | — |
| Tokenizer | — | 把文本转成 token | ml_fundamentals §13 |
| Tool Call | tool_call | 模型要调用的工具 | — |
| Top-p / Top-k | — | 采样策略 | ml_fundamentals §12 |
| Trace | — | 一次 agent 运行的完整轨迹 | concepts §1.1 |
| TRL | Transformer RL | HF 的微调库 | learning_resources §2.3 |
| Unsloth | — | LoRA 加速库 | learning_resources |
| Vllm | — | LLM 推理引擎 | vLLM docs |
| W&B | Weights & Biases | 实验追踪 | wandb.ai |
| Warmup | — | 训练初期 lr 从 0 升起 | ml_fundamentals §2 |
| Zero-shot | — | 不给例子直接问 | — |

## 项目内部术语

| 术语 | 含义 |
|---|---|
| V1 | 旧架构 agent-service，多节点流程 |
| V2 | 当前主线 DeerFlow / MarketingAI，单循环 agent |
| DP1-DP5 | 5 个关键决策点 |
| 黄金集 | 200 条人工精标 benchmark |
| 回放集 | 历史 trace 抽样的 benchmark |
| 压测集 | 长输入 / 并发测试集 |
| fallback | 小模型失败时退 Claude |
| sanity check | 快速输出合法性检查 |

## 单位

- **参数量**：1B = 10 亿，7B = 70 亿
- **Token**：约 1 汉字 = 1-2 token，1 英文词 = 1-1.5 token
- **1M tokens**：100 万 tokens
- **1 epoch**：数据集完整过一遍
