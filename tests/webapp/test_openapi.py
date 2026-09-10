"""Схема OpenAPI."""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import httpx

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "openapi.json"


@pytest.fixture(scope="session")
def schema(app: Any) -> dict[str, Any]:  # noqa: ANN401
    """Актуальная схема приложения."""
    return app.openapi()


class TestSchema:
    """Приложение отдаёт валидную схему."""

    async def test_openapi_endpoint(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"] == "VKT Bot API"

    def test_all_routers_are_present(self, schema: dict[str, Any]) -> None:
        prefixes = {
            "/api/auth",
            "/api/chats",
            "/api/roles",
            "/api/chat-users",
            "/api/bot-settings",
            "/api/events",
            "/api/overview",
            "/api/webhooks",
            "/webhooks",
            "/gl/webhooks",
        }
        paths = set(schema["paths"])
        for prefix in prefixes:
            assert any(path.startswith(prefix) for path in paths), prefix

    def test_public_webhook_has_no_security(self, schema: dict[str, Any]) -> None:
        operation = schema["paths"]["/webhooks/{webhook_id}"]["post"]
        assert "security" not in operation


class TestSchemaIsUpToDate:
    """``openapi.json`` в репозитории не должен расходиться с приложением."""

    def test_file_exists(self) -> None:
        assert SCHEMA_PATH.exists(), "нет openapi.json — запустите `make export_schema`"

    def test_committed_schema_matches_app(self, schema: dict[str, Any]) -> None:
        committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        if committed != schema:
            pytest.fail(
                "openapi.json устарел: перегенерируйте его командой "
                "`make export_schema` (или `make generate_client`)"
            )
