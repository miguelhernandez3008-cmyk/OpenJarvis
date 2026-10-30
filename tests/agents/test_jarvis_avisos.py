"""Tests for the Jarvis notification agents (jarvis_salud / jarvis_correos)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.agents import jarvis_avisos
from openjarvis.agents.jarvis_avisos import (
    JarvisCorreosAgent,
    JarvisSaludAgent,
    _normalize_spec,
)
from openjarvis.connectors._stubs import Document
from openjarvis.core.config import JarvisAgentsConfig
from openjarvis.core.registry import AgentRegistry, ConnectorRegistry
from openjarvis.core.types import ToolResult


class _FakeMail:
    docs: list = []

    def is_connected(self) -> bool:
        return True

    def sync(self, since=None):
        return iter(self.docs)


@pytest.fixture
def fake_mail():
    ConnectorRegistry.register_value("fakemail", _FakeMail)
    _FakeMail.docs = [
        Document(
            doc_id="gmail:1",
            source="fakemail",
            doc_type="email",
            content="Necesito el informe antes del viernes.",
            title="Informe urgente",
            author="jefa@empresa.com",
            timestamp=datetime(2026, 10, 30, 8, 0),
        )
    ]
    yield _FakeMail


def _engine(reply: str) -> MagicMock:
    engine = MagicMock()
    engine.generate.return_value = {
        "content": reply,
        "finish_reason": "stop",
        "usage": {},
    }
    return engine


def _correos(engine, tmp_path, channel="whatsapp_baileys:+57 300 123 4567"):
    cfg = JarvisAgentsConfig(
        email_channel=channel, email_sources=["fakemail"], voice_notes=False
    )
    return JarvisCorreosAgent(
        engine,
        "test-model",
        tools=[],
        jarvis_config=cfg,
        state_path=str(tmp_path / "state.json"),
    )


def test_agents_registered():
    AgentRegistry.register_value("jarvis_salud", JarvisSaludAgent)
    AgentRegistry.register_value("jarvis_correos", JarvisCorreosAgent)
    assert AgentRegistry.contains("jarvis_salud")
    assert AgentRegistry.contains("jarvis_correos")


def test_normalize_whatsapp_number():
    spec = _normalize_spec("whatsapp_baileys:+57 300-123 4567")
    assert spec == "whatsapp_baileys:573001234567@s.whatsapp.net"
    assert _normalize_spec("telegram:123") == "telegram:123"


def test_correos_without_destination_skips_model(fake_mail, tmp_path):
    engine = _engine("irrelevante")
    agent = _correos(engine, tmp_path, channel="whatsapp_baileys:")
    result = agent.run("tick")
    engine.generate.assert_not_called()
    assert result.metadata["sent"] is False


def test_correos_sends_once_per_email(fake_mail, tmp_path):
    engine = _engine("📬 *Correos importantes*\n• *Jefa* — pide el informe.")
    agent = _correos(engine, tmp_path)
    with patch.object(jarvis_avisos, "send_notification", return_value=True) as send:
        first = agent.run("tick")
        second = agent.run("tick")

    assert first.metadata["sent"] is True
    send.assert_called_once()
    spec, text = send.call_args.args
    assert spec.startswith("whatsapp_baileys:")
    assert "informe" in text
    # The email was remembered, so the second tick does not call the model.
    assert engine.generate.call_count == 1
    assert second.metadata["new"] == 0


def test_correos_nothing_important_is_not_sent(fake_mail, tmp_path):
    agent = _correos(_engine("NADA"), tmp_path)
    with patch.object(jarvis_avisos, "send_notification") as send:
        result = agent.run("tick")
    send.assert_not_called()
    assert result.content == "Ningún correo importante."
    assert agent._load_seen() == ["gmail:1"]


def test_correos_failed_send_is_retried(fake_mail, tmp_path):
    agent = _correos(_engine("📬 aviso"), tmp_path)
    with patch.object(jarvis_avisos, "send_notification", return_value=False):
        agent.run("tick")
    assert agent._load_seen() == []


def test_salud_sends_spanish_message(tmp_path):
    engine = _engine("Buenos días, Miguel. Hoy hace calor: hidrátate.")
    cfg = JarvisAgentsConfig(
        health_channel="telegram:123", health_sources=[], voice_notes=False
    )
    agent = JarvisSaludAgent(engine, "test-model", tools=[], jarvis_config=cfg)
    collected = ToolResult(tool_name="digest_collect", content="", success=True)
    with (
        patch(
            "openjarvis.tools.digest_collect.DigestCollectTool.execute",
            return_value=collected,
        ),
        patch.object(jarvis_avisos, "send_notification", return_value=True) as send,
    ):
        result = agent.run("tick")

    send.assert_called_once_with("telegram:123", result.content, voice=b"")
    system_prompt = engine.generate.call_args.args[0][0].content
    assert "SIEMPRE en español" in system_prompt


def test_send_notification_waits_for_whatsapp(monkeypatch):
    from openjarvis.channels._stubs import ChannelStatus

    channel = MagicMock()
    channel.status.side_effect = [ChannelStatus.CONNECTING, ChannelStatus.CONNECTED]
    channel.send.return_value = True
    monkeypatch.setattr(jarvis_avisos.time, "sleep", lambda _s: None)
    with patch(
        "openjarvis.agents.proactive_agent._build_notification_channel",
        return_value=channel,
    ) as build:
        ok = jarvis_avisos.send_notification("whatsapp_baileys:+573001234567", "hola")

    assert ok is True
    build.assert_called_once_with("whatsapp_baileys:573001234567@s.whatsapp.net")
    channel.send.assert_called_once_with("573001234567@s.whatsapp.net", "hola")
    channel.disconnect.assert_called_once()
    assert jarvis_avisos.send_notification("telegram:", "hola") is False


def test_salud_attaches_voice_note(tmp_path):
    engine = _engine("Buenos días, *Miguel* 💧. Toma agua.")
    cfg = JarvisAgentsConfig(health_channel="telegram:123", health_sources=[])
    agent = JarvisSaludAgent(engine, "test-model", tools=[], jarvis_config=cfg)
    collected = ToolResult(tool_name="digest_collect", content="", success=True)
    with (
        patch(
            "openjarvis.tools.digest_collect.DigestCollectTool.execute",
            return_value=collected,
        ),
        patch.object(jarvis_avisos, "voice_note", return_value=b"OggS") as tts,
        patch.object(jarvis_avisos, "send_notification", return_value=True) as send,
    ):
        agent.run("tick")

    tts.assert_called_once_with(
        "Buenos días, *Miguel* 💧. Toma agua.", voice_id="em_alex"
    )
    assert send.call_args.kwargs["voice"] == b"OggS"


def test_text_for_speech_strips_markup():
    text = "📬 *Correos importantes*\n• *Clínica* — cita mañana."
    assert jarvis_avisos._text_for_speech(text) == (
        "Correos importantes\nClínica, cita mañana."
    )


def test_voice_note_without_kokoro_returns_empty(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openjarvis.speech.kokoro_tts":
            raise ImportError("kokoro not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert jarvis_avisos.voice_note("hola") == b""


def test_send_notification_sends_voice_after_text(monkeypatch):
    channel = MagicMock()
    channel.send.return_value = True
    channel.send_voice.return_value = False  # a failed voice note is not fatal
    monkeypatch.setattr(jarvis_avisos.time, "sleep", lambda _s: None)
    with patch(
        "openjarvis.agents.proactive_agent._build_notification_channel",
        return_value=channel,
    ):
        ok = jarvis_avisos.send_notification("telegram:123", "hola", voice=b"OggS")

    assert ok is True
    channel.send_voice.assert_called_once_with("123", b"OggS")


def test_telegram_send_voice(monkeypatch):
    from openjarvis.channels.telegram import TelegramChannel

    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return MagicMock(status_code=200)

    monkeypatch.setattr("httpx.post", fake_post)
    ok = TelegramChannel("TOKEN").send_voice("123", b"OggS", caption="hola")
    assert ok is True
    url, kwargs = calls[0]
    assert url.endswith("/botTOKEN/sendVoice")
    assert kwargs["data"] == {"chat_id": "123", "caption": "hola"}
    assert kwargs["files"]["voice"][1] == b"OggS"


def test_whatsapp_send_voice_writes_bridge_command():
    import base64

    from openjarvis.channels._stubs import ChannelStatus
    from openjarvis.channels.whatsapp_baileys import WhatsAppBaileysChannel

    channel = WhatsAppBaileysChannel()
    channel._process = MagicMock()
    channel._status = ChannelStatus.CONNECTED
    with patch.object(channel, "_write_command") as write:
        assert channel.send_voice("57300@s.whatsapp.net", b"OggS") is True
    write.assert_called_once_with(
        {
            "type": "send_voice",
            "jid": "57300@s.whatsapp.net",
            "audio": base64.b64encode(b"OggS").decode("ascii"),
        }
    )
