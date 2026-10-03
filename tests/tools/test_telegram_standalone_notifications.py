"""Standalone Telegram sends honour display.platforms.telegram.notifications (#131924).

``hermes send`` / cron / ``send_message`` tool use ``_send_telegram`` directly (no live
adapter), which historically never set ``disable_notification`` — so in the default
"important" mode every standalone send buzzed while the identical gateway send stayed
silent. The sender now resolves the mode with the same contract as the adapter
(env override → config → "important") and honours a per-message ``notify`` override.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _install_telegram_mock(monkeypatch: pytest.MonkeyPatch, bot_factory: MagicMock) -> None:
    parse_mode = SimpleNamespace(MARKDOWN_V2="MarkdownV2", HTML="HTML")
    constants_mod = SimpleNamespace(ParseMode=parse_mode)
    _MessageEntity = lambda **_kw: SimpleNamespace(**_kw)
    telegram_mod = SimpleNamespace(Bot=bot_factory, MessageEntity=_MessageEntity,
                                   constants=constants_mod)
    monkeypatch.setitem(sys.modules, "telegram", telegram_mod)
    monkeypatch.setitem(sys.modules, "telegram.constants", constants_mod)


def _make_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=SimpleNamespace(message_id=1))
    bot.send_photo = AsyncMock(return_value=SimpleNamespace(message_id=2))
    return bot



def _no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TELEGRAM_PROXY", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY",
                "http_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)
    # Stub gateway.run *before* anything imports it: its chain (hermes_bootstrap) resolves
    # the project root and, when the checkout sits inside the real home (default install),
    # trips the home I/O guard on the manifest probe. A stub keeps this file import-order
    # independent (the caption tests carry the same latent coupling).
    monkeypatch.setitem(sys.modules, "gateway.run",
                        SimpleNamespace(_gateway_runner_ref=lambda: None))
    monkeypatch.setattr("gateway.platforms.base._detect_macos_system_proxy", lambda: None)


def _send(monkeypatch: pytest.MonkeyPatch, bot: MagicMock, **kwargs):
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    kwargs.pop("bot", None)
    return asyncio.run(_send_telegram("tok", "123", "hello", **kwargs))


def _send_telegram(**kw):
    from tools.send_message_senders import _send_telegram as fn
    return fn("tok", "123", "hello", **kw)


# --- mode resolution ---------------------------------------------------------

def test_default_mode_is_important_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.send_message_senders import _standalone_notifications_mode
    monkeypatch.delenv("HERMES_TELEGRAM_NOTIFICATIONS", raising=False)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    assert _standalone_notifications_mode() == "important"


def test_mode_from_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.send_message_senders import _standalone_notifications_mode
    monkeypatch.delenv("HERMES_TELEGRAM_NOTIFICATIONS", raising=False)
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"display": {"platforms": {"telegram": {"notifications": "all"}}}},
    )
    assert _standalone_notifications_mode() == "all"


def test_mode_env_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.send_message_senders import _standalone_notifications_mode
    monkeypatch.setenv("HERMES_TELEGRAM_NOTIFICATIONS", "important")
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"display": {"platforms": {"telegram": {"notifications": "all"}}}},
    )
    assert _standalone_notifications_mode() == "important"


def test_mode_unknown_value_defaults_to_important(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.send_message_senders import _standalone_notifications_mode
    monkeypatch.setenv("HERMES_TELEGRAM_NOTIFICATIONS", "bogus")
    assert _standalone_notifications_mode() == "important"


# --- text sends ---------------------------------------------------------------

def test_important_mode_silents_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = _make_bot()
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    monkeypatch.delenv("HERMES_TELEGRAM_NOTIFICATIONS", raising=False)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    res = asyncio.run(
        __import__("tools.send_message_senders", fromlist=[
            "_send_telegram"])._send_telegram("tok", "123", "hello"))
    assert res["success"] is True
    assert bot.send_message.await_args.kwargs.get("disable_notification") is True


def test_notify_true_buzzes_even_in_important(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = _make_bot()
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    monkeypatch.delenv("HERMES_TELEGRAM_NOTIFICATIONS", raising=False)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    res = asyncio.run(
        __import__("tools.send_message_senders", fromlist=["_send_telegram"])
        ._send_telegram("tok", "123", "hello", notify=True))
    assert res["success"] is True
    assert "disable_notification" not in bot.send_message.await_args.kwargs


def test_notify_false_silents_even_in_all_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = _make_bot()
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    monkeypatch.setenv("HERMES_TELEGRAM_NOTIFICATIONS", "all")
    res = asyncio.run(
        __import__("tools.send_message_senders", fromlist=["_send_telegram"])
        ._send_telegram("tok", "123", "hello", notify=False))
    assert res["success"] is True
    assert bot.send_message.await_args.kwargs.get("disable_notification") is True


def test_all_mode_buzzes_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = _make_bot()
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    monkeypatch.setenv("HERMES_TELEGRAM_NOTIFICATIONS", "all")
    res = asyncio.run(
        __import__("tools.send_message_senders", fromlist=["_send_telegram"])
        ._send_telegram("tok", "123", "hello"))
    assert res["success"] is True
    assert "disable_notification" not in bot.send_message.await_args.kwargs


# --- media sends --------------------------------------------------------------

def test_media_send_silenced_in_important_mode(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: pytest.TempPath) -> None:
    import os
    bot = _make_bot()
    _no_proxy(monkeypatch)
    _install_telegram_mock(monkeypatch, MagicMock(return_value=bot))
    monkeypatch.delenv("HERMES_TELEGRAM_NOTIFICATIONS", raising=False)
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: {})
    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    res = asyncio.run(
        __import__("tools.send_message_senders", fromlist=["_send_telegram"])
        ._send_telegram("tok", "123", "cap", media_files=[(str(img), False)]))
    assert res["success"] is True
    assert bot.send_photo.await_args.kwargs.get("disable_notification") is True


# --- CLI flags -----------------------------------------------------------------

def test_cli_silent_and_notify_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    import hermes_cli.send_cmd as sc
    import tools.send_message_tool as smt
    captured = {}

    def fake_tool(args, **kw):
        captured.update(args)
        return '{"success": true}'

    monkeypatch.setattr(smt, "send_message_tool", fake_tool)
    monkeypatch.setattr(sc.sys, "exit", lambda *_: None)
    base = dict(to="telegram", message="hi", mentions=None, subject=None,
                list_targets=False, quiet=False, json=False, file=None,
                silent=True, notify=False)
    sc.cmd_send(SimpleNamespace(**base))
    assert captured["notify"] is False

    base["silent"] = False
    base["notify"] = True
    sc.cmd_send(SimpleNamespace(**base))
    assert captured["notify"] is True


def test_cli_silent_and_notify_mutually_exclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    import hermes_cli.send_cmd as sc
    import tools.send_message_tool as smt
    monkeypatch.setattr(smt, "send_message_tool", lambda *a, **k: "{}")
    with pytest.raises(SystemExit):
        sc.cmd_send(SimpleNamespace(to="telegram", message="hi", mentions=None,
                                    subject=None, list_targets=False, quiet=False,
                                    json=False, file=None, silent=True, notify=True))
