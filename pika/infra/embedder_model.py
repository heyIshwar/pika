"""Local sentence-transformer embedder model path resolution."""
from __future__ import annotations

import os
import pathlib

DEFAULT_EMBEDDER_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDER_MODEL_DIRNAME = "all-MiniLM-L6-v2"
# Inference-only files (~90MB). Full HF repo includes ONNX/OpenVINO and is ~1GB.
EMBEDDER_ALLOW_PATTERNS = [
    "config.json",
    "config_sentence_transformers.json",
    "model.safetensors",
    "modules.json",
    "sentence_bert_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "1_Pooling/*",
    "README.md",
]
_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]
_DEFAULT_VENDOR_DIR = _PACKAGE_ROOT / "vendor" / "models" / DEFAULT_EMBEDDER_MODEL_DIRNAME


def vendor_embedder_model_dir() -> pathlib.Path:
    """Directory where the vendored embedder model is stored in-repo."""
    return _DEFAULT_VENDOR_DIR


def resolve_sentence_transformer_model_path() -> str:
    """
    Return a local directory path when the model is vendored, else the HF model id.

    Resolution order:
    1. $EMBEDDER_MODEL_PATH (directory)
    2. vendor/models/all-MiniLM-L6-v2 under the project root
    3. sentence-transformers/all-MiniLM-L6-v2 (download from Hugging Face on first use)
    """
    explicit = os.getenv("EMBEDDER_MODEL_PATH")
    if explicit:
        path = pathlib.Path(explicit).expanduser()
        if path.is_dir():
            return str(path.resolve())
        raise ValueError(f"EMBEDDER_MODEL_PATH is not a directory: {explicit!r}")

    vendor = vendor_embedder_model_dir()
    if vendor.is_dir() and (vendor / "config.json").exists():
        return str(vendor.resolve())

    return DEFAULT_EMBEDDER_MODEL_ID


def use_offline_hub_when_local(model_path: str) -> None:
    """Avoid Hugging Face network calls when loading from a local directory."""
    if pathlib.Path(model_path).is_dir():
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
