from __future__ import annotations

import ast
import json
import subprocess
import sys
from typing import Any

from .config import SafeboxConfig
from .gates import AuditRecord

def extract_imports(code: str) -> set[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    
    packages = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                packages.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                packages.add(node.module.split('.')[0])
    
    return {pkg for pkg in packages if pkg not in sys.stdlib_module_names and pkg}

class PreflightScreening:
    def __init__(self, config: SafeboxConfig):
        self.config = config
        self.timeout = 30
        self.audit: list[AuditRecord] = []

    def screen_code(self, code: str) -> dict[str, Any]:
        packages = extract_imports(code)
        
        for pkg in packages:
            # 1. Vuln Check (Mandatory lookup)
            vuln_cmd = ["npx", "githits@latest", "pkg", "vulns", f"pypi:{pkg}", "--json"]
            try:
                completed = subprocess.run(vuln_cmd, capture_output=True, text=True, timeout=self.timeout, check=False)
                if completed.returncode != 0:
                    self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, "security check cannot be completed"))
                    return {"ok": False, "error": f"Failed to complete security check for {pkg}"}
                
                # Check output for high/critical vulnerabilities
                # If we get any returned results from the backend while filtering for severity, it means there are vulns.
                # Actually, the command outputs a JSON envelope, let's parse it if possible.
                try:
                    vuln_data = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    vuln_data = {}
                
                # Just checking if any critical/high vulns exist in the output text or parsed json
                if "critical" in completed.stdout.lower() or "high" in completed.stdout.lower() or (vuln_data and isinstance(vuln_data, list) and len(vuln_data) > 0) or (vuln_data and isinstance(vuln_data, dict) and vuln_data.get("advisories")):
                    if self.config.security.block_high_vulnerabilities:
                        self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, "package contains high/critical vulnerabilities"))
                        return {"ok": False, "error": f"Package {pkg} contains high or critical security alerts"}
            except subprocess.TimeoutExpired:
                self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, "security check timeout"))
                return {"ok": False, "error": f"Timeout getting vulnerabilities for {pkg}"}

            # 2. License Check
            info_cmd = ["npx", "githits@latest", "pkg", "info", f"pypi:{pkg}", "--json"]
            try:
                completed = subprocess.run(info_cmd, capture_output=True, text=True, timeout=self.timeout, check=False)
                if completed.returncode != 0:
                    self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, "license check cannot be completed"))
                    return {"ok": False, "error": f"Failed to complete license check for {pkg}"}
                
                try:
                    info_data = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    info_data = {}
                
                # Try to extract license from JSON
                license = info_data.get("license") if isinstance(info_data, dict) else None
                if not license:
                    # Maybe it's nested or we just check the string representation
                    pass
                
                if license and self.config.security.blacklisted_licenses and license in self.config.security.blacklisted_licenses:
                    self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, f"package has blacklisted license: {license}"))
                    return {"ok": False, "error": f"Package {pkg} has blacklisted license: {license}"}
                
                # Check string representation if exact license key is missing
                for bl_license in self.config.security.blacklisted_licenses:
                    if bl_license.lower() in completed.stdout.lower():
                        self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, f"package has blacklisted license: {bl_license}"))
                        return {"ok": False, "error": f"Package {pkg} has blacklisted license: {bl_license}"}

            except subprocess.TimeoutExpired:
                self.audit.append(AuditRecord("preflight_screening", "DENY", pkg, "license check timeout"))
                return {"ok": False, "error": f"Timeout getting license info for {pkg}"}
            
            self.audit.append(AuditRecord("preflight_screening", "ALLOW", pkg, "package screened successfully"))

        return {"ok": True}
