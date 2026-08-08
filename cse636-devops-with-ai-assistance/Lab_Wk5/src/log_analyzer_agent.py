"""Part B: a small "log analyzer agent" instrumented with OTel GenAI
conventions.

1. Accepts a chunk of log text.
2. "Calls an LLM" to identify anomalies (simulated - see README for why:
   no ANTHROPIC_API_KEY is configured in this environment).
3. Emits an OTel span with gen_ai.system, gen_ai.request.model,
   gen_ai.usage.input_tokens, gen_ai.usage.output_tokens.

Run with: uv run python src/log_analyzer_agent.py
Captures spans to output/part_b_spans.log and writes the summary table to
output/part_b_summary.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from telemetry import SimulatedResponse, configure_tracer, estimate_cost_usd, simulated_llm_call

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

PROMPT_TEMPLATE = """You are a log analysis assistant. Identify anomalies \
(errors, warnings, unusual patterns) in the following log window and \
summarize the likely issue in 2-3 sentences.

LOG WINDOW:
{log_text}
"""


def simulate_llm_analysis(log_text: str) -> str:
    """Stand-in for a real Claude call: derive a plausible analysis from the
    actual log content (error/warn counts, dominant service) so the
    simulated response is grounded in the input rather than canned."""
    lines = log_text.strip().splitlines()
    errors = [l for l in lines if " ERROR " in l]
    warns = [l for l in lines if " WARN " in l]

    services = re.findall(r"service=(\S+)", log_text)
    top_service = max(set(services), key=services.count) if services else "unknown"

    if not errors and not warns:
        return (
            f"No anomalies detected in this {len(lines)}-line window. "
            f"All entries are INFO/DEBUG level and consistent with normal operation."
        )

    sample_error = errors[0].split("service=", 1)[-1] if errors else warns[0].split("service=", 1)[-1]
    return (
        f"Detected {len(errors)} error(s) and {len(warns)} warning(s) across {len(lines)} lines, "
        f"concentrated in service={top_service}. Representative signal: '{sample_error.strip()}'. "
        f"Pattern suggests a downstream dependency degradation (timeouts/connection issues) "
        f"rather than an isolated client error."
    )


def analyze_log_window(tracer, log_text: str) -> SimulatedResponse:
    prompt = PROMPT_TEMPLATE.format(log_text=log_text)
    response_text = simulate_llm_analysis(log_text)
    return simulated_llm_call(
        tracer,
        prompt=prompt,
        response_text=response_text,
        span_name="analyze_log_window",
        extra_attributes={"log_window.chars": len(log_text), "log_window.lines": len(log_text.splitlines())},
    )


def build_windows(all_lines: list[str]) -> list[str]:
    """5 log windows of varying size, one of which straddles the incident
    (lines ~200-215 by minute, but log volume is higher there so we pick by
    line count, not fixed offsets) so the agent has something interesting to
    say for at least one window."""
    total = len(all_lines)
    # anchor one small/medium window on the incident-heavy region (~40% mark
    # given generate_data's higher log volume 200-215/500 minutes)
    incident_center = int(total * 0.42)

    windows = {
        "tiny (10 lines, normal)": all_lines[0:10],
        "small (30 lines, normal)": all_lines[40:70],
        "medium (80 lines, incident)": all_lines[
            max(0, incident_center - 40) : incident_center + 40
        ],
        "large (200 lines, incident+recovery)": all_lines[
            max(0, incident_center - 80) : incident_center + 120
        ],
        "xlarge (400 lines, full context)": all_lines[0:400],
    }
    return windows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tracer = configure_tracer(
        "log-analyzer-agent", span_log_path=str(OUTPUT_DIR / "part_b_spans.log")
    )

    logs_path = DATA_DIR / "logs_sample.txt"
    all_lines = logs_path.read_text(encoding="utf-8").splitlines()

    windows = build_windows(all_lines)

    rows = []
    for label, lines in windows.items():
        log_text = "\n".join(lines)
        result = analyze_log_window(tracer, log_text)
        cost = estimate_cost_usd(result.input_tokens, result.output_tokens)
        rows.append(
            {
                "window": label,
                "chars": len(log_text),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "latency_ms": round(result.latency_ms, 1),
                "cost_usd": round(cost, 6),
                "analysis": result.text,
            }
        )
        print(f"[{label}] {len(log_text)} chars -> {result.input_tokens} in / "
              f"{result.output_tokens} out tok, {result.latency_ms:.1f}ms, ${cost:.6f}")
        print(f"  {result.text}\n")

    # force flush of the BatchSpanProcessor before the interpreter exits
    from opentelemetry import trace as _trace

    _trace.get_tracer_provider().force_flush()

    summary_path = OUTPUT_DIR / "part_b_summary.md"
    lines_md = [
        "# Part B — Log Window Summary\n",
        "| Log window | Log window size (chars) | Input tokens | Output tokens | Latency (ms) | Estimated cost ($) |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines_md.append(
            f"| {r['window']} | {r['chars']} | {r['input_tokens']} | {r['output_tokens']} | "
            f"{r['latency_ms']} | {r['cost_usd']:.6f} |"
        )
    summary_path.write_text("\n".join(lines_md) + "\n", encoding="utf-8")
    print(f"wrote {summary_path}")

    (OUTPUT_DIR / "part_b_rows.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
