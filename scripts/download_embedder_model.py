#!/usr/bin/env python3
"""Download the default sentence-transformer embedder model into vendor/models/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pika.infra.embedder_model import (  # noqa: E402
    DEFAULT_EMBEDDER_MODEL_ID,
    EMBEDDER_ALLOW_PATTERNS,
    vendor_embedder_model_dir,
)


def download_model(target_dir: Path | None = None, *, force: bool = False) -> Path:
    target = (target_dir or vendor_embedder_model_dir()).resolve()
    if target.is_dir() and (target / "config.json").exists() and not force:
        print(f"Model already present at {target} (use --force to re-download)")
        return target

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("huggingface_hub is required (install pika-agents[embedder])") from exc

    target.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DEFAULT_EMBEDDER_MODEL_ID} -> {target}")
    snapshot_download(
        repo_id=DEFAULT_EMBEDDER_MODEL_ID,
        local_dir=str(target),
        allow_patterns=EMBEDDER_ALLOW_PATTERNS,
    )
    print(f"Done. Model saved to {target}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help=f"Output directory (default: {vendor_embedder_model_dir()})",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if model exists")
    args = parser.parse_args()
    download_model(args.target, force=args.force)


if __name__ == "__main__":
    main()
