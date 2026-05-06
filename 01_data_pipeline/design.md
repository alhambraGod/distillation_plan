# 数据管线设计

> 与 `01_data_pipeline/data_quality_tiers.md`（分级标准）、`00_overview/anthropic_tos_compliance.md`（合规审查）配套使用。
> 设计目标：处理**多版本 schema**（如 LangSmith V1 + LangFuse V2）+ **多平台业务**（X / Reddit / Telegram / Discord 等）

---

## 0. 真实场景画像

不同业务的数据规模与特征差异巨大，本文档以一类**典型海外社媒推广业务**为例（项目自带的示例数据集）：

| 业务特征 | 数据特征 |
|---|---|
| 多账号矩阵协同（5-15 号）| 单 thread 含数百到数千 tool call |
| 复合 skill 触发（养号+跟评+裂变） | 单 thread 跨小时执行 |
| 双系统并存（V1 + V2 演进） | LangSmith / LangFuse 两套 schema |
| 跨平台（X / Reddit / Telegram） | 不同平台的 PII / ToS 模型不同 |

> 通用场景（如客服 chatbot、代码助手）可以直接套用本设计，**只需调整阈值**——例如客服业务的 token 上限通常 8k 而非 32k。

---

## 1. 目标

把可观测性平台（LangSmith / LangFuse）里的 trace 变成三种产物：
1. **SFT 数据集**（多轮对话 + 工具调用）
2. **偏好对数据集**（DPO 用，阶段 3 才用到）
3. **Benchmark 回放集**（固定样本，跨版本对比）

---

## 2. 原则

- **V1 / V2 物理隔离**：两套独立的 pipeline，从拉数据到产出数据集不混
- **按 thread 分文件存原始数据**：每个 thread 一个 JSON，便于断点续传
- **每一步可重放**：原始数据落 Parquet，下游可从任一中间态重跑
- **脱敏前置**：敏感字段（邮箱、手机、API key、**业务 ObjectId**、**社媒用户名**）在清洗阶段就去掉
- **数据血缘可追溯**：每条样本带 `source_thread_id` + `source_run_id`

---

## 3. 阶段拆解

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. pull      │ → │ 2. clean     │ → │ 3. extract   │ → │ 4. build     │
│   拉原始     │   │   清洗+脱敏  │   │   抽字段     │   │   建数据集   │
│   parquet    │   │   分 V1/V2   │   │   成标准样本 │   │   train/val/test │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

每阶段 **V1 / V2 全程独立**——脚本独立、目录独立、配置独立。

---

## 4. 多版本 Schema 处理（重点）

### 4.1 真实差异：LangSmith V1 vs LangFuse V2

```text
V1 schema (LangSmith):                   V2 schema (LangFuse):
{                                        {
  "thread_id": "...",                      "thread_id": "...",
  "trace_count": N,                        "trace_count": N,
  "runs": [                                "traces": [           ← 字段名不同
    {                                        {
      "trace_id": "...",                       "id": "...",
      "trace_name": "agent",                   "projectId": "...",       ← V2 新增
      "timestamp": "...",                      "name": "agent",
      "latency_seconds": 434.47,               "sessionId": "...",       ← V2 新增
      "total_cost": 1.18727,                   "latency": 59.9,          ← 字段名/单位不同
      "input": {...},                          "totalCost": 0.123,       ← 驼峰命名
      "output": {...}                          "input": {...},
    }                                          "output": {...},
  ]                                            "metadata": {...},        ← V2 新增
}                                              "scores": [],             ← V2 新增
                                               "observations": [...],    ← V2 新增
                                               "observation_tree": {...},
                                               "observation_count": 25
                                             }
                                           ]
                                         }
```

### 4.2 关键差异表

| 维度 | V1 | V2 | 必须分开处理 |
|---|---|---|:---:|
| 顶层数组名 | `runs` | `traces` | ✅ |
| 时长字段 | `latency_seconds` | `latency` | ✅ |
| 成本字段 | `total_cost` (snake) | `totalCost` (camel) | ✅ |
| Run ID | `trace_id` | `id` | ✅ |
| Run name | `trace_name` | `name` | ✅ |
| Project ID | （无） | `projectId` | ⚠️ |
| Observations | （无） | `observations[]` | ⚠️ |
| Cache 字段 | `cache_creation/read` | + `ephemeral_5m/1h` | ⚠️ |

### 4.3 设计选择：两套独立 parser（**不要写通用 parser**）

```python
# ❌ 错误做法：通用 parser
def parse_thread_universal(data):
    runs = data.get("runs") or data.get("traces", [])
    for run in runs:
        # try V1 fields, fallback to V2
        cost = run.get("total_cost") or run.get("totalCost", 0)
        latency = run.get("latency_seconds") or run.get("latency", 0)
        # ... 一堆 try/except
```

**为什么错**：
1. 字段单位可能不同（latency_seconds 是秒，V2 latency 文档不明）
2. 嵌套结构不同（V2 多 observations 层）
3. 6 个月后维护时没人能记得这些『或者』

