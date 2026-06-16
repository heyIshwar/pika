# pika

Opinionated multi-agent framework on [Agno](https://github.com/agno-agi/agno). SQLite by default. Zero infra to start.

## Quickstart

```bash
cd pika
pip install -e '.[dev]'
cp .env.example .env
# set OPENAI_API_KEY in .env

pika check
pika chu getting_started
# or: pikachu getting_started
# or: pika choo getting_started
```

## CLI

| Command | Description |
|---|---|
| `pika new agent <name>` | Scaffold agent |
| `pika new tool <name>` | Scaffold tool |
| `pika run <agent_id>` | REPL |
| `pika chu <agent_id>` | Interactive run (pikachu alias) |
| `pika choo <agent_id>` | Interactive run (pikachoo alias) |
| `pika serve` | AgentOS API server |
| `pika check` | Validate registry.yaml |
| `pika eval <agent_id>` | LangFuse evals (opt-in) |
| `pika optimize <agent_id>` | DSPy prompt optimize |
| `pikachu <agent_id>` | Interactive run (same as `pika chu`) |
| `pika-chu <agent_id>` | Hyphen alias for `pika chu` |
| `pika-choo <agent_id>` | Hyphen alias for `pika choo` |

## Create agent

```bash
pika new agent my_agent
# edit agents/my_agent/agent.py
# add entry to registry.yaml
pika check
pika chu my_agent
```

## Serve API

```bash
pika serve --port 8080
```

Uses Agno AgentOS — REST + WebSocket endpoints for registered agents.

## Optional extras

```bash
pip install -e '.[redis,mysql,dspy,langfuse,otel]'
```

## Project layout

```
pika/           # framework package
agents/         # your agents
tools/          # MCP tools
config/         # YAML config (overrides/ gitignored)
registry.yaml   # agent/tool manifest
```

## License

MIT
