"""Agent evaluation harness — YAML question suites per agent."""
from __future__ import annotations

import json
import pathlib
from typing import Any

import yaml

from pika.core.context import set_role, set_tenant_id, set_user_id


def _eval_path(agent_id: str) -> pathlib.Path:
    return pathlib.Path.cwd() / "agents" / agent_id / "evals" / "questions.yaml"


def load_questions(
    agent_id: str,
    *,
    limit: int | None = None,
    question_id: str | None = None,
) -> list[dict[str, Any]]:
    path = _eval_path(agent_id)
    if not path.exists():
        raise FileNotFoundError(f"No eval file at {path}")

    data = yaml.safe_load(path.read_text()) or {}
    questions = data.get("questions") or []
    if question_id:
        questions = [q for q in questions if q.get("id") == question_id]
    if limit:
        questions = questions[:limit]
    return questions


def apply_question_context(question: dict[str, Any]) -> None:
    ctx = question.get("context") or {}
    if user_id := ctx.get("user_id"):
        set_user_id(str(user_id))
    if tenant_id := ctx.get("tenant_id"):
        set_tenant_id(str(tenant_id))
    if role := ctx.get("role"):
        set_role(str(role))


def _message(question: dict[str, Any]) -> str:
    return str(question.get("input") or question.get("message") or "").strip()


def _forbidden_patterns(question: dict[str, Any]) -> list[str]:
    return list(question.get("forbid_patterns") or question.get("must_not_contain") or [])


def validate_questions(questions: list[dict[str, Any]]) -> tuple[int, int, list[str]]:
    """Static validation of eval YAML (no LLM)."""
    passed = failed = 0
    lines: list[str] = []
    for q in questions:
        qid = q.get("id", "?")
        msg = _message(q)
        ok = bool(qid) and bool(msg)
        detail = "structure ok" if ok else "missing id or input/message"
        if ok:
            passed += 1
        else:
            failed += 1
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {qid}: {detail}")
    return passed, failed, lines


async def _run_live_once(agent, message: str) -> tuple[str, list[str]]:
    tools_called: list[str] = []
    parts: list[str] = []
    async for chunk in agent.arun(message, stream=True, stream_events=True):
        event = getattr(chunk, "event", None)
        if event == "ToolCallStarted":
            name = getattr(getattr(chunk, "tool", None), "tool_name", None)
            if name:
                tools_called.append(name)
        if event in (None, "RunContent"):
            content = getattr(chunk, "content", None)
            if content:
                parts.append(str(content))
    return "".join(parts), tools_called


def _check_live_result(question: dict[str, Any], text: str, tools_called: list[str]) -> tuple[bool, str]:
    ok = True
    reasons: list[str] = []

    for needle in question.get("expect_contains") or []:
        if str(needle).lower() not in text.lower():
            ok = False
            reasons.append(f"missing expected text: {needle!r}")

    for pat in _forbidden_patterns(question):
        if pat.lower() in text.lower():
            ok = False
            reasons.append(f"forbidden pattern: {pat!r}")

    required = question.get("expect_tools") or question.get("require_tools") or []
    if required and not any(t in tools_called for t in required):
        ok = False
        reasons.append(f"expected tools {required}, got {tools_called}")

    return ok, "; ".join(reasons) or f"tools={tools_called}"


async def run_live_question(agent, question: dict[str, Any]) -> tuple[bool, str]:
    apply_question_context(question)
    text, tools_called = await _run_live_once(agent, _message(question))
    return _check_live_result(question, text, tools_called)


async def run_eval(
    agent_id: str,
    *,
    live: bool = False,
    limit: int | None = None,
    question_id: str | None = None,
    output_json: bool = False,
) -> int:
    questions = load_questions(agent_id, limit=limit, question_id=question_id)
    if not questions:
        print(f"No eval questions for {agent_id}")
        return 0

    results: list[dict[str, Any]] = []
    passed = failed = 0

    if live:
        from pika.cli.commands.loader import load_agent

        agent = load_agent(agent_id)
        for q in questions:
            ok, detail = await run_live_question(agent, q)
            qid = q.get("id", "?")
            results.append({"id": qid, "ok": ok, "detail": detail})
            if ok:
                passed += 1
            else:
                failed += 1
    else:
        passed, failed, lines = validate_questions(questions)
        for line in lines:
            print(line)
        print(f"\n{passed} passed, {failed} failed (of {len(questions)}) — use --live for LLM checks")
        return 1 if failed else 0

    if output_json:
        print(json.dumps({"agent_id": agent_id, "passed": passed, "failed": failed, "results": results}))
    else:
        for row in results:
            status = "PASS" if row["ok"] else "FAIL"
            print(f"[{status}] {row['id']}: {row['detail']}")
        print(f"\n{passed} passed, {failed} failed (of {len(questions)})")

    return 1 if failed else 0
