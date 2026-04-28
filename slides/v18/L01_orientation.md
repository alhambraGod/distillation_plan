---
marp: true
theme: default
paginate: true
header: '小模型蒸馏项目 · Day 1 · 新人第一课'
footer: '© 2026 · 基于 distill_plan/'
size: 16:9
style: |
  section {
    font-family: 'PingFang SC', 'Helvetica Neue', sans-serif;
    font-size: 24px;
  }
  h1 {
    color: #1E3A8A;
    border-bottom: 4px solid #1E3A8A;
    padding-bottom: 8px;
  }
  h2 {
    color: #2563EB;
  }
  section.cover {
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
    color: white;
  }
  section.cover h1 {
    color: white;
    border-bottom: 4px solid white;
    font-size: 64px;
  }
  section.cover h2 {
    color: #E0E7FF;
    font-size: 32px;
  }
  section.section-divider {
    background: #F3F4F6;
    text-align: center;
  }
  section.section-divider h1 {
    font-size: 72px;
    border: none;
    color: #1E3A8A;
  }
  table {
    margin: 0 auto;
    font-size: 22px;
  }
  code {
    background: #F3F4F6;
    padding: 2px 6px;
    border-radius: 4px;
  }
  pre {
    background: #1E293B;
    color: #E2E8F0;
    border-radius: 8px;
    padding: 16px;
    font-size: 18px;
  }
  .highlight {
    background: #FEF3C7;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .big {
    font-size: 48px;
    text-align: center;
    color: #1E3A8A;
  }
  .center {
    text-align: center;
  }
---

<!-- _class: cover -->

# 小模型蒸馏项目

## 新人第一课

<br>

📅 **Day 1 / Week 0**
🎯 **12 周：从零到上线**
👋 **Welcome!**

---

## 📋 今天的议程

<br>

| 环节 | 时长 | 内容 |
|:---|:---:|:---|
| 1️⃣ 项目概览 | 15 min | 我们要做什么、为什么做 |
| 2️⃣ 核心概念 | 25 min | SFT / DPO / RL 速览 |
| 3️⃣ 技术架构 | 15 min | 系统和数据流 |
| 4️⃣ 12 周路线 | 15 min | 里程碑和决策点 |
| 5️⃣ 你的第一天 | 10 min | 任务清单 + Q&A |

---

<!-- _class: section-divider -->

# 1️⃣ 项目概览

---

## 🤔 我们为什么在这里？

<br>

<div class="big">
现状：Claude 月成本 <span class="highlight">💰💰💰</span>
</div>

<br>

```
一次调用 = $0.0135
日 10 万调用 = $40,500 / 月
年  = $486,000
```

<br>

**问题**：能不能**用便宜的模型**完成 **80% 的常见任务**？

---

## 🎯 目标不是"完美替代"

<br>

| 我们 **不是** 要做的 | 我们 **真的** 要做的 |
|:---|:---|
| ❌ 小模型全量替代 Claude | ✅ 覆盖高频简单任务 |
| ❌ 追求性能超越 | ✅ 成本降低 40%+ |
| ❌ 一次到位 | ✅ 灰度 + 可回滚 |
| ❌ 闭门训练数月 | ✅ 3 个月内见结果 |

<br>

<div class="center">
🔑 <span class="highlight">降本 + 保留 Claude fallback</span>
</div>

---

## 🎯 三个业务目标

<br>

<div class="big">
🏆 85% / 40% / 100%
</div>

<br>

| 指标 | 目标 |
|:---|:---:|
| 小模型成功率 | **≥ Claude × 85%** |
| 成本节省 | **≥ 40%** |
| Claude fallback | **100% 保留** |

<br>

**任一不达标 → 不上线**

---

<!-- _class: section-divider -->

# 2️⃣ 核心概念

---

## 💡 蒸馏是什么？

<br>

