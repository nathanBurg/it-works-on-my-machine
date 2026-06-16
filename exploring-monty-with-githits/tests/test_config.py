from pathlib import Path

import pytest

from safebox.config import ConfigError, load_config


def test_missing_config_uses_secure_defaults(tmp_path: Path):
    config = load_config(cwd=tmp_path)

    assert config.used_defaults is True
    assert config.filesystem.allow_read == []
    assert config.filesystem.allow_write == []
    assert config.env.allow == []
    assert config.network.enabled is False
    assert config.model.effective_base_url() == "http://localhost:11434/v1"


def test_ollama_base_url_can_come_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test/v1")

    config = load_config(cwd=tmp_path)

    assert config.model.effective_base_url() == "http://ollama.test/v1"


def test_configured_base_url_wins_over_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test/v1")
    (tmp_path / "safebox.toml").write_text('[model]\nbase_url = "http://configured.test/v1"\n')

    config = load_config(cwd=tmp_path)

    assert config.model.effective_base_url() == "http://configured.test/v1"


def test_relative_paths_resolve_from_config_file(tmp_path: Path):
    (tmp_path / "safebox.toml").write_text('[filesystem]\nallow_read = ["data"]\nallow_write = ["out"]\n')

    config = load_config(cwd=tmp_path)

    assert config.filesystem.allow_read == [(tmp_path / "data").resolve()]
    assert config.filesystem.allow_write == [(tmp_path / "out").resolve()]


def test_invalid_toml_fails_clearly(tmp_path: Path):
    (tmp_path / "safebox.toml").write_text("[filesystem\n")

    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(cwd=tmp_path)


def test_invalid_field_type_fails(tmp_path: Path):
    (tmp_path / "safebox.toml").write_text('[filesystem]\nallow_read = "README.md"\n')

    with pytest.raises(ConfigError, match="must be a list"):
        load_config(cwd=tmp_path)


def test_network_true_is_phase_two_only(tmp_path: Path):
    (tmp_path / "safebox.toml").write_text('[network]\nenabled = true\n')

    with pytest.raises(ConfigError, match="Phase 2 only"):
        load_config(cwd=tmp_path)


def test_githits_true_is_phase_two_only(tmp_path: Path):
    (tmp_path / "safebox.toml").write_text('[helpers]\ngithits = true\n')

    with pytest.raises(ConfigError, match="Phase 2 only"):
        load_config(cwd=tmp_path)
