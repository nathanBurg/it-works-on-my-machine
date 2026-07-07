from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .gates import AuditRecord


@dataclass
class GitHitsHelperSet:
    enabled: bool
    timeout: int = 30

    def __post_init__(self) -> None:
        self.audit: list[AuditRecord] = []

    def clear_audit(self) -> None:
        self.audit.clear()

    def external_functions(self) -> dict[str, Any]:
        return {
            "fetch_url": self.fetch_url,
            "githits_search": self.githits_search,
            "githits_example": self.githits_example,
            "githits_screen": self.githits_screen,
        }

    def githits_screen(self, package: str) -> dict[str, Any]:
        if not self.enabled:
            return self._deny("githits_screen", package, "GitHits helper is disabled")
        if not package:
            return self._deny("githits_screen", package, "package is required")
        argv = ["npx", "githits@latest", "screen", package, "--json"]
        return self._run_githits("githits_screen", package, argv)

    def githits_search(self, query: str, target: str, source: str | None = None, limit: int = 5) -> dict[str, Any]:
        if not self.enabled:
            return self._deny("githits_search", target, "GitHits helper is disabled")
        if not target:
            return self._deny("githits_search", target, "target is required")
        if source is not None and source not in {"docs", "code", "symbol"}:
            return self._deny("githits_search", target, "source must be docs, code, or symbol")
        if limit < 1 or limit > 10:
            return self._deny("githits_search", target, "limit must be between 1 and 10")

        argv = ["npx", "githits@latest", "search", query, "--in", target, "--json", "--limit", str(limit)]
        if source is not None:
            argv.extend(["--source", source])
        return self._run_githits("githits_search", target, argv)

    def githits_example(self, query: str, lang: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            return self._deny("githits_example", query, "GitHits helper is disabled")
        argv = ["npx", "githits@latest", "example", query, "--json"]
        if lang:
            argv.extend(["--lang", lang])
        return self._run_githits("githits_example", query, argv)

    def fetch_url(self, url: str) -> dict[str, Any]:
        reason = "general network access is disabled; only GitHits helpers are available"
        self.audit.append(AuditRecord("fetch_url", "DENY", url, reason))
        return {"ok": False, "error": f"Refused: {reason}"}

    def _run_githits(self, helper: str, target: str, argv: list[str]) -> dict[str, Any]:
        self.audit.append(AuditRecord(helper, "ALLOW", target, "GitHits helper is enabled"))
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "GitHits command timed out"}
        except OSError as exc:
            return {"ok": False, "error": f"GitHits command failed: {exc}"}

        if completed.returncode != 0:
            error = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            return {"ok": False, "error": f"GitHits command failed: {error}"}
        return {"ok": True, "value": completed.stdout.strip()}

    def _deny(self, helper: str, target: str, reason: str) -> dict[str, Any]:
        self.audit.append(AuditRecord(helper, "DENY", target, reason))
        return {"ok": False, "error": f"Refused: {reason}"}


def merge_audit(primary: list[AuditRecord], extra: list[AuditRecord]) -> list[AuditRecord]:
    return primary + extra