```
┌─────────────┐         ┌─────────────┐
│   Claude    │  教师   │  Gemma/Qwen │
│   (大)      │  ──→   │    (小)     │
│             │         │             │
└─────────────┘         └─────────────┘
   能力强                    便宜快
   $$$$$                     $
```

<br>

**我们的蒸馏 = 用 Claude 的历史运行数据，训小模型学会**

---

## 💡 概念 1：LoRA

**不改基座，贴便利贴**

<br>

```
Qwen 2.5 7B：70 亿参数（冻结不动）
         +
    小旁路矩阵：几千万参数（训练）
         ↓
     LoRA adapter
```

<br>

| 好处 | 细节 |
|:---|:---|
| 💾 单卡能训 | 7B QLoRA 只要 24GB 显存 |
| 🔌 即插即用 | 不同任务不同 adapter |
| ⏪ 随时回滚 | 基座不污染 |

---

## 💡 概念 2：SFT（监督微调）

**给模型"正确答案"，让它学会模仿**

<br>

```
输入：用户问题 + 工具定义
  ↓
模型产出："我应该调 search 工具，参数是 ..."
  ↓
对比正确答案 → 计算 loss → 更新模型
```

<br>

**适合**：
- 🔧 格式不稳（JSON 老崩）
- 🔄 流程乱（忘了调 report_progress）
- 🆕 没见过的业务模式

---

## 💡 概念 3：DPO（偏好对齐）

**给模型两个选项，让它学哪个更好**

<br>

```
同一个 prompt："写一句高端护肤品广告"

chosen:   "点燃东方美学——唤醒肌肤本真光泽" ✅
rejected: "我们的面霜很不错，你应该买"       ❌

→ 模型学会：chosen 这种表达更好
```

<br>

**适合**：SFT 后"**能用**但**不够好**"

---

## 💡 概念 4：RL（强化学习）

<br>

<div class="big">
⚠️ 本项目<span class="highlight">暂不启动 RL</span>
</div>

<br>

需求文档给的 5 个必要条件：

1. Benchmark 体系稳定 ❌
2. 人工评分映射稳定 ❌
3. Environment 明确 ❌
4. Reward 明确 ❌
5. 是多步策略问题 ❌

**当前都不满足** → 专注 SFT + DPO 就够了

---

## 📊 三条路径对比

<br>

| 方法 | 时间 | 数据 | 改变什么 | 风险 |
|:---|:---:|:---:|:---|:---:|
| Prompt | 1 天 | 无 | 风格/格式 | 🟢 低 |
| **SFT** | 1-2 周 | 1k-10k 样本 | 能力/格式/流程 | 🟡 中 |
| **DPO** | 2-3 周 | 1k-5k 偏好对 | 风格/偏好 | 🟡 中 |
| RL | 2-3 月 | 持续在线 | 多步策略 | 🔴 高 |

<br>

<div class="center">
我们走 → <span class="highlight">SFT → DPO</span>
</div>

---

<!-- _class: section-divider -->

# 3️⃣ 技术架构

---

## 🏗️ 系统全景图

<br>

```
    LangSmith (历史 trace 数据源)
              │
              ▼
    ┌──── 数据管线 ────┐
    │ 拉取 → 清洗 → 抽字段 → 切分 │
    └───────────────────┘
              │
       ┌──────┼──────┐
       ▼      ▼      ▼
     SFT    偏好   Benchmark
       │      │      │
       ▼      ▼      │
    ┌─ 训练（LoRA）─┐ │
    │  SFT → DPO   │ │
    └──────────────┘ │
              │      │
              ▼      ▼
         vLLM 推理 ← 评估
              │
              ▼
     路由 + Claude Fallback
              │
              ▼
       DeerFlow / V1
```

---

## 📦 我们的数据长什么样

<br>

**一条 LangSmith trace** 包含：

