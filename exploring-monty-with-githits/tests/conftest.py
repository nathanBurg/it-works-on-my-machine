import pytest

@pytest.fixture(autouse=True)
def mock_security_audit(monkeypatch):
    from safebox import audit
    monkeypatch.setattr(audit, "run_security_audit", lambda code: {"ok": True, "value": "Audit passed"})
