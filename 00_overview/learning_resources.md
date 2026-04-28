# 学习资源索引（带链接）

> 给初学者的"按概念查阅表"。每个术语都附：
> - 📄 核心论文 / 官方文档
> - 📝 推荐博客（含中文）
> - 💻 开源代码仓库
> - 🎥 视频 / 课程
> - 🎯 难度标签：🟢 入门 / 🟡 进阶 / 🔴 深入

关联文档：`concepts_and_techniques.md`（术语解释）。本文只放链接和简评。

---

## 0. 入门路线图（按顺序学）

**零基础 → 能动手跑 LoRA**：大约 3-5 天
1. LLM 基础概念（🟢）
2. HuggingFace Transformers 入门（🟢）
3. LoRA 原理（🟢）
4. 跑通第一个 LoRA demo（🟡）
5. Chat template / tokenization 细节（🟡）

**进阶 → 能独立做 SFT + DPO**：大约 2-3 周
6. Chat template 细节 + 工具调用格式（🟡）
7. 数据清洗实践（🟡）
8. SFT 超参调优（🟡）
9. DPO 原理（🔴）
10. 评估体系设计（🟡）

**深入 → 能读 RL 论文**：额外 1-2 月
11. PPO 基础（🔴）
12. DPO / ORPO / SimPO 论文（🔴）
13. GRPO 论文（🔴）

---

## 1. LLM 基础

