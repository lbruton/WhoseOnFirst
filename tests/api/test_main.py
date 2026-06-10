"""
SPA static-file catch-all tests (WOF-17).

Covers the path-traversal guard in serve_frontend: traversal and absolute
paths must fall back to index.html, while legitimate frontend assets and
route_map entries keep being served with the correct cache headers.

Layer 1 calls the endpoint function directly with raw path strings because
httpx (behind TestClient) normalizes literal "../" segments client-side and
would never deliver them to the route. Layer 2 exercises the percent-encoded
variant over HTTP, which survives client normalization.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app, frontend_path


def _serve_frontend():
    """Fetch the catch-all endpoint from the route table (it is a closure, not importable)."""
    return next(
        r.endpoint for r in app.routes if getattr(r, "path", "") == "/{full_path:path}"
    )


# ---------------------------------------------------------------------------
# Layer 1 — direct endpoint unit tests
# ---------------------------------------------------------------------------

class TestServeFrontendTraversalGuard:
    """Traversal and absolute paths must never escape frontend/."""

    @pytest.mark.asyncio
    async def test_dotdot_traversal_falls_back_to_index(self):
        response = await _serve_frontend()("../pytest.ini")
        assert Path(response.path).name == "index.html"

    @pytest.mark.asyncio
    async def test_deep_dotdot_traversal_falls_back_to_index(self):
        response = await _serve_frontend()("../src/main.py")
        assert Path(response.path).name == "index.html"

    @pytest.mark.asyncio
    async def test_absolute_path_falls_back_to_index(self):
        response = await _serve_frontend()("/etc/passwd")
        assert Path(response.path).name == "index.html"

    @pytest.mark.asyncio
    async def test_nested_dotdot_inside_path(self):
        response = await _serve_frontend()("icons/../../requirements.txt")
        assert Path(response.path).name == "index.html"


class TestServeFrontendLegitAssets:
    """Legitimate assets and SPA routes must keep working exactly as before."""

    @pytest.mark.asyncio
    async def test_legit_asset_served(self):
        response = await _serve_frontend()("sw.js")
        assert Path(response.path) == frontend_path / "sw.js"
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.asyncio
    async def test_legit_nested_asset_served(self):
        response = await _serve_frontend()("icons/icon-192.png")
        assert Path(response.path) == frontend_path / "icons" / "icon-192.png"
        assert "cache-control" not in response.headers

    @pytest.mark.asyncio
    async def test_route_map_entry_served_with_no_cache(self):
        response = await _serve_frontend()("login.html")
        assert Path(response.path).name == "login.html"
        assert response.headers["cache-control"] == "no-store"

    @pytest.mark.asyncio
    async def test_unknown_spa_route_falls_back_to_index(self):
        response = await _serve_frontend()("some/spa/route")
        assert Path(response.path).name == "index.html"
        assert response.headers["cache-control"] == "no-store"


# ---------------------------------------------------------------------------
# Layer 2 — HTTP integration via TestClient
# ---------------------------------------------------------------------------

class TestServeFrontendHttp:
    """Percent-encoded traversal survives httpx normalization — the real attack vector."""

    def test_percent_encoded_traversal_via_http(self, client: TestClient):
        response = client.get("/%2e%2e/pytest.ini")
        assert response.status_code == 200
        assert "[pytest]" not in response.text

    def test_index_served_at_root(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "<html" in response.text.lower()
