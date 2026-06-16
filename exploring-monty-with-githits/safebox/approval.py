from __future__ import annotations

from .gates import AuditRecord


class ApprovalGate:
    def __init__(self) -> None:
        self.audit: list[AuditRecord] = []

    def request_approval(self, reason: str) -> dict[str, str]:
        self.audit.append(AuditRecord("request_approval", "ALLOW", reason, "human approval required"))
        return {"ok": True, "value": "approval pending"}

    def record_resume(self, approved: bool, reason: str) -> dict[str, str]:
        if approved:
            self.audit.append(AuditRecord("request_approval", "ALLOW", reason, "human approved pending action"))
            return {"ok": True, "value": "approved"}
        self.audit.append(AuditRecord("request_approval", "DENY", reason, "human denied pending action"))
        return {"ok": False, "error": "Refused: approval denied"}
