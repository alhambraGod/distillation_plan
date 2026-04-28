---
marp: true
theme: default
paginate: true
header: 'L17 · 灰度 + Shadow + 回流'
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
---

<!-- _class: cover -->

# L17 · 灰度 + Shadow + 数据回流

## 三阶上线 + 监控 + 数据循环

<br>

📅 **第 17 课 · 60 分钟**
📚 教材：`rollout_plan.md` + `monitoring.md`

---

## 🎯 本课目标

- 掌握三阶上线路径
- 理解 **Shadow Evaluation** 的价值
- 设计数据回流机制
- **动手**：画本项目的灰度计划

---

## 🏗️ 三阶上线路径

```
Stage 0: 离线 benchmark    ── 2-3 天
   │   ↓ 过阈值
Stage 1: Shadow evaluation ── 3-7 天 ← 关键补强
   │   ↓ 差异率可接受
Stage 2: Canary 5%         ── 3 天
   │
Stage 3: 20% → 50%         ── 每阶段 3-5 天
   │
Stage 4: 100% 全量
```

<br>

**每阶段守门**：关键指标不降 + P0 事故 = 0

---

## 🌗 Shadow Evaluation（影子评估）

**关键补强**（原方案漏的）

```
用户请求
  │
  ├─▶ Claude 处理 ─▶ 返回给用户（真实响应）
  │
  └─▶ 小模型也跑一次 ─▶ 对比记录（用户不知道）
```

<br>

**好处**：
- 真实分布下测小模型
- 不影响用户
- 积累对比数据

---

## 📝 Shadow 实现

```python
async def shadow_eval_chat(prompt, task_meta):
    # 用户看到 Claude 响应
    claude_resp = await claude.call(prompt)
    
    # 异步启动小模型对比（不阻塞）
    asyncio.create_task(
        _shadow_compare(prompt, claude_resp, task_meta)
    )
    
    return claude_resp

async def _shadow_compare(prompt, claude_resp, meta):
    small_resp = await small_model.call(prompt)
    log_comparison(prompt, claude_resp, small_resp, meta)
    # 后续用于生成偏好对 / DPO 数据
```

---

## 🎯 Shadow 的数据用法

| 数据 | 用途 |
|---|---|
| Claude 响应 + 小模型响应 | 比较差异 |
| 用户采纳 Claude 的 → 小模型的输出 | 铜数据 |
| 用户改写 Claude 的 → 小模型的输出 | 潜在金数据 |
| 长期记录的差异率 | 判断何时切灰度 |

<br>

<div class="highlight">
Shadow 是"免费"的数据来源
</div>

---

## 🐤 Canary（金丝雀）5%

实际用小模型响应 **5%** 流量：

```python
import random
if random.random() < 0.05:
    return await small_model.call(prompt)  # 5% 流量
else:
    return await claude.call(prompt)        # 95% 流量
```

**Fallback 保持**：小模型失败自动切 Claude。

**观察期**：3 天。

---

## 📊 每阶段守门指标

| 指标 | 阈值 |
|---|---|
| Fallback 率 | < 3% |
| 业务抽检采纳率 | > 85% |
| P95 时延 | < 15s |
| 用户重试率 | 不高于历史 + 10% |
| 成本节省 | ≥ 40% |
| P0 事故 | 0 |

<br>

任一不过 → 不进下一阶段。

---

## 🔄 数据回流

灰度期间**持续收集**：

```
线上 trace → 用户行为 → 自动打标
   │
   ├─ 采纳 → 金库（下一版 SFT 训练）
   ├─ 改稿后采纳 → 偏好对（chosen = 改后）
   └─ 弃用 → 黑库（DPO rejected）
```

<br>

**频率**：每周汇总，月度增量训练。

---

## 🎯 数据回流的配比

```
初版 SFT 数据：100% 历史 trace
   ↓ 上线 1 月后
v2 SFT 数据：80% 历史 + 20% 线上金数据
   ↓ 3 月后
v3 SFT 数据：50% 历史 + 50% 线上金数据
   ↓ 6 月后
v4 SFT 数据：基本全是线上数据
```

<br>

模型持续进化，不断"长大"。

---

## 📊 监控 Dashboard

必须有 5 块：

| 面板 | 指标 |
|---|---|
| 总览 | 路由分布 / fallback 率 / 总调用 |
| 时延 | P50 / P95 / P99 分模型 |
| 质量 | sanity fail / 业务抽检 / 采纳率 |
| 成本 | 按天累加 / 对比历史 |
| 容量 | GPU util / 显存 / token 吞吐 |

<br>

用 Prometheus + Grafana。

---

## 🔔 告警分级

| 级别 | 触发 | 通道 |
|---|---|---|
| P0 | 服务挂 / fallback > 50% | PagerDuty 电话 |
| P1 | fallback > 10% / P95 超 | Slack on-call |
| P2 | 成本异常 / 业务某指标降 | 每日邮件总结 |

---

## 📅 每日 Ritual（灰度期间）

- **早会 5 分钟**：看 dashboard，讨论异常
- **业务方抽检 30 条**：判断小模型是否 OK
- **晚会更新 on-call 日志**

<br>

<div class="highlight">
灰度期间每天都要盯，不能让系统自己飘
</div>

---

## 🔄 回滚机制

### 自动回滚触发
- Fallback 率 > 20%，持续 10 分钟
- vLLM 服务不可达 > 2 分钟
- 业务指标劣化 > 30%

### 手动回滚
- 业务方随时可以喊停
- 值班工程师有权限

### 回滚 = 配置改成 0%，不删服务

---

## 🏋️ 实操（20 分钟）

**任务**：画本项目的灰度计划

给你一张空 timeline：
```
Stage 0 → Stage 1 → Stage 2 → Stage 3 → Stage 4
离线     Shadow     5%        20%/50%    100%
```

填：
- 每阶段观察什么指标
- 每阶段过到下一阶段的阈值
- 异常回滚触发条件

---

## 📅 灰度时间轴（建议）

```
W12 Day 1-3:  Stage 0 (离线 benchmark)
W12 Day 4-7:  Stage 1 (Shadow eval 3 天)
W13 Day 1-3:  Stage 2 (Canary 5%)
W13 Day 4-6:  Stage 3a (20%)
W13 Day 7-11: Stage 3b (50%)
W14 Day 1-5:  Stage 4 (100%)
W14 Day 6+:   稳态监控 + 数据回流
```

---

## 🏠 课后作业

1. 读 `rollout_plan.md` + `monitoring.md`
2. 设计本项目 monitoring dashboard（画草图）
3. 写事故响应 runbook 一页

<br>

**下节课**：L18 反思 + 答辩

---

<!-- _class: cover -->

# Q & A

<br>

常问：
- Q: Shadow 期多久合适？→ A: 3-7 天，看差异是否稳定
- Q: 可以跳过 shadow 直接 canary 吗？→ A: 不建议，shadow 成本几乎为零
- Q: 回滚了怎么恢复信心？→ A: 事故复盘 + 重新 benchmark + 从 5% 重启
