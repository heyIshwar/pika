"""LangFuse evaluation runner (opt-in)."""


async def run_eval(agent_id: str):
    if not __import__("os").getenv("LANGFUSE_ENABLED", "").lower() == "true":
        print(f"LangFuse disabled — set LANGFUSE_ENABLED=true to eval {agent_id}")
        return

    try:
        from langfuse import Langfuse
    except ImportError:
        print("Install langfuse extra: pip install pika-agents[langfuse]")
        return

    lf = Langfuse()
    print(f"Running LangFuse eval for {agent_id} (project via env)")
    _ = lf
    print(f"Eval stub complete for {agent_id}")