```json
{
  "inputs": {
    "system": "你是营销助理...",
    "skills_loaded": ["search", "analyze"],
    "user_input": "帮我分析这个品牌"
  },
  "tool_calls": [
    {"name": "search", "args": {...}},
    {"name": "analyze", "args": {...}},
    {"name": "report_progress", "args": {...}},
    {"name": "submit_final_report", "args": {...}}
  ],
  "final_status": "success"
}
```

<br>

🔑 这就是我们**唯一**的训练数据源

---

## 🎯 基座模型选型

<br>

| 候选 | 中文 | Tool Call | License | 推荐度 |
|:---|:---:|:---:|:---:|:---:|
| **Qwen 2.5 7B** | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 | 🥇 **首选** |
| Gemma 2 9B | ⭐⭐ | ⭐ | Gemma | 🥈 备选 |
| Qwen 3 7B | ⭐⭐⭐ | ⭐⭐⭐ | Apache 2.0 | 🥉 探索 |
| Llama 3.1 8B | ⭐ | ⭐⭐⭐ | Llama | ❌ |

<br>

**为什么 Qwen 2.5**：中文强 / 原生 tool call / Apache 2.0 商用无忧

---

## 🛠️ 我们的技术栈

<br>

```
┌──────────────────────────────────────┐
│ 数据    Parquet + DuckDB             │
├──────────────────────────────────────┤
│ 模型    HuggingFace Transformers     │
│         + PEFT (LoRA)                │
│         + TRL (SFT / DPO)            │
│         + bitsandbytes (QLoRA)       │
├──────────────────────────────────────┤
│ 推理    vLLM (线上)                  │
│         Ollama (开发调试)            │
├──────────────────────────────────────┤
│ 追踪    Weights & Biases             │
├──────────────────────────────────────┤
│ 路由    自写 FastAPI 或 LiteLLM      │
└──────────────────────────────────────┘
```

---

<!-- _class: section-divider -->

# 4️⃣ 12 周路线图

---

## 🗺️ 整体节奏

<br>

```
 W0        W1-3          W4-7         W8-10         W11-12
 │          │             │             │             │
 ▼          ▼             ▼             ▼             ▼
环境   数据+Benchmark    SFT          DPO         灰度上线
学习
            ▲             ▲             ▲             ▲
            │             │             │             │
         【DP1】        【DP2】       【DP3】       【DP4】
         训不训？       够了吗？      上哪个？      全量？
```

<br>

<div class="center">
🔑 每个决策点 <span class="highlight">签字才进下阶段</span>
</div>

---

## 🎯 5 个关键决策点

<br>

| ID | 时间 | 决策 |
|:---:|:---:|:---|
| **DP1** | W3 末 | 要不要训练？ |
| **DP2** | W7 末 | SFT 够吗？要不要 DPO？ |
| **DP3** | W10 末 | DPO 有收益吗？上哪个版本？ |
| **DP4** | 灰度期 | 切换到下一灰度阶段？ |
| **DP5** | 未来 | 启动 RL 吗？ |

<br>

每个决策点都有**一页纸模板**：`06_decisions/`

---

## 5️⃣ 五条核心原则

<br>

1. 🧪 **先评估再训练** — 没 benchmark 不动手
2. 🎯 **一次只改一个变量** — 否则无法归因
3. 🏷️ **版本化一切** — 数据/模型/配置带日期
4. 🙋 **人工标注不要省** — 200 条 > 10000 条
5. 🤝 **对齐业务** — 业务方签字才算数

<br>

<div class="center">
📜 详见 <code>core_principles.md</code>
</div>

---

## ⚠️ 常见反模式（别做）

<br>

| 做 ✅ | 不做 ❌ |
|:---|:---|
| 评估先于训练 | "训完再看好不好" |
| V1/V2 分开测 | 混在一起平均 |
| 单变量实验 | 一次改 5 处 |
| 人工抽检必过 | 只看自动指标 |
| 业务方参与 | 闭门造车 |

