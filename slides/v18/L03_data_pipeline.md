---
marp: true
theme: default
paginate: true
header: 'L03 · 数据 Pipeline'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #065F46; border-bottom: 4px solid #065F46; padding-bottom: 8px; }
  h2 { color: #059669; }
  section.cover { background: linear-gradient(135deg, #065F46 0%, #059669 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  section.cover h2 { color: #D1FAE5; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #065F46; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  code { background: #D1FAE5; padding: 2px 6px; border-radius: 4px; color: #065F46; }
  .big { font-size: 44px; text-align: center; color: #065F46; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
---

<!-- _class: cover -->

# L03 · 数据 Pipeline

## LangSmith Trace → 训练数据集

<br>

📅 **第 3 课 · 60 分钟**
📚 教材：`01_data_pipeline/design.md`

---

## 🎯 本课目标

- 读懂 LangSmith trace 结构
- 掌握清洗 / 脱敏 / 去重规则
- 理解 V1 / V2 物理隔离的原因
- **动手拉 100 条 trace 跑通 pipeline**

---

## 📊 整体流程

```
LangSmith trace
     │
     ▼
1. pull_traces.py     ──▶ raw/*.parquet
     │
     ▼
2. clean.py           ──▶ processed/*.parquet (含 tier 标注)
     │
     ▼
3. extract_fields.py  ──▶ datasets/*_sft.jsonl / *_bench.jsonl
     │
     ▼
4. build_datasets.py  ──▶ train/val/test + 黄金集
```

---

## 🔍 Trace 结构解剖

```json
Run (chain):
├── inputs: {system, skills_loaded, user_input}
├── child_runs: [
│     LLM call (Claude) → {tool_calls},
│     Tool call: search → {results},
│     LLM call → {content},
│     ...
│   ]
├── outputs: {final_response, submit_final_report}
└── status: success / error
```

**我们要抽的字段**（需求文档第 3 节）：
用户输入 / system / skills / tool_calls / tool_returns / report_progress / submit_final_report / status

---

## 🧹 清洗 8 条规则

| ID | 规则 | 动作 |
|---|---|---|
| R01 | error != null | 标记，入 benchmark，不训练 |
| R02 | status == cancelled | 丢弃 |
| R03 | tool_call JSON 无效 | 丢弃 |
| R04 | 含 PII | 脱敏 |
| R05 | 长度异常（<50 或 >32k） | 短丢弃；长入 benchmark |
| R06 | 重复 prompt | 去重保最新 |
| R07 | 工具返回含错误栈 | 打 tag |
| R08 | 无 assistant 消息 | 丢弃 |

---

## 🔐 PII 脱敏必做

```python
PII_PATTERNS = {
    "email": r"[\w.-]+@[\w.-]+\.\w+",
    "phone_cn": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "id_cn": r"\d{17}[\dXx]",
    "openai_key": r"sk-[A-Za-z0-9]{20,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{36,}",
    "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    ...
}
```

**替换成** `[REDACTED_EMAIL]` 等占位。

<br>

<div class="highlight">
⚠️ 必须进训练集前完成；进后难以逆转
</div>

---

## 🚧 V1 / V2 物理隔离

为什么不能混：

- **Schema 不同**：V1 多节点 → V2 单循环 Agent
- **业务语义不同**：V1 投放分析 vs V2 营销 AI
- **benchmark 不可比**：混着报"平均成功率"是自欺

<br>

**做法**：
- 独立 pipeline 目录
- 独立 dataset 文件
- 独立 benchmark 报告
- 独立 dashboard

---

## 📦 Parquet 为什么用

| 格式 | trace 大小（1000 条） | 读取速度 |
|---|---|---|
| JSON | 500 MB | 慢 |
| CSV | 不能存嵌套 | - |
| **Parquet** | **80 MB** | **快 10x** |

<br>

**列存 + 压缩**：trace 体积大减 80%。
**DuckDB + Parquet**：不需要建数据库，直接 SQL。

---

## 🛠️ 拉数据：pull_traces.py

```python
from langsmith import Client
client = Client()

for r in client.list_runs(
    project_name="marketing-ai-v2",
    start_time="2026-01-01",
    run_type="chain",
    limit=500,
):
    yield to_raw(r)
```

**关键**：
- 按时间窗口拉（不一次拉全库）
- 分页 + 断点续传
- 429 自动退避

---

## 🔄 抽字段：extract_fields.py

```python
def to_std_sample(raw_inputs, raw_outputs):
    return {
      "sample_id": "...",
      "task_type": "marketing_ai_v2",
      "system": raw_inputs.get("system"),
      "skills_loaded": raw_inputs.get("skills", []),
      "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "...",
         "tool_calls": [...]},
        ...
      ],
      "final_status": "success",
      "metadata": {...}
    }
```

---

## 🏋️ 实操（课堂 20 分钟）

```bash
# Step 1: 拉 100 条 trace
python 01_data_pipeline/code/pull_traces.py \
  --project marketing-ai-v2 \
  --start 2026-03-01 --end 2026-03-07 \
  --out data/raw/demo.parquet

# Step 2: 清洗 + 脱敏
python 01_data_pipeline/code/clean.py \
  --in data/raw/demo.parquet \
  --out data/processed/demo_clean.parquet \
  --report data/processed/demo_report.json

# Step 3: 打开 parquet 看结构
python -c "import pandas as pd; print(pd.read_parquet('data/processed/demo_clean.parquet').head())"
```

---

## 💡 最容易踩的 3 个坑

1. **第一次拉就拉全库** → 用时间窗口 + limit
2. **以为 inputs 都是字符串** → 实际是嵌套 dict
3. **直接用 JSON.loads 解析** → trace 里有非标准类型（UUID / datetime）

<br>

清洗脚本里 `_safe_json()` 的存在就是防这个。

---

## 🏠 课后作业

1. 在 `clean.py` 里加一条新规则（比如"极端重复语句"）
2. 跑一批 500 条数据
3. 看 `report.json`：丢了多少、保了多少、PII 脱了几次

<br>

**下节课**：L04 数据质量分级 **← 解决幸存者偏差**

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: V1 V2 能合并一点点吗？ → A: 不行，宁可 benchmark 分开
- Q: trace 量不够怎么办？ → A: L04 讲合成数据补齐
- Q: 为什么用 Parquet 不用 SQLite？ → A: 列存 + Python 读快，但也可以
