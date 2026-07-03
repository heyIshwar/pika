# pika

Opinionated multi-agent framework on [Agno](https://github.com/agno-agi/agno). SQLite by default. Zero infra to start.

## Quickstart

```bash
cd pika
pip install -e '.[dev]'
cp .env.example .env
# set OPENAI_API_KEY in .env

pika check
pika choo                    # orchestrator (routes to best agent)
pika chu getting_started     # specific agent
# or: pikachu
# or: pika choo research_agent
```

## CLI

| Command | Description |
|---|---|
| `pika new agent <name>` | Scaffold agent |
| `pika new tool <name>` | Scaffold tool |
| `pika run [agent_id]` | REPL (default: orchestrator) |
| `pika chu [agent_id]` | Interactive run (default: orchestrator) |
| `pika choo [agent_id]` | Interactive run (default: orchestrator) |
| `pika serve` | AgentOS API server |
| `pika check` | Validate registry.yaml |
| `pika eval <agent_id>` | LangFuse evals (opt-in) |
| `pika optimize <agent_id>` | DSPy prompt optimize |
| `pika knowledge add <agent_id> --path <file/dir/url>` | Ingest docs/infra into an agent's knowledge base (RAG) |
| `pika knowledge add-db <agent_id> [--db-url ...]` | Ingest an existing DB's schema as searchable knowledge |
| `pika knowledge list <agent_id>` | List content ingested into an agent's knowledge base |
| `pikachu [agent_id]` | Interactive run (same as `pika chu`) |
| `pikachoo [agent_id]` | Interactive run (same as `pika choo`) |
| `pika-chu [agent_id]` | Hyphen alias for `pika chu` |
| `pika-choo [agent_id]` | Hyphen alias for `pika choo` |

In-package subcommand aliases (via `pika`):

| Alias | Canonical |
|---|---|
| `pika pikachu` | `pika chu` |
| `pika pikachoo` | `pika choo` |

## Create agent

```bash
pika new agent my_agent
# edit agents/my_agent/agent.py
# add entry to registry.yaml
pika check
pika chu my_agent
```

## RAG: turn existing infra/DB into an agentic interface

Two complementary building blocks, both driven by per-agent YAML config (`config/agents/<id>.yaml`):

**Knowledge (semantic search over existing docs/infra/DB schema)**
```yaml
# config/agents/my_agent.yaml
knowledge:
  collection: my_agent_knowledge   # vector table name
  embedder: openai                 # openai | ollama | sentence_transformer
  max_results: 5
```
```bash
pika knowledge add my_agent --path ./docs/runbook.pdf   # or a directory, or a URL
pika knowledge add-db my_agent --db-url postgresql://...  # ingest an existing DB's schema
pika knowledge list my_agent
```
Ingested content is retrieved automatically and added to the agent's context (Agno `Knowledge`, backed by the `vectordb` configured in `pika.yaml` — LanceDB hybrid search by default, or pgvector).

**Database skill (live queries against an existing DB)**
```python
from skills.database.skill import DatabaseSkill

class MyAgent(BaseAgent):
    skills = [DatabaseSkill()]  # list_tables / describe_table / run_sql_query
```
Defaults to pika's own configured database; point it at a separate existing database via `config/tools/database.yaml` (`db_url`, `schema`).

Use knowledge for "what does this mean / where do I find X" questions, and the database skill for "give me the actual current numbers" questions — see `research_agent` for both wired together.

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
