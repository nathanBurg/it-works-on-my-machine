from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pydantic_monty

from .config import SafeboxConfig
from .gates import AuditRecord, GateSet


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    output: Any | None
    stdout: str
    stderr: str
    error: str | None
    audit: list[AuditRecord]


class MontyRunner:
    def __init__(self, config: SafeboxConfig, cwd=None):
        self.config = config
        self.cwd = cwd

    def run(self, code: str) -> ExecutionResult:
        gates = GateSet(self.config, cwd=self.cwd)
        streams: list[tuple[str, str]] = []

        def collect(stream: str, text: str) -> None:
            streams.append((stream, text))

        try:
            monty = pydantic_monty.Monty(code)
            output = monty.run(external_functions=gates.external_functions(), print_callback=collect)
        except pydantic_monty.MontyError as exc:
            return ExecutionResult(
                ok=False,
                output=None,
                stdout=_join_stream(streams, "stdout"),
                stderr=_join_stream(streams, "stderr"),
                error=str(exc),
                audit=list(gates.audit),
            )
        except Exception as exc:
            return ExecutionResult(
                ok=False,
                output=None,
                stdout=_join_stream(streams, "stdout"),
                stderr=_join_stream(streams, "stderr"),
                error=f"Host execution error: {exc}",
                audit=list(gates.audit),
            )
        return ExecutionResult(
            ok=True,
            output=output,
            stdout=_join_stream(streams, "stdout"),
            stderr=_join_stream(streams, "stderr"),
            error=None,
            audit=list(gates.audit),
        )


def _join_stream(streams: list[tuple[str, str]], stream_name: str) -> str:
    return "".join(text for stream, text in streams if stream == stream_name)
