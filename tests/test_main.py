"""Точки входа ``vkt_bot.main``."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from vkt_bot import main as main_module

if TYPE_CHECKING:
    import pathlib


@pytest.fixture(autouse=True)
def no_app_build(monkeypatch: pytest.MonkeyPatch, app: Any) -> None:  # noqa: ANN401
    """Не пересобирать приложение в каждом тесте."""
    monkeypatch.setattr(main_module, "create_app", lambda: app)


class TestMainCoroutine:
    """``main``."""

    async def test_runs_dispatcher(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        async def run() -> None:
            calls.append("run")

        monkeypatch.setattr(main_module.dispatcher, "run", run)
        await main_module.main()

        assert calls == ["run"]

    async def test_cancellation_is_handled(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def run() -> None:
            raise asyncio.CancelledError

        monkeypatch.setattr(main_module.dispatcher, "run", run)

        with caplog.at_level("INFO", logger="vkt_bot"):
            await main_module.main()

        assert "Завершение работы" in caplog.text

    async def test_other_errors_propagate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def run() -> None:
            msg = "боом"
            raise RuntimeError(msg)

        monkeypatch.setattr(main_module.dispatcher, "run", run)

        with pytest.raises(RuntimeError, match="боом"):
            await main_module.main()


class TestStartBot:
    """``start_bot``."""

    def test_checks_settings_builds_app_and_runs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        monkeypatch.setattr(
            main_module, "check_settings", lambda: calls.append("check")
        )
        monkeypatch.setattr(
            main_module, "create_app", lambda: calls.append("app") or None
        )
        monkeypatch.setattr(
            main_module.asyncio, "run", lambda coro: calls.append("run") or coro.close()
        )

        main_module.start_bot()

        assert calls == ["check", "app", "run"]


class TestStartServer:
    """``start_server``."""

    def test_runs_uvicorn_on_expected_address(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def run(target: str, **kwargs: Any) -> None:  # noqa: ANN401
            captured["target"] = target
            captured.update(kwargs)

        monkeypatch.setattr(main_module, "check_settings", lambda: None)
        monkeypatch.setattr(main_module.uvicorn, "run", run)

        main_module.start_server()

        assert captured["target"] == "vkt_bot.webapp.app:create_app"
        assert captured["host"] == "0.0.0.0"  # noqa: S104
        assert captured["port"] == 8765


class TestExportSchema:
    """``export_schema``."""

    def test_writes_openapi_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(main_module, "check_settings", lambda: None)
        monkeypatch.chdir(tmp_path)

        main_module.export_schema()

        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert schema["info"]["title"] == "VKT Bot API"
        assert "openapi.json exported" in capsys.readouterr().out


class TestShell:
    """``shell``."""

    def test_starts_ipython_with_session(
        self, monkeypatch: pytest.MonkeyPatch, session_factory: Any
    ) -> None:
        captured: dict[str, Any] = {}

        def start_ipython(argv: list[str], user_ns: dict[str, Any]) -> None:  # noqa: ARG001
            captured["user_ns"] = user_ns

        monkeypatch.setattr(main_module, "check_settings", lambda: None)
        monkeypatch.setattr(main_module.IPython, "start_ipython", start_ipython)
        monkeypatch.setattr(main_module.asyncio, "run", lambda coro: coro.close())

        main_module.shell()

        assert "session" in captured["user_ns"]

    def test_does_not_call_setup_twice(self) -> None:
        """``setup`` зовётся один раз — внутри ``create_app``.

        Отдельный вызов повторно прогонял бы ``init_logging``,
        ``setup_sentry`` и ``install()`` каждого плагина.
        """
        names = main_module.shell.__code__.co_names

        assert "create_app" in names
        assert "setup" not in names


class TestCheckSettings:
    """``check_settings`` при валидных настройках."""

    def test_does_not_exit(self) -> None:
        main_module.check_settings()
