---
marp: true
theme: default
paginate: true
header: 'L18 · 反思 + 答辩'
footer: 'distill_plan · v18 curriculum'
size: 16:9
style: |
  section { font-family: 'PingFang SC', sans-serif; font-size: 24px; }
  h1 { color: #0F172A; border-bottom: 4px solid #0F172A; padding-bottom: 8px; }
  h2 { color: #1E40AF; }
  section.cover { background: linear-gradient(135deg, #0F172A 0%, #1E40AF 100%); color: white; }
  section.cover h1 { color: white; border-bottom: 4px solid white; font-size: 56px; }
  table { margin: 0 auto; font-size: 20px; }
  th { background: #0F172A; color: white; padding: 6px 10px; }
  td { padding: 6px 10px; border-bottom: 1px solid #E5E7EB; }
  pre { background: #1E293B; color: #E2E8F0; border-radius: 6px; padding: 12px; font-size: 14px; }
  .big { font-size: 44px; text-align: center; color: #0F172A; }
  .highlight { background: #FEF3C7; padding: 2px 6px; border-radius: 4px; }
  .finish { background: linear-gradient(135deg, #FEF3C7 0%, #FBBF24 100%); padding: 16px; border-radius: 8px; }
---

<!-- _class: cover -->

# L18 · 方案反思 + 答辩

## 6 大问题 + DP1-DP5 + 结业

<br>

📅 **第 18 课 · 60 分钟**
📚 教材：`project_critique_and_fixes.md` + `06_decisions/*`

---

## 🎯 本课目标

- 系统回顾 6 大问题对策
- 掌握 DP1-DP5 决策点填法
- 通过**现场答辩**
- 发放结业证书 🎉

---

## 🚨 6 大问题回顾

| # | 问题 | 对策 |
|---|---|---|
| 1 | 目标定义模糊 | 任务切片 + KPI 量化 |
| 2 | 数据幸存者偏差 | 金 / 银 / 铜 / 黑分级 |
| 3 | Benchmark 缺维度 | 三层指标 + 三组对照 + Rubric |
| 4 | 训练路线漏洞 | 配比实验 + Pilot + 灾难性遗忘防护 |
| 5 | Fallback 空谈 | 5 触发器 + 熔断 + Shadow |
| 6 | 风险不全 | ToS + schema 版本 + TCO |

---

## 📋 问题 1：目标定义模糊

**不再说 "替代 Claude"** → 按任务切片定 KPI：

| 切片 | 优先级 | KPI |
|---|---|---|
| progress_report | 🟢 高 | 成本 ≤ 15% / 业务分 ≥ 4.0 |
| 工具参数构造 | 🟡 中 | JSON 99% / 字段 90% |
| submit_final_report 写作 | 🔴 低 | 人工 4.0/5 |
| 复杂多步规划 | ⚫ 不替代 | 保留 Claude |

---

## 📋 问题 2：数据分级

<div class="big">
金 (1-5%) / 银 (20-40%) / 铜 / 黑
</div>

<br>

- **训练集** = 金 + 银
- **Benchmark 回放** = 铜（测失败模式）
- **DPO rejected** = 黑

<br>

每样本**tier 字段标注**，贯穿 pipeline。

---

## 📋 问题 3：Benchmark 三层

```
结果：成功率、工具 F1
  ↑
诊断：首 token 延迟 / JSON 合法率 / 步骤分布 / 幻觉率
  ↑
业务：采纳率 / NPS / P95
```

+ 3 组对照（Claude 上限 / Haiku 横向 / base 下限）
+ Rubric 人工评分 Kappa ≥ 0.7

---

## 📋 问题 4：训练路线补强

- **Pilot** 选基座（不预设 Gemma）
- **配比实验 5 组**（防灾难性遗忘）
- **DPO 10% 人工抽检** 防 Judge bias
- **每版 adapter 做通用能力抽测**

---

## 📋 问题 5：Fallback 工程化

5 触发器：
1. 置信度低
2. Schema 校验失败
3. 重试失败
4. 超时
5. 业务白名单

+ 熔断器 + Shadow eval + 数据回流

---

## 📋 问题 6：隐性风险

- **Anthropic ToS**：第 1 周 Legal review
- **Tool schema 漂移**：版本化 + 绑定 adapter
- **Claude 迭代**：季度 re-review
- **TCO 反直觉**：盈亏点 3700 次/日

---

## 📋 DP1-DP5 决策点

| DP | 时间 | 决策 |
|---|---|---|
| **DP1** | W3 末 | 是否训练？训什么基座+教师+方法 |
| **DP2** | W7 末 | SFT 够吗？进 DPO 吗？ |
| **DP3** | W10 末 | DPO 有收益吗？上哪个版本？ |
| **DP4** | 灰度 | 切换下一阶段灰度？ |
| **DP5** | 稳定后 | 启动 RL 吗？哪一档？ |

每个 DP 都有一页纸模板（`06_decisions/`）

---

## 🎯 答辩环节（30 分钟）

每个学员**现场回答**：

**必答题**：
1. 蒸馏 vs 微调的区别，3 句话讲清
2. 我们项目数据为什么分级？
3. 为什么 DPO 的 lr 比 SFT 小 400x？
4. Fallback 的 5 个触发器是什么？
5. RL 三档落地分别是？

**随机题**（抽一道）：
- 如果 fallback 率突然飙到 50%，5 步内做什么？
- 黄金集 Kappa 只有 0.5，怎么办？
- Legal 说 ToS 违规，怎么办？

---

## 📝 最终提交

每个学员结业**必交**：

- [ ] 签字的 DP1 决策书（本项目）
- [ ] "我会怎么启动本项目" 2 页纸
- [ ] 跑通过的 SFT adapter 一个
- [ ] 至少一次完整 benchmark 报告
- [ ] 答辩通过

---

## 📊 本次培训成果回顾

18 课时后，你们应该能：

- [x] 独立设计数据 pipeline + 分级
- [x] 起草 eval_spec.md + 跑基线
- [x] 选教师 / 学生 / 蒸馏方法
- [x] 训练 SFT 并调优
- [x] 构造 DPO 偏好对并训练
- [x] 部署推理服务 + Fallback
- [x] 填 DP1-DP5 决策书
- [x] 回答业务方的"关键问题"

---

## 🛣️ 结业后的路

| 角色 | 下一步 |
|---|---|
| 学员 | 作为项目 owner 推动 POC |
| 团队 | 按 DP1 启动阶段 1 |
| 业务方 | 参与黄金集标注 + 抽检 |
| 管理层 | 看第一个 DP 的产出决定继续投入 |

---

<div class="finish">

## 🎉 结业致辞

<br>

你们 18 课时学完的不只是"怎么微调"，更是：

- **工程方法**：单变量实验 / 版本化 / rubric
- **风险意识**：ToS / 幸存者偏差 / reward hacking
- **决策框架**：DP1-DP5 清晰边界
- **业务对齐**：和业务方共同拥有指标

<br>

**这比任何一个具体算法都有价值**。

</div>

---

## 🏠 最后的作业

1. 一周内启动阶段 1（数据 + benchmark）
2. 一月内填完 DP1
3. 遇到坑回 `troubleshooting.md` 查
4. 每月更新笔记 / 补 troubleshooting

<br>

**通讯录**：团队 Slack + 导师邮件

---

<!-- _class: cover -->

# 🎓 结业

<br>

## 📜 颁发证书

完整技术资料：`distill_plan/`（86 个文件）
持续更新：GitHub repo

<br>

**感谢学习！祝项目顺利上线！**

---

## Q & A（最后一轮）

<br>

- 任何没讲到的技术细节
- 业务落地的困惑
- 团队协作问题
- 个人职业发展
