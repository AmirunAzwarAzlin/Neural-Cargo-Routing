"""Vercel Python entrypoint: exposes the FastAPI ASGI app at api/index.py
so Vercel's @vercel/python runtime can serve it."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
