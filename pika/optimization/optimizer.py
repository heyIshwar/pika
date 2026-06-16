import pathlib

import yaml

from pika.optimization.dspy_bridge import optimize_with_dspy


async def run_optimizer(agent_id: str):
    agent_dir = pathlib.Path("agents") / agent_id
    examples_path = agent_dir / "training_examples.yaml"

    if not examples_path.exists():
        print(f"No training_examples.yaml for {agent_id} — skipping")
        return

    with open(examples_path) as f:
        examples = yaml.safe_load(f) or []

    system_path = agent_dir / "prompts" / "system.j2"
    if not system_path.exists():
        print(f"No prompts/system.j2 for {agent_id} — skipping")
        return

    current_prompt = system_path.read_text()
    result = await optimize_with_dspy(
        agent_id=agent_id,
        current_prompt=current_prompt,
        examples=examples,
    )

    system_path.write_text(result.optimized_instructions)

    demos_path = agent_dir / "prompts" / "demonstrations.yaml"
    with open(demos_path, "w") as f:
        yaml.dump(result.demonstrations, f, default_flow_style=False)

    print(f"Optimization complete for {agent_id}")
    print(f"Score before: {result.score_before:.3f}  after: {result.score_after:.3f}")
