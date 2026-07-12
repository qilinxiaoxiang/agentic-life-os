from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".dockerignore",
    ".env",
    ".example",
    ".gitignore",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_FILES = {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12"}
FORBIDDEN_TEXT = {
    "/users/": "absolute macOS user path",
    "/home/": "absolute Linux user path",
    "file://": "local file URL",
}
SECRET_PATTERNS = {
    "GitHub token": re.compile(r"gh[oprsu]_[A-Za-z0-9_]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic credential": re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"]{8,}"),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
}


def tracked_candidates() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() in FORBIDDEN_FILES:
            files.append(path)
        elif path.suffix.lower() in TEXT_SUFFIXES or path.name in {
            "Dockerfile",
            "LICENSE",
            "AGENTS.md",
            "README.md",
        }:
            files.append(path)
    return files


def main() -> int:
    problems = []
    forbidden_text = dict(FORBIDDEN_TEXT)
    for token in os.environ.get("LIFEOS_PRIVACY_DENYLIST", "").split("|"):
        if token.strip():
            forbidden_text[token.strip().lower()] = "release-specific private identifier"
    for path in tracked_candidates():
        rel = path.relative_to(ROOT)
        if path.suffix.lower() in FORBIDDEN_FILES:
            problems.append(f"{rel}: forbidden runtime/credential file")
            continue
        text = path.read_text(errors="replace")
        lowered = text.lower()
        for token, reason in forbidden_text.items():
            if token in lowered:
                problems.append(f"{rel}: {reason} ({token})")
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                if label == "email address" and match.group(0).endswith("@example.com"):
                    continue
                problems.append(f"{rel}: possible {label}")
    if problems:
        print("Privacy check failed:")
        for problem in sorted(set(problems)):
            print(f"- {problem}")
        return 1
    print(f"Privacy check passed ({len(tracked_candidates())} files scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
