---
marp: true
theme: default
paginate: true
header: 'L16 · 推理部署 + Fallback'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #0369A1; border-bottom: 4px solid #0369A1; padding-bottom: 8px; }
  h2 { color: #0284C7; }
  section.cover { background: linear-gradient(135deg, #0369A1 0%, #0284C7 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #0369A1; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #0369A1; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
  .warning { background: #FEE2E2; padding: 12px; border-left: 4px solid #DC2626; }
---

<!-- _class: cover -->

# L16 · 推理 + Fallback 工程化

## "保留 Claude fallback" 不是一句话

<br>

📅 **第 16 课 · 60 分钟**
📚 教材：`router.py` + `fallback_engineering.md`

---

## 🎯 本课目标

- 掌握 vLLM + LoRA hot-swap 部署
- 学会设计 **5 个 Fallback 触发器**
- 理解熔断器状态机
- **动手**：本地起服务 + 测 fallback

---

## 🚨 原方案的问题

<div class="warning">

原方案：**"保留 Claude fallback"**

现实：这只是一句话 —— 触发条件？切换延迟？状态管理？熔断？**一个都没说**。

</div>

**修复**：把"fallback"做成一套工程体系。

---

## 🛠️ vLLM 部署

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --enable-lora \
  --lora-modules marketing=/path/to/adapter \
  --max-lora-rank 32 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --port 8000
```

**关键特性**：
- OpenAI 兼容接口
- LoRA hot-swap（多个 adapter 热加载）
- PagedAttention 省显存

---

## 🎯 5 个 Fallback 触发器

<br>

| 触发器 | 条件 | 动作 |
|---|---|---|
| 1. **置信度** | avg logprob < -2.0 | 降级 Claude |
| 2. **Schema 校验** | JSON/args 不合法 | 降级 |
| 3. **重试失败** | 2 次都错 | 降级 |
| 4. **超时** | > 15s | 降级 |
| 5. **业务白名单** | task_type ∈ CRITICAL | 直接 Claude |

---

## 🔍 触发器 1：置信度

```python
# 学生返回 logprobs
resp = vllm.chat.completions.create(
    ...,
    logprobs=True, top_logprobs=5
)
avg_top1 = sum(t.logprob for t in resp.choices[0].logprobs.content) / len(...)

if avg_top1 < -2.0:
    return await claude.call(messages)  # fallback
```

<br>

**阈值**：在黄金集上调优，**对的比错的 logprob 高 2 倍** → 可作阈值。

---

## 🔍 触发器 2：Schema 校验

```python
try:
    args = json.loads(tool_call.arguments)
    jsonschema.validate(args, expected_schema)
except json.JSONDecodeError:
    return fallback()
except jsonschema.ValidationError:
    return fallback()
```

<br>

**阈值**：0 容忍 → 不合法立即降级。

---

## 🔍 触发器 3：重试失败

```python
for attempt in range(MAX_RETRIES):
    resp = await small_model.call(prompt)
    if passes_sanity(resp):
        return resp
    await asyncio.sleep(0.5)

# 2-3 次都失败
return await claude.call(prompt)
```

<br>

**阈值**：2-3 次。

---

## 🔍 触发器 4：超时

```python
try:
    resp = await asyncio.wait_for(
        small_model.call(prompt),
        timeout=15.0
    )
except asyncio.TimeoutError:
    return await claude.call(prompt)
```

<br>

**阈值**：P95 × 1.5（小模型 P95 10s → timeout 15s）。

---

## 🔍 触发器 5：业务白名单

```python
CRITICAL_TASK_TYPES = {
    "submit_publish",    # 发布
    "billing_decision",  # 扣费
    "legal_advice",      # 法律建议
}

if task_meta["task_type"] in CRITICAL_TASK_TYPES:
    return await claude.call(prompt)  # 不走小模型
```

<br>

由业务方定义。

---

## 🔌 熔断器（Circuit Breaker）

**为什么**：小模型挂了，每请求都走 fallback = 每个请求延迟 2x。

**状态机**：

```
CLOSED（正常） ─ 正常路由
  │ error_rate > 10% 5min
  ▼
OPEN（熔断） ─ 全部 Claude
  │ 定期探活
  ▼
HALF_OPEN（半开） ─ 10% 流量试水
  │ 成功率 > 90% → CLOSED
  │ 否则 → OPEN
```

---

## 🏗️ 路由层整体流程

```
request 来
  │
  ├── task_type ∈ CRITICAL? ── 是 ──▶ Claude
  │
  ├── Circuit OPEN? ── 是 ──▶ Claude
  │
  └── 小模型.call(timeout=15)
        │
        ├── timeout? ──▶ Claude (记录)
        ├── error? ──▶ retry N 次 → Claude
        └── resp
             ├── confidence 低? ──▶ Claude
             ├── schema 非法? ──▶ Claude
             └── 通过 ──▶ 返回
```

---

## 📝 router.py 核心

```python
class AgentRouter:
    def decide(self, task_meta):
        if task_meta["task_type"] in CRITICAL:
            return Route.CLAUDE
        if task_meta["task_type"] in TRAINED_WHITELIST:
            return Route.SMALL
        return Route.CLAUDE

    async def route_chat(self, messages, tools, task_meta):
        route = self.decide(task_meta)
        if route == Route.SMALL:
            try:
                resp = await self._call_small_with_timeout(...)
                if self.passes_sanity(resp):
                    return resp
                return await self._call_claude(...)  # fallback
            except Timeout:
                return await self._call_claude(...)
        return await self._call_claude(...)
```

---

## 🏋️ 实操（20 分钟）

```bash
# 本地起 vLLM
./05_serving/serve.sh  # 背景运行

# 另一个终端：起 router
python 05_serving/router_app.py

# 测正常路由
curl -X POST localhost:8001/chat -d '{...}'

# 测 fallback：故意传超大 prompt 触发超时
curl -X POST localhost:8001/chat -d '{"messages":[...大量内容...]}'

# 看 metrics
curl localhost:8001/metrics
```

---

## 📊 必须的监控指标

| 指标 | 告警阈值 |
|---|---|
| Fallback 率 | > 3% |
| 熔断触发 | > 0 |
| Sanity fail 率 | > 2% |
| 超时率 | > 1% |
| 小模型 P95 | > 15s |
| 小模型成功率 | < 85% |

---

## 🆘 Runbook：fallback 失控

**症状**：fallback 率 > 50%

1. 5 分钟内：看 dashboard 细分（哪个触发器）
2. 30 分钟内：
   - schema fail → 工具 schema 变了？
   - timeout → vLLM 服务问题？
   - confidence → 业务分布变了？
3. 决策：降灰度 or 熔断
4. 24h 内：事故报告

---

## 🏠 课后作业

1. 读 `fallback_engineering.md` 全文
2. 在 router.py 实现 5 个触发器（至少 3 个）
3. 写单测：故意触发每个 fallback

<br>

**下节课**：L17 灰度 + Shadow eval + 监控

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: 5 个触发器全部必要吗？→ A: 是，缺一会漏
- Q: 熔断会不会太敏感？→ A: 阈值 10% 持续 5 min，实际不常触发
- Q: Claude fallback 比小模型慢怎么办？→ A: 接受，fallback 本来就为质量让位延迟
