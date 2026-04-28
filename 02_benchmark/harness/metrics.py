"""Benchmark 指标实现。每个指标独立类，便于添加/修改。"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Protocol

from .case import BenchmarkCase, Trace


class Metric(ABC):
    name: str

    @abstractmethod
    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float: ...

    def aggregate(self, values: list[float]) -> float:
        """默认聚合是平均；指标可覆盖（比如 P95）。"""
        if not values:
            return 0.0
        return sum(values) / len(values)


class SuccessRate(Metric):
    name = "success_rate"
    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float:
        return float(trace.final_status == case.expected_status)


class ToolCallExactMatch(Metric):
    name = "tool_exact_match"
    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float:
        expected = case.expected_tools
        actual = [tc.name for tc in trace.tool_calls]
        return float(expected == actual)


class ToolCallF1(Metric):
    name = "tool_f1"
    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float:
        expected = set(case.expected_tools)
        actual = set(tc.name for tc in trace.tool_calls)
        if not expected and not actual:
            return 1.0
        if not expected or not actual:
            return 0.0
        tp = len(expected & actual)
        p = tp / len(actual) if actual else 0
        r = tp / len(expected) if expected else 0
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


class JSONValidRate(Metric):
    name = "json_valid_rate"
    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float:
        if not trace.tool_calls:
            return 1.0
        return sum(tc.arguments_valid_json for tc in trace.tool_calls) / len(trace.tool_calls)


class SchemaValidRate(Metric):
    """需要提供 tool schema。没提供时退化为 JSONValidRate。"""
    name = "schema_valid_rate"
    def __init__(self, tool_schemas: dict[str, dict] | None = None):
        self.schemas = tool_schemas or {}

    def compute_single(self, case: BenchmarkCase, trace: Trace) -> float:
        if not trace.tool_calls:
            return 1.0
        valid = 0
        for tc in trace.tool_calls:
            if not tc.arguments_valid_json or not isinstance(tc.arguments, dict):
                continue
            schema = self.schemas.get(tc.name)
            if schema is None:
                valid += 1  # 没 schema 可验证，当作通过
                continue
            try:
                import jsonschema
                jsonschema.validate(instance=tc.arguments, schema=schema)
                valid += 1
            except Exception:
                pass
        return valid / len(trace.tool_calls)


class LatencyMs(Metric):
    name = "latency_ms"
    def __init__(self, percentile: float | None = None):
        self.percentile = percentile
        if percentile:
            self.name = f"latency_p{int(percentile * 100)}_ms"

    def compute_single(self, case, trace) -> float:
        return trace.duration_ms

    def aggregate(self, values: list[float]) -> float:
        if not values:
            return 0.0
        if self.percentile is None:
            return sum(values) / len(values)
        sorted_v = sorted(values)
        idx = int(len(sorted_v) * self.percentile)
        idx = min(idx, len(sorted_v) - 1)
        return sorted_v[idx]


class TokensPerCase(Metric):
    name = "avg_tokens"
    def compute_single(self, case, trace) -> float:
        return float(trace.prompt_tokens + trace.completion_tokens)


class CostPerCase(Metric):
    """需要传入定价表（美元 / 1M token）。"""
    name = "avg_cost_usd"
    def __init__(self, input_price_per_m: float, output_price_per_m: float):
        self.ip = input_price_per_m
        self.op = output_price_per_m

    def compute_single(self, case, trace) -> float:
        return (trace.prompt_tokens * self.ip + trace.completion_tokens * self.op) / 1_000_000


DEFAULT_METRICS: list[Metric] = [
    SuccessRate(),
    ToolCallExactMatch(),
    ToolCallF1(),
    JSONValidRate(),
    TokensPerCase(),
    LatencyMs(percentile=0.5),
    LatencyMs(percentile=0.95),
]
