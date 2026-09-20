#!/usr/bin/env python3
"""Pre-commit guard: blocks staged .env files, data/ contents, and key-shaped
strings from ever being committed."""
import re
import subprocess
import sys

ALLOWED_ENV_FILES = {".env.example"}

BLOCKED_PATH_PATTERNS = [
    re.compile(r"^\.env$"),
    re.compile(r"^\.env\..*"),
    re.compile(r"^data/"),
]

KEY_PATTERNS = [
    re.compile(r"sb_secret_[A-Za-z0-9_-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT-shaped
    re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"),  # Gemini/Google API key shape
]


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def main() -> int:
    files = staged_files()
    blocked = [
        f for f in files
        if f not in ALLOWED_ENV_FILES and any(p.match(f) for p in BLOCKED_PATH_PATTERNS)
    ]
    if blocked:
        print("BLOCKED: attempting to commit sensitive paths:")
        for f in blocked:
            print(" -", f)
        return 1

    for f in files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except (FileNotFoundError, IsADirectoryError):
            continue
        for pattern in KEY_PATTERNS:
            if pattern.search(content):
                print(f"BLOCKED: {f} contains what looks like a live API key/secret.")
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
