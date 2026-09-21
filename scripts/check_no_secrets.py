#!/usr/bin/env python3
"""Pre-commit guard: blocks staged .env files, data/ contents, and key-shaped
strings from ever being committed."""
import os
import re
import subprocess
import sys

ALLOWED_ENV_FILES = {".env.example"}

BLOCKED_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\..+"),
    re.compile(r"^data/"),
]

KEY_PATTERNS = [
    re.compile(r"sb_secret_[A-Za-z0-9_-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT-shaped
    re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"),  # Gemini/Google API key shape
]


def _is_allowed_env_file(path: str) -> bool:
    return os.path.basename(path) in ALLOWED_ENV_FILES


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def staged_content(path: str) -> str | None:
    """The staged (index) version of a file's content — not the working
    tree, which could have been edited (secret removed) after `git add`
    without re-staging, letting it slip past a working-tree-only scan.

    Explicit UTF-8 decoding (rather than the platform locale default, e.g.
    cp1252 on Windows) so ordinary UTF-8 file content doesn't crash the scan.
    """
    result = subprocess.run(
        ["git", "show", f":{path}"], capture_output=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        return None
    return result.stdout


def main() -> int:
    files = staged_files()
    blocked = [
        f for f in files
        if not _is_allowed_env_file(f) and any(p.search(f) for p in BLOCKED_PATH_PATTERNS)
    ]
    if blocked:
        print("BLOCKED: attempting to commit sensitive paths:")
        for f in blocked:
            print(" -", f)
        return 1

    for f in files:
        content = staged_content(f)
        if content is None:
            continue
        for pattern in KEY_PATTERNS:
            if pattern.search(content):
                print(f"BLOCKED: {f} contains what looks like a live API key/secret.")
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
