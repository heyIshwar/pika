import os
from pathlib import Path

import pytest

from pika.infra.embedder_model import (
    DEFAULT_EMBEDDER_MODEL_ID,
    resolve_sentence_transformer_model_path,
    vendor_embedder_model_dir,
)


def test_vendor_dir_under_package_root():
    vendor = vendor_embedder_model_dir()
    assert vendor.name == "all-MiniLM-L6-v2"
    assert vendor.parent.name == "models"
    assert vendor.parent.parent.name == "vendor"


def test_resolve_falls_back_to_hf_model_id_when_vendor_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("EMBEDDER_MODEL_PATH", raising=False)
    missing = tmp_path / "missing-vendor"
    monkeypatch.setattr(
        "pika.infra.embedder_model.vendor_embedder_model_dir",
        lambda: missing,
    )
    assert resolve_sentence_transformer_model_path() == DEFAULT_EMBEDDER_MODEL_ID


def test_resolve_uses_embedder_model_path_env(monkeypatch, tmp_path):
    model_dir = tmp_path / "custom-model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setenv("EMBEDDER_MODEL_PATH", str(model_dir))
    assert resolve_sentence_transformer_model_path() == str(model_dir.resolve())


def test_resolve_uses_vendored_model_when_present():
    vendor = vendor_embedder_model_dir()
    if not (vendor / "config.json").exists():
        pytest.skip("vendored embedder model not downloaded")
    assert resolve_sentence_transformer_model_path() == str(vendor.resolve())


def test_resolve_rejects_bad_embedder_model_path(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBEDDER_MODEL_PATH", str(tmp_path / "nope"))
    with pytest.raises(ValueError, match="not a directory"):
        resolve_sentence_transformer_model_path()
