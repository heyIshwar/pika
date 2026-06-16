"""OTEL metrics helpers (opt-in via OTEL_ENABLED)."""

import os

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"


def get_meter(name: str):
    if not OTEL_ENABLED:
        return None
    from opentelemetry import metrics

    return metrics.get_meter(name)


def counter(name: str, description: str = ""):
    meter = get_meter("pika")
    if meter is None:
        return None
    return meter.create_counter(name, description=description)
