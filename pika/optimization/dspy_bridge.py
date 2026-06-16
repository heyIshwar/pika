import re
from dataclasses import dataclass


@dataclass
class OptimizationResult:
    optimized_instructions: str
    demonstrations: list
    score_before: float
    score_after: float


def _extract_jinja_vars(prompt: str) -> list[str]:
    return re.findall(r"\{\{\s*(\w+)\s*\}\}", prompt)


def _restore_jinja_vars(text: str, original_prompt: str) -> str:
    for var in _extract_jinja_vars(original_prompt):
        placeholder = f"JINJA_{var.upper()}"
        text = text.replace(placeholder, "{{ " + var + " }}")
    return text


async def optimize_with_dspy(
    agent_id: str,
    current_prompt: str,
    examples: list[dict],
) -> OptimizationResult:
    try:
        import dspy
    except ImportError as exc:
        raise ImportError("Install dspy extra: pip install pika-agents[dspy]") from exc

    safe_prompt = re.sub(
        r"\{\{\s*(\w+)\s*\}\}",
        lambda m: f"JINJA_{m.group(1).upper()}",
        current_prompt,
    )

    class AgentSignature(dspy.Signature):
        instructions = dspy.InputField(desc="System prompt")
        question = dspy.InputField(desc="User message")
        answer = dspy.OutputField(desc="Agent response")

    predictor = dspy.ChainOfThought(AgentSignature)

    trainset = [
        dspy.Example(instructions=safe_prompt, question=ex["input"], answer=ex["output"]).with_inputs(
            "instructions", "question"
        )
        for ex in examples
    ]

    from dspy.evaluate import Evaluate

    from pika.optimization.metrics import answer_quality_metric

    evaluate = Evaluate(devset=trainset, metric=answer_quality_metric, num_threads=1)
    score_before = evaluate(predictor) / 100

    optimizer = dspy.MIPROv2(metric=answer_quality_metric, auto="light")
    optimized = optimizer.compile(predictor, trainset=trainset)
    score_after = evaluate(optimized) / 100

    new_instructions = optimized.predict.extended_signature.instructions
    new_instructions = _restore_jinja_vars(str(new_instructions), current_prompt)

    demos = [{"input": ex.question, "output": ex.answer} for ex in (optimized.demos or [])]

    return OptimizationResult(
        optimized_instructions=new_instructions,
        demonstrations=demos,
        score_before=score_before,
        score_after=score_after,
    )