### 1.1 Transformer / Attention
- 📄 [Attention Is All You Need (Vaswani et al., 2017)](https://arxiv.org/abs/1706.03762) 🔴
- 📝 [Jay Alammar - The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/) 🟢【强烈推荐】
- 📝 [The Annotated Transformer (Harvard NLP)](http://nlp.seas.harvard.edu/annotated-transformer/) 🟡 带 PyTorch 代码
- 🎥 [3Blue1Brown - Transformer 可视化系列](https://www.youtube.com/watch?v=wjZofJX0v4M) 🟢
- 📝 中文：[苏剑林博客 - Transformer 升级之路系列](https://spaces.ac.cn/archives/8130) 🟡

### 1.2 LLM 推理 / Sampling
- 📝 [HuggingFace - How to generate text](https://huggingface.co/blog/how-to-generate) 🟢
- 📝 [Temperature, top-k, top-p 详解](https://peterchng.com/blog/2023/05/02/token-selection-strategies-top-k-top-p-and-temperature/) 🟢
- 💻 [llama.cpp](https://github.com/ggerganov/llama.cpp) 🟡 看代码理解推理细节

### 1.3 Tokenization
- 📝 [HuggingFace - Tokenizer summary](https://huggingface.co/docs/transformers/tokenizer_summary) 🟢
- 🎥 [Andrej Karpathy - Let's build the GPT Tokenizer](https://www.youtube.com/watch?v=zduSFxRajkE) 🟡 2 小时视频，极其清楚

---

## 2. HuggingFace 生态

### 2.1 Transformers
- 📄 [官方文档](https://huggingface.co/docs/transformers) 🟢
- 📝 [HF Course（免费）](https://huggingface.co/learn/nlp-course) 🟢 **最推荐入门**
- 💻 [transformers 源码](https://github.com/huggingface/transformers) 🟡

### 2.2 PEFT（参数高效微调）
- 📄 [PEFT 官方文档](https://huggingface.co/docs/peft) 🟢
- 📝 [PEFT LoRA conceptual guide](https://huggingface.co/docs/peft/conceptual_guides/lora) 🟢 **必读**
- 💻 [peft GitHub](https://github.com/huggingface/peft) 🟡
- 📝 [QLoRA 实战 (HF Blog)](https://huggingface.co/blog/4bit-transformers-bitsandbytes) 🟡

### 2.3 TRL（Transformer RL / 微调库）
- 📄 [TRL 官方文档](https://huggingface.co/docs/trl) 🟡
- 💻 [trl GitHub](https://github.com/huggingface/trl) 🟡
- 📝 [SFTTrainer tutorial](https://huggingface.co/docs/trl/sft_trainer) 🟢
- 📝 [DPOTrainer tutorial](https://huggingface.co/docs/trl/dpo_trainer) 🟡
- 📝 [ORPOTrainer tutorial](https://huggingface.co/docs/trl/orpo_trainer) 🟡

### 2.4 Datasets
- 📄 [datasets 官方文档](https://huggingface.co/docs/datasets) 🟢
- 📝 [Processing text with datasets](https://huggingface.co/docs/datasets/nlp_process) 🟢

### 2.5 Accelerate / DeepSpeed / FSDP
- 📄 [Accelerate docs](https://huggingface.co/docs/accelerate) 🟡
- 📝 [DeepSpeed ZeRO 原理](https://www.deepspeed.ai/tutorials/zero/) 🔴
- 📝 [FSDP 入门](https://pytorch.org/tutorials/intermediate/FSDP_tutorial.html) 🔴

---

## 3. LoRA / QLoRA

- 📄 [LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)](https://arxiv.org/abs/2106.09685) 🟡
- 📄 [QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)](https://arxiv.org/abs/2305.14314) 🔴
- 📝 [QLoRA tutorial - HF Blog](https://huggingface.co/blog/4bit-transformers-bitsandbytes) 🟡
- 📝 [LoRA 超参调优经验帖](https://magazine.sebastianraschka.com/p/practical-tips-for-finetuning-llms) 🟡 Sebastian Raschka，**强烈推荐**
- 💻 [Unsloth](https://github.com/unslothai/unsloth) 🟡 加速 LoRA 训练 2x，显存省一半
- 💻 [axolotl](https://github.com/OpenAccess-AI-Collective/axolotl) 🟡 配置驱动微调框架
- 📝 中文：[LLM 微调入门 - LoRA 详解（知乎）](https://zhuanlan.zhihu.com/p/646831196) 🟢

---

## 4. SFT（Supervised Fine-Tuning）

> SFT 是蒸馏方法之一。完整 7 种蒸馏方法对比 → `03_sft/distillation_techniques.md`

### 核心资料
- 📝 [HuggingFace - SFT guide](https://huggingface.co/docs/trl/sft_trainer) 🟢
- 📝 [Sebastian Raschka - LLM 微调 4 种方式对比](https://magazine.sebastianraschka.com/p/finetuning-large-language-models) 🟡
- 📝 [How to fine-tune LLM with custom dataset](https://huggingface.co/blog/llama3) 🟢

### 数据和格式
- 📝 [Chat template 完整解释](https://huggingface.co/docs/transformers/chat_templating) 🟢 **必读**
- 📝 [Tool use templates](https://huggingface.co/docs/transformers/chat_templating#templates-for-tool-use) 🟡
- 💻 [Alpaca 数据格式](https://github.com/tatsu-lab/stanford_alpaca) 🟢 经典参考

### 实战教程
- 📝 [HF LLM Course - Chapter 11 (Fine-tuning)](https://huggingface.co/learn/llm-course/chapter11) 🟢
- 🎥 [Sebastian Raschka - LLM 微调从零到一 (3 小时)](https://www.youtube.com/watch?v=jFNAQ6GYZTM) 🟡

### 中文资源
- 📝 [大模型微调全流程（知乎）](https://zhuanlan.zhihu.com/p/682604566) 🟢
- 💻 [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) 🟡 国内流行的一站式微调框架，**强烈推荐**试用

---

## 5. DPO（Direct Preference Optimization）

- 📄 [DPO 原论文 (Rafailov et al., NeurIPS 2023)](https://arxiv.org/abs/2305.18290) 🔴
- 📝 [DPO Explained (HF Blog)](https://huggingface.co/blog/pref-tuning) 🟡
- 📝 [DPO 超参调优实战](https://argilla.io/blog/mlabonne-llm-course/) 🟡
- 💻 [TRL DPOTrainer 示例](https://github.com/huggingface/trl/tree/main/examples/scripts) 🟡
- 📝 [DPO vs PPO 对比](https://magazine.sebastianraschka.com/p/llm-training-rlhf-and-its-alternatives) 🟡
- 📝 中文：[DPO 原理详解（苏剑林）](https://spaces.ac.cn/archives/9826) 🔴

### 常见坑
- 📝 [DPO length bias 问题](https://arxiv.org/abs/2403.19159) 🔴 长度偏差论文
- 📝 [Reward hacking in DPO](https://arxiv.org/abs/2405.19316) 🔴

---

## 6. ORPO / SimPO / KTO

### ORPO
- 📄 [ORPO 原论文 (Hong et al., 2024)](https://arxiv.org/abs/2403.07691) 🔴
- 📝 [HF ORPOTrainer docs](https://huggingface.co/docs/trl/orpo_trainer) 🟡
- 💻 [ORPO 官方实现](https://github.com/xfactlab/orpo) 🟡

### SimPO
- 📄 [SimPO (Meng et al., 2024)](https://arxiv.org/abs/2405.14734) 🔴
- 💻 [SimPO 官方实现](https://github.com/princeton-nlp/SimPO) 🟡

### KTO
- 📄 [KTO (Ethayarajh et al., 2024)](https://arxiv.org/abs/2402.01306) 🔴
- 📝 [HF KTOTrainer docs](https://huggingface.co/docs/trl/kto_trainer) 🟡

### 综合对比
- 📝 [DPO / ORPO / SimPO 横评 (HF Blog)](https://huggingface.co/blog/preference-tuning) 🟡

---

## 7. RLHF / RL

### RLHF 入门
- 📄 [InstructGPT (Ouyang et al., 2022)](https://arxiv.org/abs/2203.02155) 🔴 ChatGPT 的原始做法
- 📝 [Illustrating RLHF (HF Blog)](https://huggingface.co/blog/rlhf) 🟡 **入门必读**
- 🎥 [Andrej Karpathy - State of GPT](https://www.youtube.com/watch?v=bZQun8Y4L2A) 🟡 1 小时讲 GPT 训练全流程

### PPO
- 📄 [PPO 原论文 (Schulman et al., 2017)](https://arxiv.org/abs/1707.06347) 🔴
- 📝 [PPO 实现细节的 37 个坑](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/) 🔴
- 💻 [trl PPO 示例](https://github.com/huggingface/trl/tree/main/examples) 🔴

### GRPO
- 📄 [DeepSeek-R1 (DeepSeek, 2025)](https://arxiv.org/abs/2501.12948) 🔴
- 📝 [GRPO 解读](https://huggingface.co/blog/open-r1) 🔴
- 💻 [open-r1](https://github.com/huggingface/open-r1) 🔴 HuggingFace 的 R1 复现项目

### Constitutional AI
- 📄 [Constitutional AI (Anthropic, 2022)](https://arxiv.org/abs/2212.08073) 🔴

### 中文资源
- 📝 [RLHF 中文综述](https://zhuanlan.zhihu.com/p/624589622) 🟡
- 📝 [从零实现 PPO 中文教程](https://zhuanlan.zhihu.com/p/599416315) 🔴

---

## 8. 评估 / Benchmark

### 通用
- 💻 [lm-eval-harness (EleutherAI)](https://github.com/EleutherAI/lm-evaluation-harness) 🟡 最通用但不适合 agent
- 💻 [promptfoo](https://github.com/promptfoo/promptfoo) 🟢 Prompt 级 A/B
- 💻 [ragas](https://github.com/explodinggradients/ragas) 🟡 RAG 评估
- 📄 [HELM (Stanford, 2022)](https://arxiv.org/abs/2211.09110) 🔴

### Agent / 工具调用评估
- 📄 [Berkeley Function Calling Leaderboard (BFCL)](https://gorilla.cs.berkeley.edu/leaderboard.html) 🟡
- 💻 [BFCL 代码](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) 🟡 **工具调用评估参考**
- 📄 [AgentBench](https://arxiv.org/abs/2308.03688) 🔴
- 📄 [τ-bench](https://arxiv.org/abs/2406.12045) 🔴 Agent 多轮评估

### LLM-as-Judge
- 📄 [Judging LLM-as-a-Judge (Zheng et al., 2023)](https://arxiv.org/abs/2306.05685) 🔴 MT-Bench 的原始论文
- 📝 [LLM-as-Judge 最佳实践 (HF)](https://huggingface.co/learn/cookbook/llm_judge) 🟡

---

## 9. 数据工程

### LangSmith
- 📄 [LangSmith 官方文档](https://docs.smith.langchain.com/) 🟢
- 📝 [LangSmith Python SDK](https://docs.smith.langchain.com/reference/python) 🟢
- 💻 [langsmith-sdk GitHub](https://github.com/langchain-ai/langsmith-sdk) 🟡

### 数据质量
- 📝 [Datasets for fine-tuning LLMs (mlabonne)](https://github.com/mlabonne/llm-course#3-fine-tuning-a-llm) 🟡
- 💻 [distilabel](https://github.com/argilla-io/distilabel) 🟡 合成数据生成框架
- 💻 [Cleanlab](https://github.com/cleanlab/cleanlab) 🟡 数据噪声检测

### PII / 脱敏
- 💻 [presidio (Microsoft)](https://github.com/microsoft/presidio) 🟡 PII 检测成熟方案

---

## 10. 模型基座

### Gemma
- 📝 [Gemma 技术报告](https://storage.googleapis.com/deepmind-media/gemma/gemma-2-report.pdf) 🟡
- 📝 [Gemma Cookbook](https://github.com/google-gemini/gemma-cookbook) 🟢
- 💻 [gemma_pytorch](https://github.com/google/gemma_pytorch) 🟡

### Qwen
- 📝 [Qwen 技术报告 (v2.5)](https://qwenlm.github.io/blog/qwen2.5/) 🟡
- 📝 [Qwen3 技术报告](https://qwenlm.github.io/blog/qwen3/) 🟡
- 💻 [Qwen GitHub](https://github.com/QwenLM/Qwen) 🟢
- 💻 [Qwen Cookbook](https://github.com/QwenLM/Qwen/tree/main/examples) 🟢

### Llama
- 📝 [Llama 3 技术报告](https://arxiv.org/abs/2407.21783) 🔴
- 💻 [llama-recipes](https://github.com/meta-llama/llama-recipes) 🟡 官方微调示例

### DeepSeek
- 📄 [DeepSeek V3 技术报告](https://arxiv.org/abs/2412.19437) 🔴
- 📄 [DeepSeek R1 论文](https://arxiv.org/abs/2501.12948) 🔴
- 💻 [DeepSeek-V3 GitHub](https://github.com/deepseek-ai/DeepSeek-V3) 🟡
- 💻 [DeepSeek-R1 GitHub（含蒸馏脚本）](https://github.com/deepseek-ai/DeepSeek-R1) 🟡
- 💻 R1-Distill 模型（HF Hub 搜 `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`） 🟢

### GLM / Yi / 其他国产
- 💻 [GLM-4 GitHub](https://github.com/THUDM/GLM-4) 🟡
- 💻 [Yi GitHub](https://github.com/01-ai/Yi) 🟡

### Mistral / Cohere
- 📝 [Mistral docs](https://docs.mistral.ai/) 🟡
- 📝 [Cohere Command R+ docs](https://docs.cohere.com/docs/command-r-plus) 🟡

---

## 10b. 教师模型选型 / 蒸馏

### 综合
- 📚 本项目内 `00_overview/teacher_model_comparison.md` - 10 款教师模型对比
- 📚 本项目内 `03_sft/distillation_techniques.md` - 7 种蒸馏方法分类

### 经典蒸馏论文
- 🔴 [Hinton 2015 - Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531)
- 🔴 [DistilBERT (Sanh et al., 2019)](https://arxiv.org/abs/1910.01108)
- 🔴 [TinyBERT (Jiao et al., 2019)](https://arxiv.org/abs/1909.10351)

### LLM 时代蒸馏
- 🔴 [MiniLLM (Gu et al., 2023)](https://arxiv.org/abs/2306.08543) - 反向 KL
- 🔴 [Distilling Step-by-Step (Hsieh et al., 2023)](https://arxiv.org/abs/2305.02301) - CoT 蒸馏
- 🔴 [Self-Rewarding LM (Yuan et al., 2024)](https://arxiv.org/abs/2401.10020) - on-policy
- 🔴 [WizardLM Evol-Instruct](https://arxiv.org/abs/2304.12244) - 数据增强
- 🔴 [Orca (Mukherjee et al., 2023)](https://arxiv.org/abs/2306.02707) - 解释式蒸馏

### 工具
- 💻 [DistilKit (Arcee)](https://github.com/arcee-ai/DistillKit) - 蒸馏工具包
- 💻 [HF distillation example](https://github.com/huggingface/transformers/tree/main/examples/research_projects/distillation)
- 💻 [open-r1](https://github.com/huggingface/open-r1) - R1 复现项目

### 中文资料
- 📝 [LLM 蒸馏综述（中文）](https://zhuanlan.zhihu.com/p/681030538) 🟡
- 📝 [DeepSeek R1 蒸馏解析（中文）](https://zhuanlan.zhihu.com/search?q=deepseek+r1+%E8%92%B8%E9%A6%8F) 🟡

---

## 11. 推理 / 部署

### vLLM
- 📄 [vLLM 官方文档](https://docs.vllm.ai/) 🟡
- 📝 [PagedAttention 论文 (SOSP 2023)](https://arxiv.org/abs/2309.06180) 🔴
- 💻 [vllm GitHub](https://github.com/vllm-project/vllm) 🟡

### Ollama / llama.cpp
- 💻 [Ollama](https://github.com/ollama/ollama) 🟢 本地推理最方便
- 💻 [llama.cpp](https://github.com/ggerganov/llama.cpp) 🟡

### 约束解码
- 💻 [outlines](https://github.com/outlines-dev/outlines) 🟡 JSON / 正则约束生成
- 💻 [xgrammar](https://github.com/mlc-ai/xgrammar) 🟡

### 路由
- 💻 [LiteLLM](https://github.com/BerriAI/litellm) 🟢 多模型路由 + fallback 开箱即用

---

## 12. 端到端实战教程

### 免费课程
- 🎥 [HF LLM Course（官方）](https://huggingface.co/learn/llm-course) 🟢 **首推**
- 🎥 [Andrej Karpathy - Neural Networks: Zero to Hero](https://karpathy.ai/zero-to-hero.html) 🟡 底层实现
- 🎥 [DeepLearning.AI - Fine-tuning LLMs](https://www.deeplearning.ai/short-courses/finetuning-large-language-models/) 🟢 1 小时短课
- 🎥 [fast.ai - Practical Deep Learning](https://course.fast.ai/) 🟡

### 综合教程 / 路线图
- 💻 [mlabonne/llm-course](https://github.com/mlabonne/llm-course) 🟡 **极推荐** GitHub 61k star 的综合教程
- 💻 [rasbt/LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) 🔴 从零实现 LLM
- 📝 [A Survey of Large Language Models (中国人大, 2023+)](https://arxiv.org/abs/2303.18223) 🔴 综述论文

### 中文
- 💻 [datawhalechina/self-llm](https://github.com/datawhalechina/self-llm) 🟢 中文 LLM 微调实战
- 💻 [datawhalechina/happy-llm](https://github.com/datawhalechina/happy-llm) 🟢 新手友好

---

## 13. 实验追踪 / MLOps

- 💻 [Weights & Biases](https://wandb.ai/) 🟢 免费层够用
- 💻 [MLflow](https://mlflow.org/) 🟡 开源替代
- 💻 [aim](https://github.com/aimhubio/aim) 🟡 轻量替代

---

## 14. 本项目推荐的"3 小时入门包"

按顺序，3 小时读完，能对后续所有文档有基本把握：

1. [Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/)（30 分钟）
2. [HF Course - Chapter 1](https://huggingface.co/learn/nlp-course/chapter1)（30 分钟）
3. [PEFT LoRA conceptual guide](https://huggingface.co/docs/peft/conceptual_guides/lora)（20 分钟）
4. [Illustrating RLHF](https://huggingface.co/blog/rlhf)（30 分钟）
5. [DPO Explained](https://huggingface.co/blog/pref-tuning)（30 分钟）
6. 本项目的 `concepts_and_techniques.md`（40 分钟）

## 15. 本项目推荐的"上手 3 个练习"

完成这 3 个，就可以开始做阶段 1：

### 练习 1：LoRA hello world（半天）
用 `timdettmers/openassistant-guanaco` 数据集 + `google/gemma-2-2b-it`（或 `Qwen/Qwen2.5-1.5B-Instruct`）跑通 TRL 的 SFTTrainer。

### 练习 2：Chat template 实战（半天）
读懂 `AutoTokenizer.apply_chat_template` 源码，手动把一条多轮对话（含 tool_call）转成训练字符串，再用 `DataCollatorForCompletionOnlyLM` mask 掉 user/tool 部分。

### 练习 3：Benchmark 迷你版（1 天）
用 promptfoo 或手写 Python，对比 Claude 和 Gemma 2B 在 20 条小样本上的成功率。

---

## 提交贡献

发现新资源、坏链、错误，直接改本文件 + 更新下面的更新时间。

**更新记录**：
- 2026-04-24：首版，按概念分 15 类
