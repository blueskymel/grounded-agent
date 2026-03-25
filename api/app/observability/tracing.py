from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def trace_step(name: str):
    """Create an OpenTelemetry span when available; otherwise behave as a no-op."""
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("groundedagent")
        with tracer.start_as_current_span(name):
            yield
    except Exception:
        # Keep tracing optional so local runs and tests never fail on telemetry setup.
        yield
