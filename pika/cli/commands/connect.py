"""pika connect — generate BaseTool stubs from an OpenAPI spec."""
from __future__ import annotations

import pathlib
import re

import typer
from rich.console import Console

console = Console()

_TOOL_TEMPLATE = '''\
"""Auto-generated tool for {name} — {base_url}"""
from __future__ import annotations

import httpx
from agno.tools import tool as agno_tool
from pika import BaseTool

BASE_URL = "{base_url}"


class {class_name}(BaseTool):
    tool_id = "{tool_id}"

{methods}
'''

_METHOD_TEMPLATE = '''\
    @agno_tool(description="{summary}")
    async def {method_name}(self{params}) -> str:
        """Call {http_method} {path}"""
        async with httpx.AsyncClient() as client:
            resp = await client.{http_method_lower}(
                f"{{BASE_URL}}{path}",
                {call_args}
            )
            resp.raise_for_status()
            return resp.text
'''


def _to_identifier(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_").lower()


def _class_name(name: str) -> str:
    return "".join(w.title() for w in re.split(r"[^a-zA-Z0-9]", name) if w) + "Tool"


def connect_api(api_base_url: str, name: str):
    try:
        import httpx
    except ImportError:
        raise typer.BadParameter("httpx is required: pip install httpx")

    console.print(f"[bold purple]pika connect[/bold purple] → {api_base_url}")

    spec_url = api_base_url.rstrip("/") + "/openapi.json"
    try:
        resp = httpx.get(spec_url, timeout=10)
        resp.raise_for_status()
        spec = resp.json()
    except Exception as exc:
        console.print(f"[red]Failed to fetch OpenAPI spec from {spec_url}: {exc}[/red]")
        raise typer.Exit(1)

    methods_code: list[str] = []
    for path, path_item in spec.get("paths", {}).items():
        for http_method, operation in path_item.items():
            if http_method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = operation.get("operationId", f"{http_method}_{_to_identifier(path)}")
            summary = operation.get("summary", op_id)[:100]
            method_name = _to_identifier(op_id)

            # Collect path/query params
            params = operation.get("parameters", [])
            param_names = [p["name"] for p in params if p.get("in") in ("path", "query")]
            py_params = (", " + ", ".join(f"{_to_identifier(p)}: str" for p in param_names)) if param_names else ""

            if http_method in ("post", "put", "patch"):
                call_args = "json={}"
            else:
                call_args = "params={}"

            methods_code.append(
                _METHOD_TEMPLATE.format(
                    summary=summary,
                    method_name=method_name,
                    params=py_params,
                    http_method=http_method.upper(),
                    http_method_lower=http_method,
                    path=path,
                    call_args=call_args,
                )
            )

    if not methods_code:
        console.print("[yellow]No operations found in OpenAPI spec.[/yellow]")
        raise typer.Exit(0)

    tool_code = _TOOL_TEMPLATE.format(
        name=name,
        base_url=api_base_url.rstrip("/"),
        class_name=_class_name(name),
        tool_id=_to_identifier(name),
        methods="\n".join(methods_code),
    )

    tool_dir = pathlib.Path("tools") / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tool_dir / "tool.py"
    tool_file.write_text(tool_code)

    console.print(f"  [green]✓[/green] {tool_file}  ({len(methods_code)} endpoints)")

    # Patch registry.yaml
    registry_path = pathlib.Path("registry.yaml")
    if registry_path.exists():
        import yaml

        data = yaml.safe_load(registry_path.read_text()) or {}
        tools: list = data.setdefault("tools", [])
        tool_id = _to_identifier(name)
        if not any(t.get("id") == tool_id for t in tools):
            tools.append({"id": tool_id, "owner": "external", "path": str(tool_file)})
            registry_path.write_text(yaml.dump(data, default_flow_style=False))
            console.print("  [green]✓[/green] registry.yaml updated")

    console.print(f"\n[bold]Done![/bold]  Use [cyan]{_class_name(name)}[/cyan] in your agents.")
