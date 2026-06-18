from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pydantic_monty

from .approval import ApprovalGate
from .config import SafeboxConfig
from .gates import AuditRecord, GateSet
from .monty_runner import ExecutionResult
from .snapshots import SnapshotMetadata, SnapshotStore, policy_fingerprint


@dataclass(frozen=True)
class SnapshotRunResult:
    execution: ExecutionResult
    metadata: SnapshotMetadata | None = None


class Phase3Runner:
    def __init__(self, config: SafeboxConfig, cwd: Path | None = None, store: SnapshotStore | None = None):
        self.config = config
        self.cwd = (cwd or Path.cwd()).resolve()
        self.store = store or SnapshotStore(self.cwd / ".safebox")

    def run(self, code: str) -> ExecutionResult:
        return self.start(code).execution

    def start(self, code: str) -> SnapshotRunResult:
        gates = GateSet(self.config, cwd=self.cwd)
        approval = ApprovalGate()
        streams: list[tuple[str, str]] = []

        def collect(stream: str, text: str) -> None:
            streams.append((stream, text))

        try:
            progress = pydantic_monty.Monty(code).start(print_callback=collect)
            progress = self._dispatch_until_pause_or_complete(progress, gates, approval)
        except pydantic_monty.MontyError as exc:
            return SnapshotRunResult(_execution(False, None, streams, str(exc), _audit(gates, approval)))
        except Exception as exc:
            return SnapshotRunResult(_execution(False, None, streams, f"Host execution error: {exc}", _audit(gates, approval)))

        if _is_complete(progress):
            return SnapshotRunResult(_execution(True, progress.output, streams, None, _audit(gates, approval)))
        if _function_name(progress) != "request_approval":
            return SnapshotRunResult(
                _execution(False, None, streams, f"Unsupported pending helper: {_function_name(progress)}", _audit(gates, approval))
            )

        reason = str(progress.args[0]) if progress.args else "approval requested"
        approval.request_approval(reason)
        audit = _audit(gates, approval)
        metadata = self.store.save(
            snapshot_bytes=progress.dump(),
            config=self.config,
            code=code,
            pending_helper=str(_function_name(progress)),
            pending_args=progress.args,
            pending_kwargs=progress.kwargs,
            audit=audit,
        )
        output = {
            "ok": True,
            "value": (
                f"snapshot saved: {self.store.snapshot_path}\n"
                "next: exit this session, then run:\n"
                "uv run safebox-3 resume --approve --config configs/phase3-snapshot.toml"
            ),
        }
        return SnapshotRunResult(_execution(True, output, streams, None, audit), metadata)

    def resume(self, *, approved: bool) -> ExecutionResult:
        gates = GateSet(self.config, cwd=self.cwd)
        approval = ApprovalGate()
        streams: list[tuple[str, str]] = []

        def collect(stream: str, text: str) -> None:
            streams.append((stream, text))

        try:
            metadata = self.store.load_metadata()
            config_error = _config_mismatch_error(metadata.config_path, self.config.source_path)
            if config_error is not None:
                return _execution(False, None, streams, config_error, [])
            policy_error = _policy_mismatch_error(metadata, self.config)
            if policy_error is not None:
                return _execution(False, None, streams, policy_error, [])
            snapshot_bytes = self.store.load_snapshot_bytes()
            self.store.clear()
            snapshot = pydantic_monty.load_snapshot(snapshot_bytes, print_callback=collect)
            if _function_name(snapshot) != "request_approval":
                return _execution(False, None, streams, f"Snapshot is pending unsupported helper: {_function_name(snapshot)}", [])
            reason = str(metadata.pending_args[0]) if metadata.pending_args else "approval requested"
            approval_result = approval.record_resume(approved, reason)
            progress = snapshot.resume({"return_value": approval_result})
            progress = self._dispatch_until_pause_or_complete(progress, gates, approval)
        except pydantic_monty.MontyError as exc:
            return _execution(False, None, streams, str(exc), _audit(gates, approval))
        except Exception as exc:
            return _execution(False, None, streams, f"Host execution error: {exc}", _audit(gates, approval))

        if not _is_complete(progress):
            return _execution(False, None, streams, f"Unsupported pending helper: {_function_name(progress)}", _audit(gates, approval))
        return _execution(True, progress.output, streams, None, _audit(gates, approval))

    def _dispatch_until_pause_or_complete(self, progress: Any, gates: GateSet, approval: ApprovalGate) -> Any:
        while not _is_complete(progress):
            name = _function_name(progress)
            if name == "request_approval":
                return progress
            result = _dispatch_helper(name, progress.args, progress.kwargs, gates)
            progress = progress.resume({"return_value": result})
        return progress


def _dispatch_helper(name: str, args: tuple[Any, ...], kwargs: dict[str, Any], gates: GateSet) -> Any:
    helpers = gates.external_functions()
    helper = helpers.get(name)
    if helper is None:
        return {"ok": False, "error": f"Refused: unknown helper: {name}"}
    return helper(*args, **kwargs)


def _is_complete(progress: Any) -> bool:
    return type(progress).__name__ == "MontyComplete"


def _function_name(progress: Any) -> str:
    return str(progress.function_name)


def _config_mismatch_error(saved_config_path: str | None, active_config_path: Path | None) -> str | None:
    if saved_config_path is None and active_config_path is None:
        return None
    if saved_config_path is None or active_config_path is None:
        return "Snapshot was created with a different config; resume refused"
    if Path(saved_config_path).resolve() != active_config_path.resolve():
        return f"Snapshot was created with a different config: {saved_config_path}"
    return None


def _policy_mismatch_error(metadata: SnapshotMetadata, active_config: SafeboxConfig) -> str | None:
    if metadata.policy_fingerprint != policy_fingerprint(active_config):
        return "Snapshot policy no longer matches the active config"
    return None


def _audit(gates: GateSet, approval: ApprovalGate) -> list[AuditRecord]:
    return list(approval.audit) + list(gates.audit)


def _execution(ok: bool, output: Any, streams: list[tuple[str, str]], error: str | None, audit: list[AuditRecord]) -> ExecutionResult:
    return ExecutionResult(
        ok=ok,
        output=output,
        stdout="".join(text for stream, text in streams if stream == "stdout"),
        stderr="".join(text for stream, text in streams if stream == "stderr"),
        error=error,
        audit=audit,
    )
