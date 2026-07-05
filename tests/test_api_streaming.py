from pika.api.streaming import namespaced_session_id, sse_event
from pika.core.context import set_user_id


def test_sse_event_json():
    frame = sse_event({"type": "delta", "text": "hi"})
    assert frame.startswith("data: ")
    assert '"type": "delta"' in frame


def test_namespaced_session_id():
    set_user_id("u1")
    try:
        assert namespaced_session_id("sess-1") == "u1:sess-1"
    finally:
        set_user_id(None)
