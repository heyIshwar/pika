import os
from contextlib import contextmanager

LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"


class _NoopTracer:
    @contextmanager
    def span(self, name: str, **kwargs):
        yield


class _LangfuseTracer:
    def __init__(self, lf, component: str):
        self._lf = lf
        self._component = component

    @contextmanager
    def span(self, name: str, input=None, **kwargs):
        trace = self._lf.trace(name=f"{self._component}.{name}", input=input)
        try:
            yield trace
        finally:
            trace.update(status="success")


class _OtelTracer:
    def __init__(self, tracer):
        self._tracer = tracer

    @contextmanager
    def span(self, name: str, **kwargs):
        with self._tracer.start_as_current_span(name) as span:
            yield span


def get_tracer(component: str):
    if LANGFUSE_ENABLED:
        from langfuse import Langfuse

        return _LangfuseTracer(Langfuse(), component)
    if OTEL_ENABLED:
        from opentelemetry import trace

        return _OtelTracer(trace.get_tracer(component))
    return _NoopTracer()
