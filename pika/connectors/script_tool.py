"""Run a connector CLI script and return stdout (prefer JSON)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional, Sequence, Union


def run_json_script(
    script: Union[str, Path],
    args: Sequence[str],
    *,
    timeout: int = 60,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[dict] = None,
) -> Any:
    """Execute ``python script …args`` and parse JSON stdout.

    On non-JSON stdout, return the raw string. Raises ``RuntimeError`` on
    non-zero exit or timeout.
    """
    script_path = Path(script).expanduser().resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"Connector script not found: {script_path}")

    cmd: List[str] = [sys.executable, str(script_path), *list(args)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Connector script timed out after {timeout}s: {script_path}") from exc

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"Connector script failed (exit {proc.returncode}): {script_path}\n{err}"
        )

    out = (proc.stdout or "").strip()
    if not out:
        return ""
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out
