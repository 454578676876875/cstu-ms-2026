"""OTel setup + GenAI span helpers, shared by the Part B log-analyzer agent
and the Week 5 assignment's rca_agent.

Follows the OpenTelemetry Semantic Conventions for Generative AI:
https://opentelemetry.io/docs/specs/semconv/gen-ai/

No real LLM calls are made anywhere in this repo (see README for why) -
`simulated_llm_call()` fabricates a response and realistic token/latency
numbers so the spans below are meaningful without spending API credits.
"""

from __future__ import annotations

import random
import time
from contextlib import contextmanager
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

# --- Anthropic pricing used for cost estimation (per Anthropic's published
# pricing as of 2026-08; USD per million tokens). Update if pricing changes.
MODEL_PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

SIMULATED_MODEL = "claude-sonnet-5"


def configure_tracer(service_name: str, span_log_path: str | None = None) -> trace.Tracer:
    """Configure a TracerProvider that always prints spans to the console
    (so they can be captured to a file) and optionally also writes a
    dedicated NDJSON-ish export via ConsoleSpanExporter redirected to a file.
    """
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    exporters = [ConsoleSpanExporter()]
    if span_log_path:
        span_file = open(span_log_path, "w", encoding="utf-8")
        exporters.append(ConsoleSpanExporter(out=span_file))
    for exp in exporters:
        provider.add_span_processor(BatchSpanProcessor(exp))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


def estimate_cost_usd(input_tokens: int, output_tokens: int, model: str = SIMULATED_MODEL) -> float:
    pricing = MODEL_PRICING_PER_MTOK[model]
    return (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token), matching the rule of thumb
    Anthropic documents for English text when a real tokenizer isn't
    available offline."""
    return max(1, len(text) // 4)


@dataclass
class SimulatedResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float


def simulated_llm_call(
    tracer: trace.Tracer,
    prompt: str,
    response_text: str,
    model: str = SIMULATED_MODEL,
    span_name: str = "chat",
    extra_attributes: dict | None = None,
) -> SimulatedResponse:
    """Emit a GenAI-conventions span for one simulated LLM call and return
    fabricated-but-realistic usage/latency numbers.

    Real network latency for Claude is dominated by output length; we model
    that with a small fixed overhead plus a per-output-token cost, both with
    jitter, rather than a flat random number.
    """
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(response_text)

    with tracer.start_as_current_span(span_name) as span:
        start = time.perf_counter()

        # Simulate network + generation latency: ~40ms base + ~8ms/output token, +/-15% jitter
        simulated_seconds = (0.040 + output_tokens * 0.008) * random.uniform(0.85, 1.15)
        time.sleep(simulated_seconds)

        latency_ms = (time.perf_counter() - start) * 1000

        span.set_attribute("gen_ai.system", "anthropic")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.response.model", model)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        span.set_attribute("gen_ai.request.max_tokens", 1024)
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("simulated", True)
        span.set_attribute(
            "gen_ai.estimated_cost_usd", estimate_cost_usd(input_tokens, output_tokens, model)
        )
        if extra_attributes:
            for key, value in extra_attributes.items():
                span.set_attribute(key, value)

    return SimulatedResponse(
        text=response_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


@contextmanager
def tool_span(tracer: trace.Tracer, tool_name: str, **attrs):
    """Span wrapper for agent tool calls (e.g. get_metrics, get_logs),
    tagged per OTel GenAI conventions for tool execution."""
    with tracer.start_as_current_span(f"execute_tool {tool_name}") as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", tool_name)
        for key, value in attrs.items():
            span.set_attribute(key, value)
        yield span
