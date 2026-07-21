# Hermes bridge (MCP)

Pika agents can carry RAG, memory, evals — the full framework. Hermes (or any
MCP-capable chat shell) can drive them over Telegram, WhatsApp, and cron
without any of that logic being reimplemented on the Hermes side.

Pika is the brain. Hermes is a transport shell in front of it.

## Setup

```yaml
# pika.yaml
pika:
  mcp:
    enabled: true
```

```bash
pip install 'pika-agents[mcp]'   # installs fastmcp
pika serve --port 8080 --host 127.0.0.1
```

```bash
hermes mcp add pika --url http://127.0.0.1:8080/mcp
hermes mcp test pika
```

Hermes now has `run_agent(agent_id, message)`, `run_team`, `run_workflow`,
plus session and memory tools, all backed by AgentOS
(`agno/os/mcp.py`). Any registered pika agent — including ones with
knowledge bases attached — is reachable through those tools. Telegram
long-polling, WhatsApp (Baileys), and `hermes cron` become the delivery
layer; nothing about the agent changes.

## Notes

- Bind `pika serve` to `127.0.0.1` unless you have a reason to expose the
  MCP endpoint publicly — it is not authenticated separately from the rest
  of the AgentOS app.
- This is the supported integration path going forward. The
  `pika.core.hermes_skill.HermesSkillAdapter` / `pika.connectors.script_tool`
  pair (parsing agentskills.io `SKILL.md` + shelling out to a CLI script)
  still works for wrapping standalone connector scripts as pika skills, but
  it is not the way to connect Hermes itself to Pika — use the MCP bridge
  above for that.
