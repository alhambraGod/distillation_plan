# 监控 & 可观测性

## 核心原则

小模型上线后，监控是你唯一能发现问题的渠道。**没有监控不能灰度。**

## 必须监控的指标

### 路由层
| 指标 | 阈值 / 告警 |
|---|---|
| 小模型调用占比 | 按灰度计划，偏离 ±5% 告警 |
| Fallback 率 | > 5% 告警（说明小模型不稳） |
| Sanity fail 率 | > 2% 告警 |
| 超时率 | > 1% 告警 |

### 推理层（vLLM）
| 指标 | 阈值 |
|---|---|
| QPS | 按容量规划 |
| 时延 P50 / P95 / P99 | P95 > 15s 告警 |
| Token 吞吐 | 跌 20% 告警 |
| GPU 利用率 | < 50% 可能资源浪费 |
| GPU 显存 | > 90% 告警（OOM 风险） |

### 业务层（重要）
| 指标 | 方法 |
|---|---|
| 每日完成任务数 | 按模型分组 |
| 用户重试率 | 重试 = 不满意的信号 |
| 业务方人工抽检分数（采样） | 每日抽 30 条 |

### 成本
| 指标 |
|---|
| 小模型调用成本 / 天 |
| Claude 调用成本 / 天 |
| 总成本 vs 上线前（目标：降 50%+） |

## 技术栈建议

- **指标**：Prometheus 拉取 vLLM 的 `/metrics` + router 自己的 `/metrics`
- **可视化**：Grafana dashboard
- **日志**：vLLM + router 的 stdout → Loki 或 ES
- **Trace**：继续用 LangSmith，小模型的 trace 也上报

## 推荐 Grafana Dashboard 面板

1. **总览**：路由分布饼图 + fallback 率趋势 + 今日总调用
2. **时延**：按模型分组的 P50/P95/P99 趋势
3. **质量**：sanity fail 率、人工抽检分
4. **成本**：按天累加，对比历史
5. **容量**：GPU 利用率、显存、token 吞吐

## 告警通道

必做三档：
- **P0**：小模型服务 down、fallback 率 > 50% → PagerDuty 电话
- **P1**：fallback 率 > 10%、时延 P95 超阈值 → Slack @on-call
- **P2**：成本异常、某业务分组指标下降 → 每日邮件总结

## 日常抽检 / 影子评估

灰度期间每天：
1. 系统自动采样 30 条小模型输出
2. 生成对比（同 prompt 同时跑 Claude）
3. 业务方早会 5 分钟 quick review
4. 发现质量问题立即降灰度

## Langsmith trace 回流

小模型的 trace 继续上报到 LangSmith（同一个 project 或 fork project）：
- 后续 DPO 数据可从这里挖
- 回归测试基于真实流量
- 业务 lead 能看到实际线上样本

## 关键 dashboard 模板（YAML）

```yaml
# grafana-dashboard.yaml（简化示例）
panels:
  - title: "Routing Distribution"
    query: "rate(router_calls_total[5m]) by (route)"
  - title: "Fallback Rate"
    query: "rate(router_fallbacks_total[5m]) / rate(router_calls_total{route=\"small\"}[5m])"
  - title: "Small Model P95 Latency"
    query: "histogram_quantile(0.95, rate(vllm_request_duration_seconds_bucket[5m]))"
  - title: "Cost per Hour"
    query: "..."
```

## 异常 Runbook（On-Call 速查）

### 症状：fallback 率飙升
1. 看 sanity fail 细分（哪一类错）
2. 看 vLLM 日志是否有 OOM / CUDA error
3. 如果是模型本身问题 → 立即降灰度到 0%
4. 写事故报告

### 症状：vLLM 挂了
1. 拉起副本（k8s auto restart 应该处理）
2. 流量全部回 Claude
3. 排查 OOM / 硬件

### 症状：某类任务突然质量下降
1. 抽 20 条样本看 diff
2. 看是不是新加的 skill 没训
3. 临时加白名单让这类走 Claude
4. 回炉数据训新版
