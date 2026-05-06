import sys
import os
import traceback

# Make the parent directory (backend/) importable so "from app.xxx import ..." works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app  # noqa: F401 — Vercel detects the ASGI app
except Exception as _import_err:
    # Surface the real traceback via a minimal ASGI app so Vercel logs it
    # and the /health endpoint returns the actual error instead of a blank 500.
    _tb = traceback.format_exc()
    print("IMPORT ERROR:", _tb, flush=True)

    async def app(scope, receive, send):  # type: ignore[no-redef]
        if scope["type"] == "http":
            body = f"Import failed:\n{_tb}".encode()
            await send({"type": "http.response.start", "status": 500,
                        "headers": [[b"content-type", b"text/plain"],
                                    [b"content-length", str(len(body)).encode()]]})
            await send({"type": "http.response.body", "body": body})
