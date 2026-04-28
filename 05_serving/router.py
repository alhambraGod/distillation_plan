"""
路由层：按规则选小模型 or Claude，提供 fallback。

设计：
- 输入任务 meta → 决定走哪个模型
- 小模型超时/失败/输出不合 schema → fallback 到 Claude
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


@dataclass
class RoutingMetrics:
    calls_small: int = 0
    calls_claude: int = 0
    fallbacks: int = 0
    timeouts: int = 0
    errors: int = 0
    sanity_fails: int = 0
    latencies_ms_small: list[float] = field(default_factory=list)
    latencies_ms_claude: list[float] = field(default_factory=list)


class AgentRouter:
    """
    规则：
    - task_type 在 TRAINED_WHITELIST 里 → 小模型
    - is_critical 任务（标记为关键路径）→ 强制 Claude
    - 其他 → 按 shadow/灰度比例
    - 小模型失败 → fallback Claude
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
    ):
        self.small_client = httpx.AsyncClient(base_url=small_url, timeout=small_timeout_s)
        self.small_model = small_model_name
        self.claude = claude_client
        self.small_timeout = small_timeout_s
        self.claude_timeout = claude_timeout_s
        self.canary_pct = canary_pct
        self.metrics = RoutingMetrics()

    # ---------------- routing decision ----------------
    def decide(self, task_meta: dict) -> Route:
        if task_meta.get("task_type") in self.CRITICAL:
            return Route.CLAUDE
        if task_meta.get("task_type") in self.TRAINED_WHITELIST:
            return Route.SMALL
        # 其他按 canary 概率走小模型
        import random
        if random.random() < self.canary_pct:
            return Route.SMALL
        return Route.CLAUDE

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

    # ---------------- calls ----------------
    async def _call_small(self, messages: list[dict], tools: list[dict] | None) -> dict:
        payload = {
            "model": self.small_model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        start = time.time()
        resp = await self.small_client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        self.metrics.latencies_ms_small.append((time.time() - start) * 1000)
        return data["choices"][0]["message"]

    async def _call_claude(self, messages: list[dict], tools: list[dict] | None) -> dict:
        start = time.time()
        resp = await self.claude.chat(messages=messages, tools=tools, timeout=self.claude_timeout)
        self.metrics.latencies_ms_claude.append((time.time() - start) * 1000)
        return resp

    # ---------------- public ----------------
    async def route_chat(self, messages: list[dict], tools: list[dict] | None, task_meta: dict) -> dict:
        route = self.decide(task_meta)

        if route == Route.SMALL:
            try:
                resp = await asyncio.wait_for(
                    self._call_small(messages, tools),
                    timeout=self.small_timeout,
                )
                self.metrics.calls_small += 1
                if not self.passes_sanity(resp, task_meta):
                    self.metrics.sanity_fails += 1
                    log.warning("sanity fail, fallback to Claude task=%s", task_meta.get("task_type"))
                    resp = await self._call_claude(messages, tools)
                    self.metrics.fallbacks += 1
                    self.metrics.calls_claude += 1
                return resp
            except asyncio.TimeoutError:
                self.metrics.timeouts += 1
                log.warning("small model timeout, fallback to Claude")
                resp = await self._call_claude(messages, tools)
                self.metrics.fallbacks += 1
                self.metrics.calls_claude += 1
                return resp
            except Exception as e:
                self.metrics.errors += 1
                log.warning("small model error: %s, fallback to Claude", e)
                resp = await self._call_claude(messages, tools)
                self.metrics.fallbacks += 1
                self.metrics.calls_claude += 1
                return resp

        # Claude 直连
        resp = await self._call_claude(messages, tools)
        self.metrics.calls_claude += 1
        return resp


# Prometheus-style metrics 导出（示例骨架）
def export_metrics(m: RoutingMetrics) -> str:
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
        f"router_latency_p95_ms{{route=\"small\"}} {_p95(m.latencies_ms_small):.1f}",
        f"router_latency_p95_ms{{route=\"claude\"}} {_p95(m.latencies_ms_claude):.1f}",
    ]
    return "\n".join(lines)
