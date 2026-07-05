"""Open Knowledge Format (OKF) markdown bundle ingest."""
from __future__ import annotations

import pathlib

import yaml

OKF_RESERVED_FILENAMES = frozenset({"index.md", "log.md"})


def parse_okf_file(path: pathlib.Path) -> dict | None:
    """Parse `---\\nYAML\\n---\\nbody` OKF concept file. Returns None if invalid."""
    text = path.read_text()
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    return {"meta": meta, "body": parts[2].strip()}


async def ingest_okf_bundle(kb, directories: list[pathlib.Path]) -> int:
    """Ingest OKF concept markdown files from one or more directories."""
    count = 0
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name in OKF_RESERVED_FILENAMES:
                continue
            parsed = parse_okf_file(path)
            if parsed is None:
                continue
            meta = parsed["meta"]
            entry_type = meta.get("type", "unknown")
            title = meta.get("title", path.stem)
            text = (
                f"{entry_type}: {title}\n"
                f"Also called: {', '.join(meta.get('tags') or []) or 'n/a'}\n"
                f"{meta.get('description', '')}\n\n"
                f"{parsed['body']}"
            )
            await kb.ainsert(
                name=f"okf:{entry_type}:{title}",
                text_content=text,
                metadata={
                    "kind": "okf",
                    "type": entry_type,
                    "title": title,
                    "tags": meta.get("tags") or [],
                },
            )
            count += 1
    return count
