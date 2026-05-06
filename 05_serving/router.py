"""
路由层：按规则选小模型 or fallback 教师模型，提供生产兜底。

设计：
- 输入任务 meta → 决定走哪个模型
- 小模型低置信度 / schema 失败 / 重试失败 / 超时 / 关键业务 → fallback
- 熔断器在小模型连续异常时直接切到教师模型
- 全程记录 metric（Prometheus 格式）
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

log = logging.getLogger(__name__)


class Route(Enum):
    SMALL = "small"
    CLAUDE = "claude"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RoutingMetrics:
    calls_small: int = 0
    calls_claude: int = 0
    fallbacks: int = 0
    timeouts: int = 0
    errors: int = 0
    sanity_fails: int = 0
    confidence_fails: int = 0
    retries: int = 0
    circuit_open_fallbacks: int = 0
    business_rule_fallbacks: int = 0
    fallback_reasons: dict[str, int] = field(default_factory=dict)
    latencies_ms_small: list[float] = field(default_factory=list)
    latencies_ms_claude: list[float] = field(default_factory=list)


@dataclass
class CircuitBreaker:
    """小模型异常率过高时熔断，避免每个请求都先慢失败再 fallback。"""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    opened_at: float = 0.0
    failure_threshold: int = 5
    reset_timeout_s: float = 60.0
    half_open_success_threshold: int = 3

    def allow_small(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.opened_at >= self.reset_timeout_s:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._open()
            return
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        self.failure_count = 0
        self.success_count = 0


class AgentRouter:
    """
    规则：
    - task_type 在 TRAINED_WHITELIST 里 → 小模型
    - is_critical 任务（标记为关键路径）→ 强制 Claude
    - 其他 → 按 shadow/灰度比例
    - 小模型低置信度 / schema 失败 / 重试失败 / 超时 → fallback Claude
    - 熔断 OPEN → 直接 fallback Claude
    """

    TRAINED_WHITELIST = {"marketing_ai_v2_simple", "marketing_ai_v2_mid"}
    CRITICAL = {"submit_publish", "billing", "auth"}

    def __init__(
        self,
        small_url: str,
        small_model_name: str,
        claude_client,
        small_timeout_s: float = 30.0,
        claude_timeout_s: float = 60.0,
        canary_pct: float = 0.0,   # 额外灰度流量比例
        retry_attempts: int = 2,
        confidence_threshold: float = -2.0,
    ):
        self.small_client = httpx.AsyncClient(base_url=small_url, timeout=small_timeout_s)
        self.small_model = small_model_name
        self.claude = claude_client
        self.small_timeout = small_timeout_s
        self.claude_timeout = claude_timeout_s
        self.canary_pct = canary_pct
        self.retry_attempts = retry_attempts
        self.confidence_threshold = confidence_threshold
        self.circuit = CircuitBreaker()
        self.metrics = RoutingMetrics()

    # ---------------- routing decision ----------------
    def decide(self, task_meta: dict) -> Route:
        if task_meta.get("is_critical") or task_meta.get("task_type") in self.CRITICAL:
            return Route.CLAUDE
        if task_meta.get("task_type") in self.TRAINED_WHITELIST:
            return Route.SMALL
        # 其他按 canary 概率走小模型
        import random
        if random.random() < self.canary_pct:
            return Route.SMALL
        return Route.CLAUDE

    def _record_fallback(self, reason: str) -> None:
        self.metrics.fallbacks += 1
        self.metrics.fallback_reasons[reason] = self.metrics.fallback_reasons.get(reason, 0) + 1

    def _business_rules_pass(self, resp: dict, task_meta: dict) -> bool:
        """业务专属规则入口：白名单、禁止社区、风控分等都放这里扩展。"""
        banned_subreddits = set(task_meta.get("banned_subreddits") or [])
        content = (resp.get("content") or resp.get("output") or "").lower()
        if banned_subreddits and any(sub.lower() in content for sub in banned_subreddits):
            return False
        max_risk = task_meta.get("max_cib_risk")
        risk = task_meta.get("cib_risk")
        if max_risk is not None and risk is not None and float(risk) > float(max_risk):
            return False
        return True

    # ---------------- sanity checks ----------------
    @staticmethod
    def passes_sanity(resp: dict, task_meta: dict) -> bool:
        """超快的输出合法性检查。失败就 fallback。"""
        if not resp:
            return False
        content = resp.get("content") or resp.get("output") or ""
        if not content or len(content.strip()) < 5:
            return False
        # tool_calls 的 arguments 必须是合法 JSON
        for tc in resp.get("tool_calls", []) or []:
            args = tc.get("function", {}).get("arguments") or tc.get("arguments")
            if isinstance(args, str):
                try:
                    json.loads(args)
                except Exception:
                    return False
        # 业务 specific：submit_final_report 必须有 schema
        expected_schema = task_meta.get("final_schema")
        if expected_schema:
            try:
                import jsonschema
                data = json.loads(content) if isinstance(content, str) else content
                jsonschema.validate(data, expected_schema)
            except Exception:
                return False
        return True

    @staticmethod
    def confidence_from_response(resp: dict) -> float | None:
        """从 OpenAI-compatible logprobs 或业务自定义字段取平均 logprob。"""
        value = resp.get("_avg_logprob") or resp.get("avg_logprob")
        if value is not None:
            return float(value)
        token_logprobs = resp.get("token_logprobs") or []
        if token_logprobs:
            return sum(float(x) for x in token_logprobs) / len(token_logprobs)
        return None

    # ---------------- calls ----------------
    async def _call_small(self, messages: list[dict], tools: list[dict] | None) -> dict:
        payload = {
            "model": self.small_model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.3,
            "max_tokens": 2048,
            "logprobs": True,
            "top_logprobs": 5,
        }
        start = time.time()
        resp = await self.small_client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        self.metrics.latencies_ms_small.append((time.time() - start) * 1000)
        choice = data["choices"][0]
        message = choice["message"]
        logprob_items = (choice.get("logprobs") or {}).get("content") or []
        token_logprobs = [
            item.get("logprob")
            for item in logprob_items
            if isinstance(item, dict) and item.get("logprob") is not None
        ]
        if token_logprobs:
            message["_avg_logprob"] = sum(token_logprobs) / len(token_logprobs)
            message["token_logprobs"] = token_logprobs
        return message

    async def _call_claude(self, messages: list[dict], tools: list[dict] | None) -> dict:
        start = time.time()
        resp = await self.claude.chat(messages=messages, tools=tools, timeout=self.claude_timeout)
        self.metrics.latencies_ms_claude.append((time.time() - start) * 1000)
        return resp

    # ---------------- public ----------------
    async def route_chat(self, messages: list[dict], tools: list[dict] | None, task_meta: dict) -> dict:
        route = self.decide(task_meta)

        if route == Route.CLAUDE:
            if task_meta.get("is_critical") or task_meta.get("task_type") in self.CRITICAL:
                self.metrics.business_rule_fallbacks += 1
                self.metrics.fallback_reasons["critical_task"] = (
                    self.metrics.fallback_reasons.get("critical_task", 0) + 1
                )
            resp = await self._call_claude(messages, tools)
            self.metrics.calls_claude += 1
            return resp

        if not self.circuit.allow_small():
            self.metrics.circuit_open_fallbacks += 1
            self._record_fallback("circuit_open")
            resp = await self._call_claude(messages, tools)
            self.metrics.calls_claude += 1
            return resp

        if route == Route.SMALL:
            for attempt in range(self.retry_attempts + 1):
                try:
                    resp = await asyncio.wait_for(
                        self._call_small(messages, tools),
                        timeout=self.small_timeout,
                    )
                    self.metrics.calls_small += 1

                    confidence = self.confidence_from_response(resp)
                    if confidence is not None and confidence < self.confidence_threshold:
                        self.metrics.confidence_fails += 1
                        reason = "low_confidence"
                    elif not self.passes_sanity(resp, task_meta):
                        self.metrics.sanity_fails += 1
                        reason = "schema_or_sanity"
                    elif not self._business_rules_pass(resp, task_meta):
                        self.metrics.business_rule_fallbacks += 1
                        reason = "business_rule"
                    else:
                        self.circuit.record_success()
                        return resp

                    if attempt < self.retry_attempts:
                        self.metrics.retries += 1
                        continue
                    log.warning("small model failed checks (%s), fallback task=%s", reason, task_meta.get("task_type"))
                    self.circuit.record_failure()
                    self._record_fallback(reason)
                    resp = await self._call_claude(messages, tools)
                    self.metrics.calls_claude += 1
                    return resp
                except asyncio.TimeoutError:
                    self.metrics.timeouts += 1
                    reason = "timeout"
                except Exception as e:
                    self.metrics.errors += 1
                    reason = "error"
                    log.warning("small model error: %s", e)

                if attempt < self.retry_attempts:
                    self.metrics.retries += 1
                    continue
                log.warning("small model %s, fallback to Claude", reason)
                self.circuit.record_failure()
                self._record_fallback(reason)
                resp = await self._call_claude(messages, tools)
                self.metrics.calls_claude += 1
                return resp

        resp = await self._call_claude(messages, tools)
        self.metrics.calls_claude += 1
        return resp


# Prometheus-style metrics 导出（示例骨架）
def export_metrics(m: RoutingMetrics, breaker: CircuitBreaker | None = None) -> str:
    def _p95(vals):
        if not vals: return 0.0
        s = sorted(vals)
        return s[int(len(s) * 0.95) - 1]
    lines = [
        f"router_calls_total{{route=\"small\"}} {m.calls_small}",
        f"router_calls_total{{route=\"claude\"}} {m.calls_claude}",
        f"router_fallbacks_total {m.fallbacks}",
        f"router_timeouts_total {m.timeouts}",
        f"router_errors_total {m.errors}",
        f"router_sanity_fails_total {m.sanity_fails}",
        f"router_confidence_fails_total {m.confidence_fails}",
        f"router_retries_total {m.retries}",
        f"router_circuit_open_fallbacks_total {m.circuit_open_fallbacks}",
        f"router_business_rule_fallbacks_total {m.business_rule_fallbacks}",
        f"router_latency_p95_ms{{route=\"small\"}} {_p95(m.latencies_ms_small):.1f}",
        f"router_latency_p95_ms{{route=\"claude\"}} {_p95(m.latencies_ms_claude):.1f}",
    ]
    for reason, count in sorted(m.fallback_reasons.items()):
        lines.append(f"router_fallbacks_total_by_reason{{reason=\"{reason}\"}} {count}")
    if breaker:
        lines.append(f"router_circuit_state{{state=\"{breaker.state.value}\"}} 1")
    return "\n".join(lines)
