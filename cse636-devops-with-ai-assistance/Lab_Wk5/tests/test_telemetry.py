import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from telemetry import estimate_cost_usd, estimate_tokens, simulated_llm_call, tool_span


def make_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter


def test_estimate_tokens_uses_four_chars_per_token_heuristic():
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("") == 1  # floor of 1, never zero


def test_estimate_cost_usd_matches_published_pricing():
    # claude-sonnet-5: $3.00/Mtok input, $15.00/Mtok output
    cost = estimate_cost_usd(1_000_000, 1_000_000, model="claude-sonnet-5")
    assert cost == 18.00


def test_estimate_cost_usd_scales_linearly():
    small = estimate_cost_usd(1000, 1000)
    large = estimate_cost_usd(10000, 10000)
    assert large == pytest.approx(small * 10)


def test_simulated_llm_call_emits_gen_ai_span_with_required_attributes():
    tracer, exporter = make_tracer()

    result = simulated_llm_call(
        tracer, prompt="short prompt", response_text="ok", span_name="unit_test_call"
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.name == "unit_test_call"
    attrs = span.attributes
    assert attrs["gen_ai.system"] == "anthropic"
    assert attrs["gen_ai.request.model"] == "claude-sonnet-5"
    assert attrs["gen_ai.usage.input_tokens"] == estimate_tokens("short prompt")
    assert attrs["gen_ai.usage.output_tokens"] == estimate_tokens("ok")
    assert attrs["simulated"] is True

    assert result.input_tokens == attrs["gen_ai.usage.input_tokens"]
    assert result.output_tokens == attrs["gen_ai.usage.output_tokens"]
    assert result.latency_ms > 0


def test_tool_span_sets_execute_tool_attributes():
    tracer, exporter = make_tracer()

    with tool_span(tracer, "get_metrics", **{"incident.start": "t0"}):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "execute_tool get_metrics"
    assert span.attributes["gen_ai.operation.name"] == "execute_tool"
    assert span.attributes["gen_ai.tool.name"] == "get_metrics"
    assert span.attributes["incident.start"] == "t0"


def test_nested_spans_have_correct_parent():
    tracer, exporter = make_tracer()

    with tracer.start_as_current_span("parent") as parent_span:
        with tool_span(tracer, "get_logs"):
            pass

    spans = {s.name: s for s in exporter.get_finished_spans()}
    child = spans["execute_tool get_logs"]
    parent = spans["parent"]
    assert child.parent.span_id == parent.context.span_id
