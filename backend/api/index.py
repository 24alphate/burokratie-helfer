import sys
import os

# Make the parent directory (backend/) importable so "from app.xxx import ..." works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401 — Vercel detects the ASGI app
