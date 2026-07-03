import pathlib
import sys
from collections import Counter

import yaml


def validate_registry():
    root = _project_root()
    path = root / "registry.yaml"
    if not path.exists():
        print("ERROR: registry.yaml not found")
        sys.exit(1)

    data = yaml.safe_load(path.read_text())
    errors = []

    for kind in ("agents", "teams", "skills"):
        items = data.get(kind, [])
        ids = [item["id"] for item in items]
        dupes = [id_ for id_, n in Counter(ids).items() if n > 1]

        if dupes:
            errors.append(f"Duplicate {kind} IDs: {dupes}")

        for item in items:
            p = root / item["path"]
            if not p.exists():
                errors.append(f'{kind} path not found: {item["path"]}')
            if not item.get("owner"):
                errors.append(f'{kind}/{item["id"]} missing owner')

    if errors:
        for err in errors:
            print(f"REGISTRY ERROR: {err}")
        sys.exit(1)

    agents_n = len(data.get("agents", []))
    teams_n = len(data.get("teams", []))
    skills_n = len(data.get("skills", []))
    print(f"registry.yaml OK ({agents_n} agents, {teams_n} teams, {skills_n} skills)")


def _project_root() -> pathlib.Path:
    return pathlib.Path.cwd()
