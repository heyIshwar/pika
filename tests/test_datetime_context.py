from pika.context.datetime import resolve_date_preset


def test_resolve_today_preset():
    filt, label = resolve_date_preset("today", tz_name="UTC")
    assert "createdAt" in filt
    assert "today" in label.lower()


def test_unknown_preset_raises():
    try:
        resolve_date_preset("next_quarter")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unknown date_preset" in str(exc)
