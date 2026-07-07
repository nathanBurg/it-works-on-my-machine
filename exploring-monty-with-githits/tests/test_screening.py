import subprocess
from unittest.mock import MagicMock
from safebox.config import SafeboxConfig, SecurityConfig
from safebox.screening import PreflightScreening

def test_extract_imports():
    code = """
import requests
from bs4 import BeautifulSoup
import sys
    """
    from safebox.screening import extract_imports
    imports = extract_imports(code)
    assert imports == {"requests", "bs4"}

def test_preflight_screening_allow(monkeypatch):
    config = SafeboxConfig()
    screening = PreflightScreening(config)
    
    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        if "info" in cmd:
            mock.stdout = '{"license": "MIT"}'
        elif "vulns" in cmd:
            mock.stdout = '[]'
        return mock
        
    monkeypatch.setattr(subprocess, "run", fake_run)
    
    result = screening.screen_code("import requests")
    assert result["ok"] is True
    assert len(screening.audit) == 1
    assert screening.audit[0].decision == "ALLOW"

def test_preflight_screening_block_license(monkeypatch):
    config = SafeboxConfig(security=SecurityConfig(blacklisted_licenses=["GPL"]))
    screening = PreflightScreening(config)
    
    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        if "info" in cmd:
            mock.stdout = '{"license": "GPL"}'
        elif "vulns" in cmd:
            mock.stdout = '[]'
        return mock
        
    monkeypatch.setattr(subprocess, "run", fake_run)
    
    result = screening.screen_code("import requests")
    assert result["ok"] is False
    assert "blacklisted license: GPL" in result["error"]

def test_preflight_screening_block_vuln(monkeypatch):
    config = SafeboxConfig(security=SecurityConfig(block_high_vulnerabilities=True))
    screening = PreflightScreening(config)
    
    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        if "info" in cmd:
            mock.stdout = '{"license": "MIT"}'
        elif "vulns" in cmd:
            mock.stdout = '[{"severity": "high"}]'
        return mock
        
    monkeypatch.setattr(subprocess, "run", fake_run)
    
    result = screening.screen_code("import requests")
    assert result["ok"] is False
    assert "high or critical security alerts" in result["error"]

def test_preflight_screening_timeout(monkeypatch):
    config = SafeboxConfig()
    screening = PreflightScreening(config)
    
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 30)
        
    monkeypatch.setattr(subprocess, "run", fake_run)
    
    result = screening.screen_code("import requests")
    assert result["ok"] is False
    assert "Timeout" in result["error"]

def test_preflight_screening_nonzero(monkeypatch):
    config = SafeboxConfig()
    screening = PreflightScreening(config)
    
    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 1
        return mock
        
    monkeypatch.setattr(subprocess, "run", fake_run)
    
    result = screening.screen_code("import requests")
    assert result["ok"] is False
    assert "Failed to complete security check" in result["error"]
