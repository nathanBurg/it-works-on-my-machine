from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pydantic_monty

from .config import SafeboxConfig
from .gates import AuditRecord, GateSet
from .screening import PreflightScreening

@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output: Any | None
    stdout: str
    stderr: str
    error: str | None
    audit: list[AuditRecord]


class MontyRunner:
    def __init__(self, config: SafeboxConfig, cwd=None, extra_external_functions=None, extra_audit_sources=None):
        self.config = config
        self.cwd = cwd
        self.extra_external_functions = extra_external_functions or {}
        self.extra_audit_sources = extra_audit_sources or []

    def run(self, code: str) -> ExecutionResult:
        self._clear_extra_audit_sources()
        gates = GateSet(self.config, cwd=self.cwd)
        streams: list[tuple[str, str]] = []

        def collect(stream: str, text: str) -> None:
            streams.append((stream, text))
            
        screening = PreflightScreening(self.config)
        screening_result = screening.screen_code(code)
        
        # Combine screening audit with any existing audit records
        self.extra_audit_sources.append(screening)
        
        if not screening_result["ok"]:
            return ExecutionResult(
                ok=False,
                output=None,
                stdout="",
                stderr="",
                error=screening_result["error"],
                audit=self._audit(gates),
            )

        try:
            monty = pydantic_monty.Monty(code)
            external_functions = gates.external_functions() | self.extra_external_functions
            output = monty.run(external_functions=external_functions, print_callback=collect)
        except pydantic_monty.MontyError as exc:
            return ExecutionResult(
                ok=False,
                output=None,
                stdout=_join_stream(streams, "stdout"),
                stderr=_join_stream(streams, "stderr"),
                error=str(exc),
                audit=self._audit(gates),
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False,
                output=None,
                stdout=_join_stream(streams, "stdout"),
                stderr=_join_stream(streams, "stderr"),
                error=f"Host execution error: {exc}",
                audit=self._audit(gates),
            )
        return ExecutionResult(
            ok=True,
            output=output,
            stdout=_join_stream(streams, "stdout"),
            stderr=_join_stream(streams, "stderr"),
            error=None,
            audit=self._audit(gates),
        )

    def _audit(self, gates: GateSet):
        audit = list(gates.audit)
        for source in self.extra_audit_sources:
            audit.extend(source.audit)
        return audit

    def _clear_extra_audit_sources(self) -> None:
        for source in self.extra_audit_sources:
            clear_audit = getattr(source, "clear_audit", None)
            if clear_audit is not None:
                clear_audit()


def _join_stream(streams: list[tuple[str, str]], stream_name: str) -> str:
    return "".join(text for stream, text in streams if stream == stream_name)
