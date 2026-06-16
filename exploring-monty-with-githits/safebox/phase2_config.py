from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator

from pydantic import BaseModel

from .config import ConfigError, SafeboxConfig, _resolve_policy_path, tomllib


class NetworkConfigV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allow: list[str] = Field(default_factory=list)

    @field_validator("allow", mode="before")
    @classmethod
    def require_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of network grants")
        return value

    @model_validator(mode="after")
    def only_githits_network(self) -> NetworkConfigV2:
        if self.enabled and self.allow != ["githits"]:
            raise ValueError('Phase 2 only supports network allow = ["githits"]')
        if not self.enabled and self.allow:
            raise ValueError("network.allow requires network.enabled=true")
        return self


class HelpersConfigV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: bool = True
    githits: bool = False


class SafeboxPhase2Config(SafeboxConfig):
    network: NetworkConfigV2 = Field(default_factory=NetworkConfigV2)
    helpers: HelpersConfigV2 = Field(default_factory=HelpersConfigV2)

    @model_validator(mode="after")
    def githits_requires_githits_network(self) -> SafeboxPhase2Config:
        if self.helpers.githits and not (self.network.enabled and self.network.allow == ["githits"]):
            raise ValueError('helpers.githits=true requires network.enabled=true and network.allow = ["githits"]')
        return self


def load_phase2_config(path: Path | None = None, cwd: Path | None = None) -> SafeboxPhase2Config:
    base_dir = (cwd or Path.cwd()).resolve()
    config_path = path if path is not None else base_dir / "safebox.toml"
    config_path = config_path.expanduser()
    if not config_path.is_absolute():
        config_path = base_dir / config_path
    config_path = config_path.resolve()

    if not config_path.exists():
        return SafeboxPhase2Config(source_path=config_path, used_defaults=True)

    try:
        data = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read config {config_path}: {exc}") from exc

    try:
        config = SafeboxPhase2Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid Safebox Phase 2 config {config_path}:\n{exc}") from exc

    config.source_path = config_path
    config.used_defaults = False
    config_dir = config_path.parent
    config.filesystem.allow_read = [_resolve_policy_path(config_dir, p) for p in config.filesystem.allow_read]
    config.filesystem.allow_write = [_resolve_policy_path(config_dir, p) for p in config.filesystem.allow_write]
    return config
