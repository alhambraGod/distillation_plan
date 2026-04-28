# 回退工程化（Fallback Engineering）

> 对应 `project_critique_and_fixes.md` 问题 5。
> **"保留 Claude fallback"不是一句话承诺，是一套工程体系。**

---

## 1. 为什么 Fallback 是工程问题

没有 fallback = 小模型出问题 = 业务直接坏。

但 fallback **不是自动的**。必须回答：
- 什么时候触发 fallback？（触发条件）
- 触发后多快能切？（时延目标）
- 切到 Claude 之前的状态怎么处理？（状态管理）
- 切回小模型什么时候？（恢复策略）
- 切换是否可观测？（监控）
- 异常率失控怎么办？（熔断）

---

## 2. 五种 Fallback 触发条件

### 2.1 触发器 1：置信度过低（Confidence）

**原理**：学生 logprob 作为自我信心。top-1 token 概率 < 阈值 → 不信任自己 → fallback。

**实现**：
```python
if avg_top1_logprob < CONFIDENCE_THRESHOLD:  # e.g., -2.0
    return fallback_to_claude()
```

**阈值**：需要用 benchmark 调（在黄金集上，小模型错了的样本 logprob 分布低于对了的）。

**代价**：需要学生返回 logprobs（vLLM 支持）。

### 2.2 触发器 2：Schema 校验失败（Structural）

**原理**：tool_call arguments 不合法 JSON、不符合工具 schema → fallback。

**实现**：
```python
try:
    args = json.loads(tool_call.arguments)
    jsonschema.validate(args, expected_schema)
except Exception:
    return fallback_to_claude()
```

**阈值**：0 容忍。

**代价**：需要工具 schema 定义可查。

### 2.3 触发器 3：重试失败（Retry exhaustion）

**原理**：小模型对同 prompt 连续 N 次（如 2 次）都返回不合法 → fallback。

**实现**：
```python
for attempt in range(MAX_RETRIES):
    resp = await small_model.call(prompt)
    if passes_sanity(resp):
        return resp
# N 次都失败
return await claude.call(prompt)
```

**阈值**：通常 2-3 次。

**代价**：增加尾延迟。

### 2.4 触发器 4：超时（Timeout）

**原理**：小模型响应 > 阈值（如 15s） → fallback。

**实现**：
```python
try:
    resp = await asyncio.wait_for(small_model.call(prompt), timeout=15)
except asyncio.TimeoutError:
    return await claude.call(prompt)
```

**阈值**：P95 × 1.5（小模型正常 P95 是 10s，超时设 15s）。

### 2.5 触发器 5：业务规则白名单（Business rule）

**原理**：某些任务**必须** Claude（如关键决策 / 外部 API 调用 / 高价值输出）。

**实现**：
```python
CRITICAL_TASK_TYPES = {"submit_publish", "billing_decision", "legal_advice"}
if task_type in CRITICAL_TASK_TYPES:
    return await claude.call(prompt)  # 不走小模型
```

**阈值**：业务方定义。

---

## 3. Fallback 决策树

```
request 来
  │
  ├── task_type in CRITICAL? ──▶ Claude
  │
  └── small_model.call(prompt, timeout=15)
        │
        ├── timeout? ──▶ Claude
        ├── error? ──▶ retry N 次
        │          └── 失败 ──▶ Claude
        │
        └── response
             │
             ├── confidence < 阈值? ──▶ Claude
             ├── schema invalid? ──▶ Claude
             └── 通过 sanity check ──▶ 返回
```

代码：`05_serving/router.py`（已实现骨架，需加上述细节）。

---

## 4. 熔断器（Circuit Breaker）

### 4.1 为什么需要

当小模型服务出大面积问题（比如整个 vLLM 挂了），每个请求都重试 → 增加延迟和成本。

**熔断**：当 fallback 率 > 阈值（如 10%）持续 N 分钟 → 整体切到 Claude，不再走小模型。

### 4.2 状态机

```
CLOSED（正常）
  ├── error_rate > 10% 持续 5 分钟 → OPEN
  │
OPEN（熔断）
  ├── 所有流量直接 Claude
  ├── 定期探活（每 N 分钟试 1 个请求走小模型）
  └── 探活成功 K 次 → HALF_OPEN
  │
HALF_OPEN（半开）
  ├── 10% 流量走小模型试水
  ├── 成功率 > 90% → CLOSED
  └── 成功率 < 阈值 → OPEN
```

