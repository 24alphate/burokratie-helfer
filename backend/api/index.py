import sys
import os
import traceback

# Make the parent directory (backend/) importable so "from app.xxx import ..." works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fallback ASGI app — will be replaced by the real FastAPI app if import succeeds.
# Defined first so Vercel's static analysis always finds a top-level `app` symbol.
_import_error_body = b"Backend startup failed — check Vercel function logs."


async def app(scope, receive, send):  # noqa: E302
    """Temporary fallback; replaced below if app.main imports successfully."""
    if scope["type"] == "http":
        body = _import_error_body
        await send({
            "type": "http.response.start", "status": 500,
            "headers": [
                [b"content-type", b"text/plain; charset=utf-8"],
                [b"content-length", str(len(body)).encode()],
                [b"access-control-allow-origin", b"*"],
            ],
        })
        await send({"type": "http.response.body", "body": body})


try:
    from app.main import app  # noqa: F811 — intentionally shadows the fallback above
except Exception:
    _tb = traceback.format_exc()
    _import_error_body = ("Backend import failed:\n\n" + _tb).encode()
    print("BUROKRATIE IMPORT ERROR:\n" + _tb, flush=True)