```python
# ✅ 正确做法：两套独立 parser
class V1Parser:
    SCHEMA_NAME = "langsmith_v1"
    
    def parse(self, data: dict) -> list[Run]:
        return [self._parse_run(r) for r in data["runs"]]
    
    def _parse_run(self, r: dict) -> Run:
        return Run(
            id=r["trace_id"],
            name=r["trace_name"],
            latency_s=r["latency_seconds"],
            cost_usd=r["total_cost"],
            messages=r["output"]["messages"],
        )

class V2Parser:
    SCHEMA_NAME = "langfuse_v2"
    
    def parse(self, data: dict) -> list[Run]:
        return [self._parse_trace(t) for t in data["traces"]]
    
    def _parse_trace(self, t: dict) -> Run:
        return Run(
            id=t["id"],
            name=t["name"],
            latency_s=t["latency"],  # 注意：可能要按平台文档转单位
            cost_usd=t["totalCost"],
            messages=t["output"]["messages"],
            project_id=t["projectId"],
            session_id=t["sessionId"],
        )

def detect_format(data: dict) -> str:
    if "runs" in data:
        return "v1"
    if "traces" in data:
        return "v2"
    raise ValueError(f"Unknown format, top-level keys: {list(data.keys())}")

def parse_thread(data: dict) -> tuple[str, list[Run]]:
    fmt = detect_format(data)
    parser = V1Parser() if fmt == "v1" else V2Parser()
    return fmt, parser.parse(data)
```

---

## 5. 产出 Schema

### 5.1 SFT 样本（jsonl 一行）

```json
{
  "sample_id": "v2_20260301_000123",
  "task_type": "marketing_ai_v2_reddit",
  "platform": "reddit",
  "skill_id": "loop-caa69888",
  "skill_name": "Reddit互动抢评闭环",
  "system": "You are a marketing agent...",
  "skills_loaded": ["loop-caa69888"],
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "...", "tool_calls": [
      {"id": "call_1", "name": "marketing_reddit_task_get_comments",
       "arguments": {"post_id": "..."}}
    ]},
    {"role": "tool", "tool_call_id": "call_1", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "final_status": "success",
  "tier": "gold",
  "metadata": {
    "schema_version": "langfuse_v2",
    "source_thread_id": "019dde5e-5051-...",
    "source_run_id": "...",
    "start_time": "2026-04-30T...",
    "duration_ms": 113500,
    "token_usage": {"prompt": 22487, "completion": 24}
  }
}
```

**新增字段**（相比通用模板）：
- `platform`：`x` / `reddit` / `telegram` / `discord` / `general`
- `skill_id` / `skill_name`：业务方维护的 skill 标识
- `tier`：`gold` / `silver` / `bronze` / `trash`
- `metadata.schema_version`：`langsmith_v1` / `langfuse_v2`

### 5.2 偏好对样本

```json
{
  "pair_id": "v2_pref_000001",
  "platform": "reddit",
  "context": {
    "system": "...",
    "messages_prefix": [...]
  },
  "chosen": {
    "content": "...",
    "tool_calls": [...],
    "source_tier": "gold",
    "source_thread_id": "019dde5e-..."
  },
  "rejected": {
    "content": "...",
    "tool_calls": [...],
    "source_tier": "trash | bronze",
    "source_thread_id": "019dde6d-..."
  },
  "rejection_reason": "sop_skipped | content_refused | task_refused | low_quality",
  "source": "sampled_v1_vs_v2 | llm_judge | human_rank"
}
```

**新增字段**：
- `rejection_reason`：业务专属 4 种拒绝原因
  - `sop_skipped`：SOP 跳步（如 V2-部分成功）
  - `content_refused`：内容生成被拒（如 V1-拒绝内容）
  - `task_refused`：任务级拒绝（如 V1-拒绝执行）
  - `low_quality`：质量低但没明显错

### 5.3 Benchmark case

```json
{
  "case_id": "v2_bench_001",
  "task_type": "marketing_ai_v2_reddit",
  "platform": "reddit",
  "skill_id": "loop-caa69888",
  "initial_input": {...},
  "expected_status": "success",
  "expected_tools": ["marketing_reddit_task_get_comments",
                     "marketing_reddit_task_create_comment"],
  "expected_tools_strict": false,
  "expected_sop_steps": ["fetch_post", "list_accounts",
                         "select_persona_match", "preflight",
                         "publish", "report"],
  "golden_output": "..."
}
```

**新增字段**：
- `expected_sop_steps`：业务 SOP 必经步骤——用于检测 V2-部分成功 这种『跳步骤』错误

---

## 6. 清洗规则一览

### 6.1 通用 8 条规则

