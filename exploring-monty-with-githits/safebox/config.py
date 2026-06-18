from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 is unsupported by pyproject
    import tomli as tomllib  # type: ignore[no-redef]


class ConfigError(RuntimeError):
    """Raised when the local Safebox policy cannot be loaded."""


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "ollama"
    model: str = "gemma4:e4b"
    api_key_env: str | None = None
    base_url: str | None = None

    def effective_base_url(self) -> str | None:
        if self.base_url:
            return self.base_url
        if self.provider == "ollama":
            return os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
        return None


class FilesystemConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_read: list[Path] = Field(default_factory=list)
    allow_write: list[Path] = Field(default_factory=list)

    @field_validator("allow_read", "allow_write", mode="before")
    @classmethod
    def require_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of paths")
        return value


class EnvConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow: list[str] = Field(default_factory=list)

    @field_validator("allow", mode="before")
    @classmethod
    def require_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of env var names")
        return value


class NetworkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False

    @model_validator(mode="after")
    def phase_one_network_disabled(self) -> NetworkConfig:
        if self.enabled:
            raise ValueError("network.enabled=true is Phase 2 only; network is disabled in Phase 1")
        return self


class HelpersConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: bool = True
    githits: bool = False

    @model_validator(mode="after")
    def phase_one_githits_disabled(self) -> HelpersConfig:
        if self.githits:
            raise ValueError("helpers.githits=true is Phase 2 only")
        return self


class SafeboxConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: ModelConfig = Field(default_factory=ModelConfig)
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    env: EnvConfig = Field(default_factory=EnvConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    helpers: HelpersConfig = Field(default_factory=HelpersConfig)
    source_path: Path | None = None
    used_defaults: bool = False

    def provider_secret_names(self) -> set[str]:
        names = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}
        if self.model.api_key_env:
            names.add(self.model.api_key_env)
        return names


def load_config(path: Path | None = None, cwd: Path | None = None) -> SafeboxConfig:
    base_dir = (cwd or Path.cwd()).resolve()
    config_path = path if path is not None else base_dir / "safebox.toml"
    config_path = config_path.expanduser()
    if not config_path.is_absolute():
        config_path = base_dir / config_path
    config_path = config_path.resolve()

    if not config_path.exists():
        return SafeboxConfig(source_path=config_path, used_defaults=True)

    try:
        data = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config {config_path}: {exc}") from exc

    try:
        config = SafeboxConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid Safebox config {config_path}:\n{exc}") from exc

    config.source_path = config_path
    config.used_defaults = False
    config_dir = config_path.parent
    config.filesystem.allow_read = [_resolve_policy_path(config_dir, p) for p in config.filesystem.allow_read]
    config.filesystem.allow_write = [_resolve_policy_path(config_dir, p) for p in config.filesystem.allow_write]
    return config


def _resolve_policy_path(config_dir: Path, path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = config_dir / expanded
    return expanded.resolve()