<br>

**失败的团队都是同一种错，成功的团队守同一套规则**

---

<!-- _class: section-divider -->

# 5️⃣ 你的第一天

---

## 👥 你的队友

<br>

```
┌─────────────────────────────────────┐
│  你（主开发）    ──  全职 12 周      │
│  导师 ML eng    ──  每周 review     │
│  业务 lead      ──  评估 + 抽检     │
│  SRE            ──  灰度期间        │
│  技术负责人     ──  架构 + 签字     │
└─────────────────────────────────────┘
```

<br>

**有问题**：
- 🔧 技术 → Slack `#distill-tech`
- 💼 业务 → Slack `#distill-biz`
- 🆘 卡住 → 直接找导师

---

## ✅ 今天的任务清单

<br>

| 时段 | 任务 | 时长 |
|:---|:---|:---:|
| 🌅 上午 | 读 `README.md` + `implementation_plan.md` | 30 min |
| 🌅 上午 | 跑 `environment_setup.md` 装环境 | 1h |
| 🌞 中午 | 读 `ml_fundamentals.md` | 30 min |
| 🌆 下午 | 读 `concepts_and_techniques.md` | 40 min |
| 🌆 下午 | V1/V2 架构 walkthrough 会议 | 2h |
| 🌙 晚上 | 从 LangSmith 拉 10 条 trace 打印看 | 30 min |

---

## 🔧 环境搭建快速路径

<br>

```bash
# 1. 创建环境
mamba create -n distill python=3.11 -y
mamba activate distill

# 2. 装核心依赖（按 environment_setup.md §4）
pip install torch transformers datasets accelerate
pip install peft trl bitsandbytes vllm wandb

# 3. 验证
python -c "import torch; print(torch.cuda.is_available())"

# 4. 装账号
huggingface-cli login
wandb login
```

<br>

详见 `00_overview/environment_setup.md`

---

## 🎁 回家作业

<br>

今晚完成：

1. ✅ 装好环境，能加载 **Qwen 0.5B** 做一次推理
2. ✅ 从 LangSmith 拉 **10 条 trace**，打印出来看结构
3. ✅ 写 **100 字**解释 LoRA 给同事（用自己的话）

<br>

**明天早会 check，不过关就补**

---

## 💡 学习建议

<br>

- 📚 先看概念，**别急着改代码**
- 🐛 遇到坑**先搜** `troubleshooting.md`
- 📝 每周五写周报（W&B run + 指标 + 坑）
- 🙋 **问题早问**，卡一天不如问 10 分钟
- 📖 **文档是活的**，踩坑就更新

<br>

<div class="center">
<span class="highlight">宁可问蠢问题，别默默走错路</span>
</div>

---

## 📚 你会反复翻的 5 份文档

<br>

| 文档 | 用途 |
|:---|:---|
| `concepts_and_techniques.md` | 忘概念就翻 |
| `learning_resources.md` | 要深入某个话题 |
| `troubleshooting.md` | 训练/推理出 bug |
| `eval_spec.md` | 评估口径 |
| `core_principles.md` | 纠结要不要做某件事 |

<br>

🔖 **建议收藏到 Chrome bookmark bar**

---

## ❓ Q&A

<br>

<div class="big">
欢迎提问
</div>

<br>

常见问题：

- **Q**: 没有 GPU 能开始吗？  
  A: 装环境 + 读文档可以；训练要 GPU

- **Q**: 不懂 PyTorch 怎么办？  
  A: 不要紧，`ml_fundamentals.md` 和 HF Course 够用

- **Q**: 12 周做不完怎么办？  
  A: 阶段性验收，不达标就缓，不强推

---

<!-- _class: cover -->

# 🚀 Let's Go!

## 准备好开始了吗？

<br>

📖 下一步 → 打开 `environment_setup.md`

<br>

**问题随时来找我 👋**

Thanks!
