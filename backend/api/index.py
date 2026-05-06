import sys
import os
import traceback

# Make the parent directory (backend/) importable so "from app.xxx import ..." works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_import_error_tb: str = ""
try:
    from app.main import app as _real_app
    _import_ok = True
except Exception:
    _import_ok = False
    _import_error_tb = traceback.format_exc()
    print("BUROKRATIE IMPORT ERROR:\n" + _import_error_tb, flush=True)
    _real_app = None  # type: ignore[assignment]


# app must be defined unconditionally at module top-level for Vercel to detect it
if _import_ok:
    app = _real_app  # the real FastAPI ASGI app
else:
    async def app(scope, receive, send):  # type: ignore[misc]
        """Fallback ASGI: returns the real Python traceback so Vercel logs capture it."""
        if scope["type"] == "http":
            body = ("Backend import failed.\n\n" + _import_error_tb).encode()
            await send({
                "type": "http.response.start", "status": 500,
                "headers": [
                    [b"content-type", b"text/plain; charset=utf-8"],
                    [b"content-length", str(len(body)).encode()],
                    [b"access-control-allow-origin", b"*"],
                ],
            })
            await send({"type": "http.response.body", "body": body})
