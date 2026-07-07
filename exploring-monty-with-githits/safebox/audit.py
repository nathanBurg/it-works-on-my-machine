import subprocess
import tempfile
from typing import Any

def run_security_audit(code: str) -> dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()
            result = subprocess.run(
                ["npx", "githits@latest", "audit", f.name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
                return {"ok": False, "error": f"Security audit blocked execution: {error_msg}"}
            return {"ok": True, "value": "Audit passed"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Security audit blocked execution: timeout"}
    except Exception as exc:
        return {"ok": False, "error": f"Security audit blocked execution: tool unavailable or error ({exc})"}
