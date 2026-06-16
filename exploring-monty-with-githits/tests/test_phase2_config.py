from pathlib import Path

import pytest

from safebox.config import ConfigError, load_config
from safebox.phase2_config import load_phase2_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = PROJECT_ROOT / "configs"
SCRATCH = PROJECT_ROOT / "scratch"


def test_phase2_deny_all_loads():
    config = load_phase2_config(CONFIGS / "phase2-deny-all.toml", cwd=PROJECT_ROOT)

    assert config.network.enabled is False
    assert config.helpers.githits is False


def test_phase2_githits_loads_and_resolves_scratch():
    config = load_phase2_config(CONFIGS / "phase2-githits.toml", cwd=PROJECT_ROOT)

    assert config.network.enabled is True
    assert config.network.allow == ["githits"]
    assert config.helpers.githits is True
    assert config.filesystem.allow_read == [SCRATCH.resolve()]
    assert config.filesystem.allow_write == [SCRATCH.resolve()]


def test_phase2_invalid_network_fails():
    with pytest.raises(ConfigError, match="Phase 2 only supports network"):
        load_phase2_config(CONFIGS / "phase2-invalid-network.toml", cwd=PROJECT_ROOT)


def test_phase2_githits_requires_githits_network(tmp_path: Path):
    config_path = tmp_path / "bad.toml"
    config_path.write_text('[network]\nenabled = false\n\n[helpers]\ngithits = true\n')

    with pytest.raises(ConfigError, match="helpers.githits=true requires"):
        load_phase2_config(config_path, cwd=tmp_path)


def test_phase1_rejects_phase2_githits_config():
    with pytest.raises(ConfigError, match="Phase 2 only"):
        load_config(CONFIGS / "phase2-githits.toml", cwd=PROJECT_ROOT)
