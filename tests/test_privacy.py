from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_repository_privacy_scan_passes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/privacy_check.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
