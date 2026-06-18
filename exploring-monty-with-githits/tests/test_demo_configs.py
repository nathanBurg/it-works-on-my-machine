from pathlib import Path

import pytest

from safebox.config import ConfigError, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = PROJECT_ROOT / "configs"
SCRATCH = PROJECT_ROOT / "scratch"


def test_deny_all_config_loads():
    config = load_config(CONFIGS / "deny-all.toml", cwd=PROJECT_ROOT)

    assert config.filesystem.allow_read == []
    assert config.filesystem.allow_write == []
    assert config.env.allow == []


def test_read_scratch_config_loads_and_resolves_scratch():
    config = load_config(CONFIGS / "read-scratch.toml", cwd=PROJECT_ROOT)

    assert config.filesystem.allow_read == [SCRATCH.resolve()]
    assert config.filesystem.allow_write == []


def test_write_scratch_config_loads_and_grants_only_scratch():
    config = load_config(CONFIGS / "write-scratch.toml", cwd=PROJECT_ROOT)

    assert config.filesystem.allow_read == [SCRATCH.resolve()]
    assert config.filesystem.allow_write == [SCRATCH.resolve()]


def test_env_demo_config_loads_demo_token_only():
    config = load_config(CONFIGS / "env-demo.toml", cwd=PROJECT_ROOT)

    assert config.env.allow == ["DEMO_TOKEN"]
    assert "OPENAI_API_KEY" in config.provider_secret_names()


def test_phase3_snapshot_config_loads_and_grants_only_scratch():
    config = load_config(CONFIGS / "phase3-snapshot.toml", cwd=PROJECT_ROOT)

    assert config.filesystem.allow_read == [SCRATCH.resolve()]
    assert config.filesystem.allow_write == [SCRATCH.resolve()]
    assert config.network.enabled is False
    assert config.helpers.githits is False


def test_invalid_network_config_fails():
    with pytest.raises(ConfigError, match="Phase 2 only"):
        load_config(CONFIGS / "invalid-network.toml", cwd=PROJECT_ROOT)


def test_invalid_githits_config_fails():
    with pytest.raises(ConfigError, match="Phase 2 only"):
        load_config(CONFIGS / "invalid-githits.toml", cwd=PROJECT_ROOT)
