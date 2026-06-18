from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .config import SafeboxConfig

Decision = Literal["ALLOW", "DENY"]


@dataclass(frozen=True)
class AuditRecord:
    helper: str
    decision: Decision
    target: str
    reason: str

    def render(self) -> str:
        return f"[gate] {self.decision} {self.helper} {self.target} - {self.reason}"


class GateSet:
    def __init__(self, config: SafeboxConfig, cwd: Path | None = None):
        self.config = config
        self.cwd = (cwd or Path.cwd()).resolve()
        self.audit: list[AuditRecord] = []

    def external_functions(self) -> dict[str, Any]:
        if not self.config.helpers.files:
            return {"get_env": self.get_env}
        return {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "list_files": self.list_files,
            "get_env": self.get_env,
        }

    def read_file(self, path: str) -> dict[str, Any]:
        resolved = self._resolve_request_path(path)
        allowed = self._is_allowed(resolved, self.config.filesystem.allow_read)
        if not allowed:
            return self._deny("read_file", resolved, "path is not allowlisted for read")
        try:
            value = resolved.read_text()
        except OSError as exc:
            self._record("read_file", "DENY", resolved, f"read failed: {exc}")
            return {"ok": False, "error": f"Refused: read failed: {exc}"}
        self._record("read_file", "ALLOW", resolved, "path is allowlisted for read")
        return {"ok": True, "value": value}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        resolved = self._resolve_request_path(path)
        allowed = self._is_allowed(resolved, self.config.filesystem.allow_write)
        if not allowed:
            return self._deny("write_file", resolved, "path is not allowlisted for write")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content)
        except OSError as exc:
            self._record("write_file", "DENY", resolved, f"write failed: {exc}")
            return {"ok": False, "error": f"Refused: write failed: {exc}"}
        self._record("write_file", "ALLOW", resolved, "path is allowlisted for write")
        return {"ok": True, "value": str(resolved)}

    def list_files(self, path: str) -> dict[str, Any]:
        resolved = self._resolve_request_path(path)
        allowed = self._is_allowed(resolved, self.config.filesystem.allow_read)
        if not allowed:
            return self._deny("list_files", resolved, "path is not allowlisted for read")
        try:
            entries = sorted(child.name for child in resolved.iterdir())
        except OSError as exc:
            self._record("list_files", "DENY", resolved, f"list failed: {exc}")
            return {"ok": False, "error": f"Refused: list failed: {exc}"}
        self._record("list_files", "ALLOW", resolved, "path is allowlisted for read")
        return {"ok": True, "value": entries}

    def get_env(self, name: str) -> dict[str, Any]:
        if name in self.config.provider_secret_names():
            self._record("get_env", "DENY", name, "provider API keys are host-only")
            return {"ok": False, "error": f"Refused: env var is host-only: {name}"}
        if name not in self.config.env.allow:
            self._record("get_env", "DENY", name, "env var is not allowlisted")
            return {"ok": False, "error": f"Refused: env var is not allowlisted: {name}"}
        value = os.environ.get(name)
        if value is None:
            self._record("get_env", "ALLOW", name, "env var is allowlisted but not set")
            return {"ok": True, "value": None}
        self._record("get_env", "ALLOW", name, "env var is allowlisted")
        return {"ok": True, "value": value}

    def _deny(self, helper: str, target: Path, reason: str) -> dict[str, Any]:
        self._record(helper, "DENY", target, reason)
        return {"ok": False, "error": f"Refused: {reason}: {target}"}

    def _record(self, helper: str, decision: Decision, target: Path | str, reason: str) -> None:
        self.audit.append(AuditRecord(helper=helper, decision=decision, target=str(target), reason=reason))

    def _resolve_request_path(self, path: str) -> Path:
        requested = Path(path).expanduser()
        if not requested.is_absolute():
            requested = self.cwd / requested
        return requested.resolve()

    @staticmethod
    def _is_allowed(path: Path, allowed_paths: list[Path]) -> bool:
        for allowed in allowed_paths:
            if path == allowed:
                return True
            try:
                path.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False