### 4.3 实现

```python
# 伪代码
class CircuitBreaker:
    def should_use_small(self) -> bool:
        if self.state == "OPEN":
            return False
        if self.state == "HALF_OPEN":
            return random.random() < 0.1
        return True  # CLOSED
```

---

## 5. 三阶上线路径

改进 `rollout_plan.md`，加 shadow evaluation：

### 阶段 0：离线 benchmark
- ✅ benchmark 通过阈值
- 时长：2-3 天

### 阶段 1：Shadow Evaluation（影子评估）🆕

**关键补强**。

- 真实线上请求都走 Claude（用户看到的是 Claude）
- **同时**让小模型也跑一遍（用户不知道）
- 每日自动对比：差异率、质量差、成本差
- 时长：3-7 天

**好处**：真实分布下测小模型，不影响用户。

**代码骨架**：
```python
async def shadow_eval(prompt):
    claude_resp = await claude.call(prompt)
    asyncio.create_task(shadow_small(prompt, claude_resp))  # fire-and-forget
    return claude_resp

async def shadow_small(prompt, claude_resp):
    small_resp = await small_model.call(prompt)
    log_comparison(prompt, claude_resp, small_resp)
```

### 阶段 2：Canary 5%
- 真实用小模型响应 5% 流量
- 带 fallback 兜底
- 时长：3 天

### 阶段 3-5：20% → 50% → 100%
- 逐步放量
- 每阶段指标守门

---

## 6. 在线双跑与数据回流

### 6.1 双跑（持续）

**规则**：即使 100% 灰度，也保留**每日 5%** 流量双跑（Claude + 小模型）。

**目的**：
- 检测分布漂移
- 积累 DPO 偏好对数据（chosen = 用户选的那个）
- 发现小模型新退化

### 6.2 数据回流

```
线上 trace → 用户行为（采纳 / 修改 / 弃用） → 自动打标
    │
    ├── 采纳 → 金库（下一版 SFT 训练数据）
    ├── 修改 → 偏好对（用户改后的版本作 chosen）
    └── 弃用 → 黑库（DPO 的 rejected）
```

**频率**：每周自动汇总一次，月度增量训练。

---

## 7. 监控指标（必须有 dashboard）

| 指标 | 阈值告警 |
|---|---|
| Fallback 率 | > 3% |
| 熔断触发次数 | > 0 即告警 |
| 小模型成功率 | < 85% |
| 小模型 P95 时延 | > 15s |
| Claude P95 时延 | > 30s |
| 双跑差异率 | > 20% |
| 采纳率（业务） | 低于历史 5% |
| 成本节省 | 低于目标 30% |

---

## 8. Runbook：fallback 失控怎么办

### 症状：fallback 率飙到 50%+

**5 分钟内**：
1. 开 dashboard 看细分（哪个触发器）
2. 如果 schema fail 多 → 工具 schema 可能变了
3. 如果 timeout 多 → vLLM 服务问题
4. 如果 confidence 低 → 业务分布变了

**30 分钟内**：
- 降灰度比例（100% → 20%）
- 如果还失控 → 熔断（全走 Claude）
- 写事故报告

### 症状：双跑差异突然变大

**可能原因**：
- Claude 版本升级（Anthropic 悄悄更新）
- 业务 prompt 模板被改
- 工具 schema 变动

**行动**：
- 冻结当前版本
- 重新 benchmark
- 必要时重训

---

## 9. 代码清单

| 文件 | 用途 | 状态 |
|---|---|---|
| `05_serving/router.py` | 主路由 + fallback 逻辑 | ✅ 已骨架 |
| `05_serving/circuit_breaker.py` | 熔断器 | ⏳ 待实现 |
| `05_serving/shadow_eval.py` | 影子评估 | ⏳ 待实现 |
| `05_serving/online_feedback.py` | 数据回流 | ⏳ 待实现 |
| `05_serving/monitoring.md` | 监控说明 | ✅ |

---

## 10. 验收清单（上线前必过）

- [ ] 5 个触发器全部实现并单测
- [ ] 熔断器在沙盒环境可手动触发
- [ ] Shadow eval 运行 ≥ 3 天无重大差异
- [ ] 监控 dashboard 上线
- [ ] 告警规则配置 + 测试（故意触发）
- [ ] Runbook 演练一次（工程师 10 分钟内定位问题）

---

## 变更记录
- 2026-04-24：首版