| ID | 规则 | 处理方式 |
|---|---|---|
| R01 | `error != null` | 标记，**不进 SFT**；进 benchmark（复现用） |
| R02 | `final_status == "cancelled"` | 丢弃 |
| R03 | tool_call JSON 无法 parse | 丢弃 |
| R04 | 含 PII（email / phone / API key / **ObjectId / 社媒 handle**）| 正则脱敏替换 |
| R05 | 内容长度 < 50 token 或 > 32k | 短丢弃；长进 benchmark |
| R06 | 同一 prompt 多次出现 | 保留最新一次 |
| R07 | 工具返回包含 stack trace | 保留但打 tag `tool_error` |
| R08 | 无 assistant 消息 | 丢弃（空对话） |

### 6.2 业务专属规则（学员业务示例）

| ID | 规则 | 处理方式 |
|---|---|---|
| R09 | **道德拒绝**（Claude 输出含『拒绝执行』『违反安全准则』等关键词）| 标黑数据，进 DPO rejected |
| R10 | **SOP 跳步**（plan 中缺失业务定义的必经步骤） | 标铜数据，进 benchmark 回放 |
| R11 | **跨账号操作高频**（5+ 账号在 60s 内同动作） | 打 tag `coord_behavior`，业务方人工 review |

### 6.3 业务 PII（学员业务额外 5 类）

```python
PII_PATTERNS_BUSINESS = {
    "mongo_id": re.compile(r"\b[a-f0-9]{24}\b"),
    "x_handle": re.compile(r"@[A-Za-z0-9_]{1,15}\b"),
    "reddit_user": re.compile(r"\bu/[A-Za-z0-9_-]{3,20}\b"),
    "reddit_post_id": re.compile(r"/comments/[a-z0-9]{6,7}/"),
    "telegram_handle": re.compile(r"@[a-z][a-z0-9_]{4,31}\b"),
}
```

**关键策略**：
- **稳定映射**：同一 ID 在 trace 中出现 N 次，统一替换成同一占位符（保留追溯能力）
- **保留前缀**：`[REDACTED_MONGO_69e7****_001]`——前 4 位 hex 不可反查但可关联
- **不破坏 JSON**：永远不要替换成空字符串，永远用占位符

---

## 7. 数据血缘（必做）

每条样本必须带：
- `source_thread_id`：原 thread JSON 文件名
- `source_run_id`：trace ID
- `schema_version`：`langsmith_v1` / `langfuse_v2`
- `pii_redacted_count`：脱敏命中数（按类型）

**为什么**：
- 训完发现某条样本异常 → 能回查原 trace
- PII 脱敏出错 → 能定位原始数据修补
- 业务方质询 → 能给出血缘证据

---

## 8. 下一步：代码实现

代码示例见 `code/`：
- `pull_traces.py` - 从 LangSmith / LangFuse API 拉 thread JSON
- `clean.py` - 清洗 + 脱敏 + 双 schema 处理
- `extract_fields.py` - 字段抽取（按 platform / skill 分流）
- `build_datasets.py` - train/val/test 切分 + 通用数据混入

---

## 9. 注意事项

1. **API 流量配额**：
   - LangSmith：一次拉取 5000 条以内
   - LangFuse：按 project_id 分批
   - 都要：分页 + 重试 + 记录 last_id 支持断点续传

2. **PII 脱敏**：
   - 至少覆盖通用 8 类（email/phone/id/credit_card/api_keys/ipv4）
   - 业务专属 5 类（学员业务）：MongoDB ObjectId / X handle / Reddit user / Reddit post / Telegram handle
   - **必须双层防御**：正则 + Presidio NER（覆盖中英文姓名、地址等语义 PII）

3. **去重算法**：
   - 用 prompt 的 normalized hash（去除空格和标点后的 sha256）
   - **学员业务特殊**：V1 trace 的 input 含 user_id，去重时**先脱敏再 hash**

4. **跨版本对齐**：
   - 同一业务的 V1 / V2 数据**不要合并训**
   - 但**可以共享 PII 脱敏脚本**（写成 library，两边 import）

---

## 10. 业务定制 checklist

新业务上手时按这个 checklist 走：

- [ ] 识别 trace schema 版本（LangSmith / LangFuse / 自研）
- [ ] 列出业务平台（X / Reddit / 自有 / 其他）
- [ ] 列出业务 PII 类型（账号 ID / 用户名 / 帖子 ID 等）
- [ ] 列出业务专属规则（如 SOP 跳步、道德拒绝、跨账号协同）
- [ ] 确定阈值（token 上限 / tool call 步骤上限 / latency 上限）
- [ ] 写**两套** parser（如果有版本演进）
- [ ] 业务红线文档三方签字（业务 / 工程 / Legal）

---

## 11. 相关文档

- `01_data_pipeline/data_quality_tiers.md` — 金/银/铜/黑分级细则
- `00_overview/anthropic_tos_compliance.md` — 合规审查模板
- `00_overview/project_critique_and_fixes.md` §2 — 数据质量原方案问题

---

## 变更记录

- 2026-04：v1 通用版
- 2026-05：增加 LangSmith V1 / LangFuse V2 双 schema 支持 + 业务专属规则与 PII
